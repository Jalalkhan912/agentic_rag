from fastapi import APIRouter
from app.schemas import HealthOut
from app.config import get_settings

settings = get_settings()
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health():
    return HealthOut(
        status="ok",
        version="1.0.0",
        environment=settings.environment,
    )
