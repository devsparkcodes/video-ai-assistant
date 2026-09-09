from pydantic import BaseModel, Field
from typing import Optional


class ErrorDetail(BaseModel):
    """Standardized error detail."""
    
    code: str
    message: str
    retryable: bool = False


class ErrorResponse(BaseModel):
    """Standardized error response format."""
    
    error: ErrorDetail


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str = "ok"


class MessageResponse(BaseModel):
    """Message response schema."""
    
    id: str
    session_id: str
    role: str
    content: str
    model: Optional[str] = None
    interaction_id: Optional[str] = None
    created_at: str


class SessionResponse(BaseModel):
    """Session response schema."""
    
    session_id: str
    status: str
    source_type: str
    active_model: Optional[str] = None
    created_at: str


class ConversationResponse(BaseModel):
    """Conversation history response."""
    
    session_id: str
    messages: list[MessageResponse]


class QuestionCreate(BaseModel):
    """Question request schema."""
    
    question: str


class AnswerResponse(BaseModel):
    """Answer response schema."""
    
    message_id: str
    answer: str
    model: str
    timestamps: list[dict] = []
    created_at: str


class SessionNotFoundResponse(BaseModel):
    """Response for session not found."""
    
    error: ErrorDetail = Field(
        default=ErrorDetail(
            code="SESSION_NOT_FOUND",
            message="Session not found. Please check the session ID.",
            retryable=False
        )
    )


class VideoInvalidResponse(BaseModel):
    """Response for invalid video."""
    
    error: ErrorDetail = Field(
        default=ErrorDetail(
            code="VIDEO_INVALID",
            message="This video could not be processed. Please choose another supported video.",
            retryable=False
        )
    )


class UnsupportedVideoResponse(BaseModel):
    """Response for unsupported video format."""
    
    error: ErrorDetail = Field(
        default=ErrorDetail(
            code="UNSUPPORTED_VIDEO",
            message="This video format is not supported.",
            retryable=False
        )
    )


class VideoTooLargeResponse(BaseModel):
    """Response for file too large."""
    
    error: ErrorDetail = Field(
        default=ErrorDetail(
            code="VIDEO_TOO_LARGE",
            message="File is too large. Please upload a smaller video.",
            retryable=False
        )
    )


class InvalidYouTubeUrlResponse(BaseModel):
    """Response for invalid YouTube URL."""
    
    error: ErrorDetail = Field(
        default=ErrorDetail(
            code="INVALID_YOUTUBE_URL",
            message="Invalid YouTube URL. Please provide a valid public YouTube video URL.",
            retryable=False
        )
    )
