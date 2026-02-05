"""User and authentication models."""
from datetime import datetime, timezone
import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index, Enum as SQLEnum, ForeignKey, Text, TypeDecorator
from sqlalchemy.orm import relationship
from app.core.database import Base


class UserRole(str, enum.Enum):
    """User role enumeration."""
    ADMIN = "ADMIN"
    USER = "USER"


class ProviderType(str, enum.Enum):
    """AI provider type enumeration."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    SALESFORCE = "salesforce"
    VERTEX = "vertex"
    APPLE_ENDOR = "apple_endor"


class ProviderTypeType(TypeDecorator):
    """Custom type decorator to handle enum values - ensures lowercase values are used."""
    impl = String(20)
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        """Convert enum to lowercase string value when binding to database."""
        if value is None:
            return None
        if isinstance(value, ProviderType):
            # Return the enum value which is lowercase
            return value.value
        if isinstance(value, str):
            # Normalize to lowercase and validate
            lower_value = value.lower()
            # Validate it's a valid provider type
            valid_values = [p.value for p in ProviderType]
            if lower_value not in valid_values:
                raise ValueError(f"Invalid provider type: {value}. Valid values: {valid_values}")
            return lower_value
        # Convert to string and normalize
        str_value = str(value).lower()
        valid_values = [p.value for p in ProviderType]
        if str_value not in valid_values:
            raise ValueError(f"Invalid provider type: {value}")
        return str_value
    
    def process_result_value(self, value, dialect):
        """Convert database value back to enum when loading."""
        if value is None:
            return None
        if isinstance(value, ProviderType):
            return value
        # Convert string to enum - handle both uppercase and lowercase
        if isinstance(value, str):
            lower_value = value.lower()
            try:
                return ProviderType(lower_value)
            except ValueError:
                # Try to find matching enum by value
                for provider in ProviderType:
                    if provider.value == lower_value:
                        return provider
        return value


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole, name="user_role", native_enum=True), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    tableau_configs = relationship("TableauServerConfig", back_populates="created_by_user", cascade="all, delete-orphan")
    provider_configs = relationship("ProviderConfig", back_populates="created_by_user", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_user_username_active", "username", "is_active"),
    )

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"


class TableauServerConfig(Base):
    """Tableau server configuration model."""
    __tablename__ = "tableau_server_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, comment="Display name for this configuration")
    server_url = Column(String(500), nullable=False)
    site_id = Column(String(100), nullable=True, comment="Site content URL (empty string for default site)")
    api_version = Column(String(20), nullable=True, default="3.15", comment="Tableau REST API version (e.g., 3.15, 3.22)")
    client_id = Column(String(255), nullable=False, comment="Connected App client ID")
    client_secret = Column(String(500), nullable=False, comment="Connected App secret (encrypted)")
    secret_id = Column(String(255), nullable=True, comment="Secret ID for JWT 'kid' header (defaults to client_id)")
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    created_by_user = relationship("User", back_populates="tableau_configs")

    # Indexes
    __table_args__ = (
        Index("idx_tableau_config_server_site", "server_url", "site_id"),
        Index("idx_tableau_config_active", "is_active"),
    )

    def __repr__(self):
        return f"<TableauServerConfig(id={self.id}, name={self.name}, server_url={self.server_url}, site_id={self.site_id})>"


class ProviderConfig(Base):
    """AI provider configuration model."""
    __tablename__ = "provider_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, comment="Display name for this configuration")
    provider_type = Column(ProviderTypeType(), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Common fields
    api_key = Column(String(500), nullable=True, comment="API key (for OpenAI, Anthropic, Apple Endor)")
    
    # Salesforce specific
    salesforce_client_id = Column(String(255), nullable=True, comment="Salesforce Connected App client ID")
    salesforce_private_key_path = Column(String(500), nullable=True, comment="Path to Salesforce private key file")
    salesforce_username = Column(String(255), nullable=True, comment="Salesforce username/service account")
    salesforce_models_api_url = Column(String(500), nullable=True, comment="Salesforce Models API URL")
    
    # Vertex AI specific
    vertex_project_id = Column(String(255), nullable=True, comment="GCP project ID")
    vertex_location = Column(String(100), nullable=True, comment="GCP location/region")
    vertex_service_account_path = Column(String(500), nullable=True, comment="Path to Vertex service account JSON")
    
    # Apple Endor specific
    apple_endor_endpoint = Column(String(500), nullable=True, comment="Apple Endor API endpoint URL")
    
    # Relationships
    created_by_user = relationship("User", back_populates="provider_configs")

    # Indexes
    __table_args__ = (
        Index("idx_provider_config_type_active", "provider_type", "is_active"),
    )

    def __repr__(self):
        return f"<ProviderConfig(id={self.id}, name={self.name}, provider_type={self.provider_type.value})>"
