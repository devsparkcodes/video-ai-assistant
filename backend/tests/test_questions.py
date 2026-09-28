"""Tests for questions API endpoint."""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.db.session import get_session
from app.models import VideoSession, SessionStatus
from app.services.gemini_service import GeminiAnswer, GeminiError, GeminiErrorCategory
from app.api.v1.endpoints.questions import get_gemini_service


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


@pytest.fixture(name="client")
def client_fixture(engine, session):
    """Create test client with test database."""
    def get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


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


@pytest.fixture(name="uploading_session")
def uploading_session_fixture(session):
    """Create an uploading video session for testing."""
    video_session = VideoSession(
        source_type="youtube",
        source_url="https://www.youtube.com/watch?v=test",
        status=SessionStatus.UPLOADING,
    )
    session.add(video_session)
    session.commit()
    session.refresh(video_session)
    return video_session


class TestQuestionEndpointSuccess:
    """Test successful question scenarios."""

    def test_ask_first_question_success(self, client, ready_session, session):
        """Test first question in a READY session succeeds."""
        mock_gemini = MagicMock()
        mock_gemini_answer = GeminiAnswer(
            text="The video explains HTTP requests.",
            interaction_id="interaction-abc-123",
            model="gemini-3.8-flash",
        )
        mock_gemini.create_interaction.return_value = mock_gemini_answer

        def get_gemini_service_override():
            return mock_gemini

        app.dependency_overrides[get_gemini_service] = get_gemini_service_override

        response = client.post(
            f"/api/v1/sessions/{ready_session.id}/questions",
            json={"question": "What is this video about?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "The video explains HTTP requests."
        assert data["model"] == "gemini-3.8-flash"
        assert data["message_id"] == "interaction-abc-123"
        assert "timestamps" in data
        assert "created_at" in data

    def test_ask_first_question_calls_gemini_with_correct_params(self, client, ready_session, session):
        """Test first question sends correct parameters to Gemini."""
        mock_gemini = MagicMock()
        mock_gemini_answer = GeminiAnswer(
            text="Answer",
            interaction_id="interaction-123",
            model="gemini-3.8-flash",
        )
        mock_gemini.create_interaction.return_value = mock_gemini_answer

        def get_gemini_service_override():
            return mock_gemini

        app.dependency_overrides[get_gemini_service] = get_gemini_service_override

        response = client.post(
            f"/api/v1/sessions/{ready_session.id}/questions",
            json={"question": "What is this video about?"},
        )

        assert response.status_code == 200
        mock_gemini.create_interaction.assert_called_once()
        call_kwargs = mock_gemini.create_interaction.call_args[1]
        assert call_kwargs["question"] == "What is this video about?"
        assert call_kwargs["video_uri"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert call_kwargs["previous_interaction_id"] is None

    def test_ask_follow_up_uses_previous_interaction_id(self, client, ready_session, session):
        """Test follow-up question uses previous_interaction_id."""
        mock_gemini = MagicMock()
        mock_gemini_answer = GeminiAnswer(
            text="Follow-up answer",
            interaction_id="interaction-followup-789",
            model="gemini-3.8-flash",
        )
        mock_gemini.create_interaction.return_value = mock_gemini_answer

        ready_session.previous_interaction_id = "interaction-first-123"
        session.add(ready_session)
        session.commit()

        def get_gemini_service_override():
            return mock_gemini

        app.dependency_overrides[get_gemini_service] = get_gemini_service_override

        response = client.post(
            f"/api/v1/sessions/{ready_session.id}/questions",
            json={"question": "What happens after that?"},
        )

        assert response.status_code == 200
        call_kwargs = mock_gemini.create_interaction.call_args[1]
        assert call_kwargs["previous_interaction_id"] == "interaction-first-123"


class TestQuestionEndpointValidation:
    """Test request validation."""

    def test_empty_question_rejected(self, client, ready_session):
        """Test empty question is rejected."""
        response = client.post(
            f"/api/v1/sessions/{ready_session.id}/questions",
            json={"question": ""},
        )

        assert response.status_code == 422

    def test_question_over_max_length_rejected(self, client, ready_session):
        """Test question over 4000 characters is rejected."""
        long_question = "x" * 4001
        response = client.post(
            f"/api/v1/sessions/{ready_session.id}/questions",
            json={"question": long_question},
        )

        assert response.status_code == 422

    def test_missing_question_field_rejected(self, client, ready_session):
        """Test request without question field is rejected."""
        response = client.post(
            f"/api/v1/sessions/{ready_session.id}/questions",
            json={},
        )

        assert response.status_code == 422


class TestQuestionEndpointSessionErrors:
    """Test session-related error scenarios."""

    def test_nonexistent_session_returns_404(self, client):
        """Test nonexistent session returns 404."""
        response = client.post(
            "/api/v1/sessions/nonexistent-id/questions",
            json={"question": "What is this video about?"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "SESSION_NOT_FOUND"

    def test_non_ready_session_returns_409(self, client, uploading_session):
        """Test non-READY session returns 409."""
        response = client.post(
            f"/api/v1/sessions/{uploading_session.id}/questions",
            json={"question": "What is this video about?"},
        )

        assert response.status_code == 409
        data = response.json()
        assert data["detail"]["error"]["code"] == "SESSION_NOT_READY"


class TestQuestionEndpointGeminiErrors:
    """Test Gemini error scenarios."""

    def test_gemini_auth_error_returns_502(self, client, ready_session):
        """Test Gemini authentication error returns 502."""
        mock_gemini = MagicMock()
        mock_gemini.create_interaction.side_effect = GeminiError(
            category=GeminiErrorCategory.AUTHENTICATION,
            message="Authentication failed",
            retryable=False,
        )

        def get_gemini_service_override():
            return mock_gemini

        app.dependency_overrides[get_gemini_service] = get_gemini_service_override

        response = client.post(
            f"/api/v1/sessions/{ready_session.id}/questions",
            json={"question": "What is this video about?"},
        )

        assert response.status_code == 502
        data = response.json()
        assert data["detail"]["error"]["code"] == "GEMINI_AUTH_ERROR"
        assert data["detail"]["error"]["retryable"] is False

    def test_gemini_rate_limit_returns_429(self, client, ready_session):
        """Test Gemini rate limit error returns 429."""
        mock_gemini = MagicMock()
        mock_gemini.create_interaction.side_effect = GeminiError(
            category=GeminiErrorCategory.RATE_LIMITED,
            message="Rate limit exceeded",
            retryable=True,
        )

        def get_gemini_service_override():
            return mock_gemini

        app.dependency_overrides[get_gemini_service] = get_gemini_service_override

        response = client.post(
            f"/api/v1/sessions/{ready_session.id}/questions",
            json={"question": "What is this video about?"},
        )

        assert response.status_code == 429
        data = response.json()
        assert data["detail"]["error"]["code"] == "GEMINI_RATE_LIMITED"
        assert data["detail"]["error"]["retryable"] is True

    def test_gemini_safety_rejected_returns_502(self, client, ready_session):
        """Test Gemini content blocked error returns 502."""
        mock_gemini = MagicMock()
        mock_gemini.create_interaction.side_effect = GeminiError(
            category=GeminiErrorCategory.CONTENT_BLOCKED,
            message="Content blocked",
            retryable=False,
        )

        def get_gemini_service_override():
            return mock_gemini

        app.dependency_overrides[get_gemini_service] = get_gemini_service_override

        response = client.post(
            f"/api/v1/sessions/{ready_session.id}/questions",
            json={"question": "What is this video about?"},
        )

        assert response.status_code == 502
        data = response.json()
        assert data["detail"]["error"]["code"] == "GEMINI_SAFETY_REJECTED"
        assert data["detail"]["error"]["retryable"] is False

    def test_gemini_unavailable_returns_502(self, client, ready_session):
        """Test Gemini unavailable error returns 502."""
        mock_gemini = MagicMock()
        mock_gemini.create_interaction.side_effect = GeminiError(
            category=GeminiErrorCategory.NETWORK_ERROR,
            message="Service unavailable",
            retryable=True,
        )

        def get_gemini_service_override():
            return mock_gemini

        app.dependency_overrides[get_gemini_service] = get_gemini_service_override

        response = client.post(
            f"/api/v1/sessions/{ready_session.id}/questions",
            json={"question": "What is this video about?"},
        )

        assert response.status_code == 502
        data = response.json()
        assert data["detail"]["error"]["code"] == "GEMINI_UNAVAILABLE"
        assert data["detail"]["error"]["retryable"] is True
