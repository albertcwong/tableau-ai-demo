"""Auth0 IdP adapter."""
import logging
from sqlalchemy.orm import Session

from app.core.database import safe_commit
from app.models.user import User, UserRole
from app.services.auth_config_service import get_auth_config
from app.services.claims import extract_claim_value

logger = logging.getLogger(__name__)


def _json_safe(obj):
    """Return JSON-serializable copy of claims for storage."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    return str(obj)


class Auth0IdpAdapter:
    """Auth0 IdP adapter. Uses 'sub' as user id."""

    def get_user_id(self, claims: dict) -> str | None:
        return claims.get("sub")

    def get_or_create_user(self, db: Session, claims: dict) -> User:
        user_id = self.get_user_id(claims)
        if not user_id:
            raise ValueError("Auth0 claims missing 'sub' (user ID)")

        auth_config = get_auth_config(db)
        user = db.query(User).filter(User.auth0_user_id == user_id).first()
        tableau_username = extract_claim_value(claims, auth_config.tableau_username_field) if auth_config.tableau_username_field else None
        idp_claims = _json_safe(claims)

        if user:
            if tableau_username and user.tableau_username != tableau_username:
                user.tableau_username = tableau_username
            user.idp_claims = idp_claims
            safe_commit(db)
            db.refresh(user)
            return user

        email = claims.get("email") or claims.get("https://tableau-ai-demo-api/email")
        username = email or f"auth0_{user_id[:20]}"
        base_username = username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}_{counter}"
            counter += 1

        user = User(
            username=username,
            password_hash=None,
            auth0_user_id=user_id,
            tableau_username=tableau_username,
            role=UserRole.USER,
            is_active=True,
            idp_claims=idp_claims,
        )
        db.add(user)
        safe_commit(db)
        db.refresh(user)
        logger.info("Created user from Auth0: %s", username)
        return user
