"""Request/response translators for unified LLM gateway."""
from app.services.gateway.translators.base import BaseTranslator
from app.services.gateway.translators.openai import OpenAITranslator
from app.services.gateway.translators.salesforce import SalesforceTranslator
from app.services.gateway.translators.vertex import VertexTranslator
from app.services.gateway.translators.normalizer import normalize_response, normalize_stream_chunk

__all__ = [
    "BaseTranslator",
    "OpenAITranslator",
    "SalesforceTranslator",
    "VertexTranslator",
    "normalize_response",
    "normalize_stream_chunk",
]


def get_translator(provider: str, context=None):
    """
    Get translator instance for provider.
    
    Args:
        provider: Provider name ("openai", "anthropic", "salesforce", "vertex")
        context: Optional ProviderContext
        
    Returns:
        Translator instance
    """
    if provider in ("openai", "anthropic"):
        return OpenAITranslator()
    elif provider == "salesforce":
        return SalesforceTranslator()
    elif provider == "vertex":
        return VertexTranslator()
    else:
        raise ValueError(f"Unknown provider: {provider}")
