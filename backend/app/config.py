from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT / ".env", Path(".env")),
        extra="ignore",
    )

    # Demo / local
    use_placeholders: bool = True
    use_local_yolo: bool = False
    worker_url: str = "http://localhost:8001"
    uploads_dir: str = str(ROOT / "data" / "uploads")
    admin_secret: str = "placeholder-admin-secret"
    cors_origins: str = "http://localhost:3000,http://localhost:8081"

    # Auth
    auth_provider: str = "placeholder"  # placeholder | cognito | supabase
    supabase_url: str = "https://placeholder.supabase.co"
    supabase_jwt_secret: str = "placeholder-jwt-secret-for-local-dev-only"
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_issuer: str = ""
    aws_region: str = "us-east-1"

    # Data
    database_url: str = "postgresql://postgres:postgres@localhost:54322/postgres"
    redis_url: str = ""

    # Storage / queue
    storage_bucket_raw: str = "plate-raw-uploads"
    storage_bucket_recipes: str = "plate-recipe-images"
    cloudfront_domain: str = ""
    sqs_moderation_url: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def uses_aws(self) -> bool:
        return (
            not self.use_placeholders
            and not self.use_local_yolo
            and self.auth_provider == "cognito"
        )

    @property
    def uses_db(self) -> bool:
        return self.uses_aws or (
            not self.use_placeholders and not self.use_local_yolo
        )


settings = Settings()
