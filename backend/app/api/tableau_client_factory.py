"""Tableau client factory - shared logic for building TableauClient from config/token."""
from typing import Optional, Callable, Any

from sqlalchemy.orm import Session

from app.models.user import UserTableauServerMapping
from app.services.tableau.client import TableauClient
from app.services.tableau.token_store import TokenEntry

_AUTH_PLACEHOLDERS = {
    "pat": ("pat-placeholder", "pat-placeholder"),
    "standard": ("standard-placeholder", "standard-placeholder"),
}


def _site_id_for_client(config: Any, token_entry: Optional[TokenEntry] = None) -> Optional[str]:
    """Normalize site_id for TableauClient (empty string = default site = None)."""
    if token_entry and token_entry.site_id:
        return token_entry.site_id
    if config.site_id and isinstance(config.site_id, str) and config.site_id.strip():
        return config.site_id.strip() or None
    return None


def site_id_from_config(config: Any) -> Optional[str]:
    """Get normalized site_id from config only."""
    return _site_id_for_client(config, None)


def create_tableau_client_from_token(
    config: Any,
    token_entry: TokenEntry,
    auth_type: str,
    tableau_username: Optional[str] = None,
    on_401_invalidate: Optional[Callable[[], None]] = None,
) -> TableauClient:
    """
    Build TableauClient from cached token.
    Handles pat/standard/connected_app placeholders.
    """
    site_id = _site_id_for_client(config, token_entry)
    if auth_type in _AUTH_PLACEHOLDERS:
        cid, csec = _AUTH_PLACEHOLDERS[auth_type]
    else:
        cid, csec = config.client_id, config.client_secret
    kwargs = {
        "server_url": config.server_url,
        "site_id": site_id,
        "api_version": config.api_version or "3.15",
        "client_id": cid,
        "client_secret": csec,
        "verify_ssl": not getattr(config, "skip_ssl_verify", False),
        "initial_token": token_entry.token,
        "initial_site_id": token_entry.site_id,
        "initial_site_content_url": token_entry.site_content_url,
    }
    if tableau_username is not None:
        kwargs["username"] = tableau_username
        kwargs["secret_id"] = config.secret_id or config.client_id
    if on_401_invalidate:
        kwargs["on_401_invalidate"] = on_401_invalidate
    client = TableauClient(**kwargs)
    if auth_type == "pat":
        client._pat_auth = True
    elif auth_type == "standard":
        client._standard_auth = True
    return client


def create_tableau_client_for_credential_signin(
    config: Any,
    auth_type: str,
    site_id_for_client: Optional[str] = None,
) -> TableauClient:
    """Create unauthenticated TableauClient for PAT or standard sign-in."""
    cid, csec = _AUTH_PLACEHOLDERS[auth_type]
    return TableauClient(
        server_url=config.server_url,
        site_id=site_id_for_client,
        api_version=config.api_version or "3.15",
        client_id=cid,
        client_secret=csec,
        verify_ssl=not getattr(config, "skip_ssl_verify", False),
    )


def resolve_tableau_username(db: Session, config: Any, current_user: Any) -> str:
    """Resolve tableau username: mapping > Auth0 metadata > app username."""
    mapping = db.query(UserTableauServerMapping).filter(
        UserTableauServerMapping.user_id == current_user.id,
        UserTableauServerMapping.tableau_server_config_id == config.id,
    ).first()
    if mapping:
        return mapping.tableau_username
    if getattr(current_user, "tableau_username", None):
        return current_user.tableau_username
    return current_user.username
