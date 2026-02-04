"""Salesforce translator - nested parameters + Trust Layer header."""
import logging
from typing import Dict, Any, Tuple, Optional
from app.services.gateway.translators.base import BaseTranslator
from app.services.gateway.router import ProviderContext
from app.core.config import settings

logger = logging.getLogger(__name__)

# Salesforce Trust Layer header value
SALESFORCE_TRUST_HEADER = "EinsteinGPT"


class SalesforceTranslator(BaseTranslator):
    """Translator for Salesforce Models API."""
    
    def __init__(self, base_url: Optional[str] = None):
        """Initialize Salesforce translator.
        
        Args:
            base_url: Optional custom base URL (defaults to SALESFORCE_MODELS_API_URL)
        """
        self.base_url = base_url or settings.SALESFORCE_MODELS_API_URL
    
    def transform_request(
        self,
        request: Dict[str, Any],
        context: Optional[ProviderContext] = None
    ) -> Tuple[str, Dict[str, Any], Dict[str, str]]:
        """
        Transform OpenAI request to Salesforce format.
        
        Salesforce expects:
        - Nested parameters object for temperature, top_p, etc.
        - Model name in URL path
        - x-sfdc-app-context header for Trust Layer
        
        Args:
            request: OpenAI-compatible request dict
            context: Provider context (optional)
            
        Returns:
            Tuple of (url, payload, headers)
        """
        model_name = request.get("model", "")
        
        # Build Salesforce URL: {base_url}/models/{modelName}/chat-generations
        url = f"{self.base_url.rstrip('/')}/models/{model_name}/chat-generations"
        
        # Extract parameters that go into nested object
        parameters = {}
        if "temperature" in request:
            parameters["temperature"] = request["temperature"]
        if "top_p" in request:
            parameters["top_p"] = request["top_p"]
        if "max_tokens" in request:
            parameters["max_tokens"] = request["max_tokens"]
        if "stop" in request:
            parameters["stop"] = request["stop"]
        
        # Build Salesforce payload
        payload = {
            "messages": request.get("messages", [])
        }
        
        # Add nested parameters if any
        if parameters:
            payload["parameters"] = parameters
        
        # Add other OpenAI fields that Salesforce might accept
        if "stream" in request:
            payload["stream"] = request["stream"]
        
        # Headers with Trust Layer
        headers = {
            "Content-Type": "application/json",
            "x-sfdc-app-context": SALESFORCE_TRUST_HEADER
        }
        
        logger.debug(f"Salesforce translator: transformed request for model {model_name}")
        return url, payload, headers
    
    def normalize_response(
        self,
        response: Dict[str, Any],
        context: Optional[ProviderContext] = None
    ) -> Dict[str, Any]:
        """
        Normalize Salesforce response to OpenAI format.
        
        Salesforce response format:
        {
            "choices": [{"message": {"content": "..."}}],
            "usage": {"totalTokens": 123}
        }
        
        OpenAI format:
        {
            "choices": [{"message": {"content": "..."}}],
            "usage": {"total_tokens": 123}
        }
        
        Args:
            response: Salesforce response dict
            context: Provider context (optional)
            
        Returns:
            OpenAI-compatible response dict
        """
        normalized = {
            "choices": [],
            "usage": {}
        }
        
        # Normalize choices
        if "choices" in response:
            for choice in response["choices"]:
                normalized_choice = {
                    "index": choice.get("index", 0),
                    "message": choice.get("message", {}),
                    "finish_reason": choice.get("finish_reason", "stop")
                }
                normalized["choices"].append(normalized_choice)
        
        # Normalize usage (totalTokens -> total_tokens)
        if "usage" in response:
            usage = response["usage"]
            normalized["usage"] = {
                "prompt_tokens": usage.get("promptTokens", usage.get("prompt_tokens", 0)),
                "completion_tokens": usage.get("completionTokens", usage.get("completion_tokens", 0)),
                "total_tokens": usage.get("totalTokens", usage.get("total_tokens", 0))
            }
        
        # Copy other fields
        if "id" in response:
            normalized["id"] = response["id"]
        if "model" in response:
            normalized["model"] = response["model"]
        if "created" in response:
            normalized["created"] = response["created"]
        
        logger.debug("Salesforce translator: normalized response")
        return normalized
    
    def normalize_stream_chunk(
        self,
        chunk: Dict[str, Any],
        context: Optional[ProviderContext] = None
    ) -> Dict[str, Any]:
        """
        Normalize Salesforce streaming chunk to OpenAI format.
        
        Args:
            chunk: Salesforce streaming chunk
            context: Provider context (optional)
            
        Returns:
            OpenAI-compatible streaming chunk
        """
        # Salesforce streaming chunks should follow similar format
        # If they have choices[0].delta, normalize it
        if "choices" in chunk and len(chunk["choices"]) > 0:
            choice = chunk["choices"][0]
            if "delta" in choice:
                return {
                    "id": chunk.get("id", ""),
                    "object": "chat.completion.chunk",
                    "created": chunk.get("created", 0),
                    "model": chunk.get("model", ""),
                    "choices": [{
                        "index": choice.get("index", 0),
                        "delta": choice["delta"],
                        "finish_reason": choice.get("finish_reason")
                    }]
                }
        
        # Fallback: normalize as regular response
        return self.normalize_response(chunk, context)
