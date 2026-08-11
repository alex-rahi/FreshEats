"""Run YOLO + moderation + food rules on a recipe image."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass

import cv2

from app.config import settings
from app.pipeline.moderation import aggregate_moderation_scores, moderate_frame
from app.pipeline.yolo_detector import detect_objects
from app.rules.engine import EvaluationContext, evaluate_all_rules
from app.rules.outcomes import recipe_status_for_outcome


@dataclass
class AnalysisResult:
    detections: list[dict]
    moderation_scores: list[dict]
    outcome: str
    moderation_decision: str
    moderation_reason: str | None
    rules: list[dict]


def analyze_path(path: str) -> AnalysisResult:
    frame = cv2.imread(path)
    if frame is None:
        raise ValueError(f"Could not read image: {path}")

    detections = detect_objects(frame, settings.yolo_model_path)
    mod_scores = aggregate_moderation_scores([moderate_frame(frame, settings.moderation_threshold)])
    ctx = EvaluationContext(detections=detections, moderation_scores=mod_scores)
    final_outcome, rule_results = evaluate_all_rules(ctx)

    reason = None
    for rr in rule_results:
        if rr.outcome.value in ("reject", "flag_for_review", "manual_review"):
            reason = rr.details.get("reason") or rr.rule_name
            break

    return AnalysisResult(
        detections=detections,
        moderation_scores=mod_scores,
        outcome=recipe_status_for_outcome(final_outcome),
        moderation_decision=final_outcome.value,
        moderation_reason=reason,
        rules=[
            {
                "rule_name": rr.rule_name,
                "outcome": rr.outcome.value,
                "confidence": rr.confidence,
                "details": rr.details,
            }
            for rr in rule_results
        ],
    )


def analyze_bytes(data: bytes, suffix: str) -> AnalysisResult:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        return analyze_path(tmp_path)
    finally:
        os.unlink(tmp_path)
