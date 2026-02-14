"""User and authentication models."""
from datetime import datetime, timezone
import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index, Enum as SQLEnum, ForeignKey, Text, TypeDecorator, UniqueConstraint
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
            # Backward compatibility: 'apple' -> 'apple_endor'
            if lower_value == 'apple':
                lower_value = 'apple_endor'
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
            # Backward compatibility: 'apple' -> 'apple_endor'
            if lower_value == 'apple':
                lower_value = 'apple_endor'
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
    password_hash = Column(String(255), nullable=True)  # Nullable for Auth0 users
    role = Column(SQLEnum(UserRole, name="user_role", native_enum=True), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Auth0 integration (MVP)
    auth0_user_id = Column(String(255), unique=True, nullable=True, index=True, comment="Auth0 user ID (sub claim)")
    tableau_username = Column(String(255), nullable=True, comment="Tableau username extracted from Auth0 metadata")
    
    # User preferences for AI agent
    preferred_provider = Column(String(50), nullable=True, comment="Preferred AI provider (e.g., 'openai', 'anthropic')")
    preferred_model = Column(String(100), nullable=True, comment="Preferred AI model (e.g., 'gpt-4', 'claude-3-opus')")
    preferred_agent_type = Column(String(50), nullable=True, comment="Preferred agent type ('general', 'vizql', 'summary')")
    preferred_tableau_auth_type = Column(String(50), nullable=True, comment="Preferred Tableau auth: connected_app, connected_app_oauth, pat, standard")

    # Relationships
    tableau_configs = relationship("TableauServerConfig", back_populates="created_by_user", cascade="all, delete-orphan")
    provider_configs = relationship("ProviderConfig", back_populates="created_by_user", cascade="all, delete-orphan")
    tableau_server_mappings = relationship("UserTableauServerMapping", back_populates="user", cascade="all, delete-orphan")
    tableau_pats = relationship("UserTableauPAT", back_populates="user", cascade="all, delete-orphan")
    tableau_passwords = relationship("UserTableauPassword", back_populates="user", cascade="all, delete-orphan")
    tableau_auth_preferences = relationship("UserTableauAuthPreference", back_populates="user", cascade="all, delete-orphan")

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
    client_id = Column(String(255), nullable=True, comment="Connected App client ID (optional when allow_pat_auth)")
    client_secret = Column(String(500), nullable=True, comment="Connected App secret (optional when allow_pat_auth)")
    secret_id = Column(String(255), nullable=True, comment="Secret ID for JWT 'kid' header (defaults to client_id)")
    allow_pat_auth = Column(Boolean, default=False, nullable=False, comment="Allow users to authenticate with Personal Access Token")
    allow_standard_auth = Column(Boolean, default=False, nullable=False, comment="Allow users to authenticate with username and password")
    allow_connected_app_oauth = Column(Boolean, default=False, nullable=False, comment="Allow OAuth 2.0 Trust (EAS-issued JWT)")
    eas_issuer_url = Column(String(500), nullable=True, comment="EAS issuer URL (e.g. https://tenant.auth0.com/)")
    eas_client_id = Column(String(255), nullable=True, comment="OAuth client ID at EAS")
    eas_client_secret = Column(String(500), nullable=True, comment="EAS client secret (encrypted at rest)")
    eas_authorization_endpoint = Column(String(500), nullable=True, comment="EAS authorize endpoint (optional, from discovery)")
    eas_token_endpoint = Column(String(500), nullable=True, comment="EAS token endpoint (optional, from discovery)")
    eas_sub_claim_field = Column(String(100), nullable=True, comment="Auth0 claim/field for JWT sub (e.g. email, tableau_username, name). Passed to authorize URL.")
    skip_ssl_verify = Column(Boolean, default=False, nullable=False, comment="Skip SSL certificate verification for Tableau API calls")
    # ssl_cert_path will be added by migration ae_add_unique_server_url_and_ssl_cert_path
    # Temporarily commented out until migration runs to avoid SQLAlchemy errors
    # Uncomment after running: alembic upgrade head
    # ssl_cert_path = Column(String(500), nullable=True, comment="Path to SSL certificate file (.pem or .crt) for verifying Tableau server certificate")
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    created_by_user = relationship("User", back_populates="tableau_configs")
    user_mappings = relationship("UserTableauServerMapping", back_populates="tableau_server_config", cascade="all, delete-orphan")
    user_pats = relationship("UserTableauPAT", back_populates="tableau_config", cascade="all, delete-orphan")
    user_passwords = relationship("UserTableauPassword", back_populates="tableau_config", cascade="all, delete-orphan")
    user_auth_preferences = relationship("UserTableauAuthPreference", back_populates="tableau_config", cascade="all, delete-orphan")

    # Indexes and constraints
    __table_args__ = (
        Index("idx_tableau_config_server_site", "server_url", "site_id"),
        Index("idx_tableau_config_active", "is_active"),
        # Unique constraint: server_url is the unique identifier for a Tableau server
        # Normalized to lowercase with trailing slash removed
        UniqueConstraint("server_url", name="uq_tableau_server_config_server_url"),
    )

    def __repr__(self):
        return f"<TableauServerConfig(id={self.id}, name={self.name}, server_url={self.server_url}, site_id={self.site_id})>"


class UserTableauServerMapping(Base):
    """Mapping between users and Tableau Connected App configurations with custom username."""
    __tablename__ = "user_tableau_server_mappings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tableau_server_config_id = Column(Integer, ForeignKey("tableau_server_configs.id"), nullable=False, index=True)
    tableau_username = Column(String(255), nullable=False, comment="Tableau server username to use for this user/Connected App combination. Site ID comes from the Connected App configuration.")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="tableau_server_mappings")
    tableau_server_config = relationship("TableauServerConfig", back_populates="user_mappings")

    # Indexes
    # Unique constraint: one mapping per user per Connected App (site comes from config)
    __table_args__ = (
        Index("idx_user_tableau_mapping_unique", "user_id", "tableau_server_config_id", unique=True),
    )

    def __repr__(self):
        return f"<UserTableauServerMapping(id={self.id}, user_id={self.user_id}, tableau_server_config_id={self.tableau_server_config_id}, tableau_username={self.tableau_username})>"


class UserTableauPAT(Base):
    """User's Personal Access Token for Tableau Server."""
    __tablename__ = "user_tableau_pats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tableau_server_config_id = Column(Integer, ForeignKey("tableau_server_configs.id"), nullable=False, index=True)
    pat_name = Column(String(255), nullable=False, comment="PAT name for identification")
    pat_secret = Column(Text, nullable=False, comment="Encrypted PAT secret")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="tableau_pats")
    tableau_config = relationship("TableauServerConfig", back_populates="user_pats")

    __table_args__ = (
        UniqueConstraint('user_id', 'tableau_server_config_id', name='uq_user_tableau_pat'),
    )

    def __repr__(self):
        return f"<UserTableauPAT(id={self.id}, user_id={self.user_id}, tableau_server_config_id={self.tableau_server_config_id}, pat_name={self.pat_name})>"


class UserTableauPassword(Base):
    """User's Tableau username/password for standard authentication."""
    __tablename__ = "user_tableau_passwords"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tableau_server_config_id = Column(Integer, ForeignKey("tableau_server_configs.id"), nullable=False, index=True)
    tableau_username = Column(String(255), nullable=False, comment="Tableau username")
    password_encrypted = Column(Text, nullable=False, comment="Encrypted Tableau password")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="tableau_passwords")
    tableau_config = relationship("TableauServerConfig", back_populates="user_passwords")

    __table_args__ = (
        UniqueConstraint('user_id', 'tableau_server_config_id', name='uq_user_tableau_password'),
    )

    def __repr__(self):
        return f"<UserTableauPassword(id={self.id}, user_id={self.user_id}, tableau_server_config_id={self.tableau_server_config_id})>"


class UserTableauAuthPreference(Base):
    """User's preferred authentication method per Tableau server."""
    __tablename__ = "user_tableau_auth_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tableau_server_config_id = Column(Integer, ForeignKey("tableau_server_configs.id"), nullable=False, index=True)
    preferred_auth_type = Column(String(50), nullable=False, comment="Preferred Tableau auth: connected_app, connected_app_oauth, pat, standard")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="tableau_auth_preferences")
    tableau_config = relationship("TableauServerConfig", back_populates="user_auth_preferences")

    __table_args__ = (
        UniqueConstraint('user_id', 'tableau_server_config_id', name='uq_user_tableau_auth_preference'),
    )

    def __repr__(self):
        return f"<UserTableauAuthPreference(id={self.id}, user_id={self.user_id}, tableau_server_config_id={self.tableau_server_config_id}, preferred_auth_type={self.preferred_auth_type})>"


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
    api_key = Column(String(500), nullable=True, comment="API key (for OpenAI, Anthropic; not used by Apple Endor)")
    
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
    apple_endor_app_id = Column(String(255), nullable=True, comment="Apple Endor App ID for A3 token generation")
    apple_endor_app_password = Column(String(500), nullable=True, comment="Apple Endor App Password for A3 token generation")
    apple_endor_other_app = Column(Integer, nullable=True, comment="Apple Endor otherApp parameter (default: 199323)")
    apple_endor_context = Column(String(100), nullable=True, comment="Apple Endor context parameter (default: 'endor')")
    apple_endor_one_time_token = Column(Boolean, nullable=True, default=False, comment="Apple Endor oneTimeToken flag")
    apple_endor_verify_ssl = Column(Boolean, nullable=True, comment="Verify SSL for idmsac.corp.apple.com; False if corp certs not in trust store")
    
    # Relationships
    created_by_user = relationship("User", back_populates="provider_configs")

    # Indexes
    __table_args__ = (
        Index("idx_provider_config_type_active", "provider_type", "is_active"),
    )

    def __repr__(self):
        return f"<ProviderConfig(id={self.id}, name={self.name}, provider_type={self.provider_type.value})>"


class AuthConfig(Base):
    """Authentication configuration model - stores system-wide auth settings."""
    __tablename__ = "auth_configs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Authentication methods enabled
    enable_password_auth = Column(Boolean, default=True, nullable=False, comment="Enable username/password authentication")
    enable_oauth_auth = Column(Boolean, default=False, nullable=False, comment="Enable OAuth (Auth0) authentication")
    
    # Auth0 OAuth configuration
    auth0_domain = Column(String(255), nullable=True, comment="Auth0 tenant domain (e.g., your-tenant.auth0.com)")
    auth0_client_id = Column(String(255), nullable=True, comment="Auth0 SPA client ID (public, safe to store in DB)")
    auth0_client_secret = Column(String(512), nullable=True, comment="Auth0 client secret (for server-side token exchange, optional for SPAs)")
    auth0_audience = Column(String(255), nullable=True, comment="Auth0 API audience identifier")
    auth0_issuer = Column(String(255), nullable=True, comment="Auth0 issuer URL")
    auth0_tableau_metadata_field = Column(String(255), nullable=True, comment="Auth0 metadata field name to extract Tableau username (e.g., 'app_metadata.tableau_username' or 'tableau_username')")

    # App / OAuth config (overrides .env when set)
    backend_api_url = Column(String(500), nullable=True, comment="Backend API URL for OAuth callback and EAS issuer")
    tableau_oauth_frontend_redirect = Column(String(500), nullable=True, comment="Frontend URL for OAuth redirect after connect")
    eas_jwt_key_pem_encrypted = Column(Text(), nullable=True, comment="Encrypted RSA private key PEM for EAS JWT signing")

    # App config (CORS, gateway, MCP, Redis)
    cors_origins = Column(String(500), nullable=True, comment="CORS allowed origins (comma-separated)")
    gateway_enabled = Column(Boolean, nullable=True, comment="Enable embedded gateway")
    mcp_server_name = Column(String(100), nullable=True, comment="MCP server name (default: tableau-ai-demo-mcp)")
    mcp_transport = Column(String(20), nullable=True, comment="MCP transport: stdio or sse")
    mcp_log_level = Column(String(20), nullable=True, comment="MCP log level")
    redis_token_ttl = Column(Integer, nullable=True, comment="Redis token cache TTL in seconds")

    # Metadata
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    updated_by_user = relationship("User", foreign_keys=[updated_by])

    # Indexes - only one active config
    __table_args__ = (
        Index("idx_auth_config_active", "enable_password_auth", "enable_oauth_auth"),
    )

    def __repr__(self):
        return f"<AuthConfig(id={self.id}, password={self.enable_password_auth}, oauth={self.enable_oauth_auth})>"
