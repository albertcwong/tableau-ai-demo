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
    auth_type: str  # "direct", "jwt_oauth", "service_account"
    model_name: str  # Original model name
    requires_trust_header: bool = False  # For Salesforce Trust Layer
    credentials_path: Optional[str] = None  # Path to credentials file
    client_id: Optional[str] = None  # For Salesforce JWT OAuth
    private_key_path: Optional[str] = None  # For Salesforce JWT OAuth
    username: Optional[str] = None  # For Salesforce JWT OAuth
    project_id: Optional[str] = None  # For Vertex AI
    location: Optional[str] = None  # For Vertex AI
    endpoint: Optional[str] = None  # For Apple Endor or custom endpoints


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
        "auth": "direct"
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


def resolve_context(model_name: str) -> ProviderContext:
    """
    Resolve provider context from model name.
    
    Args:
        model_name: The model identifier (e.g., "gpt-4", "gemini-pro", "chatgpt-4o-latest")
        
    Returns:
        ProviderContext with provider, auth type, and credentials info
        
    Raises:
        ValueError: If model name is not recognized and cannot be inferred
    """
    if not model_name:
        raise ValueError("Model name is required")
    
    mapping = get_model_mapping()
    
    # First, check static mapping
    if model_name in mapping:
        model_config = mapping[model_name]
        provider = model_config["provider"]
        auth_type = model_config["auth"]
    else:
        # Try to infer provider from model name pattern
        model_lower = model_name.lower()
        
        # OpenAI patterns: gpt-*, chatgpt-*, o1, o3, o4-*, text-embedding-*, etc.
        if (model_lower.startswith("gpt-") or 
            model_lower.startswith("chatgpt-") or 
            model_lower.startswith("o1") or 
            model_lower.startswith("o3") or 
            model_lower.startswith("o4-") or 
            model_lower.startswith("text-embedding-") or
            model_lower.startswith("codex-") or
            model_lower.startswith("computer-use-") or
            model_lower.startswith("omni-moderation-") or
            model_lower.startswith("sora-") or
            model_lower.startswith("gpt4o-") or
            model_lower.startswith("nectarine-")):
            provider = "openai"
            auth_type = "direct"
        # Anthropic patterns: claude-*
        elif model_lower.startswith("claude-"):
            provider = "anthropic"
            auth_type = "direct"
        # Vertex AI (Gemini) patterns: gemini-*
        elif model_lower.startswith("gemini-"):
            provider = "vertex"
            auth_type = "service_account"
        # Salesforce patterns: sfdc-*, einstein-*
        elif model_lower.startswith("sfdc-") or model_lower.startswith("einstein-"):
            provider = "salesforce"
            auth_type = "jwt_oauth"
        # Apple Endor patterns: endor
        elif model_lower == "endor":
            provider = "apple"
            auth_type = "direct"
        else:
            # Unknown model - raise error with available models
            available_models = ", ".join(sorted(mapping.keys()))
            raise ValueError(
                f"Unknown model: '{model_name}'. "
                f"Available models: {available_models}"
            )
    
    # Build context based on provider and auth type
    requires_trust_header = False
    if model_name in mapping:
        requires_trust_header = mapping[model_name].get("requires_trust_header", False)
    
    context = ProviderContext(
        provider=provider,
        auth_type=auth_type,
        model_name=model_name,
        requires_trust_header=requires_trust_header
    )
    
    # Add provider-specific configuration
    if provider == "salesforce" and auth_type == "jwt_oauth":
        context.client_id = settings.SALESFORCE_CLIENT_ID
        context.private_key_path = settings.SALESFORCE_PRIVATE_KEY_PATH
        context.username = settings.SALESFORCE_USERNAME
        context.endpoint = settings.SALESFORCE_MODELS_API_URL
        
    elif provider == "vertex" and auth_type == "service_account":
        context.project_id = settings.VERTEX_PROJECT_ID
        context.location = settings.VERTEX_LOCATION
        context.credentials_path = settings.VERTEX_SERVICE_ACCOUNT_PATH
        
    elif provider == "apple":
        context.endpoint = settings.APPLE_ENDOR_ENDPOINT
        # Apple Endor uses direct auth but may have custom endpoint
    
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
