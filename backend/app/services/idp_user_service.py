"""IdP-agnostic user service. Supports Auth0, Entra, Okta, etc."""
import logging
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)


class IdpAdapter(Protocol):
    """Adapter for a specific IdP. Extracts user id and optionally normalizes claims."""

    def get_user_id(self, claims: dict) -> str | None:
        """Extract stable user identifier from claims (e.g. sub, oid)."""
        ...

    def enrich_claims(self, claims: dict, token: str, config: Any) -> dict:
        """Fetch additional user info when token lacks standard claims (e.g. email). Default: return claims unchanged."""
        ...

    def get_or_create_user(self, db: Session, claims: dict) -> User:
        """Get or create user from IdP claims."""
        ...


def get_idp_adapter(provider: str) -> IdpAdapter:
    """Return adapter for the given IdP provider."""
    if provider in ("auth0",):
        from app.services.idp_adapters.auth0 import Auth0IdpAdapter
        return Auth0IdpAdapter()
    raise ValueError(f"Unknown IdP provider: {provider}")


def get_or_create_user(db: Session, claims: dict, provider: str = "auth0") -> User:
    """Get or create user from IdP claims. Provider: auth0, entra, okta, etc."""
    adapter = get_idp_adapter(provider)
    return adapter.get_or_create_user(db, claims)
