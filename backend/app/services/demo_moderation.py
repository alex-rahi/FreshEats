"""Demo-mode YOLO rule evaluation without a live worker.

Uses image heuristics to synthesize detections, then applies the same
rule names / outcomes as the real worker rules engine.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageStat


FOOD_CORE = {
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "food",
    "dish",
    "meal",
    "ingredient",
}

# Present in many food scenes but never enough alone under food-only policy
COOKWARE = {
    "bowl",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "dining table",
}

FOOD_OBJECTS = FOOD_CORE | COOKWARE

UNRELATED_OBJECTS = {
    "car",
    "truck",
    "bus",
    "laptop",
    "cell phone",
    "keyboard",
    "tv",
    "remote",
    "book",
    "teddy bear",
    "person",
    "cat",
    "dog",
    "bird",
}

RULE_CATALOG = [
    {
        "rule_name": "content_moderation",
        "description": "Block unsafe / explicit content before anything else.",
        "on_fail": "Rejected — never published.",
    },
    {
        "rule_name": "food_detection",
        "description": "Food only: YOLO must find real food or a plated dish. Utensils, people, phones, cars, pets, or blank frames fail.",
        "on_fail": "Rejected — not published. Upload a food photo.",
    },
    {
        "rule_name": "recipe_relevance",
        "description": "FreshEats food-only policy: the image must be recipe content (ingredients or a finished dish).",
        "on_fail": "Rejected as off-topic for the recipe feed.",
    },
    {
        "rule_name": "user_trust",
        "description": "Low-trust accounts still need a clear food detection; food-only is not waived.",
        "on_fail": "Held for manual review only when food is present but account trust is low.",
    },
]


def _rule(name: str, outcome: str, confidence: float, details: dict | None = None) -> dict:
    return {
        "rule_name": name,
        "outcome": outcome,
        "confidence": round(confidence, 3),
        "details": details or {},
    }


def _skin_ratio(rgb: Image.Image) -> float:
    """Fraction of pixels that look like human skin (rejects portraits / babies as food)."""
    small = rgb.resize((64, 64))
    pixels = list(small.getdata())
    skin = 0
    for r, g, b in pixels:
        if (
            r > 95
            and g > 40
            and b > 20
            and r > g
            and r > b
            and abs(r - g) > 15
            and abs(g - b) < 50
            and (r - g) > (g - b)
        ):
            skin += 1
        # pink undertone common in faces / infants
        elif r > 150 and g > 90 and b > 90 and r > g + 25 and abs(g - b) < 40:
            skin += 1
    return skin / max(len(pixels), 1)


def _synthesize_detections(img: Image.Image) -> list[dict]:
    """Map simple pixel stats → fake YOLO labels for the demo path."""
    rgb = img.convert("RGB")
    stat = ImageStat.Stat(rgb)
    means = stat.mean  # R,G,B
    stdevs = stat.stddev
    variance = sum(stdevs) / 3
    skin = _skin_ratio(rgb)

    # Extremely flat / blank → no detections
    if variance < 8:
        return []

    r, g, b = means

    # People / portraits / infants — must beat the warm-food heuristic
    if skin >= 0.28 or (r > 160 and g > 100 and b > 100 and abs(g - b) < 40 and r > g + 30):
        return [{"label": "person", "confidence": min(0.97, 0.75 + skin / 2), "detection_type": "object"}]

    # Dark asphalt / vehicle-like
    if r < 70 and g < 80 and b < 100 and variance < 35:
        return [{"label": "car", "confidence": 0.82, "detection_type": "object"}]
    # Cool blue device frames
    if b >= r + 20 and b >= g + 12:
        return [{"label": "cell phone", "confidence": 0.88, "detection_type": "object"}]
    # Flat gray laptop / keyboard
    if abs(r - g) < 10 and abs(g - b) < 10 and 85 < r < 130 and variance < 25:
        return [{"label": "laptop", "confidence": 0.79, "detection_type": "object"}]

    # Warm / colorful food-like scenes (not skin-dominated)
    if skin < 0.18 and ((r > g and r > 90 and b < g + 25) or (g > 100 and r > 80) or variance >= 45):
        return [
            {"label": "food", "confidence": 0.91, "detection_type": "object"},
            {"label": "dish", "confidence": 0.84, "detection_type": "object"},
        ]

    # No clear food signal → empty detections (food-only rejects this)
    return []


def _evaluate_rules(detections: list[dict], moderation_scores: list[dict] | None = None) -> tuple[str, list[dict], str]:
    scores = moderation_scores or []
    labels = {d["label"].lower() for d in detections}
    confidences = {d["label"].lower(): float(d.get("confidence", 0)) for d in detections}

    # content_moderation
    content = _rule("content_moderation", "approve", 1.0)
    for score in scores:
        value = float(score.get("score", 0))
        cat = score.get("category")
        if value >= 0.9:
            content = _rule("content_moderation", "reject", value, {"category": cat, "score": value})
            break
        if value >= 0.5:
            content = _rule(
                "content_moderation",
                "flag_for_review",
                value,
                {"category": cat, "score": value},
            )

    food_core = labels & FOOD_CORE
    cookware = labels & COOKWARE
    unrelated = labels & UNRELATED_OBJECTS

    # food_detection — food only (core food labels required)
    if food_core and "person" not in labels:
        food = _rule(
            "food_detection",
            "approve",
            0.92,
            {"food": sorted(food_core), "detected": sorted(labels), "policy": "food_only"},
        )
    elif unrelated:
        max_u = max((confidences.get(l, 0) for l in unrelated), default=0)
        food = _rule(
            "food_detection",
            "reject",
            max_u,
            {"reason": "Food only — non-food object detected", "detected": sorted(unrelated)},
        )
    elif cookware and not food_core:
        food = _rule(
            "food_detection",
            "reject",
            0.7,
            {"reason": "Food only — utensils/table without food is not enough", "detected": sorted(labels)},
        )
    elif not labels:
        food = _rule(
            "food_detection",
            "reject",
            0.85,
            {"reason": "Food only — no food detected in image"},
        )
    else:
        food = _rule(
            "food_detection",
            "reject",
            0.75,
            {"reason": "Food only — image is not clearly food", "detected": sorted(labels)},
        )

    # recipe_relevance
    if food_core and "person" not in labels:
        relevance = _rule(
            "recipe_relevance",
            "approve",
            0.9,
            {"reason": "Food-only policy satisfied", "policy": "food_only"},
        )
    else:
        relevance = _rule(
            "recipe_relevance",
            "reject",
            0.9,
            {
                "reason": "Food only — FreshEats publishes recipe food photos only",
                "detected": sorted(labels),
                "policy": "food_only",
            },
        )

    # user_trust — only matters when food already passed
    trust = _rule("user_trust", "approve", 0.9)

    rules = [content, food, relevance, trust]
    priority = {"reject": 5, "manual_review": 4, "flag_for_review": 3, "approve": 2, "publish": 1}
    best = max(rules, key=lambda r: priority.get(r["outcome"], 0))
    final = "publish" if best["outcome"] == "approve" else best["outcome"]

    if final == "reject":
        reason = best["details"].get("reason") or f"Failed rule: {best['rule_name']}"
    elif final in ("flag_for_review", "manual_review"):
        reason = best["details"].get("reason") or f"Needs review: {best['rule_name']}"
    else:
        reason = "Food only — YOLO rules passed; publish to grid"

    return final, rules, reason


def analyze_image_file(path: Path) -> dict:
    with Image.open(path) as img:
        detections = _synthesize_detections(img)

    decision, rules, reason = _evaluate_rules(detections)
    status_map = {
        "publish": "published",
        "approve": "published",
        "reject": "rejected",
        "flag_for_review": "pending_review",
        "manual_review": "pending_review",
    }
    return {
        "status": status_map.get(decision, "pending_review"),
        "moderation_decision": decision,
        "moderation_reason": reason,
        "detection_labels": [d["label"] for d in detections],
        "detections": detections,
        "moderation_scores": [],
        "rules": rules,
        "what_happens": _what_happens(decision),
    }


def _what_happens(decision: str) -> str:
    if decision == "reject":
        return (
            "Rejected (food only) — this post is not published and does not appear on the grid. "
            "Upload a clear food / recipe photo."
        )
    if decision in ("flag_for_review", "manual_review"):
        return (
            "Held for manual review — not on the public grid until a moderator "
            "publishes or rejects it in the admin dashboard."
        )
    return "Published — food-only checks passed; the post is live on the FreshEats grid."


PASS_RULES = [
    _rule("content_moderation", "approve", 1.0),
    _rule(
        "food_detection",
        "approve",
        0.92,
        {"food": ["food", "dish"], "detected": ["food", "dish"], "policy": "food_only"},
    ),
    _rule(
        "recipe_relevance",
        "approve",
        0.9,
        {"reason": "Food-only policy satisfied", "policy": "food_only"},
    ),
    _rule("user_trust", "approve", 0.9),
]


def write_fail_samples(out_dir: Path) -> list[Path]:
    """Generate images that the demo analyzer should reject or flag."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # 1) Blank gray → no detections → pending review
    blank = Image.new("RGB", (800, 500), (136, 136, 136))
    p = out_dir / "fail-blank.jpg"
    blank.save(p, quality=92)
    written.append(p)

    # 2) Cell-phone-like cool blue/gray → reject (unrelated)
    phone = Image.new("RGB", (800, 500), (70, 90, 130))
    draw = ImageDraw.Draw(phone)
    draw.rectangle((220, 40, 580, 460), fill=(40, 48, 64), outline=(200, 210, 230), width=6)
    draw.rectangle((250, 80, 550, 400), fill=(120, 150, 190))
    draw.text((300, 220), "PHONE", fill=(230, 240, 255))
    p = out_dir / "fail-cellphone.jpg"
    phone.save(p, quality=92)
    written.append(p)

    # 3) Car-like dark asphalt → reject (unrelated)
    car = Image.new("RGB", (800, 500), (55, 58, 62))
    draw = ImageDraw.Draw(car)
    draw.ellipse((140, 180, 660, 380), fill=(40, 44, 50))
    draw.rectangle((180, 210, 620, 320), fill=(35, 90, 150))
    draw.text((340, 250), "CAR", fill=(220, 230, 240))
    p = out_dir / "fail-car.jpg"
    car.save(p, quality=92)
    written.append(p)

    # 4) Laptop-like flat gray → reject (unrelated)
    laptop = Image.new("RGB", (800, 500), (110, 112, 114))
    draw = ImageDraw.Draw(laptop)
    draw.rectangle((100, 80, 700, 360), fill=(90, 92, 94))
    for y in range(100, 340, 18):
        draw.line((120, y, 680, y), fill=(70, 72, 74), width=2)
    draw.text((300, 400), "LAPTOP", fill=(40, 40, 40))
    p = out_dir / "fail-laptop.jpg"
    laptop.save(p, quality=92)
    written.append(p)

    return written
