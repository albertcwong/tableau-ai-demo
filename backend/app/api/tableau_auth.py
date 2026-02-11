"""Tableau authentication endpoints for user-selected server/site."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User, TableauServerConfig, UserTableauPAT, UserTableauPassword
from app.services.tableau.client import TableauClient, TableauAuthenticationError
from app.api.tableau_client_factory import (
    create_tableau_client_from_token,
    create_tableau_client_for_credential_signin,
    resolve_tableau_username,
    site_id_from_config,
)
from app.services.pat_encryption import decrypt_pat
from app.services.tableau.token_store_factory import get_token_store
from app.services.tableau.token_store import TokenEntry
from app.services.tableau.token_cache import with_lock as token_cache_lock

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
    has_connected_app: Optional[bool] = False


class TableauAuthRequest(BaseModel):
    """Tableau authentication request."""
    config_id: int
    auth_type: str = "connected_app"  # "connected_app", "pat", or "standard"


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
    
    return [TableauConfigOption(
        id=c.id,
        name=c.name,
        server_url=c.server_url,
        site_id=c.site_id if c.site_id else None,
        allow_pat_auth=getattr(c, 'allow_pat_auth', False),
        allow_standard_auth=getattr(c, 'allow_standard_auth', False),
        has_connected_app=bool(c.client_id and c.client_secret),
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
        except Exception as e:
            logger.error(f"Failed to decrypt PAT: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to decrypt stored PAT"
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
        except Exception as e:
            logger.error(f"Failed to decrypt password: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to decrypt stored credentials",
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


@router.get("/sites", response_model=List[SiteInfo])
async def list_sites(
    config_id: int = Query(..., description="Tableau server config ID"),
    auth_type: str = Query(..., description="standard or pat"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List sites the user has access to. For standard and PAT only.
    """
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
    client = create_tableau_client_from_token(config, token_entry, auth_type)
    try:
        sites = await client.list_sites()
    except TableauAuthenticationError as e:
        logger.error(f"List sites failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    return [SiteInfo(id=s.get("id"), name=s.get("name"), contentUrl=s.get("contentUrl")) for s in sites]
