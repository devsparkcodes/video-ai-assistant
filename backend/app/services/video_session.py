"""Video session service for handling video uploads and YouTube URLs."""

import logging
from typing import Optional
from datetime import datetime, timezone

from sqlmodel import Session

from app.models.video_session import VideoSession, SessionStatus
from app.services.gemini_service import GeminiService, GeminiError, GeminiErrorCategory
from app.services.video_validation import validate_video_file, validate_youtube_url

logger = logging.getLogger(__name__)


class VideoSessionService:
    """Service for managing video sessions."""
    
    def __init__(self, gemini_service: GeminiService):
        """Initialize the video session service.
        
        Args:
            gemini_service: Gemini service instance
        """
        self.gemini_service = gemini_service
    
    def create_upload_session(
        self,
        db: Session,
        filename: str,
        content_type: str,
        file_size: int,
        file_path: str,
    ) -> VideoSession:
        """Create a session from uploaded video.
        
        Args:
            db: Database session
            filename: Original filename
            content_type: MIME type
            file_size: File size in bytes
            file_path: Path to uploaded file
            
        Returns:
            Created VideoSession
            
        Raises:
            ValueError: If validation fails
            GeminiError: If Gemini upload fails
        """
        # Validate video file
        is_valid, error_message = validate_video_file(filename, content_type, file_size)
        if not is_valid:
            raise ValueError(error_message)
        
        # Create session with uploading status
        session = VideoSession(
            source_type="upload",
            original_filename=filename,
            mime_type=content_type,
            size_bytes=file_size,
            status=SessionStatus.UPLOADING,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        try:
            # Upload to Gemini File API
            file_result = self.gemini_service.upload_file(file_path)
            
            # Update session with Gemini file URI
            session.gemini_file_uri = file_result.get("uri")
            session.status = SessionStatus.PROCESSING
            session.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(session)
            
            # Check file processing status
            if file_result.get("state") == "ACTIVE":
                session.status = SessionStatus.READY
                session.updated_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(session)
            
            logger.info(f"Upload session created: {session.id}")
            return session
            
        except GeminiError as e:
            # Update session with failed status
            session.status = SessionStatus.FAILED
            session.updated_at = datetime.now(timezone.utc)
            db.commit()
            
            logger.error(f"Gemini upload failed for session {session.id}: {e.message}")
            raise
        except Exception as e:
            # Update session with failed status
            session.status = SessionStatus.FAILED
            session.updated_at = datetime.now(timezone.utc)
            db.commit()
            
            logger.error(f"Upload failed for session {session.id}: {str(e)}")
            raise
    
    def create_youtube_session(
        self,
        db: Session,
        url: str,
    ) -> VideoSession:
        """Create a session from YouTube URL.
        
        Args:
            db: Database session
            url: YouTube URL
            
        Returns:
            Created VideoSession
            
        Raises:
            ValueError: If URL validation fails
        """
        # Validate YouTube URL
        is_valid, error_message = validate_youtube_url(url)
        if not is_valid:
            raise ValueError(error_message)
        
        # Create session
        session = VideoSession(
            source_type="youtube",
            source_url=url,
            status=SessionStatus.READY,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        logger.info(f"YouTube session created: {session.id}")
        return session
    
    def get_session(self, db: Session, session_id: str) -> Optional[VideoSession]:
        """Get session by ID.
        
        Args:
            db: Database session
            session_id: Session ID
            
        Returns:
            VideoSession if found, None otherwise
        """
        from sqlmodel import select
        
        statement = select(VideoSession).where(VideoSession.id == session_id)
        return db.exec(statement).first()
    
    def delete_session(self, db: Session, session_id: str) -> bool:
        """Delete session by ID.
        
        Args:
            db: Database session
            session_id: Session ID
            
        Returns:
            True if deleted, False if not found
        """
        session = self.get_session(db, session_id)
        if not session:
            return False
        
        db.delete(session)
        db.commit()
        
        logger.info(f"Session deleted: {session_id}")
        return True