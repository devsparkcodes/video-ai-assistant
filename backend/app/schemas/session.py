"""Session schemas for video upload and YouTube URL endpoints."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SessionCreateResponse(BaseModel):
    """Response schema for session creation."""
    session_id: str
    status: str
    source_type: str


class YouTubeSessionCreate(BaseModel):
    """Request schema for YouTube session creation."""
    url: str = Field(..., description="Public YouTube URL")


class SessionResponse(BaseModel):
    """Response schema for session retrieval."""
    session_id: str
    status: str
    source_type: str
    active_model: Optional[str] = None
    created_at: str


class SessionDeleteResponse(BaseModel):
    """Response schema for session deletion."""
    deleted: bool = True