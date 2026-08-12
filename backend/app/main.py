from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import admin, moderation, profiles, recipes, social
from app.config import settings
from app.db.pool import close_pool, get_pool
from app.middleware.errors import register_exception_handlers
from app.middleware.logging import RequestLoggingMiddleware, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    Path(settings.uploads_dir).mkdir(parents=True, exist_ok=True)
    if settings.uses_db:
        await get_pool()
    yield
    if settings.uses_db:
        await close_pool()


app = FastAPI(
    title="RecipeBoard API",
    description="Backend for RecipeBoard — grid-style recipe sharing with YOLO moderation",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

register_exception_handlers(app)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiles.router, prefix="/api/v1")
app.include_router(recipes.router, prefix="/api/v1")
app.include_router(social.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(moderation.router, prefix="/api/v1")

uploads = Path(settings.uploads_dir)
uploads.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(uploads)), name="media")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "recipeboard-api",
        "placeholder_mode": settings.use_placeholders,
        "local_yolo": settings.use_local_yolo,
        "auth_provider": settings.auth_provider,
        "aws_mode": settings.uses_aws,
    }
