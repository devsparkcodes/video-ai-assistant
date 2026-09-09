import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.db.session import get_session
from app.models import VideoSession, Message


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


def test_health_endpoint(client):
    """Test health check endpoint returns ok."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_application_startup():
    """Test application can be created."""
    from app.main import app
    assert app is not None
    assert app.title == "Video AI Assistant"


def test_video_session_model():
    """Test VideoSession model can be created."""
    session = VideoSession(
        source_type="upload",
        original_filename="test.mp4",
        mime_type="video/mp4",
        size_bytes=1024,
        status="pending"
    )
    assert session.source_type == "upload"
    assert session.status == "pending"
    assert session.id is not None
    assert session.created_at is not None


def test_message_model():
    """Test Message model can be created."""
    session = VideoSession(source_type="upload", status="ready")
    message = Message(
        session_id=session.id,
        role="user",
        content="What is this video about?"
    )
    assert message.role == "user"
    assert message.content == "What is this video about?"
    assert message.session_id == session.id
    assert message.id is not None
    assert message.created_at is not None


def test_database_operations(session):
    """Test basic database operations."""
    # Create session
    db_session = VideoSession(
        source_type="youtube",
        source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        status="ready"
    )
    session.add(db_session)
    session.commit()
    session.refresh(db_session)
    
    # Create message
    message = Message(
        session_id=db_session.id,
        role="assistant",
        content="This is a music video."
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    
    # Verify
    assert db_session.id is not None
    assert message.id is not None
    assert message.session_id == db_session.id
    
    # Query
    from sqlmodel import select
    statement = select(VideoSession).where(VideoSession.id == db_session.id)
    result = session.exec(statement).first()
    assert result is not None
    assert result.source_type == "youtube"
