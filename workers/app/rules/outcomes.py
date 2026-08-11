from app.rules.engine import Outcome

RECIPE_STATUS_BY_OUTCOME: dict[Outcome, str] = {
    Outcome.PUBLISH: "published",
    Outcome.APPROVE: "published",
    Outcome.REJECT: "rejected",
    Outcome.FLAG_FOR_REVIEW: "pending_review",
    Outcome.MANUAL_REVIEW: "pending_review",
}


def recipe_status_for_outcome(outcome: Outcome) -> str:
    return RECIPE_STATUS_BY_OUTCOME.get(outcome, "pending_review")
