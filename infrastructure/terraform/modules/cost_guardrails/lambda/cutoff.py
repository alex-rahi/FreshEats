"""Progressive AWS cost guardrails for FreshEats.

Budget notifications (of $budget_limit, default $100):
  50% — alert only (email via SNS)
  70% — scale EKS node groups down (min 1, desired 1)
  80% — full shutoff: EKS → 0, delete Redis, stop/tag RDS

Phase 1: alert @ 50%, shutoff @ 80%
Phase 2: adds 70% progressive scale-down before hard cutoff
"""

from __future__ import annotations

import json
import logging
import os
import re

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

EKS_CLUSTER = os.environ["EKS_CLUSTER_NAME"]
RDS_INSTANCE_ID = os.environ.get("RDS_INSTANCE_ID", "")
REDIS_CLUSTER_ID = os.environ.get("REDIS_CLUSTER_ID", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Phase thresholds (% of monthly budget)
ALERT_THRESHOLD = float(os.environ.get("ALERT_THRESHOLD", "50"))
SCALE_THRESHOLD = float(os.environ.get("SCALE_THRESHOLD", "70"))
SHUTOFF_THRESHOLD = float(os.environ.get("SHUTOFF_THRESHOLD", "80"))


def _extract_threshold(event: dict) -> float | None:
    """Best-effort parse of AWS Budgets SNS threshold percentage."""
    for record in event.get("Records", []):
        raw = record.get("Sns", {}).get("Message", "")
        subject = record.get("Sns", {}).get("Subject", "")

        try:
            msg = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            msg = None

        if isinstance(msg, dict):
            threshold = (
                msg.get("threshold")
                or msg.get("Threshold")
                or msg.get("budgetNotification", {}).get("threshold")
                or msg.get("budgetNotification", {}).get("Threshold")
            )
            try:
                if threshold is not None:
                    return float(threshold)
            except (TypeError, ValueError):
                pass

        blob = f"{subject} {raw}"
        # Match "80%", "80.0", "threshold of 80"
        m = re.search(r"(?:threshold[^0-9]*)?(\d+(?:\.\d+)?)\s*%", blob, re.I)
        if m:
            return float(m.group(1))
        for candidate in (80, 70, 50, 100):
            if re.search(rf"\b{candidate}(?:\.0)?\b", blob) and (
                "ACTUAL" in blob.upper() or "FORECASTED" in blob.upper() or "exceed" in blob.lower()
            ):
                return float(candidate)
    return None


def _scale_eks(eks, cluster: str, desired: int, minimum: int, maximum: int) -> list[str]:
    actions = []
    paginator = eks.get_paginator("list_nodegroups")
    for page in paginator.paginate(clusterName=cluster):
        for ng in page.get("nodegroups", []):
            logger.info(
                "Scaling node group %s → desired=%s min=%s max=%s",
                ng,
                desired,
                minimum,
                maximum,
            )
            eks.update_nodegroup_config(
                clusterName=cluster,
                nodegroupName=ng,
                scalingConfig={
                    "minSize": minimum,
                    "maxSize": max(maximum, desired, 1) if desired > 0 else 1,
                    "desiredSize": desired,
                },
            )
            actions.append(f"eks:{cluster}/{ng}->desired={desired}")
    return actions


def _stop_rds(rds, instance_id: str) -> list[str]:
    if not instance_id:
        return []
    try:
        desc = rds.describe_db_instances(DBInstanceIdentifier=instance_id)
        db = desc["DBInstances"][0]
        if db.get("MultiAZ"):
            logger.warning(
                "RDS %s is Multi-AZ — cannot stop automatically; tagging for manual review",
                instance_id,
            )
            rds.add_tags_to_resource(
                ResourceName=db["DBInstanceArn"],
                Tags=[
                    {"Key": "fresheats:cost-cutoff", "Value": "true"},
                    {"Key": "fresheats:cost-cutoff-action", "Value": "needs-manual-stop"},
                ],
            )
            return [f"rds:{instance_id}:tagged-multiaz"]
        if db["DBInstanceStatus"] == "available":
            rds.stop_db_instance(DBInstanceIdentifier=instance_id)
            return [f"rds:{instance_id}:stopped"]
        return [f"rds:{instance_id}:status={db['DBInstanceStatus']}"]
    except Exception as exc:
        logger.exception("RDS stop failed: %s", exc)
        return [f"rds:{instance_id}:error"]


def _delete_redis(elasticache, cluster_id: str) -> list[str]:
    if not cluster_id:
        return []
    try:
        elasticache.delete_cache_cluster(CacheClusterId=cluster_id)
        return [f"redis:{cluster_id}:deleting"]
    except Exception as exc:
        logger.exception("Redis delete failed: %s", exc)
        return [f"redis:{cluster_id}:error"]


def _phase_for_threshold(threshold: float) -> str:
    if threshold >= SHUTOFF_THRESHOLD:
        return "shutoff"
    if threshold >= SCALE_THRESHOLD:
        return "scale"
    if threshold >= ALERT_THRESHOLD:
        return "alert"
    return "none"


def handler(event, context):
    logger.info("Budget event received: %s", json.dumps(event))
    threshold = _extract_threshold(event)
    if threshold is None:
        logger.warning("Could not parse budget threshold — treating as alert-only")
        return {"ok": True, "phase": "alert", "threshold": None, "actions": []}

    phase = _phase_for_threshold(threshold)
    logger.info("Threshold=%.1f%% → phase=%s", threshold, phase)

    if phase == "alert" or phase == "none":
        return {"ok": True, "phase": phase, "threshold": threshold, "actions": [], "skipped": "alert_only"}

    eks = boto3.client("eks", region_name=AWS_REGION)
    actions: list[str] = []

    if phase == "scale":
        # Phase 2: shrink cluster but keep a minimal footprint
        actions.extend(_scale_eks(eks, EKS_CLUSTER, desired=1, minimum=1, maximum=2))
        return {"ok": True, "phase": "scale", "threshold": threshold, "actions": actions}

    # Phase 1/2 shutoff at 80%
    rds = boto3.client("rds", region_name=AWS_REGION)
    elasticache = boto3.client("elasticache", region_name=AWS_REGION)
    actions.extend(_scale_eks(eks, EKS_CLUSTER, desired=0, minimum=0, maximum=1))
    actions.extend(_stop_rds(rds, RDS_INSTANCE_ID))
    actions.extend(_delete_redis(elasticache, REDIS_CLUSTER_ID))

    result = {"ok": True, "phase": "shutoff", "threshold": threshold, "actions": actions}
    logger.info("Shutoff complete: %s", result)
    return result
