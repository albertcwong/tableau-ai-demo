"""Admin API endpoints."""
import logging
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app.core.database import get_db
from app.core.auth import get_password_hash
from app.api.auth import get_current_admin_user
from app.models.user import User, UserRole, TableauServerConfig, ProviderConfig, ProviderType, UserTableauServerMapping, AuthConfig
from app.models.chat import Message, Conversation, ChatContext
from app.models.agent_config import AgentConfig
from app.services.auth_config_service import get_auth_config, update_auth_config
from app.services.agent_config_service import AgentConfigService
from app.api.models import (
    AgentConfigResponse, AgentVersionResponse, AgentVersionUpdate,
    AgentSettingsResponse, AgentSettingsUpdate
)


def get_provider_type_value(provider_type) -> str:
    """Safely get provider type value, handling both enum and string."""
    if isinstance(provider_type, ProviderType):
        return provider_type.value
    if isinstance(provider_type, str):
        return provider_type.lower()
    return str(provider_type).lower()

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


# User management models
class UserCreate(BaseModel):
    """User creation model."""
    username: str
    password: str
    role: str = "USER"


class UserUpdate(BaseModel):
    """User update model."""
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """User response model."""
    id: int
    username: str
    role: str
    is_active: bool
    created_at: str
    preferred_provider: Optional[str] = None
    preferred_model: Optional[str] = None
    preferred_agent_type: Optional[str] = None
    tableau_username: Optional[str] = None

    class Config:
        from_attributes = True


# Tableau config models
class TableauConfigCreate(BaseModel):
    """Tableau server config creation model."""
    name: str
    server_url: str
    site_id: Optional[str] = None
    api_version: Optional[str] = "3.15"
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    secret_id: Optional[str] = None
    allow_pat_auth: Optional[bool] = False
    allow_standard_auth: Optional[bool] = False
    skip_ssl_verify: Optional[bool] = False


class TableauConfigUpdate(BaseModel):
    """Tableau server config update model."""
    name: Optional[str] = None
    server_url: Optional[str] = None
    site_id: Optional[str] = None
    api_version: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    secret_id: Optional[str] = None
    allow_pat_auth: Optional[bool] = None
    allow_standard_auth: Optional[bool] = None
    skip_ssl_verify: Optional[bool] = None
    is_active: Optional[bool] = None


class TableauConfigResponse(BaseModel):
    """Tableau server config response model."""
    id: int
    name: str
    server_url: str
    site_id: Optional[str]
    api_version: Optional[str]
    client_id: Optional[str]
    client_secret: Optional[str]  # Note: In production, consider masking this
    secret_id: Optional[str]
    allow_pat_auth: Optional[bool] = False
    allow_standard_auth: Optional[bool] = False
    skip_ssl_verify: Optional[bool] = False
    is_active: bool
    created_by: Optional[int]
    created_at: str

    class Config:
        from_attributes = True


# Provider config models
class ProviderConfigCreate(BaseModel):
    """Provider config creation model."""
    name: str
    provider_type: str
    api_key: Optional[str] = None
    salesforce_client_id: Optional[str] = None
    salesforce_private_key_path: Optional[str] = None
    salesforce_username: Optional[str] = None
    salesforce_models_api_url: Optional[str] = None
    vertex_project_id: Optional[str] = None
    vertex_location: Optional[str] = None
    vertex_service_account_path: Optional[str] = None
    apple_endor_endpoint: Optional[str] = None
    apple_endor_app_id: Optional[str] = None
    apple_endor_app_password: Optional[str] = None
    apple_endor_other_app: Optional[int] = None
    apple_endor_context: Optional[str] = None
    apple_endor_one_time_token: Optional[bool] = None


class ProviderConfigUpdate(BaseModel):
    """Provider config update model."""
    name: Optional[str] = None
    provider_type: Optional[str] = None
    api_key: Optional[str] = None
    salesforce_client_id: Optional[str] = None
    salesforce_private_key_path: Optional[str] = None
    salesforce_username: Optional[str] = None
    salesforce_models_api_url: Optional[str] = None
    vertex_project_id: Optional[str] = None
    vertex_location: Optional[str] = None
    vertex_service_account_path: Optional[str] = None
    apple_endor_endpoint: Optional[str] = None
    apple_endor_app_id: Optional[str] = None
    apple_endor_app_password: Optional[str] = None
    apple_endor_other_app: Optional[int] = None
    apple_endor_context: Optional[str] = None
    apple_endor_one_time_token: Optional[bool] = None
    is_active: Optional[bool] = None


class ProviderConfigResponse(BaseModel):
    """Provider config response model."""
    id: int
    name: str
    provider_type: str
    is_active: bool
    created_by: Optional[int]
    created_at: str
    api_key: Optional[str] = None  # Note: In production, consider masking this
    salesforce_client_id: Optional[str] = None
    salesforce_private_key_path: Optional[str] = None
    salesforce_username: Optional[str] = None
    salesforce_models_api_url: Optional[str] = None
    vertex_project_id: Optional[str] = None
    vertex_location: Optional[str] = None
    vertex_service_account_path: Optional[str] = None
    apple_endor_endpoint: Optional[str] = None
    apple_endor_app_id: Optional[str] = None
    apple_endor_app_password: Optional[str] = None  # Note: In production, consider masking this
    apple_endor_other_app: Optional[int] = None
    apple_endor_context: Optional[str] = None
    apple_endor_one_time_token: Optional[bool] = None

    class Config:
        from_attributes = True


# User management endpoints
@router.get("/admin/users", response_model=List[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """List all users."""
    users = db.query(User).all()
    return [UserResponse(
        id=u.id,
        username=u.username,
        role=u.role.value,
        is_active=u.is_active,
        created_at=u.created_at.isoformat(),
        preferred_provider=u.preferred_provider,
        preferred_model=u.preferred_model,
        preferred_agent_type=u.preferred_agent_type
    ) for u in users]


@router.post("/admin/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Create a new user."""
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Validate role
    try:
        role = UserRole(user_data.role.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {user_data.role}"
        )
    
    # Create user
    new_user = User(
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        role=role,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return UserResponse(
        id=new_user.id,
        username=new_user.username,
        role=new_user.role.value,
        is_active=new_user.is_active,
        created_at=new_user.created_at.isoformat(),
        preferred_provider=new_user.preferred_provider,
        preferred_model=new_user.preferred_model,
        preferred_agent_type=new_user.preferred_agent_type
    )


@router.get("/admin/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get user by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
        preferred_provider=user.preferred_provider,
        preferred_model=user.preferred_model,
        preferred_agent_type=user.preferred_agent_type
    )


@router.put("/admin/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update username if provided
    if user_data.username is not None:
        # Check if username already exists (excluding current user)
        existing_user = db.query(User).filter(
            User.username == user_data.username,
            User.id != user_id
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        user.username = user_data.username
    
    # Update password if provided
    if user_data.password:
        user.password_hash = get_password_hash(user_data.password)
    
    # Update role if provided
    if user_data.role:
        try:
            user.role = UserRole(user_data.role.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {user_data.role}"
            )
    
    # Update is_active if provided
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
        preferred_provider=user.preferred_provider,
        preferred_model=user.preferred_model,
        preferred_agent_type=user.preferred_agent_type
    )


@router.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Permanently delete user from the database."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent deleting yourself
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Hard delete - permanently remove user from database
    # Related objects will be handled by cascade deletes:
    # - tableau_configs (cascade="all, delete-orphan")
    # - provider_configs (cascade="all, delete-orphan")
    # - tableau_server_mappings (cascade="all, delete-orphan")
    # Conversations will have user_id set to NULL (ondelete="SET NULL")
    db.delete(user)
    db.commit()


# Tableau config management endpoints
@router.get("/admin/tableau-configs", response_model=List[TableauConfigResponse])
async def list_tableau_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """List all Tableau server configurations."""
    configs = db.query(TableauServerConfig).all()
    return [TableauConfigResponse(
        id=c.id,
        name=c.name,
        server_url=c.server_url,
        site_id=c.site_id,
        api_version=getattr(c, 'api_version', None) or "3.15",  # Handle missing column gracefully
        client_id=c.client_id,
        client_secret=c.client_secret,
        secret_id=c.secret_id,
        allow_pat_auth=getattr(c, 'allow_pat_auth', False),
        allow_standard_auth=getattr(c, 'allow_standard_auth', False),
        skip_ssl_verify=getattr(c, 'skip_ssl_verify', False),
        is_active=c.is_active,
        created_by=c.created_by,
        created_at=c.created_at.isoformat()
    ) for c in configs]


@router.post("/admin/tableau-configs", response_model=TableauConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_tableau_config(
    config_data: TableauConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Create a new Tableau server configuration."""
    allow_pat = config_data.allow_pat_auth or False
    allow_standard = config_data.allow_standard_auth or False
    has_connected_app = bool((config_data.client_id or "").strip() and (config_data.client_secret or "").strip())
    if not allow_pat and not allow_standard and not has_connected_app:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either Connected App credentials (client_id and client_secret), allow_pat_auth, or allow_standard_auth must be provided"
        )
    new_config = TableauServerConfig(
        name=config_data.name,
        server_url=config_data.server_url.rstrip('/'),
        site_id=config_data.site_id or "",
        api_version=config_data.api_version or "3.15",
        client_id=(config_data.client_id or "").strip() or None,
        client_secret=(config_data.client_secret or "").strip() or None,  # TODO: Encrypt this
        secret_id=(config_data.secret_id or config_data.client_id or "").strip() or None,
        allow_pat_auth=config_data.allow_pat_auth or False,
        allow_standard_auth=config_data.allow_standard_auth or False,
        skip_ssl_verify=config_data.skip_ssl_verify or False,
        is_active=True,
        created_by=current_user.id
    )
    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    
    return TableauConfigResponse(
        id=new_config.id,
        name=new_config.name,
        server_url=new_config.server_url,
        site_id=new_config.site_id,
        api_version=getattr(new_config, 'api_version', None) or "3.15",
        client_id=new_config.client_id,
        client_secret=new_config.client_secret,
        secret_id=new_config.secret_id,
        allow_pat_auth=getattr(new_config, 'allow_pat_auth', False),
        allow_standard_auth=getattr(new_config, 'allow_standard_auth', False),
        skip_ssl_verify=getattr(new_config, 'skip_ssl_verify', False),
        is_active=new_config.is_active,
        created_by=new_config.created_by,
        created_at=new_config.created_at.isoformat()
    )


@router.get("/admin/tableau-configs/{config_id}", response_model=TableauConfigResponse)
async def get_tableau_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get Tableau server configuration by ID."""
    config = db.query(TableauServerConfig).filter(TableauServerConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    return TableauConfigResponse(
        id=config.id,
        name=config.name,
        server_url=config.server_url,
        site_id=config.site_id,
        api_version=getattr(config, 'api_version', None) or "3.15",
        client_id=config.client_id,
        client_secret=config.client_secret,
        secret_id=config.secret_id,
        allow_pat_auth=getattr(config, 'allow_pat_auth', False),
        allow_standard_auth=getattr(config, 'allow_standard_auth', False),
        skip_ssl_verify=getattr(config, 'skip_ssl_verify', False),
        is_active=config.is_active,
        created_by=config.created_by,
        created_at=config.created_at.isoformat()
    )


@router.put("/admin/tableau-configs/{config_id}", response_model=TableauConfigResponse)
async def update_tableau_config(
    config_id: int,
    config_data: TableauConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update Tableau server configuration."""
    config = db.query(TableauServerConfig).filter(TableauServerConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    if config_data.name is not None:
        config.name = config_data.name
    if config_data.server_url is not None:
        config.server_url = config_data.server_url.rstrip('/')
    if config_data.site_id is not None:
        config.site_id = config_data.site_id
    if config_data.api_version is not None:
        config.api_version = config_data.api_version
    if config_data.client_id is not None:
        config.client_id = (config_data.client_id or "").strip() or None
    if config_data.client_secret is not None:
        config.client_secret = (config_data.client_secret or "").strip() or None  # TODO: Encrypt this
    if config_data.secret_id is not None:
        config.secret_id = (config_data.secret_id or "").strip() or None
    if config_data.allow_pat_auth is not None:
        config.allow_pat_auth = config_data.allow_pat_auth
    if config_data.allow_standard_auth is not None:
        config.allow_standard_auth = config_data.allow_standard_auth
    if config_data.skip_ssl_verify is not None:
        config.skip_ssl_verify = config_data.skip_ssl_verify
    if config_data.is_active is not None:
        config.is_active = config_data.is_active

    allow_pat = getattr(config, 'allow_pat_auth', False)
    allow_standard = getattr(config, 'allow_standard_auth', False)
    has_connected_app = bool((config.client_id or "").strip() and (config.client_secret or "").strip())
    if not allow_pat and not allow_standard and not has_connected_app:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either Connected App credentials (client_id and client_secret), allow_pat_auth, or allow_standard_auth must be provided"
        )

    db.commit()
    db.refresh(config)
    
    return TableauConfigResponse(
        id=config.id,
        name=config.name,
        server_url=config.server_url,
        site_id=config.site_id,
        api_version=getattr(config, 'api_version', None) or "3.15",
        client_id=config.client_id,
        client_secret=config.client_secret,
        secret_id=config.secret_id,
        allow_pat_auth=getattr(config, 'allow_pat_auth', False),
        allow_standard_auth=getattr(config, 'allow_standard_auth', False),
        skip_ssl_verify=getattr(config, 'skip_ssl_verify', False),
        is_active=config.is_active,
        created_by=config.created_by,
        created_at=config.created_at.isoformat()
    )


@router.delete("/admin/tableau-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tableau_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Delete Tableau server configuration (soft delete)."""
    config = db.query(TableauServerConfig).filter(TableauServerConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    config.is_active = False
    db.commit()


# Provider config management endpoints
@router.get("/admin/provider-configs", response_model=List[ProviderConfigResponse])
async def list_provider_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """List all provider configurations."""
    configs = db.query(ProviderConfig).all()
    return [ProviderConfigResponse(
        id=c.id,
        name=c.name,
        provider_type=get_provider_type_value(c.provider_type),
        is_active=c.is_active,
        created_by=c.created_by,
        created_at=c.created_at.isoformat(),
        api_key=c.api_key,
        salesforce_client_id=c.salesforce_client_id,
        salesforce_private_key_path=c.salesforce_private_key_path,
        salesforce_username=c.salesforce_username,
        salesforce_models_api_url=c.salesforce_models_api_url,
        vertex_project_id=c.vertex_project_id,
        vertex_location=c.vertex_location,
        vertex_service_account_path=c.vertex_service_account_path,
        apple_endor_endpoint=c.apple_endor_endpoint,
        apple_endor_app_id=c.apple_endor_app_id,
        apple_endor_app_password=c.apple_endor_app_password,
        apple_endor_other_app=c.apple_endor_other_app,
        apple_endor_context=c.apple_endor_context,
        apple_endor_one_time_token=c.apple_endor_one_time_token,
    ) for c in configs]


@router.post("/admin/provider-configs", response_model=ProviderConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_provider_config(
    config_data: ProviderConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Create a new provider configuration."""
    # Validate provider type and get lowercase value string
    try:
        provider_type_enum = ProviderType(config_data.provider_type.lower())
        provider_type_value = provider_type_enum.value  # Get lowercase string value
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider type: {config_data.provider_type}"
        )
    
    # Apple Endor uses A3 token (App ID + App Password), not API key
    api_key_val = None if provider_type_value == "apple_endor" else config_data.api_key
    new_config = ProviderConfig(
        name=config_data.name,
        provider_type=provider_type_value,  # Pass lowercase string directly - TypeDecorator will handle it
        api_key=api_key_val,
        salesforce_client_id=config_data.salesforce_client_id,
        salesforce_private_key_path=config_data.salesforce_private_key_path,
        salesforce_username=config_data.salesforce_username,
        salesforce_models_api_url=config_data.salesforce_models_api_url,
        vertex_project_id=config_data.vertex_project_id,
        vertex_location=config_data.vertex_location,
        vertex_service_account_path=config_data.vertex_service_account_path,
        apple_endor_endpoint=config_data.apple_endor_endpoint,
        apple_endor_app_id=config_data.apple_endor_app_id,
        apple_endor_app_password=config_data.apple_endor_app_password,
        apple_endor_other_app=config_data.apple_endor_other_app,
        apple_endor_context=config_data.apple_endor_context,
        apple_endor_one_time_token=config_data.apple_endor_one_time_token,
        is_active=True,
        created_by=current_user.id
    )
    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    
    return ProviderConfigResponse(
        id=new_config.id,
        name=new_config.name,
        provider_type=get_provider_type_value(new_config.provider_type),
        is_active=new_config.is_active,
        created_by=new_config.created_by,
        created_at=new_config.created_at.isoformat(),
        api_key=new_config.api_key,
        salesforce_client_id=new_config.salesforce_client_id,
        salesforce_private_key_path=new_config.salesforce_private_key_path,
        salesforce_username=new_config.salesforce_username,
        salesforce_models_api_url=new_config.salesforce_models_api_url,
        vertex_project_id=new_config.vertex_project_id,
        vertex_location=new_config.vertex_location,
        vertex_service_account_path=new_config.vertex_service_account_path,
        apple_endor_endpoint=new_config.apple_endor_endpoint,
        apple_endor_app_id=new_config.apple_endor_app_id,
        apple_endor_app_password=new_config.apple_endor_app_password,
        apple_endor_other_app=new_config.apple_endor_other_app,
        apple_endor_context=new_config.apple_endor_context,
        apple_endor_one_time_token=new_config.apple_endor_one_time_token,
    )


@router.get("/admin/provider-configs/{config_id}", response_model=ProviderConfigResponse)
async def get_provider_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get provider configuration by ID."""
    config = db.query(ProviderConfig).filter(ProviderConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    return ProviderConfigResponse(
        id=config.id,
        name=config.name,
        provider_type=config.provider_type.value,
        is_active=config.is_active,
        created_by=config.created_by,
        created_at=config.created_at.isoformat(),
        api_key=config.api_key,
        salesforce_client_id=config.salesforce_client_id,
        salesforce_private_key_path=config.salesforce_private_key_path,
        salesforce_username=config.salesforce_username,
        salesforce_models_api_url=config.salesforce_models_api_url,
        vertex_project_id=config.vertex_project_id,
        vertex_location=config.vertex_location,
        vertex_service_account_path=config.vertex_service_account_path,
        apple_endor_endpoint=config.apple_endor_endpoint,
        apple_endor_app_id=config.apple_endor_app_id,
        apple_endor_app_password=config.apple_endor_app_password,
        apple_endor_other_app=config.apple_endor_other_app,
        apple_endor_context=config.apple_endor_context,
        apple_endor_one_time_token=config.apple_endor_one_time_token,
    )


@router.put("/admin/provider-configs/{config_id}", response_model=ProviderConfigResponse)
async def update_provider_config(
    config_id: int,
    config_data: ProviderConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update provider configuration."""
    config = db.query(ProviderConfig).filter(ProviderConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    if config_data.name is not None:
        config.name = config_data.name
    if config_data.provider_type is not None:
        try:
            provider_type_enum = ProviderType(config_data.provider_type.lower())
            config.provider_type = provider_type_enum.value  # Pass lowercase string value directly
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider type: {config_data.provider_type}"
            )
    # Apple Endor uses A3 token, not API key - ignore api_key for this provider
    if config_data.api_key is not None and config.provider_type.value != "apple_endor":
        config.api_key = config_data.api_key
    if config_data.salesforce_client_id is not None:
        config.salesforce_client_id = config_data.salesforce_client_id
    if config_data.salesforce_private_key_path is not None:
        config.salesforce_private_key_path = config_data.salesforce_private_key_path
    if config_data.salesforce_username is not None:
        config.salesforce_username = config_data.salesforce_username
    if config_data.salesforce_models_api_url is not None:
        config.salesforce_models_api_url = config_data.salesforce_models_api_url
    if config_data.vertex_project_id is not None:
        config.vertex_project_id = config_data.vertex_project_id
    if config_data.vertex_location is not None:
        config.vertex_location = config_data.vertex_location
    if config_data.vertex_service_account_path is not None:
        config.vertex_service_account_path = config_data.vertex_service_account_path
    if config_data.apple_endor_endpoint is not None:
        config.apple_endor_endpoint = config_data.apple_endor_endpoint
    if config_data.apple_endor_app_id is not None:
        config.apple_endor_app_id = config_data.apple_endor_app_id
    if config_data.apple_endor_app_password is not None:
        config.apple_endor_app_password = config_data.apple_endor_app_password
    if config_data.apple_endor_other_app is not None:
        config.apple_endor_other_app = config_data.apple_endor_other_app
    if config_data.apple_endor_context is not None:
        config.apple_endor_context = config_data.apple_endor_context
    if config_data.apple_endor_one_time_token is not None:
        config.apple_endor_one_time_token = config_data.apple_endor_one_time_token
    if config_data.is_active is not None:
        config.is_active = config_data.is_active
    
    db.commit()
    db.refresh(config)
    
    return ProviderConfigResponse(
        id=config.id,
        name=config.name,
        provider_type=config.provider_type.value,
        is_active=config.is_active,
        created_by=config.created_by,
        created_at=config.created_at.isoformat(),
        api_key=config.api_key,
        salesforce_client_id=config.salesforce_client_id,
        salesforce_private_key_path=config.salesforce_private_key_path,
        salesforce_username=config.salesforce_username,
        salesforce_models_api_url=config.salesforce_models_api_url,
        vertex_project_id=config.vertex_project_id,
        vertex_location=config.vertex_location,
        vertex_service_account_path=config.vertex_service_account_path,
        apple_endor_endpoint=config.apple_endor_endpoint,
        apple_endor_app_id=config.apple_endor_app_id,
        apple_endor_app_password=config.apple_endor_app_password,
        apple_endor_other_app=config.apple_endor_other_app,
        apple_endor_context=config.apple_endor_context,
        apple_endor_one_time_token=config.apple_endor_one_time_token,
    )


@router.delete("/admin/provider-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Delete provider configuration (soft delete)."""
    config = db.query(ProviderConfig).filter(ProviderConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    config.is_active = False
    db.commit()


# Feedback management models
class ContextObjectResponse(BaseModel):
    """Context object response model."""
    object_id: str
    object_type: str
    object_name: Optional[str] = None
    added_at: str

    class Config:
        from_attributes = True


class ConversationMessageResponse(BaseModel):
    """Conversation message response model."""
    id: int
    role: str
    content: str
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    total_time_ms: Optional[float] = None
    created_at: str

    class Config:
        from_attributes = True


class UserInfoResponse(BaseModel):
    """User info response model."""
    id: int
    username: str
    role: str

    class Config:
        from_attributes = True


class FeedbackDetailResponse(BaseModel):
    """Feedback detail response model."""
    message_id: int
    conversation_id: int
    role: str
    content: str
    feedback: str
    feedback_text: Optional[str] = None
    agent_type: Optional[str] = None
    total_time_ms: Optional[float]
    model_used: Optional[str]
    created_at: str
    conversation_name: Optional[str] = None
    user: Optional[UserInfoResponse] = None
    context_objects: List[ContextObjectResponse] = []
    conversation_thread: List[ConversationMessageResponse] = []

    class Config:
        from_attributes = True


# Feedback management endpoints
@router.get("/admin/feedback", response_model=List[FeedbackDetailResponse])
async def list_feedback(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
    feedback_type: Optional[str] = Query(None, description="Filter by feedback type: 'thumbs_up' or 'thumbs_down'")
):
    """List all messages with feedback, including user info, context objects, and full conversation thread."""
    query = db.query(Message).filter(Message.feedback.isnot(None))
    
    if feedback_type:
        query = query.filter(Message.feedback == feedback_type)
    
    messages = query.order_by(Message.created_at.desc()).all()
    
    # Get conversation names and related data
    conversation_ids = {msg.conversation_id for msg in messages}
    conversations = {conv.id: conv for conv in db.query(Conversation).filter(Conversation.id.in_(conversation_ids)).all()}
    
    # Get all context objects for these conversations
    context_objects_map = {}
    all_contexts = db.query(ChatContext).filter(ChatContext.conversation_id.in_(conversation_ids)).all()
    for ctx in all_contexts:
        if ctx.conversation_id not in context_objects_map:
            context_objects_map[ctx.conversation_id] = []
        context_objects_map[ctx.conversation_id].append(ctx)
    
    # Get all messages for these conversations (full thread)
    all_messages_map = {}
    all_thread_messages = db.query(Message).filter(Message.conversation_id.in_(conversation_ids)).order_by(Message.created_at).all()
    for msg in all_thread_messages:
        if msg.conversation_id not in all_messages_map:
            all_messages_map[msg.conversation_id] = []
        all_messages_map[msg.conversation_id].append(msg)
    
    # Fetch user information for conversations that have user_id
    user_ids = {conv.user_id for conv in conversations.values() if conv and conv.user_id}
    users_map = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        users_map = {user.id: user for user in users}
    
    result = []
    for msg in messages:
        conv = conversations.get(msg.conversation_id)
        conversation_name = conv.get_display_name() if conv else f"Conversation {msg.conversation_id}"
        
        role_value = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)
        content_preview = msg.content[:500] + '...' if len(msg.content) > 500 else msg.content
        
        # Get context objects for this conversation
        context_objects = context_objects_map.get(msg.conversation_id, [])
        context_responses = [
            ContextObjectResponse(
                object_id=ctx.object_id,
                object_type=ctx.object_type,
                object_name=ctx.object_name,
                added_at=ctx.added_at.isoformat()
            )
            for ctx in context_objects
        ]
        
        # Get full conversation thread
        thread_messages = all_messages_map.get(msg.conversation_id, [])
        thread_responses = [
            ConversationMessageResponse(
                id=m.id,
                role=m.role.value if hasattr(m.role, 'value') else str(m.role),
                content=m.content,
                model_used=m.model_used,
                tokens_used=m.tokens_used,
                total_time_ms=m.total_time_ms,
                created_at=m.created_at.isoformat()
            )
            for m in thread_messages
        ]
        
        # Extract agent_type from extra_metadata if available
        agent_type = None
        if msg.extra_metadata and isinstance(msg.extra_metadata, dict):
            agent_type = msg.extra_metadata.get('agent_type')
        
        # Get user info from conversation
        user_info = None
        if conv and conv.user_id and conv.user_id in users_map:
            user = users_map[conv.user_id]
            user_info = UserInfoResponse(
                id=user.id,
                username=user.username,
                role=user.role.value
            )
        
        result.append(FeedbackDetailResponse(
            message_id=msg.id,
            conversation_id=msg.conversation_id,
            role=role_value,
            content=content_preview,
            feedback=msg.feedback,
            feedback_text=msg.feedback_text,
            agent_type=agent_type,
            total_time_ms=msg.total_time_ms,
            model_used=msg.model_used,
            created_at=msg.created_at.isoformat(),
            conversation_name=conversation_name,
            user=user_info,
            context_objects=context_responses,
            conversation_thread=thread_responses
        ))
    
    return result


# User-Tableau Server Mapping endpoints
class UserTableauMappingCreate(BaseModel):
    """User-Tableau server mapping creation model."""
    user_id: int
    tableau_server_config_id: int
    tableau_username: str
    # Note: site_id comes from the Tableau Connected App configuration, not from user input


class UserTableauMappingUpdate(BaseModel):
    """User-Tableau server mapping update model."""
    tableau_username: str
    # Note: site_id comes from the Tableau Connected App configuration, not from user input


class UserTableauMappingResponse(BaseModel):
    """User-Tableau server mapping response model."""
    id: int
    user_id: int
    tableau_server_config_id: int
    tableau_username: str
    created_at: str
    updated_at: str
    # Note: site_id is not included as it comes from the Connected App configuration

    class Config:
        from_attributes = True


@router.get("/admin/users/{user_id}/tableau-mappings", response_model=List[UserTableauMappingResponse])
async def list_user_tableau_mappings(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """List all Tableau server mappings for a user."""
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    mappings = db.query(UserTableauServerMapping).filter(
        UserTableauServerMapping.user_id == user_id
    ).all()
    
    return [UserTableauMappingResponse(
        id=m.id,
        user_id=m.user_id,
        tableau_server_config_id=m.tableau_server_config_id,
        tableau_username=m.tableau_username,
        created_at=m.created_at.isoformat(),
        updated_at=m.updated_at.isoformat()
    ) for m in mappings]


@router.post("/admin/users/{user_id}/tableau-mappings", response_model=UserTableauMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_user_tableau_mapping(
    user_id: int,
    mapping_data: UserTableauMappingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Create a new user-Tableau server mapping."""
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify tableau server config exists
    config = db.query(TableauServerConfig).filter(
        TableauServerConfig.id == mapping_data.tableau_server_config_id
    ).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tableau server configuration not found"
        )
    
    # Check if mapping already exists for this user/Connected App combination
    # Site ID comes from the config, so we only need to check user_id + config_id
    existing = db.query(UserTableauServerMapping).filter(
        UserTableauServerMapping.user_id == user_id,
        UserTableauServerMapping.tableau_server_config_id == mapping_data.tableau_server_config_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mapping already exists for this user and Connected App configuration"
        )
    
    # Create mapping (site_id comes from config, not stored in mapping table)
    new_mapping = UserTableauServerMapping(
        user_id=user_id,
        tableau_server_config_id=mapping_data.tableau_server_config_id,
        tableau_username=mapping_data.tableau_username
    )
    db.add(new_mapping)
    db.commit()
    db.refresh(new_mapping)
    
    return UserTableauMappingResponse(
        id=new_mapping.id,
        user_id=new_mapping.user_id,
        tableau_server_config_id=new_mapping.tableau_server_config_id,
        tableau_username=new_mapping.tableau_username,
        created_at=new_mapping.created_at.isoformat(),
        updated_at=new_mapping.updated_at.isoformat()
    )


@router.put("/admin/users/{user_id}/tableau-mappings/{mapping_id}", response_model=UserTableauMappingResponse)
async def update_user_tableau_mapping(
    user_id: int,
    mapping_id: int,
    mapping_data: UserTableauMappingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update a user-Tableau server mapping."""
    mapping = db.query(UserTableauServerMapping).filter(
        UserTableauServerMapping.id == mapping_id,
        UserTableauServerMapping.user_id == user_id
    ).first()
    
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mapping not found"
        )
    
    # Update tableau username
    # Note: site_id comes from the config, not from the update request
    mapping.tableau_username = mapping_data.tableau_username
    db.commit()
    db.refresh(mapping)
    
    return UserTableauMappingResponse(
        id=mapping.id,
        user_id=mapping.user_id,
        tableau_server_config_id=mapping.tableau_server_config_id,
        tableau_username=mapping.tableau_username,
        created_at=mapping.created_at.isoformat(),
        updated_at=mapping.updated_at.isoformat()
    )


@router.delete("/admin/users/{user_id}/tableau-mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_tableau_mapping(
    user_id: int,
    mapping_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Delete a user-Tableau server mapping."""
    mapping = db.query(UserTableauServerMapping).filter(
        UserTableauServerMapping.id == mapping_id,
        UserTableauServerMapping.user_id == user_id
    ).first()
    
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mapping not found"
        )
    
    db.delete(mapping)
    db.commit()
    
    return None


# Auth Configuration models
class AuthConfigResponse(BaseModel):
    """Auth configuration response model."""
    id: int
    enable_password_auth: bool
    enable_oauth_auth: bool
    auth0_domain: Optional[str] = None
    auth0_client_id: Optional[str] = None
    auth0_client_secret: Optional[str] = None  # Note: Only returned to admins
    auth0_audience: Optional[str] = None
    auth0_issuer: Optional[str] = None
    auth0_tableau_metadata_field: Optional[str] = None
    updated_by: Optional[int] = None
    updated_at: str
    created_at: str


class AuthConfigUpdate(BaseModel):
    """Auth configuration update model."""
    enable_password_auth: Optional[bool] = None
    enable_oauth_auth: Optional[bool] = None
    auth0_domain: Optional[str] = None
    auth0_client_id: Optional[str] = None
    auth0_client_secret: Optional[str] = None
    auth0_audience: Optional[str] = None
    auth0_issuer: Optional[str] = None
    auth0_tableau_metadata_field: Optional[str] = None


# Agent management
@router.get("/admin/agents")
async def list_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """List all agents with their versions."""
    service = AgentConfigService(db)
    agents = service.get_all_agents()
    return agents


@router.get("/admin/agents/{agent_name}/settings", response_model=AgentSettingsResponse)
async def get_agent_settings(
    agent_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get agent-level settings (e.g. retry config for vizql)."""
    service = AgentConfigService(db)
    settings_dict = service.get_agent_settings(agent_name)
    return AgentSettingsResponse(
        agent_name=agent_name,
        max_build_retries=settings_dict.get('max_build_retries'),
        max_execution_retries=settings_dict.get('max_execution_retries')
    )


class ActiveVersionUpdate(BaseModel):
    """Request model for setting active agent version."""
    version: str


@router.put("/admin/agents/{agent_name}/active-version", response_model=AgentVersionResponse)
async def set_active_agent_version(
    agent_name: str,
    body: ActiveVersionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Set the active version for an agent. Only one version can be active at a time."""
    service = AgentConfigService(db)
    try:
        updated = service.set_active_version(agent_name=agent_name, version=body.version)
        return AgentVersionResponse(
            version=updated.version,
            is_enabled=updated.is_enabled,
            is_default=updated.is_default,
            description=updated.description
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/admin/agents/{agent_name}/settings", response_model=AgentSettingsResponse)
async def update_agent_settings(
    agent_name: str,
    settings_data: AgentSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update agent-level settings (retry config)."""
    service = AgentConfigService(db)
    updated = service.update_agent_settings(
        agent_name=agent_name,
        max_build_retries=settings_data.max_build_retries,
        max_execution_retries=settings_data.max_execution_retries
    )
    return AgentSettingsResponse(
        agent_name=agent_name,
        max_build_retries=updated.max_build_retries,
        max_execution_retries=updated.max_execution_retries
    )


@router.get("/admin/auth-config", response_model=AuthConfigResponse)
async def get_auth_config_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get current authentication configuration."""
    config = get_auth_config(db)
    return AuthConfigResponse(
        id=config.id,
        enable_password_auth=config.enable_password_auth,
        enable_oauth_auth=config.enable_oauth_auth,
        auth0_domain=config.auth0_domain,
        auth0_client_id=config.auth0_client_id,
        auth0_client_secret=config.auth0_client_secret,
        auth0_audience=config.auth0_audience,
        auth0_issuer=config.auth0_issuer,
        auth0_tableau_metadata_field=config.auth0_tableau_metadata_field,
        updated_by=config.updated_by,
        updated_at=config.updated_at.isoformat(),
        created_at=config.created_at.isoformat()
    )


@router.put("/admin/auth-config", response_model=AuthConfigResponse)
async def update_auth_config_endpoint(
    config_data: AuthConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update authentication configuration."""
    # Validate that at least one auth method is enabled
    enable_password = config_data.enable_password_auth
    enable_oauth = config_data.enable_oauth_auth
    
    # Get current config to check what's being changed
    current_config = get_auth_config(db, use_cache=False)
    
    if enable_password is None:
        enable_password = current_config.enable_password_auth
    if enable_oauth is None:
        enable_oauth = current_config.enable_oauth_auth
    
    if not enable_password and not enable_oauth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one authentication method must be enabled"
        )
    
    # Validate OAuth config if enabling OAuth
    if enable_oauth:
        if not config_data.auth0_domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="auth0_domain is required when OAuth authentication is enabled"
            )
        if not config_data.auth0_audience:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="auth0_audience is required when OAuth authentication is enabled"
            )
    
    # Update configuration
    config = update_auth_config(
        db,
        enable_password_auth=enable_password,
        enable_oauth_auth=enable_oauth,
        auth0_domain=config_data.auth0_domain,
        auth0_client_id=config_data.auth0_client_id,
        auth0_client_secret=config_data.auth0_client_secret,
        auth0_audience=config_data.auth0_audience,
        auth0_issuer=config_data.auth0_issuer,
        auth0_tableau_metadata_field=config_data.auth0_tableau_metadata_field,
        updated_by=current_user.id
    )
    
    return AuthConfigResponse(
        id=config.id,
        enable_password_auth=config.enable_password_auth,
        enable_oauth_auth=config.enable_oauth_auth,
        auth0_domain=config.auth0_domain,
        auth0_client_id=config.auth0_client_id,
        auth0_client_secret=config.auth0_client_secret,
        auth0_audience=config.auth0_audience,
        auth0_issuer=config.auth0_issuer,
        auth0_tableau_metadata_field=config.auth0_tableau_metadata_field,
        updated_by=config.updated_by,
        updated_at=config.updated_at.isoformat(),
        created_at=config.created_at.isoformat()
    )
