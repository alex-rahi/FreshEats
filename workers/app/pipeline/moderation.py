"""Content moderation scoring (local heuristics)."""

import numpy as np

MODERATION_CATEGORIES = [
    "explicit_content", "violence_gore", "nudity",
    "hate_harassment", "unsafe_activity",
]


def moderate_frame(frame: np.ndarray, threshold: float = 0.7) -> list[dict]:
    scores = []
    for category in MODERATION_CATEGORIES:
        score = _mock_score(frame, category)
        if score > 0.1:
            scores.append({"category": category, "score": score})
    return scores


def _mock_score(frame: np.ndarray, category: str) -> float:
    h = hash(frame.tobytes()[:1000]) % 1000
    base = (h % 100) / 1000.0
    if category == "unsafe_activity":
        base *= 0.4
    return round(base, 3)


def aggregate_moderation_scores(frame_scores: list[list[dict]]) -> list[dict]:
    max_scores: dict[str, float] = {}
    for scores in frame_scores:
        for s in scores:
            cat = s["category"]
            max_scores[cat] = max(max_scores.get(cat, 0), s["score"])
    return [{"category": k, "score": v} for k, v in max_scores.items()]
