"""Gateway router for unified LLM provider routing."""
import json
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ProviderContext:
    """Context information for a provider."""
    provider: str  # "openai", "anthropic", "salesforce", "vertex", "apple"
    auth_type: str  # "direct", "jwt_oauth", "service_account", "endor_a3", "endor_a3"
    model_name: str  # Original model name
    requires_trust_header: bool = False  # For Salesforce Trust Layer
    credentials_path: Optional[str] = None  # Path to credentials file
    client_id: Optional[str] = None  # For Salesforce JWT OAuth
    private_key_path: Optional[str] = None  # For Salesforce JWT OAuth
    username: Optional[str] = None  # For Salesforce JWT OAuth
    project_id: Optional[str] = None  # For Vertex AI
    location: Optional[str] = None  # For Vertex AI
    endpoint: Optional[str] = None  # For Apple Endor or custom endpoints
    config_id: Optional[int] = None  # ProviderConfig ID for database lookups


# Default model-to-provider mapping
# Can be overridden via MODEL_MAPPING environment variable
DEFAULT_MODEL_MAPPING: Dict[str, Dict[str, Any]] = {
    # OpenAI models
    "gpt-4": {
        "provider": "openai",
        "auth": "direct"
    },
    "gpt-4-turbo": {
        "provider": "openai",
        "auth": "direct"
    },
    "gpt-4o": {
        "provider": "openai",
        "auth": "direct"
    },
    "gpt-3.5-turbo": {
        "provider": "openai",
        "auth": "direct"
    },
    "gpt-3.5-turbo-16k": {
        "provider": "openai",
        "auth": "direct"
    },
    # Anthropic models
    "claude-3-opus": {
        "provider": "anthropic",
        "auth": "direct"
    },
    "claude-3-sonnet": {
        "provider": "anthropic",
        "auth": "direct"
    },
    "claude-3-haiku": {
        "provider": "anthropic",
        "auth": "direct"
    },
    "claude-3-5-sonnet": {
        "provider": "anthropic",
        "auth": "direct"
    },
    # Vertex AI (Gemini) models
    "gemini-pro": {
        "provider": "vertex",
        "auth": "service_account"
    },
    "gemini-1.5-pro": {
        "provider": "vertex",
        "auth": "service_account"
    },
    "gemini-1.5-flash": {
        "provider": "vertex",
        "auth": "service_account"
    },
    # Salesforce models
    "sfdc-xgen": {
        "provider": "salesforce",
        "auth": "jwt_oauth",
        "requires_trust_header": True
    },
    "einstein-gpt": {
        "provider": "salesforce",
        "auth": "jwt_oauth",
        "requires_trust_header": True
    },
    # Apple Endor models (if configured)
    "endor": {
        "provider": "apple",
        "auth": "endor_a3"
    }
}


def load_model_mapping() -> Dict[str, Dict[str, Any]]:
    """Load model mapping from environment variable or use default."""
    model_mapping_str = getattr(settings, 'MODEL_MAPPING', None)
    
    if model_mapping_str:
        try:
            # Parse JSON string from environment
            if isinstance(model_mapping_str, str):
                custom_mapping = json.loads(model_mapping_str)
            else:
                custom_mapping = model_mapping_str
            
            # Merge with defaults (custom takes precedence)
            merged = DEFAULT_MODEL_MAPPING.copy()
            merged.update(custom_mapping)
            return merged
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse MODEL_MAPPING: {e}. Using defaults.")
            return DEFAULT_MODEL_MAPPING
    
    return DEFAULT_MODEL_MAPPING


# Cache the model mapping
_model_mapping_cache: Optional[Dict[str, Dict[str, Any]]] = None


def get_model_mapping() -> Dict[str, Dict[str, Any]]:
    """Get model mapping (cached)."""
    global _model_mapping_cache
    if _model_mapping_cache is None:
        _model_mapping_cache = load_model_mapping()
    return _model_mapping_cache


def resolve_context(model_name: str, provider: str) -> ProviderContext:
    """
    Resolve provider context from provider name.
    
    Args:
        model_name: The model identifier (e.g., "gpt-4", "gemini-1.5-pro")
        provider: The provider name (e.g., "openai", "apple", "vertex")
        
    Returns:
        ProviderContext with provider, auth type, and credentials info
        
    Raises:
        ValueError: If provider is not recognized
    """
    if not model_name:
        raise ValueError("Model name is required")
    if not provider:
        raise ValueError("Provider is required")
    
    # Map provider to auth type (endor is alias for apple)
    provider_lower = provider.lower().strip()
    if provider_lower == "endor":
        provider_lower = "apple"
    
    if provider_lower == "openai":
        auth_type = "direct"
    elif provider_lower == "anthropic":
        auth_type = "direct"
    elif provider_lower == "vertex":
        auth_type = "service_account"
    elif provider_lower == "salesforce":
        auth_type = "jwt_oauth"
    elif provider_lower == "apple":
        auth_type = "endor_a3"
    else:
        raise ValueError(f"Unknown provider: '{provider}'. Supported providers: openai, anthropic, vertex, salesforce, apple")
    
    # Build context based on provider and auth type
    mapping = get_model_mapping()
    requires_trust_header = False
    if model_name in mapping:
        requires_trust_header = mapping[model_name].get("requires_trust_header", False)
    
    context = ProviderContext(
        provider=provider_lower,
        auth_type=auth_type,
        model_name=model_name,
        requires_trust_header=requires_trust_header
    )
    
    # Add provider-specific configuration
    if provider_lower == "salesforce" and auth_type == "jwt_oauth":
        context.client_id = settings.SALESFORCE_CLIENT_ID
        context.private_key_path = settings.SALESFORCE_PRIVATE_KEY_PATH
        context.username = settings.SALESFORCE_USERNAME
        context.endpoint = settings.SALESFORCE_MODELS_API_URL
        
    elif provider_lower == "vertex" and auth_type == "service_account":
        context.project_id = settings.VERTEX_PROJECT_ID
        context.location = settings.VERTEX_LOCATION
        context.credentials_path = settings.VERTEX_SERVICE_ACCOUNT_PATH
        
    elif provider_lower == "apple":
        # Load Endor config from database if available
        try:
            from app.core.database import SessionLocal
            from app.models.user import ProviderConfig
            
            db = SessionLocal()
            try:
                endor_config = db.query(ProviderConfig).filter(
                    ProviderConfig.provider_type == "apple_endor",
                    ProviderConfig.is_active == True
                ).first()
                
                if endor_config:
                    context.endpoint = endor_config.apple_endor_endpoint or settings.APPLE_ENDOR_ENDPOINT
                    # Store config_id for authenticator to use
                    context.config_id = endor_config.id
                else:
                    context.endpoint = settings.APPLE_ENDOR_ENDPOINT
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to load Endor config from database: {e}, using settings")
            context.endpoint = settings.APPLE_ENDOR_ENDPOINT
    
    return context


def get_available_providers() -> list[str]:
    """Get list of available providers based on configuration."""
    providers = set()
    mapping = get_model_mapping()
    
    for model_config in mapping.values():
        providers.add(model_config["provider"])
    
    return sorted(providers)


def get_available_models(provider: Optional[str] = None) -> list[str]:
    """
    Get list of available models, optionally filtered by provider.
    
    Args:
        provider: Optional provider name to filter by
        
    Returns:
        List of model names
    """
    mapping = get_model_mapping()
    
    if provider:
        return sorted([
            model for model, config in mapping.items()
            if config["provider"] == provider
        ])
    
    return sorted(mapping.keys())
