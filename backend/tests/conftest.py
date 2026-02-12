"""Pytest configuration and fixtures."""
import pytest
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base, get_db
from app.models.user import User, UserRole

# Import all models to ensure they're registered with Base.metadata
# This is necessary for Base.metadata.create_all() to create all tables
from app.models import Conversation, Message, Session, ChatContext, Datasource, View  # noqa: F401

# We'll create a unique database file per test to avoid conflicts
# Store the engine and sessionmaker as None initially - will be created per test
test_engine = None
TestSessionLocal = None


@pytest.fixture(scope="function")
def db_session():
    """Create a test database session with a unique database file."""
    # Create a unique temporary file for this test
    test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    test_db_path = test_db_file.name
    test_db_file.close()
    
    # Ensure file has write permissions
    os.chmod(test_db_path, 0o666)
    
    # Create engine and sessionmaker for this test
    engine = create_engine(
        f"sqlite:///{test_db_path}",
        connect_args={"check_same_thread": False}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables in the test database
    Base.metadata.create_all(bind=engine)
    
    # Create session
    session = SessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        # Clean up: drop tables and delete file
        try:
            Base.metadata.drop_all(bind=engine)
            engine.dispose()
        except Exception:
            pass  # Ignore errors during cleanup
        finally:
            # Delete the database file
            if os.path.exists(test_db_path):
                try:
                    os.unlink(test_db_path)
                except OSError:
                    pass  # Ignore if file is locked


@pytest.fixture(scope="function")
def test_user(db_session):
    """Create a test user for auth bypass in integration tests."""
    user = User(username="testuser", role=UserRole.USER, is_active=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def client(db_session, test_user):
    """Create a test client with database session override."""
    # Import models BEFORE importing app to ensure they're registered
    # This is critical for Base.metadata.create_all() to work
    from app.models import Conversation, Message, Session, ChatContext, Datasource, View  # noqa: F401
    
    # Tables should already exist from db_session fixture
    # The db_session fixture creates them, so we don't need to create again
    
    from app.main import app
    from fastapi.testclient import TestClient
    from app.core.database import get_db
    from app.api.auth import get_current_user

    def override_get_current_user():
        return test_user

    # Override get_db dependency to reuse the same test session
    # This ensures all API operations use the same database and see each other's commits
    def override_get_db():
        # Reuse the same session from db_session fixture
        # This ensures all operations (API and test queries) see the same data
        try:
            yield db_session
        finally:
            # Don't close the session here - it's managed by db_session fixture
            # Just ensure any pending operations are flushed
            db_session.flush()
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    test_client = TestClient(app)
    
    try:
        yield test_client
    finally:
        # Clean up override
        app.dependency_overrides.clear()
