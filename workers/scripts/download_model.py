"""Download YOLOv8 nano weights into workers/models/."""

from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_PATH = MODEL_DIR / "yolov8n.pt"


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if MODEL_PATH.exists():
        print(f"Model already present at {MODEL_PATH}")
        return

    from ultralytics import YOLO

    print("Downloading yolov8n.pt …")
    model = YOLO("yolov8n.pt")
    src = Path(getattr(model, "ckpt_path", None) or "yolov8n.pt")
    if src.resolve() != MODEL_PATH.resolve():
        MODEL_PATH.write_bytes(src.read_bytes())
    print(f"Saved model to {MODEL_PATH}")


if __name__ == "__main__":
    main()
