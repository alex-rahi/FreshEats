"""YOLO object detection tuned for food / cooking labels."""

import logging

import numpy as np

logger = logging.getLogger(__name__)

# Map COCO labels into food taxonomy used by the rules engine.
LABEL_ALIASES: dict[str, str] = {
    "banana": "banana",
    "apple": "apple",
    "sandwich": "sandwich",
    "orange": "orange",
    "broccoli": "broccoli",
    "carrot": "carrot",
    "hot dog": "hot dog",
    "pizza": "pizza",
    "donut": "donut",
    "cake": "cake",
    "bowl": "bowl",
    "bottle": "bottle",
    "wine glass": "wine glass",
    "cup": "cup",
    "fork": "fork",
    "knife": "knife",
    "spoon": "spoon",
    "dining table": "dining table",
    "plate": "dish",
    "person": "person",
    "oven": "oven",
    "microwave": "microwave",
    "refrigerator": "refrigerator",
    "sink": "sink",
}


def normalize_label(label: str) -> str:
    key = label.lower().strip()
    return LABEL_ALIASES.get(key, key)


try:
    from ultralytics import YOLO

    _model = None

    def _get_model(model_path: str):
        global _model
        if _model is None:
            logger.info("Loading YOLO model from %s", model_path)
            _model = YOLO(model_path)
        return _model

    def detect_objects(frame: np.ndarray, model_path: str, confidence: float = 0.35) -> list[dict]:
        model = _get_model(model_path)
        results = model(frame, verbose=False)
        detections = []
        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                if conf < confidence:
                    continue
                raw_label = result.names.get(cls_id, f"class_{cls_id}")
                label = normalize_label(raw_label)
                xyxy = box.xyxy[0].tolist()
                detections.append({
                    "detection_type": "object",
                    "label": label,
                    "raw_label": raw_label,
                    "confidence": conf,
                    "bounding_box": {
                        "x1": xyxy[0], "y1": xyxy[1],
                        "x2": xyxy[2], "y2": xyxy[3],
                    },
                })
        return detections

except ImportError:
    logger.warning("ultralytics not available — using mock food detections")

    def detect_objects(frame: np.ndarray, model_path: str, confidence: float = 0.35) -> list[dict]:
        return [
            {
                "detection_type": "object",
                "label": "pizza",
                "raw_label": "pizza",
                "confidence": 0.91,
                "bounding_box": {"x1": 80, "y1": 60, "x2": 420, "y2": 380},
            },
            {
                "detection_type": "object",
                "label": "dining table",
                "raw_label": "dining table",
                "confidence": 0.72,
                "bounding_box": {"x1": 20, "y1": 200, "x2": 500, "y2": 480},
            },
        ]
