#!/usr/bin/env python3
"""Script to create admin user manually."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.auth import get_password_hash
from app.models.user import User, UserRole

def create_admin_user(force_reset=False):
    """Create admin user."""
    db: Session = SessionLocal()
    try:
        # Check if admin user already exists
        admin_user = db.query(User).filter(User.username == "admin").first()
        if admin_user:
            if force_reset:
                print("Admin user exists, resetting password...")
                admin_user.password_hash = get_password_hash("admin")
                db.commit()
                print("Admin user password reset successfully!")
                print("Username: admin")
                print("Password: admin")
            else:
                print("Admin user already exists!")
                print("To reset password, run with --reset flag")
            return
        
        # Create admin user
        admin_user = User(
            username="admin",
            password_hash=get_password_hash("admin"),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin_user)
        db.commit()
        print("Admin user created successfully!")
        print("Username: admin")
        print("Password: admin")
    except Exception as e:
        print(f"Error creating admin user: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    force_reset = "--reset" in sys.argv or "-r" in sys.argv
    create_admin_user(force_reset=force_reset)

if __name__ == "__main__":
    create_admin_user()
