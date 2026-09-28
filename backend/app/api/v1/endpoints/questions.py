"""Question endpoint for asking questions about video sessions."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.session import get_session
from app.services.gemini_service import GeminiService, GeminiError, GeminiErrorCategory
from app.services.conversation import ConversationService
from app.schemas.error import (
    QuestionCreate,
    AnswerResponse,
    ErrorResponse,
)

router = APIRouter()


def get_gemini_service() -> GeminiService:
    """Dependency for Gemini service."""
    return GeminiService()


def get_conversation_service(
    gemini_service: GeminiService = Depends(get_gemini_service),
    db: Session = Depends(get_session),
) -> ConversationService:
    """Dependency for conversation service."""
    return ConversationService(db=db, gemini_service=gemini_service)


@router.post(
    "/sessions/{session_id}/questions",
    response_model=AnswerResponse,
    status_code=200,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
async def ask_question(
    session_id: str,
    request: QuestionCreate,
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """Ask a question about a video session.

    Args:
        session_id: Session ID from URL path
        request: Question request body
        conversation_service: Conversation service dependency

    Returns:
        Answer response with answer, model, timestamps

    Raises:
        HTTPException: If session not found, not ready, or Gemini fails
    """
    try:
        gemini_answer = conversation_service.ask(
            session_id=session_id,
            question=request.question,
        )

        return AnswerResponse(
            message_id=gemini_answer.interaction_id or "",
            answer=gemini_answer.text,
            model=gemini_answer.model,
            timestamps=[],
            created_at="",
        )

    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
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
        else:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "SESSION_NOT_READY",
                        "message": "Session is not ready for questions. Please wait for processing to complete.",
                        "retryable": False,
                    }
                },
            )

    except GeminiError as e:
        if e.category == GeminiErrorCategory.AUTHENTICATION:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": {
                        "code": "GEMINI_AUTH_ERROR",
                        "message": "The video service is not configured correctly. Please contact the administrator.",
                        "retryable": False,
                    }
                },
            )
        elif e.category == GeminiErrorCategory.RATE_LIMITED:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": {
                        "code": "GEMINI_RATE_LIMITED",
                        "message": "Rate limit exceeded. Please try again later.",
                        "retryable": True,
                    }
                },
            )
        elif e.category == GeminiErrorCategory.CONTENT_BLOCKED:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": {
                        "code": "GEMINI_SAFETY_REJECTED",
                        "message": "The request cannot be processed due to content restrictions.",
                        "retryable": False,
                    }
                },
            )
        else:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": {
                        "code": "GEMINI_UNAVAILABLE",
                        "message": "Video analysis failed. Please try again.",
                        "retryable": True,
                    }
                },
            )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred. Please try again.",
                    "retryable": False,
                }
            },
        )
