"""Tests for database connection."""
from sqlalchemy import text
from app.core.database import engine, get_db


def test_database_connection():
    """Test database connection."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


def test_session_creation():
    """Test database session creation."""
    db = next(get_db())
    assert db is not None
    db.close()
