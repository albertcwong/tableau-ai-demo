"""Tableau authentication endpoints for user-selected server/site."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User, TableauServerConfig, UserTableauServerMapping, UserTableauPAT
from app.services.tableau.client import TableauClient, TableauAuthenticationError
from app.services.pat_encryption import decrypt_pat
from app.services.tableau.token_store_factory import get_token_store
from app.services.tableau.token_store import TokenEntry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tableau-auth", tags=["tableau-auth"])


class TableauConfigOption(BaseModel):
    """Tableau config option for selection."""
    id: int
    name: str
    server_url: str
    site_id: Optional[str]
    allow_pat_auth: Optional[bool] = False
    has_connected_app: Optional[bool] = False


class TableauAuthRequest(BaseModel):
    """Tableau authentication request."""
    config_id: int
    auth_type: str = "connected_app"  # "connected_app" or "pat"


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
        site_id_for_client = config.site_id.strip() or None if config.site_id else None
        client = TableauClient(
            server_url=config.server_url,
            site_id=site_id_for_client,
            api_version=config.api_version or "3.15",
            client_id="pat-placeholder",
            client_secret="pat-placeholder",
            verify_ssl=not getattr(config, 'skip_ssl_verify', False),
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
    
    # Connected App authentication
    if not (config.client_id and config.client_secret):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connected App credentials are not configured for this server. Use PAT authentication or contact your admin."
        )
    # Determine the username that will be used for authentication
    # Priority: 1) Manual mapping, 2) Auth0 metadata, 3) App username
    mapping = db.query(UserTableauServerMapping).filter(
        UserTableauServerMapping.user_id == current_user.id,
        UserTableauServerMapping.tableau_server_config_id == config.id
    ).first()
    
    logger.debug(f"Tableau auth for user {current_user.id} (username: {current_user.username}): "
                 f"mapping exists: {mapping is not None}, tableau_username: {current_user.tableau_username}")
    
    if mapping:
        tableau_username = mapping.tableau_username
        username_source = "manual mapping"
        logger.info(f"Using manual mapping Tableau username: {tableau_username}")
    elif current_user.tableau_username:
        tableau_username = current_user.tableau_username
        username_source = "Auth0 metadata"
        logger.info(f"Using Auth0 metadata Tableau username: {tableau_username}")
    else:
        tableau_username = current_user.username
        username_source = "app username"
        logger.info(f"Using app username as Tableau username: {tableau_username}")
    
    # Normalize config site_id for TableauClient (empty string = default site = None)
    if config.site_id and isinstance(config.site_id, str) and config.site_id.strip():
        site_id_for_client = config.site_id.strip() or None
    else:
        site_id_for_client = None  # Default site
    
    try:
        
        # Create Tableau client with config and username (mapped or default)
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
        # Include the username that was actually used and whether it was mapped
        error_detail = f"Tableau authentication failed using {username_source} '{tableau_username}': {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_detail
        )
    except Exception as e:
        logger.error(f"Unexpected error during Tableau authentication: {e}")
        # Include the username that was actually used and whether it was mapped
        error_detail = f"Tableau authentication error using {username_source} '{tableau_username}': {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )
