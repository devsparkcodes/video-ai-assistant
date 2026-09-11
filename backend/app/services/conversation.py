"""Conversation service for managing video Q&A messages."""

import logging
from typing import List, Optional
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.message import Message
from app.models.video_session import VideoSession, SessionStatus
from app.services.gemini_service import GeminiAnswer, GeminiService, GeminiError

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing conversation messages and history."""
    
    def __init__(self, db: Session, gemini_service: Optional[GeminiService] = None):
        """Initialize the conversation service.
        
        Args:
            db: Database session
            gemini_service: Gemini service instance (optional, for ask() method)
        """
        self.db = db
        self.gemini_service = gemini_service
    
    def get_session(self, session_id: str) -> Optional[VideoSession]:
        """Get session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            VideoSession if found, None otherwise
        """
        statement = select(VideoSession).where(VideoSession.id == session_id)
        return self.db.exec(statement).first()
    
    def validate_session_ready(self, session: VideoSession) -> bool:
        """Validate that session is ready for questions.
        
        Args:
            session: VideoSession to validate
            
        Returns:
            True if session is ready, False otherwise
        """
        return session.status == SessionStatus.READY
    
    def create_user_message(
        self,
        session_id: str,
        content: str,
    ) -> Message:
        """Create and persist a user message.
        
        Args:
            session_id: Session ID
            content: Message content
            
        Returns:
            Created Message
        """
        message = Message(
            session_id=session_id,
            role="user",
            content=content,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        
        logger.info(f"User message created: {message.id} for session: {session_id}")
        return message
    
    def create_assistant_message(
        self,
        session_id: str,
        content: str,
        model: str,
        interaction_id: Optional[str] = None,
    ) -> Message:
        """Create and persist an assistant message.
        
        Args:
            session_id: Session ID
            content: Message content
            model: Model used for response
            interaction_id: Gemini interaction ID (optional)
            
        Returns:
            Created Message
        """
        message = Message(
            session_id=session_id,
            role="assistant",
            content=content,
            model=model,
            interaction_id=interaction_id,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        
        logger.info(f"Assistant message created: {message.id} for session: {session_id}")
        return message
    
    def update_session_conversation_state(
        self,
        session: VideoSession,
        model: str,
        interaction_id: Optional[str] = None,
    ) -> VideoSession:
        """Update session conversation state after successful question.
        
        Args:
            session: VideoSession to update
            model: Model used for response
            interaction_id: Gemini interaction ID (optional)
            
        Returns:
            Updated VideoSession
        """
        session.active_model = model
        if interaction_id:
            session.previous_interaction_id = interaction_id
        session.updated_at = datetime.now(timezone.utc)
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        logger.info(f"Session conversation state updated: {session.id}")
        return session
    
    def get_message_history(
        self,
        session_id: str,
    ) -> List[Message]:
        """Get message history for a session in chronological order.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of Messages in chronological order
        """
        statement = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
        )
        messages = list(self.db.exec(statement).all())
        
        logger.info(f"Retrieved {len(messages)} messages for session: {session_id}")
        return messages
    
    def save_gemini_response(
        self,
        session_id: str,
        user_content: str,
        gemini_answer: GeminiAnswer,
    ) -> tuple[Message, Message]:
        """Save user question and Gemini response as messages.
        
        Args:
            session_id: Session ID
            user_content: User's question
            gemini_answer: Gemini's response
            
        Returns:
            Tuple of (user_message, assistant_message)
        """
        user_message = self.create_user_message(session_id, user_content)
        
        assistant_message = self.create_assistant_message(
            session_id=session_id,
            content=gemini_answer.text,
            model=gemini_answer.model,
            interaction_id=gemini_answer.interaction_id,
        )
        
        session = self.get_session(session_id)
        if session:
            self.update_session_conversation_state(
                session=session,
                model=gemini_answer.model,
                interaction_id=gemini_answer.interaction_id,
            )
        
        logger.info(f"Gemini response saved for session: {session_id}")
        return user_message, assistant_message
    
    def ask(
        self,
        session_id: str,
        question: str,
    ) -> GeminiAnswer:
        """Ask a question about a video session.
        
        For the first question, sends the video context to Gemini.
        For follow-ups, uses the previous_interaction_id for conversation continuity.
        
        Args:
            session_id: Session ID
            question: User's question
            
        Returns:
            GeminiAnswer with the response
            
        Raises:
            ValueError: If session not found or not ready
            GeminiError: If Gemini call fails
        """
        # Validate session exists and is ready
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        if not self.validate_session_ready(session):
            raise ValueError(f"Session is not ready for questions: {session.status}")
        
        # Determine video context
        video_uri = session.gemini_file_uri or session.source_url
        
        # Call Gemini
        gemini_answer = self.gemini_service.create_interaction(
            question=question,
            video_uri=video_uri,
            previous_interaction_id=session.previous_interaction_id,
        )
        
        # Persist the conversation
        self.save_gemini_response(
            session_id=session_id,
            user_content=question,
            gemini_answer=gemini_answer,
        )
        
        logger.info(f"Question answered for session: {session_id}")
        return gemini_answer
