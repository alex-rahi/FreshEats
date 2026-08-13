"""Progressive AWS cost guardrails for FreshEats.

Designed so steady-state stays inside the monthly budget envelope, and
spend triggers shrink *before* hard shutoff:

  50% — soft scale: EKS → desired=1 (email via SNS too)
  70% — hard lock: EKS → desired=1, max=1 (cannot grow)
  80% — shutoff: EKS → 0, delete Redis, stop/tag RDS

Set DRY_RUN=true to exercise threshold routing and planned actions
without calling mutating AWS APIs.
"""

from __future__ import annotations

import json
import logging
import os
import re

logger = logging.getLogger()
logger.setLevel(logging.INFO)

EKS_CLUSTER = os.environ["EKS_CLUSTER_NAME"]
RDS_INSTANCE_ID = os.environ.get("RDS_INSTANCE_ID", "")
REDIS_CLUSTER_ID = os.environ.get("REDIS_CLUSTER_ID", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() in {"1", "true", "yes", "on"}

# Phase thresholds (% of monthly budget)
ALERT_THRESHOLD = float(os.environ.get("ALERT_THRESHOLD", "50"))
SCALE_THRESHOLD = float(os.environ.get("SCALE_THRESHOLD", "70"))
SHUTOFF_THRESHOLD = float(os.environ.get("SHUTOFF_THRESHOLD", "80"))


def _boto3():
    import boto3

    return boto3


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
            plan = f"eks:{cluster}/{ng}->desired={desired},max={maximum}"
            if DRY_RUN:
                logger.info("[DRY_RUN] would scale node group %s", plan)
                actions.append(f"dry_run:{plan}")
                continue
            logger.info(
                "Scaling node group %s → desired=%s min=%s max=%s",
                ng,
                desired,
                minimum,
                maximum,
            )
            # EKS requires maxSize >= 1 even when desired is 0
            max_size = 1 if desired == 0 else max(maximum, desired, 1)
            min_size = 0 if desired == 0 else minimum
            eks.update_nodegroup_config(
                clusterName=cluster,
                nodegroupName=ng,
                scalingConfig={
                    "minSize": min_size,
                    "maxSize": max_size,
                    "desiredSize": desired,
                },
            )
            actions.append(plan)
    return actions


def _plan_scale_eks_no_api(cluster: str, desired: int, maximum: int) -> list[str]:
    return [f"dry_run:eks:{cluster}/*->desired={desired},max={maximum}"]


def _stop_rds(rds, instance_id: str) -> list[str]:
    if not instance_id:
        return []
    if DRY_RUN:
        plan = f"rds:{instance_id}:stop_or_tag"
        logger.info("[DRY_RUN] would stop/tag RDS %s", instance_id)
        return [f"dry_run:{plan}"]
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
    if DRY_RUN:
        plan = f"redis:{cluster_id}:deleting"
        logger.info("[DRY_RUN] would delete Redis %s", cluster_id)
        return [f"dry_run:{plan}"]
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
        return "lock"
    if threshold >= ALERT_THRESHOLD:
        return "soft_scale"
    return "none"


def _eks_actions(desired: int, minimum: int, maximum: int) -> list[str]:
    if DRY_RUN:
        try:
            eks = _boto3().client("eks", region_name=AWS_REGION)
            return _scale_eks(eks, EKS_CLUSTER, desired=desired, minimum=minimum, maximum=maximum)
        except Exception as exc:
            logger.warning("[DRY_RUN] EKS list failed (%s); using generic plan", exc)
            return _plan_scale_eks_no_api(EKS_CLUSTER, desired=desired, maximum=maximum)
    eks = _boto3().client("eks", region_name=AWS_REGION)
    return _scale_eks(eks, EKS_CLUSTER, desired=desired, minimum=minimum, maximum=maximum)


def _notify(result: dict) -> None:
    """Emit a stable log line for metric filters and optional SNS email."""
    phase = result.get("phase")
    dry = result.get("dry_run")
    logger.info(
        "COST_GUARDRAIL_EVENT phase=%s dry_run=%s threshold=%s actions=%s",
        phase,
        str(dry).lower(),
        result.get("threshold"),
        result.get("actions"),
    )
    if dry:
        logger.info("COST_GUARDRAIL_EVENT dry_run=true")
    if not SNS_TOPIC_ARN:
        return
    try:
        subject = f"FreshEats cost guardrail: {phase}" + (" [DRY_RUN]" if dry else "")
        _boto3().client("sns", region_name=AWS_REGION).publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject[:100],
            Message=json.dumps(result, indent=2),
        )
    except Exception as exc:
        logger.exception("SNS notify failed: %s", exc)


def handler(event, context):
    logger.info("Budget event received: %s", json.dumps(event))
    logger.info("DRY_RUN=%s", DRY_RUN)
    threshold = _extract_threshold(event)
    if threshold is None:
        logger.warning("Could not parse budget threshold — treating as soft_scale")
        result = {"ok": True, "phase": "soft_scale", "threshold": None, "actions": [], "dry_run": DRY_RUN}
        _notify(result)
        return result

    phase = _phase_for_threshold(threshold)
    logger.info("Threshold=%.1f%% → phase=%s", threshold, phase)

    if phase == "none":
        return {
            "ok": True,
            "phase": phase,
            "threshold": threshold,
            "actions": [],
            "skipped": "below_alert",
            "dry_run": DRY_RUN,
        }

    actions: list[str] = []

    if phase == "soft_scale":
        actions.extend(_eks_actions(desired=1, minimum=1, maximum=2))
        result = {
            "ok": True,
            "phase": "soft_scale",
            "threshold": threshold,
            "actions": actions,
            "dry_run": DRY_RUN,
        }
        _notify(result)
        return result

    if phase == "lock":
        actions.extend(_eks_actions(desired=1, minimum=1, maximum=1))
        result = {
            "ok": True,
            "phase": "lock",
            "threshold": threshold,
            "actions": actions,
            "dry_run": DRY_RUN,
        }
        _notify(result)
        return result

    # 80%: full shutoff
    actions.extend(_eks_actions(desired=0, minimum=0, maximum=1))
    if DRY_RUN:
        actions.extend(_stop_rds(None, RDS_INSTANCE_ID))
        actions.extend(_delete_redis(None, REDIS_CLUSTER_ID))
    else:
        boto3 = _boto3()
        rds = boto3.client("rds", region_name=AWS_REGION)
        elasticache = boto3.client("elasticache", region_name=AWS_REGION)
        actions.extend(_stop_rds(rds, RDS_INSTANCE_ID))
        actions.extend(_delete_redis(elasticache, REDIS_CLUSTER_ID))

    result = {
        "ok": True,
        "phase": "shutoff",
        "threshold": threshold,
        "actions": actions,
        "dry_run": DRY_RUN,
    }
    logger.info("Shutoff %s: %s", "planned" if DRY_RUN else "complete", result)
    _notify(result)
    return result
