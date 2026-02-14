"""Tableau authentication endpoints for user-selected server/site."""
import logging
from datetime import datetime, timedelta, timezone

import jwt
from typing import Dict, List, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.tableau_client_factory import (
    create_tableau_client_for_credential_signin,
    create_tableau_client_from_token,
    resolve_tableau_username,
    site_id_from_config,
)
from app.services.auth0_user_service import extract_metadata_value
from app.services.eas_jwt_builder import build_tableau_jwt
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, TableauServerConfig, UserTableauPAT, UserTableauPassword
from app.services.eas_oauth import (
    exchange_code_for_jwt,
    generate_state,
    get_authorization_url,
    get_and_clear_oauth_state,
    store_oauth_state,
)
from app.services.pat_encryption import decrypt_pat
from app.services.tableau.client import TableauClient, TableauAuthenticationError, TableauAPIError, TableauClientError
from app.services.tableau.token_store import TokenEntry
from app.services.tableau.token_store_factory import get_token_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tableau-auth", tags=["tableau-auth"])


class TableauConfigOption(BaseModel):
    """Tableau config option for selection."""
    id: int
    name: str
    server_url: str
    site_id: Optional[str]
    allow_pat_auth: Optional[bool] = False
    allow_standard_auth: Optional[bool] = False
    allow_connected_app_oauth: Optional[bool] = False
    has_connected_app: Optional[bool] = False
    has_connected_app_oauth: Optional[bool] = False


class TableauAuthRequest(BaseModel):
    """Tableau authentication request."""
    config_id: int
    auth_type: str = "connected_app"  # "connected_app", "pat", "standard", "connected_app_oauth"


class OAuthAuthorizeUrlResponse(BaseModel):
    """OAuth authorize URL response."""
    authorize_url: str


class TableauAuthResponse(BaseModel):
    """Tableau authentication response."""
    authenticated: bool
    server_url: str
    site_id: Optional[str]
    user_id: Optional[str]
    token: str  # Partial token for security
    expires_at: Optional[str]


@router.get("/configs", response_model=List[TableauConfigOption])
async def list_available_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List available Tableau server configurations."""
    configs = db.query(TableauServerConfig).filter(
        TableauServerConfig.is_active == True
    ).all()
    
    def _has_oauth(c):
        return bool(
            getattr(c, 'allow_connected_app_oauth', False)
            and getattr(c, 'eas_issuer_url', None)
            and getattr(c, 'eas_client_id', None)
            and getattr(c, 'eas_client_secret', None)
        )

    return [TableauConfigOption(
        id=c.id,
        name=c.name,
        server_url=c.server_url,
        site_id=c.site_id if c.site_id else None,
        allow_pat_auth=getattr(c, 'allow_pat_auth', False),
        allow_standard_auth=getattr(c, 'allow_standard_auth', False),
        allow_connected_app_oauth=getattr(c, 'allow_connected_app_oauth', False),
        has_connected_app=bool(c.client_id and c.client_secret),
        has_connected_app_oauth=_has_oauth(c),
    ) for c in configs]


@router.post("/authenticate", response_model=TableauAuthResponse)
async def authenticate_tableau(
    auth_request: TableauAuthRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Authenticate with Tableau using selected server configuration.
    
    Supports Connected App (JWT) or Personal Access Token based on auth_type.
    """
    # Get the configuration
    config = db.query(TableauServerConfig).filter(
        TableauServerConfig.id == auth_request.config_id,
        TableauServerConfig.is_active == True
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tableau server configuration not found or inactive"
        )
    
    auth_type = (auth_request.auth_type or "connected_app").lower()
    if auth_type == "connected_app_oauth":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use OAuth flow: GET /tableau-auth/oauth/authorize-url?config_id=N and redirect to authorize_url",
        )

    if auth_type == "pat":
        if not getattr(config, 'allow_pat_auth', False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PAT authentication is not enabled for this server"
            )
        pat_record = db.query(UserTableauPAT).filter(
            UserTableauPAT.user_id == current_user.id,
            UserTableauPAT.tableau_server_config_id == config.id,
        ).first()
        if not pat_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No PAT configured for this server. Add one in Settings."
            )
        try:
            pat_secret = decrypt_pat(pat_record.pat_secret)
        except ValueError as e:
            # decrypt_pat raises ValueError with descriptive message
            logger.error(f"Failed to decrypt PAT: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Failed to decrypt PAT: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to decrypt stored PAT: {e}"
            )
        client = create_tableau_client_for_credential_signin(
            config, "pat", site_id_from_config(config)
        )
        try:
            auth_result = await client.sign_in_with_pat(pat_record.pat_name, pat_secret)
        except TableauAuthenticationError as e:
            logger.error(f"Tableau PAT authentication error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
        
        # Cache the PAT token in Redis-backed store
        token_store = get_token_store("pat")
        token_entry = TokenEntry(
            token=client.auth_token,
            expires_at=client.token_expires_at or datetime.now(timezone.utc) + timedelta(minutes=8),
            site_id=client.site_id,
            site_content_url=client.site_content_url,
        )
        token_store.set(current_user.id, config.id, "pat", token_entry)
        logger.info(f"Cached PAT token for user={current_user.id} config={config.id}")
        
        return TableauAuthResponse(
            authenticated=True,
            server_url=config.server_url,
            site_id=auth_result.get("site", {}).get("id") or auth_result.get("credentials", {}).get("site", {}).get("id"),
            user_id=auth_result.get("user", {}).get("id"),
            token=(auth_result.get("token") or "")[:20] + "...",
            expires_at=auth_result.get("expires_at"),
        )

    if auth_type == "standard":
        if not getattr(config, 'allow_standard_auth', False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Standard authentication is not enabled for this server",
            )
        pw_record = db.query(UserTableauPassword).filter(
            UserTableauPassword.user_id == current_user.id,
            UserTableauPassword.tableau_server_config_id == config.id,
        ).first()
        if not pw_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No credentials configured for this server. Add username/password in Settings.",
            )
        try:
            password = decrypt_pat(pw_record.password_encrypted)
        except ValueError as e:
            # decrypt_pat raises ValueError with descriptive message
            logger.error(f"Failed to decrypt password: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Failed to decrypt password: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to decrypt stored credentials: {e}"
            )
        client = create_tableau_client_for_credential_signin(
            config, "standard", site_id_from_config(config)
        )
        try:
            auth_result = await client.sign_in_with_password(pw_record.tableau_username, password)
        except TableauAuthenticationError as e:
            logger.error(f"Tableau standard authentication error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
            )
        token_store = get_token_store("standard")
        token_entry = TokenEntry(
            token=client.auth_token,
            expires_at=client.token_expires_at or datetime.now(timezone.utc) + timedelta(minutes=240),
            site_id=client.site_id,
            site_content_url=client.site_content_url,
        )
        token_store.set(current_user.id, config.id, "standard", token_entry)
        logger.info(f"Cached standard auth token for user={current_user.id} config={config.id}")
        return TableauAuthResponse(
            authenticated=True,
            server_url=config.server_url,
            site_id=auth_result.get("site", {}).get("id") or auth_result.get("credentials", {}).get("site", {}).get("id"),
            user_id=auth_result.get("user", {}).get("id"),
            token=(auth_result.get("token") or "")[:20] + "...",
            expires_at=auth_result.get("expires_at"),
        )

    # Connected App authentication
    if not (config.client_id and config.client_secret):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connected App credentials are not configured for this server. Use PAT authentication or contact your admin."
        )
    tableau_username = resolve_tableau_username(db, config, current_user)
    logger.debug(f"Tableau auth for user {current_user.id} (username: {current_user.username})")
    site_id_for_client = site_id_from_config(config)
    try:
        client = TableauClient(
            server_url=config.server_url,
            site_id=site_id_for_client,
            api_version=config.api_version or "3.15",
            client_id=config.client_id,
            client_secret=config.client_secret,
            username=tableau_username,
            secret_id=config.secret_id or config.client_id,
            verify_ssl=not getattr(config, 'skip_ssl_verify', False),
        )
        
        # Authenticate
        auth_result = await client.sign_in()
        
        # Cache the Connected App token in in-memory store
        token_store = get_token_store("connected_app")
        creds = auth_result.get("credentials", {})
        expires_at_str = creds.get("expiresAt")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            except Exception:
                expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        
        token_entry = TokenEntry(
            token=client.auth_token,
            expires_at=expires_at,
            site_id=client.site_id,
            site_content_url=client.site_content_url,
        )
        token_store.set(current_user.id, config.id, "connected_app", token_entry)
        logger.info(f"Cached Connected App token for user={current_user.id} config={config.id}")
        
        return TableauAuthResponse(
            authenticated=True,
            server_url=config.server_url,
            site_id=auth_result.get("site", {}).get("id"),
            user_id=auth_result.get("user", {}).get("id"),
            token=auth_result.get("credentials", {}).get("token", "")[:20] + "...",  # Partial token
            expires_at=auth_result.get("credentials", {}).get("expiresAt")
        )
    except TableauAuthenticationError as e:
        logger.error(f"Tableau authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Tableau authentication failed for '{tableau_username}': {e}",
        )
    except Exception as e:
        logger.error(f"Unexpected error during Tableau authentication: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tableau authentication error for '{tableau_username}': {e}",
        )


class SwitchSiteRequest(BaseModel):
    """Request to switch to another site."""
    config_id: int
    auth_type: str  # "standard" or "pat"
    site_content_url: str


class SiteInfo(BaseModel):
    """Site info for list."""
    id: Optional[str]
    name: Optional[str]
    contentUrl: Optional[str]


class SitesPagination(BaseModel):
    page_number: int
    page_size: int
    total_available: int


class SitesPaginatedResponse(BaseModel):
    sites: List[SiteInfo]
    pagination: SitesPagination


@router.post("/switch-site", response_model=TableauAuthResponse)
async def switch_site(
    body: SwitchSiteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Switch to another site. Tableau Server only (not Cloud).
    Supported for standard and PAT auth types only.
    """
    auth_type = (body.auth_type or "").lower()
    if auth_type not in ("standard", "pat"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Site switching is only supported for standard or PAT authentication. Connected Apps are site-specific.",
        )
    config = db.query(TableauServerConfig).filter(
        TableauServerConfig.id == body.config_id,
        TableauServerConfig.is_active == True,
    ).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tableau server configuration not found or inactive",
        )
    token_store = get_token_store(auth_type)
    token_entry = token_store.get(current_user.id, config.id, auth_type)
    if not token_entry:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please connect first.",
        )
    async with token_cache_lock(current_user.id, config.id, auth_type):
        token_entry = token_store.get(current_user.id, config.id, auth_type)
        if not token_entry:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated. Please connect first.",
            )
        client = create_tableau_client_from_token(config, token_entry, auth_type)
        try:
            result = await client.switch_site(body.site_content_url or "")
        except TableauAuthenticationError as e:
            logger.error(f"Switch site failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        token_store.invalidate(current_user.id, config.id, auth_type)
        new_entry = TokenEntry(
            token=client.auth_token,
            expires_at=client.token_expires_at or datetime.now(timezone.utc) + timedelta(minutes=240),
            site_id=client.site_id,
            site_content_url=client.site_content_url,
        )
        token_store.set(current_user.id, config.id, auth_type, new_entry)
        site_info = result.get("site", {})
        return TableauAuthResponse(
            authenticated=True,
            server_url=config.server_url,
            site_id=site_info.get("id"),
            user_id=result.get("user", {}).get("id"),
            token=(result.get("token") or "")[:20] + "...",
            expires_at=new_entry.expires_at.isoformat() if new_entry.expires_at else None,
        )


@router.get("/sites", response_model=SitesPaginatedResponse)
async def list_sites(
    config_id: int = Query(..., description="Tableau server config ID"),
    auth_type: str = Query(..., description="standard or pat"),
    page_size: int = Query(100, ge=1, le=1000),
    page_number: int = Query(1, ge=1),
    search: Optional[str] = Query(None, description="Filter by name or contentUrl (case-insensitive contains)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List sites the user has access to. Paginated. For standard and PAT only.
    Tableau API does not support filter on sites, so search is applied client-side.
    """
    logger.info(f"list_sites: config_id={config_id} auth_type={auth_type} user_id={current_user.id}")
    auth_type = auth_type.lower()
    if auth_type not in ("standard", "pat"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="List sites is only supported for standard or PAT authentication.",
        )
    config = db.query(TableauServerConfig).filter(
        TableauServerConfig.id == config_id,
        TableauServerConfig.is_active == True,
    ).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tableau server configuration not found or inactive",
        )
    token_store = get_token_store(auth_type)
    token_entry = token_store.get(current_user.id, config.id, auth_type)
    if not token_entry:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please connect first.",
        )
    try:
        client = create_tableau_client_from_token(config, token_entry, auth_type)
    except Exception as e:
        logger.error(f"Failed to create Tableau client for list_sites: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize Tableau client: {str(e)}",
        )

    try:
        all_sites: List[Dict] = []
        page = 1
        while True:
            batch = await client.list_sites(page_size=100, page_number=page)
            if not batch:
                break
            all_sites.extend(batch)
            if len(batch) < 100:
                break
            page += 1
            if page > 50:
                break
        logger.debug(f"list_sites fetched {len(all_sites)} site(s)")
    except TableauAuthenticationError as e:
        logger.error(f"List sites authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except TableauAPIError as e:
        logger.error(f"List sites API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tableau API error: {str(e)}",
        )
    except TableauClientError as e:
        logger.error(f"List sites client error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tableau client error: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Unexpected error listing sites: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )

    items = [
        {"id": s.get("id"), "name": s.get("name"), "contentUrl": s.get("contentUrl") or s.get("contenturl")}
        for s in all_sites
        if isinstance(s, dict)
    ]
    if search and search.strip():
        q = search.strip().lower()
        items = [s for s in items if (s.get("name") or "").lower().find(q) >= 0 or (s.get("contentUrl") or "").lower().find(q) >= 0]
    total = len(items)
    start = (page_number - 1) * page_size
    page_items = items[start : start + page_size]
    return SitesPaginatedResponse(
        sites=[SiteInfo(id=s["id"], name=s["name"], contentUrl=s["contentUrl"]) for s in page_items],
        pagination=SitesPagination(page_number=page_number, page_size=page_size, total_available=total),
    )


def _oauth_callback_url(db: Session) -> str:
    from app.services.auth_config_service import get_resolved_backend_api_url
    base = get_resolved_backend_api_url(db).rstrip("/")
    return f"{base}/api/v1/tableau-auth/oauth/callback"


def _frontend_redirect_url(
    success: bool,
    db: Session,
    error: Optional[str] = None,
    config_id: Optional[int] = None,
    error_detail: Optional[str] = None,
) -> str:
    from app.services.auth_config_service import get_resolved_tableau_oauth_frontend_redirect
    base = get_resolved_tableau_oauth_frontend_redirect(db).rstrip("/")
    params = {}
    if error:
        params["tableau_error"] = error
        if error_detail:
            params["tableau_error_detail"] = error_detail
    else:
        params["tableau_connected"] = "1"
        if config_id is not None:
            params["tableau_config_id"] = str(config_id)
    return f"{base}/?{urlencode(params)}"


@router.get("/oauth/authorize-url", response_model=OAuthAuthorizeUrlResponse)
async def get_oauth_authorize_url(
    config_id: int = Query(..., description="Tableau server config ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return EAS OAuth authorize URL for OAuth 2.0 Trust flow."""
    config = db.query(TableauServerConfig).filter(
        TableauServerConfig.id == config_id,
        TableauServerConfig.is_active == True,
    ).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tableau server configuration not found or inactive",
        )
    if not getattr(config, "allow_connected_app_oauth", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth 2.0 Trust is not enabled for this server",
        )
    if not all([
        getattr(config, "eas_issuer_url", None),
        getattr(config, "eas_client_id", None),
        getattr(config, "eas_client_secret", None),
    ]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="EAS OAuth is not fully configured (eas_issuer_url, eas_client_id, eas_client_secret required)",
        )
    state = generate_state()
    redirect_uri = _oauth_callback_url(db)
    store_oauth_state(state, config_id, current_user.id)
    authorize_url = await get_authorization_url(config, redirect_uri, state)
    return OAuthAuthorizeUrlResponse(authorize_url=authorize_url)


@router.get("/oauth/callback")
async def oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """OAuth callback: exchange code for JWT, sign in to Tableau, cache token, redirect to frontend."""
    logger.info("OAuth callback invoked: error=%s code=%s state=%s", error, bool(code), bool(state))
    if error:
        msg = error_description or error
        logger.warning("OAuth callback error from IdP: %s", msg)
        return RedirectResponse(url=_frontend_redirect_url(False, db, error=msg))
    if not code or not state:
        logger.warning("OAuth callback missing code or state")
        return RedirectResponse(url=_frontend_redirect_url(False, db, error="missing_code_or_state"))
    state_data = get_and_clear_oauth_state(state)
    if not state_data:
        logger.warning("OAuth callback invalid or expired state (Redis)")
        return RedirectResponse(url=_frontend_redirect_url(False, db, error="invalid_state"))
    config_id, user_id = state_data
    logger.info("OAuth callback state valid: config_id=%s user_id=%s", config_id, user_id)
    config = db.query(TableauServerConfig).filter(
        TableauServerConfig.id == config_id,
        TableauServerConfig.is_active == True,
    ).first()
    if not config:
        logger.warning("OAuth callback config not found: config_id=%s", config_id)
        return RedirectResponse(url=_frontend_redirect_url(False, db, error="config_not_found"))
    try:
        redirect_uri = _oauth_callback_url(db)
        logger.info("Exchanging code for JWT (redirect_uri=%s)", redirect_uri)
        eas_jwt = await exchange_code_for_jwt(code, config, redirect_uri)
        logger.info("JWT obtained (len=%d)", len(eas_jwt))
        try:
            payload = jwt.decode(eas_jwt, options={"verify_signature": False})
            logger.info(
                "JWT claims for Tableau: aud=%s sub=%s iss=%s scp=%s jti=%s exp=%s",
                payload.get("aud"),
                payload.get("sub"),
                payload.get("iss"),
                payload.get("scp"),
                payload.get("jti"),
                payload.get("exp"),
            )
            logger.info("JWT payload for Tableau: %s", payload)
            logger.debug("JWT raw (for debugging): %s", eas_jwt)
        except Exception as decode_err:
            logger.debug("Could not decode JWT for logging: %s", decode_err)
    except Exception as e:
        logger.error("EAS token exchange failed: %s", e, exc_info=True)
        return RedirectResponse(url=_frontend_redirect_url(False, db, error="token_exchange_failed"))

    # Auth0 cannot set aud/sub (restricted claims). Use backend-constructed JWT when EAS key is configured (DB or file).
    from app.services.auth_config_service import (
        get_resolved_backend_api_url,
        get_resolved_eas_jwt_key_content,
    )
    eas_key_content = get_resolved_eas_jwt_key_content(db)
    eas_key_path = getattr(settings, "EAS_JWT_KEY_PATH", None) if not eas_key_content else None
    if eas_key_content or eas_key_path:
        current_user = db.query(User).filter(User.id == user_id).first()
        if not current_user:
            logger.warning("OAuth callback user not found: user_id=%s", user_id)
            return RedirectResponse(url=_frontend_redirect_url(False, db, error="user_not_found"))
        auth0_payload = jwt.decode(eas_jwt, options={"verify_signature": False})
        sub_field = (getattr(config, "eas_sub_claim_field", None) or "email").strip()
        sub_value = extract_metadata_value(auth0_payload, sub_field) if sub_field else None
        if not sub_value:
            sub_value = resolve_tableau_username(db, config, current_user)
        issuer = get_resolved_backend_api_url(db).rstrip("/")
        aud = getattr(settings, "EAS_JWT_AUD", None) or "tableau"
        built = build_tableau_jwt(
            issuer=issuer, sub=sub_value, key_path=eas_key_path, key_content=eas_key_content, aud=aud
        )
        if built:
            eas_jwt = built
            logger.info("Using backend-constructed JWT (sub=%s, field=%s)", sub_value, sub_field)
        else:
            logger.error("Backend JWT construction failed")
            return RedirectResponse(url=_frontend_redirect_url(False, db, error="jwt_construction_failed"))
    else:
        try:
            payload = jwt.decode(eas_jwt, options={"verify_signature": False})
            if payload.get("aud") != "tableau":
                logger.warning(
                    "Auth0 cannot set aud=tableau (restricted claim). Set EAS_JWT_KEY_PATH for backend-constructed JWT."
                )
                return RedirectResponse(url=_frontend_redirect_url(False, db, error="auth0_aud_not_tableau"))
        except Exception:
            pass  # Continue with eas_jwt as-is; Tableau will reject if invalid

    client = create_tableau_client_for_credential_signin(
        config, "connected_app_oauth", site_id_from_config(config)
    )
    client.client_id = "connected_app_oauth-placeholder"
    client.client_secret = "connected_app_oauth-placeholder"
    try:
        auth_result = await client.sign_in_with_eas_jwt(eas_jwt)
        logger.info("Tableau sign-in success: site=%s", auth_result.get("site_content_url"))
    except TableauAuthenticationError as e:
        logger.error("Tableau EAS JWT sign-in failed: %s", e)
        # Surface Tableau's error in URL for debugging (e.g. "401 - {...}")
        err_detail = str(e).replace(" ", "+")[:200] if str(e) else "unknown"
        return RedirectResponse(url=_frontend_redirect_url(False, db, error="tableau_signin_failed", error_detail=err_detail))
    token_store = get_token_store("connected_app_oauth")
    token_entry = TokenEntry(
        token=client.auth_token,
        expires_at=client.token_expires_at or datetime.now(timezone.utc) + timedelta(minutes=8),
        site_id=client.site_id,
        site_content_url=client.site_content_url,
    )
    token_store.set(user_id, config_id, "connected_app_oauth", token_entry)
    logger.info(f"Cached OAuth 2.0 Trust token for user={user_id} config={config_id}")
    redirect_url = _frontend_redirect_url(True, db, config_id=config_id)
    return RedirectResponse(url=redirect_url)
