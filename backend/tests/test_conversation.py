"""Tests for conversation service and schemas."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pydantic import ValidationError
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.models import VideoSession, Message, SessionStatus
from app.models.video_session import SessionStatus
from app.schemas.error import (
    QuestionCreate,
    AnswerResponse,
    TimestampRef,
)
from app.services.conversation import ConversationService
from app.services.gemini_service import GeminiAnswer


@pytest.fixture(name="engine")
def engine_fixture():
    """Create test database engine."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session")
def session_fixture(engine):
    """Create test database session."""
    with Session(engine) as session:
        yield session


@pytest.fixture(name="ready_session")
def ready_session_fixture(session):
    """Create a ready video session for testing."""
    video_session = VideoSession(
        source_type="youtube",
        source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        status=SessionStatus.READY,
    )
    session.add(video_session)
    session.commit()
    session.refresh(video_session)
    return video_session


class TestQuestionCreateSchema:
    """Test QuestionCreate schema validation."""
    
    def test_question_create_valid(self):
        """Test valid question is accepted."""
        question = QuestionCreate(question="What is this video about?")
        assert question.question == "What is this video about?"
    
    def test_question_create_min_length_rejects_empty(self):
        """Test QuestionCreate rejects empty questions."""
        with pytest.raises(ValidationError) as exc_info:
            QuestionCreate(question="")
        assert "String should have at least 1 character" in str(exc_info.value)
    
    def test_question_create_accepts_whitespace_only(self):
        """Test QuestionCreate accepts whitespace-only questions (min_length checks length, not content)."""
        question = QuestionCreate(question="   ")
        assert question.question == "   "
    
    def test_question_create_max_length_rejects_long(self):
        """Test QuestionCreate rejects questions longer than 4000 characters."""
        long_question = "x" * 4001
        with pytest.raises(ValidationError) as exc_info:
            QuestionCreate(question=long_question)
        assert "String should have at most 4000 characters" in str(exc_info.value)
    
    def test_question_create_accepts_exact_max_length(self):
        """Test QuestionCreate accepts questions at exactly 4000 characters."""
        exact_question = "x" * 4000
        question = QuestionCreate(question=exact_question)
        assert len(question.question) == 4000


class TestTimestampRefSchema:
    """Test TimestampRef schema."""
    
    def test_timestamp_ref_minimal(self):
        """Test TimestampRef with required fields only."""
        ref = TimestampRef(start_seconds=42.5)
        assert ref.start_seconds == 42.5
        assert ref.label is None
    
    def test_timestamp_ref_with_label(self):
        """Test TimestampRef with optional label."""
        ref = TimestampRef(start_seconds=42.5, label="Chapter 1")
        assert ref.start_seconds == 42.5
        assert ref.label == "Chapter 1"


class TestAnswerResponseSchema:
    """Test AnswerResponse schema."""
    
    def test_answer_response_minimal(self):
        """Test AnswerResponse with required fields only."""
        response = AnswerResponse(
            message_id="test-id",
            answer="The video explains...",
            model="gemini-3.8-flash",
            created_at="2026-09-09T12:00:00Z",
        )
        assert response.message_id == "test-id"
        assert response.answer == "The video explains..."
        assert response.model == "gemini-3.8-flash"
        assert response.timestamps == []
    
    def test_answer_response_with_timestamps(self):
        """Test AnswerResponse with timestamps."""
        timestamps = [
            TimestampRef(start_seconds=10.5, label="Introduction"),
            TimestampRef(start_seconds=45.0),
        ]
        response = AnswerResponse(
            message_id="test-id",
            answer="The video discusses...",
            model="gemini-3.8-flash",
            timestamps=timestamps,
            created_at="2026-09-09T12:00:00Z",
        )
        assert len(response.timestamps) == 2
        assert response.timestamps[0].label == "Introduction"
        assert response.timestamps[1].label is None


class TestConversationService:
    """Test ConversationService message operations."""
    
    def test_create_user_message(self, session, ready_session):
        """Test user message can be persisted."""
        service = ConversationService(session)
        
        message = service.create_user_message(
            session_id=ready_session.id,
            content="What is this video about?",
        )
        
        assert message.id is not None
        assert message.session_id == ready_session.id
        assert message.role == "user"
        assert message.content == "What is this video about?"
        assert message.model is None
        assert message.interaction_id is None
        assert message.created_at is not None
    
    def test_create_assistant_message(self, session, ready_session):
        """Test assistant message can be persisted."""
        service = ConversationService(session)
        
        message = service.create_assistant_message(
            session_id=ready_session.id,
            content="The video explains HTTP requests.",
            model="gemini-3.8-flash",
            interaction_id="interaction-123",
        )
        
        assert message.id is not None
        assert message.session_id == ready_session.id
        assert message.role == "assistant"
        assert message.content == "The video explains HTTP requests."
        assert message.model == "gemini-3.8-flash"
        assert message.interaction_id == "interaction-123"
        assert message.created_at is not None
    
    def test_message_history_chronological_order(self, session, ready_session):
        """Test message history is returned in chronological order."""
        service = ConversationService(session)
        
        msg1 = service.create_user_message(ready_session.id, "First question")
        msg2 = service.create_assistant_message(ready_session.id, "First answer", "gemini-3.8-flash")
        msg3 = service.create_user_message(ready_session.id, "Second question")
        
        history = service.get_message_history(ready_session.id)
        
        assert len(history) == 3
        assert history[0].id == msg1.id
        assert history[1].id == msg2.id
        assert history[2].id == msg3.id
    
    def test_interaction_id_preserved(self, session, ready_session):
        """Test interaction ID is preserved on persisted messages."""
        service = ConversationService(session)
        
        msg = service.create_assistant_message(
            session_id=ready_session.id,
            content="Answer",
            model="gemini-3.8-flash",
            interaction_id="interaction-abc-123",
        )
        
        retrieved = session.get(Message, msg.id)
        assert retrieved.interaction_id == "interaction-abc-123"
    
    def test_update_session_conversation_state(self, session, ready_session):
        """Test session conversation state can be updated."""
        service = ConversationService(session)
        
        updated = service.update_session_conversation_state(
            session=ready_session,
            model="gemini-3.8-flash",
            interaction_id="interaction-new-456",
        )
        
        assert updated.active_model == "gemini-3.8-flash"
        assert updated.previous_interaction_id == "interaction-new-456"
    
    def test_update_session_conversation_state_without_interaction_id(self, session, ready_session):
        """Test state update without an interaction ID clears the stale ID.

        Phase 5 approved decision: a successful response without an interaction
        ID must not retain an interaction ID from a previous model.
        """
        service = ConversationService(session)
        ready_session.previous_interaction_id = "old-id"
        
        updated = service.update_session_conversation_state(
            session=ready_session,
            model="gemini-3.7-flash",
            interaction_id=None,
        )
        
        assert updated.active_model == "gemini-3.7-flash"
        assert updated.previous_interaction_id is None
    
    def test_validate_session_ready(self, session, ready_session):
        """Test session validation for READY status."""
        service = ConversationService(session)
        
        assert service.validate_session_ready(ready_session) is True
    
    def test_validate_session_not_ready(self, session):
        """Test session validation rejects non-READY status."""
        video_session = VideoSession(
            source_type="youtube",
            source_url="https://www.youtube.com/watch?v=test",
            status=SessionStatus.UPLOADING,
        )
        session.add(video_session)
        session.commit()
        session.refresh(video_session)
        
        service = ConversationService(session)
        
        assert service.validate_session_ready(video_session) is False
    
    def test_get_session(self, session, ready_session):
        """Test get session returns correct session."""
        service = ConversationService(session)
        
        retrieved = service.get_session(ready_session.id)
        
        assert retrieved is not None
        assert retrieved.id == ready_session.id
    
    def test_get_session_not_found(self, session):
        """Test get session returns None for non-existent session."""
        service = ConversationService(session)
        
        retrieved = service.get_session("non-existent-id")
        
        assert retrieved is None
    
    def test_save_gemini_response(self, session, ready_session):
        """Test save Gemini response creates both messages."""
        service = ConversationService(session)
        
        gemini_answer = GeminiAnswer(
            text="The video explains HTTP requests.",
            interaction_id="interaction-xyz",
            model="gemini-3.8-flash",
        )
        
        user_msg, assistant_msg = service.save_gemini_response(
            session_id=ready_session.id,
            user_content="What is this video about?",
            gemini_answer=gemini_answer,
        )
        
        assert user_msg.role == "user"
        assert user_msg.content == "What is this video about?"
        assert assistant_msg.role == "assistant"
        assert assistant_msg.content == "The video explains HTTP requests."
        assert assistant_msg.interaction_id == "interaction-xyz"
        
        history = service.get_message_history(ready_session.id)
        assert len(history) == 2


class TestConversationServiceAsk:
    """Test ConversationService.ask() method for Gemini question flow."""
    
    def test_ask_first_question_success(self, session, ready_session):
        """Test first question in a READY session succeeds."""
        mock_gemini = MagicMock()
        mock_gemini_answer = GeminiAnswer(
            text="The video explains HTTP requests.",
            interaction_id="interaction-abc-123",
            model="gemini-3.8-flash",
        )
        mock_gemini.create_interaction.return_value = mock_gemini_answer
        
        service = ConversationService(session, gemini_service=mock_gemini)
        
        result = service.ask(
            session_id=ready_session.id,
            question="What is this video about?",
        )
        
        assert result.text == "The video explains HTTP requests."
        assert result.interaction_id == "interaction-abc-123"
        assert result.model == "gemini-3.8-flash"
    
    def test_ask_first_question_calls_gemini_with_video_uri(self, session, ready_session):
        """Test first question sends video context to Gemini."""
        mock_gemini = MagicMock()
        mock_gemini_answer = GeminiAnswer(
            text="Answer",
            interaction_id="interaction-123",
            model="gemini-3.8-flash",
        )
        mock_gemini.create_interaction.return_value = mock_gemini_answer
        
        ready_session.gemini_file_uri = "gs://test-bucket/test-video.mp4"
        session.add(ready_session)
        session.commit()
        
        service = ConversationService(session, gemini_service=mock_gemini)
        
        service.ask(
            session_id=ready_session.id,
            question="What is this video about?",
        )
        
        mock_gemini.create_interaction.assert_called_once()
        call_kwargs = mock_gemini.create_interaction.call_args[1]
        assert call_kwargs["video_uri"] == "gs://test-bucket/test-video.mp4"
        assert call_kwargs["question"] == "What is this video about?"
        assert call_kwargs["previous_interaction_id"] is None
    
    def test_ask_first_question_uses_youtube_url_when_no_file_uri(self, session):
        """Test first question uses YouTube URL when no gemini_file_uri."""
        youtube_session = VideoSession(
            source_type="youtube",
            source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            status=SessionStatus.READY,
        )
        session.add(youtube_session)
        session.commit()
        session.refresh(youtube_session)
        
        mock_gemini = MagicMock()
        mock_gemini_answer = GeminiAnswer(
            text="Answer",
            interaction_id="interaction-yt-123",
            model="gemini-3.8-flash",
        )
        mock_gemini.create_interaction.return_value = mock_gemini_answer
        
        service = ConversationService(session, gemini_service=mock_gemini)
        
        service.ask(
            session_id=youtube_session.id,
            question="What is this video about?",
        )
        
        call_kwargs = mock_gemini.create_interaction.call_args[1]
        assert call_kwargs["video_uri"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    def test_ask_first_question_persists_messages(self, session, ready_session):
        """Test first question persists user and assistant messages."""
        mock_gemini = MagicMock()
        mock_gemini_answer = GeminiAnswer(
            text="The video explains HTTP requests.",
            interaction_id="interaction-abc-123",
            model="gemini-3.8-flash",
        )
        mock_gemini.create_interaction.return_value = mock_gemini_answer
        
        service = ConversationService(session, gemini_service=mock_gemini)
        
        service.ask(
            session_id=ready_session.id,
            question="What is this video about?",
        )
        
        history = service.get_message_history(ready_session.id)
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[0].content == "What is this video about?"
        assert history[1].role == "assistant"
        assert history[1].content == "The video explains HTTP requests."
        assert history[1].interaction_id == "interaction-abc-123"
    
    def test_ask_first_question_updates_session_state(self, session, ready_session):
        """Test first question updates session's previous_interaction_id and active_model."""
        mock_gemini = MagicMock()
        mock_gemini_answer = GeminiAnswer(
            text="Answer",
            interaction_id="interaction-new-456",
            model="gemini-3.8-flash",
        )
        mock_gemini.create_interaction.return_value = mock_gemini_answer
        
        service = ConversationService(session, gemini_service=mock_gemini)
        
        service.ask(
            session_id=ready_session.id,
            question="What is this video about?",
        )
        
        updated_session = session.get(VideoSession, ready_session.id)
        assert updated_session.previous_interaction_id == "interaction-new-456"
        assert updated_session.active_model == "gemini-3.8-flash"
    
    def test_ask_follow_up_uses_previous_interaction_id(self, session, ready_session):
        """Test follow-up question uses previous_interaction_id."""
        mock_gemini = MagicMock()
        mock_gemini_answer = GeminiAnswer(
            text="Follow-up answer",
            interaction_id="interaction-followup-789",
            model="gemini-3.8-flash",
        )
        mock_gemini.create_interaction.return_value = mock_gemini_answer
        
        ready_session.active_model = "gemini-3.8-flash"
        ready_session.previous_interaction_id = "interaction-first-123"
        session.add(ready_session)
        session.commit()
        
        service = ConversationService(session, gemini_service=mock_gemini)
        
        service.ask(
            session_id=ready_session.id,
            question="What happens after that?",
        )
        
        call_kwargs = mock_gemini.create_interaction.call_args[1]
        assert call_kwargs["previous_interaction_id"] == "interaction-first-123"
    
    def test_ask_follow_up_updates_interaction_id(self, session, ready_session):
        """Test follow-up question updates session's previous_interaction_id."""
        mock_gemini = MagicMock()
        mock_gemini_answer = GeminiAnswer(
            text="Follow-up answer",
            interaction_id="interaction-followup-789",
            model="gemini-3.8-flash",
        )
        mock_gemini.create_interaction.return_value = mock_gemini_answer
        
        ready_session.active_model = "gemini-3.8-flash"
        ready_session.previous_interaction_id = "interaction-first-123"
        session.add(ready_session)
        session.commit()
        
        service = ConversationService(session, gemini_service=mock_gemini)
        
        service.ask(
            session_id=ready_session.id,
            question="What happens after that?",
        )
        
        updated_session = session.get(VideoSession, ready_session.id)
        assert updated_session.previous_interaction_id == "interaction-followup-789"
    
    def test_ask_non_ready_session_raises_error(self, session):
        """Test ask() raises error for non-READY session."""
        uploading_session = VideoSession(
            source_type="youtube",
            source_url="https://www.youtube.com/watch?v=test",
            status=SessionStatus.UPLOADING,
        )
        session.add(uploading_session)
        session.commit()
        session.refresh(uploading_session)
        
        mock_gemini = MagicMock()
        service = ConversationService(session, gemini_service=mock_gemini)
        
        with pytest.raises(ValueError, match="not ready"):
            service.ask(
                session_id=uploading_session.id,
                question="What is this video about?",
            )
        
        mock_gemini.create_interaction.assert_not_called()
    
    def test_ask_session_not_found_raises_error(self, session):
        """Test ask() raises error for non-existent session."""
        mock_gemini = MagicMock()
        service = ConversationService(session, gemini_service=mock_gemini)
        
        with pytest.raises(ValueError, match="not found"):
            service.ask(
                session_id="non-existent-id",
                question="What is this video about?",
            )
        
        mock_gemini.create_interaction.assert_not_called()
    
    def test_ask_gemini_error_propagates(self, session, ready_session):
        """Test Gemini error is propagated correctly."""
        from app.services.gemini_service import GeminiError, GeminiErrorCategory
        
        mock_gemini = MagicMock()
        mock_gemini.create_interaction.side_effect = GeminiError(
            category=GeminiErrorCategory.RATE_LIMITED,
            message="Rate limit exceeded",
            retryable=True,
        )
        
        service = ConversationService(session, gemini_service=mock_gemini)
        
        with pytest.raises(GeminiError) as exc_info:
            service.ask(
                session_id=ready_session.id,
                question="What is this video about?",
            )
        
        assert exc_info.value.category == GeminiErrorCategory.RATE_LIMITED
    
    def test_ask_gemini_error_no_assistant_message_persisted(self, session, ready_session):
        """Test Gemini error does not persist assistant message."""
        from app.services.gemini_service import GeminiError, GeminiErrorCategory
        
        mock_gemini = MagicMock()
        mock_gemini.create_interaction.side_effect = GeminiError(
            category=GeminiErrorCategory.CONTENT_BLOCKED,
            message="Content blocked",
            retryable=False,
        )
        
        service = ConversationService(session, gemini_service=mock_gemini)
        
        with pytest.raises(GeminiError):
            service.ask(
                session_id=ready_session.id,
                question="What is this video about?",
            )
        
        history = service.get_message_history(ready_session.id)
        assert len(history) == 0
