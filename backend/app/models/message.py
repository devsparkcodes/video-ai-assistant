import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship


class Message(SQLModel, table=True):
    """Message model for conversation history."""
    
    __tablename__ = "messages"
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        description="Message ID"
    )
    session_id: str = Field(
        ...,
        foreign_key="video_sessions.id",
        description="Associated session ID"
    )
    role: str = Field(
        ...,
        description="Message role: 'user' or 'assistant'"
    )
    content: str = Field(
        ...,
        description="Message content"
    )
    model: Optional[str] = Field(
        default=None,
        description="Model used for this message"
    )
    interaction_id: Optional[str] = Field(
        default=None,
        description="Gemini interaction ID"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Message creation time"
    )
    
    session: Optional["VideoSession"] = Relationship(back_populates="messages")
