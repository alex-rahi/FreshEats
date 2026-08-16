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


# COCO food labels that count as edible / plated food under food-only policy
FOOD_CORE = {
    "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "food", "dish", "meal", "ingredient",
}

COOKWARE = {
    "bowl", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "dining table",
}

FOOD_OBJECTS = FOOD_CORE | COOKWARE

COOKING_CONTEXT = {
    "oven", "microwave", "refrigerator", "sink", "bowl",
    "dining table", "cup", "bottle", "knife", "fork", "spoon",
}

# Clearly unrelated — reject when no food present
UNRELATED_OBJECTS = {
    "car", "truck", "bus", "motorcycle", "airplane", "train", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter",
    "bench", "bird", "cat", "dog", "horse", "sheep", "cow", "elephant",
    "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "laptop", "mouse", "remote", "keyboard", "cell phone",
    "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush", "tv", "toilet", "person",
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
    """Food-only policy: require edible/plated food labels; reject everything else."""
    labels = {d["label"].lower() for d in ctx.detections}
    confidences = {d["label"].lower(): d["confidence"] for d in ctx.detections}

    food_core = labels & FOOD_CORE
    cookware = labels & COOKWARE
    cooking_hits = labels & COOKING_CONTEXT
    unrelated = labels & UNRELATED_OBJECTS

    if food_core and "person" not in labels:
        return RuleResult(
            "food_detection", Outcome.APPROVE, 0.92,
            {"food": list(food_core), "context": list(cooking_hits | cookware), "policy": "food_only"},
        )

    if "person" in labels and not food_core:
        return RuleResult(
            "food_detection", Outcome.REJECT, confidences.get("person", 0.8),
            {"reason": "Not a food image — person/portrait without food", "detected": list(labels)},
        )

    if unrelated and not food_core:
        max_unrelated = max((confidences.get(l, 0) for l in unrelated), default=0)
        return RuleResult(
            "food_detection", Outcome.REJECT, max(max_unrelated, 0.7),
            {
                "reason": f"Not a food image — detected {', '.join(sorted(unrelated))} instead of food",
                "detected": list(unrelated),
            },
        )

    if (cookware or cooking_hits) and not food_core:
        return RuleResult(
            "food_detection", Outcome.REJECT, 0.75,
            {"reason": "Not a food image — kitchen items without food", "detected": list(labels)},
        )

    if not labels:
        return RuleResult(
            "food_detection", Outcome.REJECT, 0.85,
            {"reason": "Not a food image — no food detected"},
        )

    return RuleResult(
        "food_detection", Outcome.REJECT, 0.8,
        {"reason": "Not a food image — photo is not clearly food", "detected": list(labels)},
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
