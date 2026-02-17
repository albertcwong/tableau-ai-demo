"""Auth0 IdP adapter."""
import logging
from typing import Any, Optional

import requests
from sqlalchemy.orm import Session

from app.core.database import safe_commit
from app.models.user import User, UserRole
from app.services.auth_config_service import get_auth_config
from app.services.claims import extract_claim_value

logger = logging.getLogger(__name__)


def _normalize_domain(domain: Optional[str]) -> str:
    """Strip protocol and trailing slash for URL construction."""
    if not domain:
        return ""
    d = domain.strip().rstrip("/")
    for prefix in ("https://", "http://"):
        if d.lower().startswith(prefix):
            d = d[len(prefix) :].split("/")[0]
            break
    return d


def _fetch_userinfo(token: str, domain: str) -> Optional[dict]:
    """Fetch user profile from Auth0 /userinfo when JWT lacks email (common for access tokens)."""
    if not domain or not token:
        return None
    url = f"https://{domain}/userinfo"
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        status_code = getattr(getattr(e, "response", None), "status_code", None)
        logger.warning("Auth0 userinfo fetch failed: status=%s error=%s", status_code, e)
        return None
    except Exception as e:
        logger.warning("Auth0 userinfo fetch failed: %s", e)
        return None


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

    def enrich_claims(self, claims: dict, token: str, config: Any) -> dict:
        """When access token lacks email, fetch from Auth0 /userinfo."""
        if claims.get("email"):
            logger.debug("Auth0 enrich_claims: email already in token")
            return claims
        domain = getattr(config, "auth0_domain", None)
        if not domain or not token:
            logger.debug("Auth0 enrich_claims: no domain/token, skipping userinfo fetch")
            return claims
        domain = _normalize_domain(domain)
        userinfo = _fetch_userinfo(token, domain)
        if userinfo:
            merged = {**claims, **{k: v for k, v in userinfo.items() if v is not None}}
            has_email = "email" in merged
            logger.debug("Auth0 enrich_claims: userinfo keys=%s email_present=%s", list(userinfo.keys()), has_email)
            return merged
        logger.warning("Auth0 enrich_claims: userinfo fetch failed or returned empty; claims may lack email")
        return claims

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
