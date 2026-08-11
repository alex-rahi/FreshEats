"""Business rules for food / cooking image moderation."""

from dataclasses import dataclass, field
from enum import Enum


class Outcome(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    FLAG_FOR_REVIEW = "flag_for_review"
    MANUAL_REVIEW = "manual_review"
    PUBLISH = "publish"


@dataclass
class RuleResult:
    rule_name: str
    outcome: Outcome
    confidence: float
    details: dict = field(default_factory=dict)


@dataclass
class EvaluationContext:
    detections: list[dict]
    moderation_scores: list[dict]
    user_trust_level: int = 50


# COCO food + cooking context labels (YOLOv8n)
FOOD_OBJECTS = {
    "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "bowl", "bottle", "wine glass",
    "cup", "fork", "knife", "spoon", "dining table", "food", "plate",
    "meal", "ingredient",
}

COOKING_CONTEXT = {
    "person", "oven", "microwave", "refrigerator", "sink", "bowl",
    "dining table", "cup", "bottle", "knife", "fork", "spoon",
}

# Clearly unrelated — reject when dominant and no food present
UNRELATED_OBJECTS = {
    "car", "truck", "bus", "motorcycle", "airplane", "train", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter",
    "bench", "bird", "cat", "dog", "horse", "sheep", "cow", "elephant",
    "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "laptop", "mouse", "remote", "keyboard", "cell phone",
    "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush", "tv", "toilet",
}

MODERATION_CATEGORIES = {
    "explicit_content", "violence_gore", "nudity",
    "hate_harassment", "unsafe_activity",
}

REJECT_THRESHOLD = 0.9
FLAG_THRESHOLD = 0.5


def rule_content_moderation(ctx: EvaluationContext) -> RuleResult:
    flagged_category = None
    flagged_score = 0.0
    for score in ctx.moderation_scores:
        if score["category"] not in MODERATION_CATEGORIES:
            continue
        value = score["score"]
        if value >= REJECT_THRESHOLD:
            return RuleResult(
                "content_moderation", Outcome.REJECT, value,
                {"category": score["category"], "score": value},
            )
        if value >= FLAG_THRESHOLD and value > flagged_score:
            flagged_category = score["category"]
            flagged_score = value

    if flagged_category:
        return RuleResult(
            "content_moderation", Outcome.FLAG_FOR_REVIEW, flagged_score,
            {"category": flagged_category, "score": flagged_score},
        )
    return RuleResult("content_moderation", Outcome.APPROVE, 1.0)


def rule_food_detection(ctx: EvaluationContext) -> RuleResult:
    """Require food/cooking signals; reject clearly unrelated; queue uncertain."""
    labels = {d["label"].lower() for d in ctx.detections}
    confidences = {d["label"].lower(): d["confidence"] for d in ctx.detections}

    food_hits = labels & FOOD_OBJECTS
    cooking_hits = labels & COOKING_CONTEXT
    unrelated = labels & UNRELATED_OBJECTS

    if food_hits:
        return RuleResult(
            "food_detection", Outcome.APPROVE, 0.92,
            {"food": list(food_hits), "context": list(cooking_hits)},
        )

    if cooking_hits and not unrelated:
        # Person + utensils / dining table — uncertain food scene
        max_conf = max((confidences[l] for l in cooking_hits), default=0.5)
        if max_conf >= 0.7:
            return RuleResult(
                "food_detection", Outcome.FLAG_FOR_REVIEW, max_conf,
                {"reason": "Cooking context without clear food", "detected": list(labels)},
            )

    if unrelated and not food_hits:
        max_unrelated = max((confidences.get(l, 0) for l in unrelated), default=0)
        if max_unrelated >= 0.65:
            return RuleResult(
                "food_detection", Outcome.REJECT, max_unrelated,
                {"reason": "Unrelated non-food image", "detected": list(unrelated)},
            )

    if not labels:
        return RuleResult(
            "food_detection", Outcome.FLAG_FOR_REVIEW, 0.4,
            {"reason": "No objects detected — manual review"},
        )

    return RuleResult(
        "food_detection", Outcome.FLAG_FOR_REVIEW, 0.55,
        {"reason": "Uncertain food relevance", "detected": list(labels)},
    )


def rule_user_trust(ctx: EvaluationContext) -> RuleResult:
    if ctx.user_trust_level < 15:
        return RuleResult(
            "user_trust", Outcome.FLAG_FOR_REVIEW, 0.6,
            {"reason": "Low trust account"},
        )
    return RuleResult("user_trust", Outcome.APPROVE, 0.9)


OUTCOME_PRIORITY = {
    Outcome.REJECT: 5,
    Outcome.MANUAL_REVIEW: 4,
    Outcome.FLAG_FOR_REVIEW: 3,
    Outcome.APPROVE: 2,
    Outcome.PUBLISH: 1,
}


def evaluate_all_rules(ctx: EvaluationContext) -> tuple[Outcome, list[RuleResult]]:
    rules = [
        rule_content_moderation(ctx),
        rule_food_detection(ctx),
        rule_user_trust(ctx),
    ]
    best = max(rules, key=lambda r: OUTCOME_PRIORITY[r.outcome])
    final = Outcome.PUBLISH if best.outcome == Outcome.APPROVE else best.outcome
    return final, rules
