"""Tests for video session endpoints."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.db.session import get_session
from app.models import VideoSession
from app.services.gemini_service import GeminiService, GeminiError, GeminiErrorCategory
from app.services.video_session import VideoSessionService


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
def client_fixture(engine):
    """Create test client with test database."""
    def get_session_override():
        with Session(engine) as session:
            yield session
    
    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestVideoValidation:
    """Test video validation utilities."""
    
    def test_validate_video_file_valid(self):
        """Test valid video file validation."""
        from app.services.video_validation import validate_video_file
        
        is_valid, error = validate_video_file(
            filename="test.mp4",
            content_type="video/mp4",
            file_size=1024 * 1024,  # 1MB
        )
        assert is_valid is True
        assert error is None
    
    def test_validate_video_file_empty(self):
        """Test empty file validation."""
        from app.services.video_validation import validate_video_file
        
        is_valid, error = validate_video_file(
            filename="test.mp4",
            content_type="video/mp4",
            file_size=0,
        )
        assert is_valid is False
        assert "empty" in error.lower()
    
    def test_validate_video_file_too_large(self):
        """Test file too large validation."""
        from app.services.video_validation import validate_video_file
        
        is_valid, error = validate_video_file(
            filename="test.mp4",
            content_type="video/mp4",
            file_size=1024 * 1024 * 1024 * 1024,  # 1TB
        )
        assert is_valid is False
        assert "too large" in error.lower()
    
    def test_validate_video_file_unsupported_format(self):
        """Test unsupported format validation."""
        from app.services.video_validation import validate_video_file
        
        is_valid, error = validate_video_file(
            filename="test.txt",
            content_type="text/plain",
            file_size=1024,
        )
        assert is_valid is False
        assert "unsupported" in error.lower()
    
    def test_validate_youtube_url_valid(self):
        """Test valid YouTube URL validation."""
        from app.services.video_validation import validate_youtube_url
        
        urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
        ]
        
        for url in urls:
            is_valid, error = validate_youtube_url(url)
            assert is_valid is True, f"URL should be valid: {url}"
            assert error is None
    
    def test_validate_youtube_url_invalid(self):
        """Test invalid YouTube URL validation."""
        from app.services.video_validation import validate_youtube_url
        
        urls = [
            "https://www.google.com",
            "https://vimeo.com/123456",
            "not-a-url",
            "",
        ]
        
        for url in urls:
            is_valid, error = validate_youtube_url(url)
            assert is_valid is False, f"URL should be invalid: {url}"
            assert error is not None


class TestSessionSchemas:
    """Test session schemas."""
    
    def test_session_create_response(self):
        """Test session creation response schema."""
        from app.schemas.session import SessionCreateResponse
        
        response = SessionCreateResponse(
            session_id="test-id",
            status="READY",
            source_type="upload",
        )
        assert response.session_id == "test-id"
        assert response.status == "READY"
        assert response.source_type == "upload"
    
    def test_youtube_session_create(self):
        """Test YouTube session creation schema."""
        from app.schemas.session import YouTubeSessionCreate
        
        request = YouTubeSessionCreate(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        assert request.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    def test_session_response(self):
        """Test session response schema."""
        from app.schemas.session import SessionResponse
        
        response = SessionResponse(
            session_id="test-id",
            status="READY",
            source_type="upload",
            active_model="gemini-3.8-flash",
            created_at="2026-09-09T12:00:00Z",
        )
        assert response.session_id == "test-id"
        assert response.active_model == "gemini-3.8-flash"
    
    def test_session_delete_response(self):
        """Test session deletion response schema."""
        from app.schemas.session import SessionDeleteResponse
        
        response = SessionDeleteResponse(deleted=True)
        assert response.deleted is True


class TestVideoSessionEndpoints:
    """Test video session endpoints."""
    
    def test_create_youtube_session_success(self, client):
        """Test successful YouTube session creation."""
        response = client.post(
            "/api/v1/sessions/url",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "READY"
        assert data["source_type"] == "youtube"
    
    def test_create_youtube_session_invalid_url(self, client):
        """Test YouTube session creation with invalid URL."""
        response = client.post(
            "/api/v1/sessions/url",
            json={"url": "https://www.google.com"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INVALID_YOUTUBE_URL"
    
    def test_get_session_success(self, client):
        """Test successful session retrieval."""
        # First create a session
        create_response = client.post(
            "/api/v1/sessions/url",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        assert create_response.status_code == 201
        session_id = create_response.json()["session_id"]
        
        # Then retrieve it
        response = client.get(f"/api/v1/sessions/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["source_type"] == "youtube"
    
    def test_get_session_not_found(self, client):
        """Test session retrieval with non-existent session."""
        response = client.get("/api/v1/sessions/non-existent-id")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "SESSION_NOT_FOUND"
    
    def test_delete_session_success(self, client):
        """Test successful session deletion."""
        # First create a session
        create_response = client.post(
            "/api/v1/sessions/url",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        assert create_response.status_code == 201
        session_id = create_response.json()["session_id"]
        
        # Then delete it
        response = client.delete(f"/api/v1/sessions/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        
        # Verify it's deleted
        get_response = client.get(f"/api/v1/sessions/{session_id}")
        assert get_response.status_code == 404
    
    def test_delete_session_not_found(self, client):
        """Test session deletion with non-existent session."""
        response = client.delete("/api/v1/sessions/non-existent-id")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "SESSION_NOT_FOUND"