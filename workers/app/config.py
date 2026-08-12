from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:54322/postgres"
    yolo_model_path: str = "models/yolov8n.pt"
    moderation_threshold: float = 0.7
    uploads_dir: str = "/data/uploads"
    http_port: int = 8001
    aws_region: str = "us-east-1"
    sqs_moderation_url: str = ""
    storage_bucket_raw: str = "fresheats-raw-uploads"
    storage_bucket_recipes: str = "fresheats-recipe-images"


settings = WorkerSettings()
