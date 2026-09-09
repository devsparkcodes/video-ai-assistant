from pydantic import BaseModel
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


class YouTubeSessionCreate(BaseModel):
    """YouTube URL session creation schema."""
    
    url: str
