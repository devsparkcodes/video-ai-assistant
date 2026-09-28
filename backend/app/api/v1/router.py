from fastapi import APIRouter
from app.api.v1.endpoints import health, sessions, questions, messages

router = APIRouter()

router.include_router(health.router, tags=["health"])
router.include_router(sessions.router, tags=["sessions"])
router.include_router(questions.router, tags=["questions"])
router.include_router(messages.router, tags=["messages"])
