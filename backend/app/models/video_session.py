import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship


class SessionStatus(str, Enum):
    """Session lifecycle status values."""
    UPLOADING = "UPLOADING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class VideoSession(SQLModel, table=True):
    """Video session model."""
    
    __tablename__ = "video_sessions"
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        description="Application session ID"
    )
    source_type: str = Field(
        ...,
        description="Source type: 'upload' or 'youtube'"
    )
    source_url: Optional[str] = Field(
        default=None,
        description="YouTube URL if source_type is youtube"
    )
    original_filename: Optional[str] = Field(
        default=None,
        description="Original upload filename"
    )
    mime_type: Optional[str] = Field(
        default=None,
        description="Uploaded MIME type"
    )
    size_bytes: Optional[int] = Field(
        default=None,
        description="Upload size in bytes"
    )
    gemini_file_uri: Optional[str] = Field(
        default=None,
        description="Gemini File API URI"
    )
    status: SessionStatus = Field(
        default=SessionStatus.UPLOADING,
        description="Session lifecycle status"
    )
    active_model: Optional[str] = Field(
        default=None,
        description="Last successful Gemini model"
    )
    previous_interaction_id: Optional[str] = Field(
        default=None,
        description="Same-model conversation state"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation time"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update time"
    )
    
    messages: list["Message"] = Relationship(back_populates="session")
