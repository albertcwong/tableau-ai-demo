"""Utility functions for model management."""
import logging
from typing import Optional
from app.services.gateway.api import fetch_models_from_provider
from app.services.gateway.router import get_available_models, get_available_providers

logger = logging.getLogger(__name__)


async def get_default_model(
    provider: Optional[str] = None,
    authorization: Optional[str] = None
) -> str:
    """
    Get a default model, preferring API-fetched models over static ones.
    
    Args:
        provider: Optional provider to get default model from
        authorization: Optional Authorization header
        
    Returns:
        Default model name (e.g., "gpt-4", "claude-3-5-sonnet")
    """
    try:
        if provider:
            # Try to fetch from provider API
            try:
                models = await fetch_models_from_provider(provider, authorization)
                if models:
                    # Prefer newer models (gpt-4o, claude-3-5-sonnet, etc.)
                    # Exclude models that don't support function calling
                    excluded_models = ["chatgpt-4o-latest", "chatgpt-image-latest", "o1-preview", "o1-mini", "o1"]
                    function_calling_models = [m for m in models if m.lower() not in [ex.lower() for ex in excluded_models]]
                    
                    if function_calling_models:
                        # Prefer newer models that support function calling
                        preferred = [m for m in function_calling_models if any(x in m.lower() for x in ["gpt-4o", "claude-3-5", "gemini-1.5"])]
                        if preferred:
                            logger.info(f"get_default_model: returning preferred model {preferred[0]}")
                            return preferred[0]
                        logger.info(f"get_default_model: returning first function-calling model {function_calling_models[0]}")
                        return function_calling_models[0]
                    # Fallback to first model if no function-calling models found
                    logger.warning(f"get_default_model: no function-calling models found, using {models[0]}")
                    return models[0]
            except Exception as e:
                logger.warning(f"Failed to fetch models from {provider}: {e}")
        
        # Fallback: get from static mapping
        static_models = get_available_models(provider)
        if static_models:
            # Prefer newer models
            preferred = [m for m in static_models if any(x in m.lower() for x in ["gpt-4o", "claude-3-5", "gemini-1.5"])]
            if preferred:
                return preferred[0]
            return static_models[0]
        
        # Last resort: hardcoded defaults
        if provider == "openai":
            return "gpt-4"
        elif provider == "anthropic":
            return "claude-3-5-sonnet"
        elif provider == "vertex":
            return "gemini-1.5-pro"
        else:
            return "gpt-4"  # Universal fallback
            
    except Exception as e:
        logger.error(f"Error getting default model: {e}", exc_info=True)
        return "gpt-4"  # Safe fallback
