from sqlmodel import SQLModel, create_engine
from app.core.config import settings


def create_db_engine():
    """Create database engine."""
    connect_args = {}
    if settings.DATABASE_URL.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args=connect_args,
        echo=False
    )
    return engine


engine = create_db_engine()


def create_db_and_tables():
    """Create database tables."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Dependency for database sessions."""
    from sqlmodel import Session
    
    with Session(engine) as session:
        yield session
