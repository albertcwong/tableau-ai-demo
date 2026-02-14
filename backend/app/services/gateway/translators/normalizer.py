"""Response normalizer - converts all provider responses to OpenAI format."""
import logging
from typing import Dict, Any, Optional
from app.services.gateway.translators.openai import OpenAITranslator
from app.services.gateway.translators.salesforce import SalesforceTranslator
from app.services.gateway.translators.vertex import VertexTranslator
from app.services.gateway.translators.endor import EndorTranslator
from app.services.gateway.router import ProviderContext

logger = logging.getLogger(__name__)


def normalize_response(
    response: Dict[str, Any],
    provider: str,
    context: Optional[ProviderContext] = None
) -> Dict[str, Any]:
    """
    Normalize provider-specific response to OpenAI format.
    
    Args:
        response: Provider-specific response dict
        provider: Provider name ("openai", "anthropic", "salesforce", "vertex")
        context: Optional ProviderContext
        
    Returns:
        OpenAI-compatible response dict with structure:
        {
            "choices": [{"message": {"content": "..."}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 123},
            "id": "...",
            "model": "...",
            "created": 1234567890
        }
    """
    # Get appropriate translator
    if provider in ("openai", "anthropic"):
        translator = OpenAITranslator()
    elif provider == "salesforce":
        translator = SalesforceTranslator()
    elif provider == "vertex":
        translator = VertexTranslator()
    elif provider in ("apple", "endor"):
        translator = EndorTranslator()
    else:
        logger.warning(f"Unknown provider {provider}, using OpenAI translator")
        translator = OpenAITranslator()
    
    # Normalize response
    normalized = translator.normalize_response(response, context)
    
    logger.debug(f"Normalized {provider} response to OpenAI format")
    return normalized


def normalize_stream_chunk(
    chunk: Dict[str, Any],
    provider: str,
    context: Optional[ProviderContext] = None
) -> Dict[str, Any]:
    """
    Normalize provider-specific streaming chunk to OpenAI format.
    
    Args:
        chunk: Provider-specific streaming chunk
        provider: Provider name
        context: Optional ProviderContext
        
    Returns:
        OpenAI-compatible streaming chunk
    """
    # Get appropriate translator
    if provider in ("openai", "anthropic"):
        translator = OpenAITranslator()
    elif provider == "salesforce":
        translator = SalesforceTranslator()
    elif provider == "vertex":
        translator = VertexTranslator()
    elif provider in ("apple", "endor"):
        translator = EndorTranslator()
    else:
        logger.warning(f"Unknown provider {provider}, using OpenAI translator")
        translator = OpenAITranslator()
    
    # Normalize chunk
    normalized = translator.normalize_stream_chunk(chunk, context)
    
    logger.debug(f"Normalized {provider} streaming chunk to OpenAI format")
    return normalized
