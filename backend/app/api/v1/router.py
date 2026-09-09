from fastapi import APIRouter
from app.api.v1.endpoints import health, sessions

router = APIRouter()

router.include_router(health.router, tags=["health"])
router.include_router(sessions.router, tags=["sessions"])
