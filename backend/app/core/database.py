"""Database configuration and session management."""
import time
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, DisconnectionError
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool
from app.core.config import settings

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds


def create_engine_with_retry():
    """Create database engine with retry logic for connection failures."""
    retries = 0
    while retries < MAX_RETRIES:
        try:
            engine = create_engine(
                settings.DATABASE_URL,
                pool_pre_ping=True,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                poolclass=QueuePool,
            )
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except (OperationalError, DisconnectionError) as e:
            retries += 1
            if retries >= MAX_RETRIES:
                raise ConnectionError(
                    f"Failed to connect to database after {MAX_RETRIES} retries: {e}"
                )
            time.sleep(RETRY_DELAY * retries)  # Exponential backoff
    raise ConnectionError("Failed to create database engine")


# Create database engine with retry logic
engine = create_engine_with_retry()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_health() -> bool:
    """Check database connection health."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def safe_commit(db: Session) -> None:
    """
    Safely commit a database transaction with rollback on error.
    
    Args:
        db: SQLAlchemy session
        
    Raises:
        Exception: Re-raises the original exception after rollback
    """
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise
