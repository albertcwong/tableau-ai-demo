"""Auth0 user mapping service."""
import logging
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.services.auth_config_service import get_auth_config

logger = logging.getLogger(__name__)


def extract_metadata_value(claims: dict, field_path: str) -> str | None:
    """
    Extract a value from Auth0 claims using a dot-notation path.
    
    Supports:
    - Simple fields: "email" -> claims["email"]
    - Nested fields: "app_metadata.tableau_username" -> claims["app_metadata"]["tableau_username"]
    - Namespaced fields: "https://tableau-ai-demo-api/tableau_username" -> claims["https://tableau-ai-demo-api/tableau_username"]
    
    Args:
        claims: Auth0 JWT claims dictionary
        field_path: Dot-separated path to the field (e.g., "app_metadata.tableau_username")
    
    Returns:
        Extracted value or None if not found
    """
    if not field_path:
        return None
    
    # Handle namespaced fields (with slashes)
    if '/' in field_path:
        return claims.get(field_path)
    
    # Handle dot-notation paths
    parts = field_path.split('.')
    value = claims
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
        if value is None:
            return None
    
    return str(value) if value is not None else None


def get_or_create_user_from_auth0(db: Session, auth0_claims: dict) -> User:
    """
    Get or create a user from Auth0 claims.
    Extracts Tableau username from configured metadata field if available.
    
    Args:
        db: Database session
        auth0_claims: Decoded Auth0 JWT claims (must contain 'sub')
    
    Returns:
        User: Existing or newly created user
    """
    auth0_user_id = auth0_claims.get('sub')
    if not auth0_user_id:
        raise ValueError("Auth0 claims missing 'sub' (user ID)")
    
    # Get auth config to check for metadata field configuration
    auth_config = get_auth_config(db)
    
    # Try to find existing user by Auth0 user ID
    user = db.query(User).filter(User.auth0_user_id == auth0_user_id).first()
    
    # Extract Tableau username from metadata if configured
    tableau_username = None
    if auth_config.auth0_tableau_metadata_field:
        logger.info(f"Attempting to extract Tableau username from configured field: '{auth_config.auth0_tableau_metadata_field}'")
        logger.debug(f"Available claims keys: {list(auth0_claims.keys())}")
        tableau_username = extract_metadata_value(auth0_claims, auth_config.auth0_tableau_metadata_field)
        if tableau_username:
            logger.info(f"✓ Successfully extracted Tableau username '{tableau_username}' from field '{auth_config.auth0_tableau_metadata_field}'")
        else:
            available_keys_str = ', '.join([f"'{k}'" for k in auth0_claims.keys()])
            logger.warning(
                f"✗ Failed to extract Tableau username from field '{auth_config.auth0_tableau_metadata_field}'. "
                f"Available claim keys in token: [{available_keys_str}]. "
                f"If you're using an Auth0 Action/Rule, make sure the field path matches exactly. "
                f"For namespaced claims, use: 'https://tableau-ai-demo-api/tableau_username'. "
                f"See docs/AUTH0_TABLEAU_METADATA_SETUP.md for instructions."
            )
    
    if user:
        # Update Tableau username if it changed or wasn't set before
        if tableau_username and user.tableau_username != tableau_username:
            user.tableau_username = tableau_username
            safe_commit(db)
            db.refresh(user)
            logger.info(f"Updated Tableau username for user {user.username}: {tableau_username}")
        logger.debug(f"Found existing user for Auth0 ID: {auth0_user_id} (username: {user.username}, tableau_username: {user.tableau_username})")
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
        tableau_username=tableau_username,
        role=UserRole.USER,  # Default role
        is_active=True
    )
    
    db.add(user)
    safe_commit(db)
    db.refresh(user)
    
    logger.info(f"Created new user from Auth0: {username} (Auth0 ID: {auth0_user_id}, Tableau username: {tableau_username})")
    return user
