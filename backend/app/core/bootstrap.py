"""Bootstrap logic for initial setup."""
import logging
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.auth import get_password_hash
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


def bootstrap_admin_user() -> bool:
    """
    Create initial admin user if no users exist.
    
    Returns:
        True if admin user was created, False if it already exists or creation failed.
    """
    db: Session = SessionLocal()
    try:
        # Check if any users exist
        existing_user = db.query(User).first()
        if existing_user:
            logger.info("Users already exist, skipping admin user creation")
            return False
        
        # Create admin user
        admin_user = User(
            username="admin",
            password_hash=get_password_hash("admin"),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin_user)
        db.commit()
        logger.info("Created initial admin user (username: admin, password: admin)")
        return True
    except Exception as e:
        logger.error(f"Error creating admin user: {e}")
        db.rollback()
        return False
    finally:
        db.close()
