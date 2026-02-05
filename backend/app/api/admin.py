"""Admin API endpoints."""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import get_password_hash
from app.api.auth import get_current_admin_user
from app.models.user import User, UserRole, TableauServerConfig, ProviderConfig, ProviderType
from app.models.chat import Message, Conversation, ChatContext


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

    class Config:
        from_attributes = True


# Tableau config models
class TableauConfigCreate(BaseModel):
    """Tableau server config creation model."""
    name: str
    server_url: str
    site_id: Optional[str] = None
    api_version: Optional[str] = "3.15"
    client_id: str
    client_secret: str
    secret_id: Optional[str] = None


class TableauConfigUpdate(BaseModel):
    """Tableau server config update model."""
    name: Optional[str] = None
    server_url: Optional[str] = None
    site_id: Optional[str] = None
    api_version: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    secret_id: Optional[str] = None
    is_active: Optional[bool] = None


class TableauConfigResponse(BaseModel):
    """Tableau server config response model."""
    id: int
    name: str
    server_url: str
    site_id: Optional[str]
    api_version: Optional[str]
    client_id: str
    client_secret: str  # Note: In production, consider masking this
    secret_id: Optional[str]
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
        created_at=u.created_at.isoformat()
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
        created_at=new_user.created_at.isoformat()
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
        created_at=user.created_at.isoformat()
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
        created_at=user.created_at.isoformat()
    )


@router.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Delete user (soft delete by setting is_active=False)."""
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
    
    user.is_active = False
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
    new_config = TableauServerConfig(
        name=config_data.name,
        server_url=config_data.server_url.rstrip('/'),
        site_id=config_data.site_id or "",
        api_version=config_data.api_version or "3.15",
        client_id=config_data.client_id,
        client_secret=config_data.client_secret,  # TODO: Encrypt this
        secret_id=config_data.secret_id or config_data.client_id,
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
        config.client_id = config_data.client_id
    if config_data.client_secret is not None:
        config.client_secret = config_data.client_secret  # TODO: Encrypt this
    if config_data.secret_id is not None:
        config.secret_id = config_data.secret_id
    if config_data.is_active is not None:
        config.is_active = config_data.is_active
    
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
    
    new_config = ProviderConfig(
        name=config_data.name,
        provider_type=provider_type_value,  # Pass lowercase string directly - TypeDecorator will handle it
        api_key=config_data.api_key,
        salesforce_client_id=config_data.salesforce_client_id,
        salesforce_private_key_path=config_data.salesforce_private_key_path,
        salesforce_username=config_data.salesforce_username,
        salesforce_models_api_url=config_data.salesforce_models_api_url,
        vertex_project_id=config_data.vertex_project_id,
        vertex_location=config_data.vertex_location,
        vertex_service_account_path=config_data.vertex_service_account_path,
        apple_endor_endpoint=config_data.apple_endor_endpoint,
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
    if config_data.api_key is not None:
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
    
    # Note: Conversations don't have a direct user_id field, so we can't determine the user
    # This would require adding a user_id field to Conversation model or tracking it via sessions
    # For now, user will be None
    
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
        
        result.append(FeedbackDetailResponse(
            message_id=msg.id,
            conversation_id=msg.conversation_id,
            role=role_value,
            content=content_preview,
            feedback=msg.feedback,
            total_time_ms=msg.total_time_ms,
            model_used=msg.model_used,
            created_at=msg.created_at.isoformat(),
            conversation_name=conversation_name,
            user=None,  # Not available without user_id in Conversation model
            context_objects=context_responses,
            conversation_thread=thread_responses
        ))
    
    return result
