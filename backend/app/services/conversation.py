"""Conversation service for managing video Q&A messages."""

import logging
from typing import List, Optional
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.config import settings
from app.models.message import Message
from app.models.video_session import VideoSession, SessionStatus
from app.services.gemini_service import GeminiAnswer, GeminiService, GeminiError
from app.services.model_router import ModelRouter

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing conversation messages and history."""
    
    def __init__(
        self,
        db: Session,
        gemini_service: Optional[GeminiService] = None,
        router: Optional[ModelRouter] = None,
    ):
        """Initialize the conversation service.
        
        Args:
            db: Database session
            gemini_service: Gemini service instance (optional, for ask() method)
            router: Model router instance. When omitted, a default router is
                built around the provided gemini_service.
        """
        self.db = db
        self.gemini_service = gemini_service
        if router is not None:
            self.router = router
        elif gemini_service is not None:
            self.router = ModelRouter(gemini_service=gemini_service)
        else:
            self.router = None
    
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
            interaction_id: Gemini interaction ID (optional). When missing, any
                previously stored interaction ID is explicitly cleared so an ID
                from another model is never retained.
            
        Returns:
            Updated VideoSession
        """
        session.active_model = model
        session.previous_interaction_id = interaction_id or None
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
    
    def _build_conversation_context(self, session_id: str) -> str:
        """Reconstruct a bounded conversation context from persisted messages.

        Used when a fresh interaction is required (model switch), per
        docs/06-conversation-system.md §6. The context is truncated to the
        most recent CONVERSATION_CONTEXT_MAX_MESSAGES messages; the current
        question is not persisted yet and therefore never duplicated.

        Args:
            session_id: Session ID

        Returns:
            Bounded transcript ("User: ..." / "Assistant: ..." lines), or an
            empty string when there is no history.
        """
        history = self.get_message_history(session_id)
        if not history:
            return ""

        max_messages = settings.CONVERSATION_CONTEXT_MAX_MESSAGES
        try:
            max_messages = int(max_messages)
        except (TypeError, ValueError):
            max_messages = 20
        if max_messages > 0:
            history = history[-max_messages:]

        lines = [
            f"{'User' if message.role == 'user' else 'Assistant'}: {message.content}"
            for message in history
        ]
        return "\n".join(lines)

    def ask(
        self,
        session_id: str,
        question: str,
    ) -> GeminiAnswer:
        """Ask a question about a video session.
        
        Model selection and bounded fallback are delegated to the model
        router. For same-model follow-ups the router reuses the session's
        previous_interaction_id; after a model switch it starts a fresh
        interaction with the video input and reconstructed context.

        On failure nothing is persisted: no failed user question, no fake
        assistant answer, and no conversation-state mutation.
        
        Args:
            session_id: Session ID
            question: User's question
            
        Returns:
            GeminiAnswer with the response
            
        Raises:
            ValueError: If session not found or not ready
            GeminiError: If all eligible attempts fail or a non-retryable
                error occurs
        """
        # Validate session exists and is ready
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        if not self.validate_session_ready(session):
            raise ValueError(f"Session is not ready for questions: {session.status}")

        if self.router is None:
            raise RuntimeError(
                "Conversation service is not configured with a Gemini service."
            )
        
        # Bounded context from persisted messages (used only on model switch)
        conversation_context = self._build_conversation_context(session_id)

        # The router selects the model, applies bounded fallback, and decides
        # whether previous_interaction_id may be reused for the chosen model.
        gemini_answer = self.router.answer(
            session=session,
            question=question,
            conversation_context=conversation_context,
        )
        
        # Persist the conversation only after a successful answer
        self.save_gemini_response(
            session_id=session_id,
            user_content=question,
            gemini_answer=gemini_answer,
        )
        
        logger.info(
            f"Question answered for session: {session_id} by model: {gemini_answer.model}"
        )
        return gemini_answer
