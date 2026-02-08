"""Tableau authentication endpoints for user-selected server/site."""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User, TableauServerConfig, UserTableauServerMapping
from app.services.tableau.client import TableauClient, TableauAuthenticationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tableau-auth", tags=["tableau-auth"])


class TableauConfigOption(BaseModel):
    """Tableau config option for selection."""
    id: int
    name: str
    server_url: str
    site_id: Optional[str]


class TableauAuthRequest(BaseModel):
    """Tableau authentication request."""
    config_id: int


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
        site_id=c.site_id if c.site_id else None
    ) for c in configs]


@router.post("/authenticate", response_model=TableauAuthResponse)
async def authenticate_tableau(
    auth_request: TableauAuthRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Authenticate with Tableau using selected server configuration.
    
    Uses the username from the current authenticated user for Tableau Connected App authentication.
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
            secret_id=config.secret_id or config.client_id
        )
        
        # Authenticate
        auth_result = await client.sign_in()
        
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
