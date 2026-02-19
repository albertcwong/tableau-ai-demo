"""Request/response translators for unified LLM gateway."""
from app.services.gateway.translators.base import BaseTranslator
from app.services.gateway.translators.openai import OpenAITranslator
from app.services.gateway.translators.salesforce import SalesforceTranslator
from app.services.gateway.translators.vertex import VertexTranslator
from app.services.gateway.translators.endor import EndorTranslator
from app.services.gateway.translators.normalizer import normalize_response, normalize_stream_chunk

__all__ = [
    "BaseTranslator",
    "OpenAITranslator",
    "SalesforceTranslator",
    "VertexTranslator",
    "EndorTranslator",
    "normalize_response",
    "normalize_stream_chunk",
]


def get_translator(provider: str, context=None):
    """
    Get translator instance for provider.
    
    Args:
        provider: Provider name ("openai", "anthropic", "salesforce", "vertex", "apple")
        context: Optional ProviderContext
        
    Returns:
        Translator instance
    """
    if provider in ("openai", "anthropic"):
        return OpenAITranslator()
    elif provider == "salesforce":
        # eng-ai-model-gateway is OpenAI-compatible; endpoint uses /chat/completions (no /v1 prefix)
        if context and context.auth_type == "direct" and context.endpoint:
            base = f"{context.endpoint.rstrip('/')}/chat/completions"
            return OpenAITranslator(base_url=base)
        # Einstein Platform uses a different request/response shape
        return SalesforceTranslator()
    elif provider == "vertex":
        return VertexTranslator()
    elif provider in ("apple", "endor"):
        return EndorTranslator()
    else:
        raise ValueError(f"Unknown provider: {provider}")
