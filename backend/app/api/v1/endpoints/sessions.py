"""Video session endpoints for upload and YouTube URL."""

import os
import tempfile
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlmodel import Session

from app.db.session import get_session
from app.services.gemini_service import GeminiService, GeminiError, GeminiErrorCategory
from app.services.video_session import VideoSessionService
from app.schemas.session import (
    SessionCreateResponse,
    YouTubeSessionCreate,
    SessionResponse,
    SessionDeleteResponse,
)
from app.schemas.error import (
    ErrorResponse,
    ErrorDetail,
    SessionNotFoundResponse,
)

router = APIRouter()


def get_gemini_service() -> GeminiService:
    """Dependency for Gemini service."""
    return GeminiService()


def get_video_session_service(
    gemini_service: GeminiService = Depends(get_gemini_service),
) -> VideoSessionService:
    """Dependency for video session service."""
    return VideoSessionService(gemini_service)


@router.post(
    "/sessions",
    response_model=SessionCreateResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
async def create_upload_session(
    file: UploadFile = File(...),
    session_service: VideoSessionService = Depends(get_video_session_service),
    db: Session = Depends(get_session),
):
    """Create a session from uploaded video.
    
    Args:
        file: Uploaded video file
        session_service: Video session service
        db: Database session
        
    Returns:
        Session creation response
        
    Raises:
        HTTPException: If validation or upload fails
    """
    # Validate file exists
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_VIDEO", "message": "No file provided.", "retryable": False}},
        )
    
    # Get file size by reading content
    content = await file.read()
    file_size = len(content)
    
    # Reset file position
    await file.seek(0)
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # Create session
        session = session_service.create_upload_session(
            db=db,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            file_size=file_size,
            file_path=tmp_path,
        )
        
        return SessionCreateResponse(
            session_id=session.id,
            status=session.status,
            source_type=session.source_type,
        )
        
    except ValueError as e:
        # Validation error
        error_message = str(e)
        if "too large" in error_message.lower():
            raise HTTPException(status_code=413, detail={"error": {"code": "VIDEO_TOO_LARGE", "message": error_message, "retryable": False}})
        elif "unsupported" in error_message.lower():
            raise HTTPException(status_code=415, detail={"error": {"code": "UNSUPPORTED_VIDEO", "message": error_message, "retryable": False}})
        else:
            raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_VIDEO", "message": error_message, "retryable": False}})
    
    except GeminiError as e:
        # Gemini error
        if e.category == GeminiErrorCategory.AUTHENTICATION:
            raise HTTPException(status_code=502, detail={"error": {"code": "GEMINI_AUTH_ERROR", "message": "The video service is not configured correctly. Please contact the administrator.", "retryable": False}})
        elif e.category == GeminiErrorCategory.RATE_LIMITED:
            raise HTTPException(status_code=429, detail={"error": {"code": "GEMINI_RATE_LIMITED", "message": "Rate limit exceeded. Please try again later.", "retryable": True}})
        else:
            raise HTTPException(status_code=502, detail={"error": {"code": "GEMINI_UNAVAILABLE", "message": "Video upload failed. Please try again.", "retryable": True}})
    
    except Exception as e:
        # Unknown error
        raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred. Please try again.", "retryable": False}})
    
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post(
    "/sessions/url",
    response_model=SessionCreateResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def create_youtube_session(
    request: YouTubeSessionCreate,
    session_service: VideoSessionService = Depends(get_video_session_service),
    db: Session = Depends(get_session),
):
    """Create a session from YouTube URL.
    
    Args:
        request: YouTube session creation request
        session_service: Video session service
        db: Database session
        
    Returns:
        Session creation response
        
    Raises:
        HTTPException: If URL validation fails
    """
    try:
        # Create session
        session = session_service.create_youtube_session(
            db=db,
            url=request.url,
        )
        
        return SessionCreateResponse(
            session_id=session.id,
            status=session.status,
            source_type=session.source_type,
        )
        
    except ValueError as e:
        # Validation error
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_YOUTUBE_URL", "message": str(e), "retryable": False}},
        )
    
    except Exception as e:
        # Unknown error
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred. Please try again.", "retryable": False}},
        )


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_session(
    session_id: str,
    session_service: VideoSessionService = Depends(get_video_session_service),
    db: Session = Depends(get_session),
):
    """Get session by ID.
    
    Args:
        session_id: Session ID
        session_service: Video session service
        db: Database session
        
    Returns:
        Session response
        
    Raises:
        HTTPException: If session not found
    """
    session = session_service.get_session(db, session_id)
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "SESSION_NOT_FOUND", "message": "Session not found. Please check the session ID.", "retryable": False}},
        )
    
    return SessionResponse(
        session_id=session.id,
        status=session.status,
        source_type=session.source_type,
        active_model=session.active_model,
        created_at=session.created_at.isoformat(),
    )


@router.delete(
    "/sessions/{session_id}",
    response_model=SessionDeleteResponse,
    responses={
        404: {"model": ErrorResponse},
    },
)
async def delete_session(
    session_id: str,
    session_service: VideoSessionService = Depends(get_video_session_service),
    db: Session = Depends(get_session),
):
    """Delete session by ID.
    
    Args:
        session_id: Session ID
        session_service: Video session service
        db: Database session
        
    Returns:
        Deletion response
        
    Raises:
        HTTPException: If session not found
    """
    deleted = session_service.delete_session(db, session_id)
    
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "SESSION_NOT_FOUND", "message": "Session not found. Please check the session ID.", "retryable": False}},
        )
    
    return SessionDeleteResponse(deleted=True)