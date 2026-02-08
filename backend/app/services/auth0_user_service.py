"""Auth0 user mapping service."""
import logging
from sqlalchemy.orm import Session
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


def get_or_create_user_from_auth0(db: Session, auth0_claims: dict) -> User:
    """
    Get or create a user from Auth0 claims.
    
    Args:
        db: Database session
        auth0_claims: Decoded Auth0 JWT claims (must contain 'sub')
    
    Returns:
        User: Existing or newly created user
    """
    auth0_user_id = auth0_claims.get('sub')
    if not auth0_user_id:
        raise ValueError("Auth0 claims missing 'sub' (user ID)")
    
    # Try to find existing user by Auth0 user ID
    user = db.query(User).filter(User.auth0_user_id == auth0_user_id).first()
    
    if user:
        logger.debug(f"Found existing user for Auth0 ID: {auth0_user_id} (username: {user.username})")
        return user
    
    # User doesn't exist - create new user
    # Extract email from claims (common Auth0 claim)
    email = auth0_claims.get('email') or auth0_claims.get('https://tableau-ai-demo-api/email')
    name = auth0_claims.get('name') or auth0_claims.get('https://tableau-ai-demo-api/name')
    
    # Use email as username if available, otherwise use Auth0 user ID
    username = email or f"auth0_{auth0_user_id[:20]}"
    
    # Ensure username is unique
    base_username = username
    counter = 1
    while db.query(User).filter(User.username == username).first():
        username = f"{base_username}_{counter}"
        counter += 1
    
    # Create new user
    user = User(
        username=username,
        password_hash=None,  # Auth0 users don't have passwords
        auth0_user_id=auth0_user_id,
        role=UserRole.USER,  # Default role
        is_active=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logger.info(f"Created new user from Auth0: {username} (Auth0 ID: {auth0_user_id})")
    return user
