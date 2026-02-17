"""Tableau client factory - shared logic for building TableauClient from config/token."""
import logging
from typing import Optional, Callable, Any

from sqlalchemy.orm import Session

from app.models.user import UserTableauServerMapping
from app.services.auth_config_service import get_auth_config
from app.services.claims import extract_claim_value

logger = logging.getLogger(__name__)
from app.services.tableau.client import TableauClient
from app.services.tableau.token_store import TokenEntry

_AUTH_PLACEHOLDERS = {
    "pat": ("pat-placeholder", "pat-placeholder"),
    "standard": ("standard-placeholder", "standard-placeholder"),
    "connected_app_oauth": ("connected_app_oauth-placeholder", "connected_app_oauth-placeholder"),
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
        "ssl_cert_path": getattr(config, "ssl_cert_path", None),
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
    elif auth_type == "connected_app_oauth":
        client._eas_oauth_auth = True
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
        ssl_cert_path=getattr(config, "ssl_cert_path", None),
    )


def resolve_tableau_username(db: Session, config: Any, current_user: Any) -> str:
    """Resolve tableau username: mapping > claim (eas_sub_claim_field = Connected App User Claim). No fallbacks."""
    mapping = db.query(UserTableauServerMapping).filter(
        UserTableauServerMapping.user_id == current_user.id,
        UserTableauServerMapping.tableau_server_config_id == config.id,
    ).first()
    if mapping:
        logger.info("Tableau sign-in username: value=%r source=mapping", mapping.tableau_username)
        return mapping.tableau_username

    claim = (getattr(config, "eas_sub_claim_field", None) or "").strip() or "email"
    idp_claims = getattr(current_user, "idp_claims", None) or {}
    keys = list(idp_claims.keys()) if isinstance(idp_claims, dict) else []
    logger.debug("Tableau username resolution: claim=%r idp_claims_keys=%s", claim, keys)

    val = extract_claim_value(idp_claims, claim)
    if not val and claim == "email":
        for alt in ("preferred_username", "upn", "unique_name"):
            v = extract_claim_value(idp_claims, alt)
            if v and "@" in v:
                val = v
                break
        if not val:
            auth_config = get_auth_config(db)
            audience = getattr(auth_config, "auth0_audience", None) if auth_config else None
            if audience and audience.strip():
                ns = audience.strip().rstrip("/")
                val = extract_claim_value(idp_claims, f"{ns}/email")
                if val:
                    logger.debug("Tableau username: resolved from namespaced claim %s/email", ns)

    if val:
        if claim == "email" and "@" not in val:
            msg = (
                f"Resolved username '{val}' from claim '{claim}' does not look like an email. "
                f"Tableau Connected App with email claim expects email format. "
                f"idp_claims keys: {keys}. "
                f"Ensure Auth0 returns email (add 'email' scope to your API, check Rules). "
                f"Or set a per-server mapping with your Tableau email in Settings > Tableau Server Mapping."
            )
            logger.error("Tableau username resolution: %s", msg)
            raise ValueError(msg)
        logger.info("Tableau sign-in username: value=%r source=claim claim=%r", val, claim)
        return val

    audience = getattr(get_auth_config(db), "auth0_audience", None) or ""
    ns_email = f"{audience.strip().rstrip('/')}/email" if audience else "https://YOUR_AUDIENCE/email"
    msg = (
        f"Connected App User Claim '{claim}' not found in idp_claims. "
        f"idp_claims keys: {keys}. "
        f"Auth0 access tokens do NOT include email by default. Add a Post-Login Action: "
        f"api.accessToken.setCustomClaim('{ns_email}', event.user.email). "
        f"See docs/AUTH0_TABLEAU_METADATA_SETUP.md. "
        f"Or set a per-server mapping in Admin > User Management > Tableau Server Mapping."
    )
    logger.error("Tableau username resolution failed: %s", msg)
    raise ValueError(msg)
