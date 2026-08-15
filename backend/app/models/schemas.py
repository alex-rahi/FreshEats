from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class RecipeStatus(str, Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class UserProfile(BaseModel):
    id: UUID
    username: str
    display_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    recipe_count: int = 0
    created_at: datetime | None = None


class ProfileUpdate(BaseModel):
    username: str | None = None
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None


class RecipeImage(BaseModel):
    id: UUID | None = None
    storage_path: str
    public_url: str | None = None
    sort_order: int = 0
    is_primary: bool = True


class RecipeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=500)


class RecipeResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: str | None = None
    status: RecipeStatus | str
    moderation_decision: str | None = None
    moderation_reason: str | None = None
    like_count: int = 0
    comment_count: int = 0
    liked_by_me: bool = False
    image_url: str | None = None
    images: list[RecipeImage] = Field(default_factory=list)
    detection_labels: list[str] = Field(default_factory=list)
    moderation_rules: list[dict] = Field(default_factory=list)
    what_happens: str | None = None
    author: UserProfile | None = None
    created_at: datetime | None = None


class RecipeCreateResponse(BaseModel):
    recipe: RecipeResponse
    upload_url: str | None = None
    storage_path: str | None = None
    job_id: str | None = None


class RecipeGridResponse(BaseModel):
    items: list[RecipeResponse]
    next_cursor: str | None = None


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class CommentResponse(BaseModel):
    id: UUID
    recipe_id: UUID
    user_id: UUID
    content: str
    author: UserProfile | None = None
    created_at: datetime | None = None


class ReviewDecision(BaseModel):
    outcome: str  # publish | reject
    notes: str | None = None


class ReviewQueueItem(BaseModel):
    id: UUID
    recipe_id: UUID
    priority: int = 0
    review_status: str = "pending"
    recipe: RecipeResponse | None = None
    detections: list[dict] = Field(default_factory=list)
    moderation_scores: list[dict] = Field(default_factory=list)
    created_at: datetime | None = None


class AdminStats(BaseModel):
    pending_reviews: int = 0
    published_today: int = 0
    rejected_today: int = 0
    total_recipes: int = 0
    total_users: int = 0
