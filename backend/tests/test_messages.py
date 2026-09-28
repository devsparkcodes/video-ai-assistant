"""Tests for messages API endpoint."""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.db.session import get_session
from app.models import VideoSession, Message, SessionStatus


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


class TestMessagesEndpointSuccess:
    """Test successful message retrieval scenarios."""

    def test_get_messages_with_history(self, client, ready_session, session):
        """Test retrieving messages for a session with history."""
        msg1 = Message(
            session_id=ready_session.id,
            role="user",
            content="What happens first?",
            created_at=datetime(2026, 9, 8, 12, 1, 0, tzinfo=timezone.utc),
        )
        msg2 = Message(
            session_id=ready_session.id,
            role="assistant",
            content="First, the video shows...",
            model="gemini-3.8-flash",
            interaction_id="interaction-123",
            created_at=datetime(2026, 9, 8, 12, 1, 4, tzinfo=timezone.utc),
        )
        session.add_all([msg1, msg2])
        session.commit()
        session.refresh(msg1)
        session.refresh(msg2)

        response = client.get(f"/api/v1/sessions/{ready_session.id}/messages")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == ready_session.id
        assert len(data["messages"]) == 2

        m1 = data["messages"][0]
        assert m1["id"] == msg1.id
        assert m1["session_id"] == ready_session.id
        assert m1["role"] == "user"
        assert m1["content"] == "What happens first?"
        assert m1["model"] is None
        assert m1["interaction_id"] is None
        assert "created_at" in m1

        m2 = data["messages"][1]
        assert m2["id"] == msg2.id
        assert m2["session_id"] == ready_session.id
        assert m2["role"] == "assistant"
        assert m2["content"] == "First, the video shows..."
        assert m2["model"] == "gemini-3.8-flash"
        assert m2["interaction_id"] == "interaction-123"
        assert "created_at" in m2

    def test_get_messages_returns_chronological_order(self, client, ready_session, session):
        """Test messages are returned in chronological order."""
        msg_earlier = Message(
            session_id=ready_session.id,
            role="user",
            content="First question",
            created_at=datetime(2026, 9, 8, 12, 1, 0, tzinfo=timezone.utc),
        )
        msg_middle = Message(
            session_id=ready_session.id,
            role="assistant",
            content="First answer",
            model="gemini-3.8-flash",
            created_at=datetime(2026, 9, 8, 12, 1, 2, tzinfo=timezone.utc),
        )
        msg_later = Message(
            session_id=ready_session.id,
            role="user",
            content="Second question",
            created_at=datetime(2026, 9, 8, 12, 2, 0, tzinfo=timezone.utc),
        )
        session.add_all([msg_later, msg_earlier, msg_middle])
        session.commit()

        response = client.get(f"/api/v1/sessions/{ready_session.id}/messages")

        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 3
        assert data["messages"][0]["content"] == "First question"
        assert data["messages"][1]["content"] == "First answer"
        assert data["messages"][2]["content"] == "Second question"

    def test_get_messages_preserves_roles(self, client, ready_session, session):
        """Test message roles are preserved as stored."""
        msg_user = Message(
            session_id=ready_session.id,
            role="user",
            content="User message",
        )
        msg_assistant = Message(
            session_id=ready_session.id,
            role="assistant",
            content="Assistant message",
            model="gemini-3.8-flash",
        )
        session.add_all([msg_user, msg_assistant])
        session.commit()

        response = client.get(f"/api/v1/sessions/{ready_session.id}/messages")

        assert response.status_code == 200
        data = response.json()
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][1]["role"] == "assistant"

    def test_get_messages_preserves_model_and_interaction_id(self, client, ready_session, session):
        """Test model and interaction_id fields are preserved when available."""
        msg = Message(
            session_id=ready_session.id,
            role="assistant",
            content="Answer with metadata",
            model="gemini-3.8-flash",
            interaction_id="interaction-abc-456",
        )
        session.add(msg)
        session.commit()

        response = client.get(f"/api/v1/sessions/{ready_session.id}/messages")

        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 1
        assert data["messages"][0]["model"] == "gemini-3.8-flash"
        assert data["messages"][0]["interaction_id"] == "interaction-abc-456"

    def test_get_messages_preserves_ids(self, client, ready_session, session):
        """Test message IDs and session_id are preserved."""
        msg = Message(
            session_id=ready_session.id,
            role="user",
            content="Test",
        )
        session.add(msg)
        session.commit()
        session.refresh(msg)

        response = client.get(f"/api/v1/sessions/{ready_session.id}/messages")

        assert response.status_code == 200
        data = response.json()
        assert data["messages"][0]["id"] == msg.id
        assert data["messages"][0]["session_id"] == ready_session.id


class TestMessagesEndpointEmptyHistory:
    """Test empty history scenarios."""

    def test_get_messages_empty_history(self, client, ready_session):
        """Test valid session with no messages returns empty list."""
        response = client.get(f"/api/v1/sessions/{ready_session.id}/messages")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == ready_session.id
        assert data["messages"] == []


class TestMessagesEndpointErrors:
    """Test error scenarios."""

    def test_nonexistent_session_returns_404(self, client):
        """Test nonexistent session returns 404 with standardized error."""
        response = client.get("/api/v1/sessions/nonexistent-id/messages")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "SESSION_NOT_FOUND"
        assert data["detail"]["error"]["retryable"] is False

    def test_nonexistent_session_error_message(self, client):
        """Test nonexistent session returns correct error message."""
        response = client.get("/api/v1/sessions/fake-session-id/messages")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"]["error"]["message"].lower()
