"""Message history endpoint for retrieving conversation history."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.session import get_session
from app.services.conversation import ConversationService
from app.schemas.error import (
    ErrorResponse,
    MessageResponse,
    ConversationResponse,
)

router = APIRouter()


def get_conversation_service(
    db: Session = Depends(get_session),
) -> ConversationService:
    """Dependency for conversation service."""
    return ConversationService(db=db)


@router.get(
    "/sessions/{session_id}/messages",
    response_model=ConversationResponse,
    status_code=200,
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_messages(
    session_id: str,
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """Get conversation history for a video session.

    Args:
        session_id: Session ID from URL path
        conversation_service: Conversation service dependency

    Returns:
        Conversation history with messages in chronological order

    Raises:
        HTTPException: If session not found
    """
    session = conversation_service.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": "Session not found. Please check the session ID.",
                    "retryable": False,
                }
            },
        )

    messages = conversation_service.get_message_history(session_id)

    return ConversationResponse(
        session_id=session_id,
        messages=[
            MessageResponse(
                id=msg.id,
                session_id=msg.session_id,
                role=msg.role,
                content=msg.content,
                model=msg.model,
                interaction_id=msg.interaction_id,
                created_at=msg.created_at.isoformat(),
            )
            for msg in messages
        ],
    )
