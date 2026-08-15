from datetime import datetime, timezone
from uuid import UUID

from app.models.schemas import RecipeResponse, UserProfile

PLACEHOLDER_USER_ID = UUID("00000000-0000-4000-8000-000000000001")

PLACEHOLDER_AUTHORS: dict[UUID, dict] = {
    PLACEHOLDER_USER_ID: {"username": "you", "display_name": "You"},
    UUID("00000000-0000-4000-8000-000000000002"): {"username": "maya_cooks", "display_name": "Maya"},
    UUID("00000000-0000-4000-8000-000000000003"): {"username": "chef_leo", "display_name": "Leo"},
    UUID("00000000-0000-4000-8000-000000000004"): {"username": "sourdough_sam", "display_name": "Sam"},
}

PLACEHOLDER_PROFILE = UserProfile(
    id=PLACEHOLDER_USER_ID,
    username="you",
    display_name="You",
    bio="Home cook sharing weeknight dishes.",
    recipe_count=2,
    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
)

_IMAGE = "https://images.unsplash.com/photo-{id}?auto=format&fit=crop&w=1600&q=90"

PLACEHOLDER_RECIPES: list[RecipeResponse] = [
    RecipeResponse(
        id=UUID("10000000-0000-4000-8000-000000000001"),
        user_id=UUID("00000000-0000-4000-8000-000000000002"),
        title="Tomato Basil Pasta",
        description="Weeknight pasta with blistered cherry tomatoes and fresh basil.",
        status="published",
        like_count=128,
        comment_count=14,
        image_url=_IMAGE.format(id="1473093295043-cdd812d0e601"),
        author=UserProfile(id=UUID("00000000-0000-4000-8000-000000000002"), username="maya_cooks", display_name="Maya"),
        created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    ),
    RecipeResponse(
        id=UUID("10000000-0000-4000-8000-000000000002"),
        user_id=UUID("00000000-0000-4000-8000-000000000003"),
        title="Crispy Salmon Bowl",
        description="Sesame-crusted salmon over rice with cucumber and avocado.",
        status="published",
        like_count=96,
        comment_count=8,
        image_url=_IMAGE.format(id="1519708227418-c8fd9a32b7a2"),
        author=UserProfile(id=UUID("00000000-0000-4000-8000-000000000003"), username="chef_leo", display_name="Leo"),
        created_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
    ),
    RecipeResponse(
        id=UUID("10000000-0000-4000-8000-000000000003"),
        user_id=UUID("00000000-0000-4000-8000-000000000004"),
        title="Sourdough Toast Stack",
        description="Toasted sourdough, whipped ricotta, honey, and cracked pepper.",
        status="published",
        like_count=210,
        comment_count=22,
        image_url=_IMAGE.format(id="1482049016688-2d3e1b311543"),
        author=UserProfile(id=UUID("00000000-0000-4000-8000-000000000004"), username="sourdough_sam", display_name="Sam"),
        created_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
    ),
    RecipeResponse(
        id=UUID("10000000-0000-4000-8000-000000000004"),
        user_id=UUID("00000000-0000-4000-8000-000000000002"),
        title="Green Goddess Salad",
        description="Crunchy greens with herby yogurt dressing.",
        status="published",
        like_count=54,
        comment_count=5,
        image_url=_IMAGE.format(id="1512621776951-a57141f2eefd"),
        author=UserProfile(id=UUID("00000000-0000-4000-8000-000000000002"), username="maya_cooks", display_name="Maya"),
        created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
    ),
    RecipeResponse(
        id=UUID("10000000-0000-4000-8000-000000000005"),
        user_id=UUID("00000000-0000-4000-8000-000000000003"),
        title="Miso Butter Mushrooms",
        description="Roasted mushrooms glazed in miso butter.",
        status="published",
        like_count=77,
        comment_count=9,
        image_url=_IMAGE.format(id="1414235077428-338989a2e8c0"),
        author=UserProfile(id=UUID("00000000-0000-4000-8000-000000000003"), username="chef_leo", display_name="Leo"),
        created_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
    ),
    RecipeResponse(
        id=UUID("10000000-0000-4000-8000-000000000006"),
        user_id=PLACEHOLDER_USER_ID,
        title="Honey Garlic Chicken",
        description="Sticky skillet chicken with rice and scallions.",
        status="published",
        like_count=33,
        comment_count=4,
        image_url=_IMAGE.format(id="1604908176997-125f25cc6f3d"),
        author=PLACEHOLDER_PROFILE,
        created_at=datetime(2026, 8, 6, tzinfo=timezone.utc),
    ),
]

PLACEHOLDER_COMMENTS = {
    "10000000-0000-4000-8000-000000000001": [
        {
            "id": "20000000-0000-4000-8000-000000000001",
            "recipe_id": "10000000-0000-4000-8000-000000000001",
            "user_id": "00000000-0000-4000-8000-000000000003",
            "content": "Making this tonight!",
            "author": {"id": "00000000-0000-4000-8000-000000000003", "username": "chef_leo", "display_name": "Leo"},
            "created_at": "2026-08-02T12:00:00Z",
        }
    ]
}
