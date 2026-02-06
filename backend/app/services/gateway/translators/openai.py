"""OpenAI translator - passthrough (no transformation)."""
import logging
from typing import Dict, Any, Tuple, Optional
from app.services.gateway.translators.base import BaseTranslator
from app.services.gateway.router import ProviderContext

logger = logging.getLogger(__name__)

# OpenAI API endpoints
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"


class OpenAITranslator(BaseTranslator):
    """Translator for OpenAI and Anthropic APIs (passthrough)."""
    
    def __init__(self, base_url: Optional[str] = None):
        """Initialize OpenAI translator.
        
        Args:
            base_url: Optional custom base URL (for OpenAI-compatible APIs)
        """
        self.base_url = base_url or OPENAI_CHAT_COMPLETIONS_URL
    
    def transform_request(
        self,
        request: Dict[str, Any],
        context: Optional[ProviderContext] = None
    ) -> Tuple[str, Dict[str, Any], Dict[str, str]]:
        """
        Transform request (passthrough for OpenAI/Anthropic).
        
        Args:
            request: OpenAI-compatible request dict
            context: Provider context (optional)
            
        Returns:
            Tuple of (url, payload, headers)
        """
        # Determine provider and URL
        provider = context.provider if context else "openai"
        
        if provider == "anthropic":
            url = ANTHROPIC_MESSAGES_URL
            # Anthropic uses slightly different format, but we'll keep it simple for now
            # The actual API client will handle the differences
        else:
            url = self.base_url
        
        # Headers - no special headers needed
        headers = {
            "Content-Type": "application/json"
        }
        
        # Payload passes through unchanged, but parse function_call strings back to objects
        payload = request.copy()
        
        # Fix function_call in messages: gateway model requires strings, but OpenAI needs objects
        if "messages" in payload:
            for msg in payload["messages"]:
                if "function_call" in msg and isinstance(msg["function_call"], str):
                    try:
                        import json
                        msg["function_call"] = json.loads(msg["function_call"])
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse function_call string: {msg['function_call']}")
        
        logger.debug(f"OpenAI translator: passthrough request for {provider}")
        return url, payload, headers
    
    def normalize_response(
        self,
        response: Dict[str, Any],
        context: Optional[ProviderContext] = None
    ) -> Dict[str, Any]:
        """
        Normalize response (already in OpenAI format).
        
        Args:
            response: OpenAI response dict
            context: Provider context (optional)
            
        Returns:
            OpenAI-compatible response dict (unchanged)
        """
        # OpenAI responses are already in the correct format
        return response
    
    def normalize_stream_chunk(
        self,
        chunk: Dict[str, Any],
        context: Optional[ProviderContext] = None
    ) -> Dict[str, Any]:
        """
        Normalize streaming chunk (already in OpenAI format).
        
        Args:
            chunk: OpenAI streaming chunk
            context: Provider context (optional)
            
        Returns:
            OpenAI-compatible streaming chunk (unchanged)
        """
        # OpenAI streaming chunks are already in the correct format
        return chunk
