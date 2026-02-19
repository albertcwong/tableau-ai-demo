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
        # Salesforce Models API: POST /models/{modelName}/chat-generations
        base_url = (context.endpoint if context and context.endpoint else self.base_url) or settings.SALESFORCE_MODELS_API_URL
        model_name = request.get("model", "")
        url = f"{base_url.rstrip('/')}/models/{model_name}/chat-generations"
        payload = {
            "messages": request.get("messages", []),
            "stream": request.get("stream", False),
            "temperature": request.get("temperature"),
            "max_tokens": request.get("max_tokens"),
            "max_completion_tokens": request.get("max_completion_tokens"),
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        headers = {
            "Content-Type": "application/json;charset=utf-8",
            "x-sfdc-app-context": SALESFORCE_TRUST_HEADER,
            "x-client-feature-id": "ai-platform-models-connected-app",
        }
        
        logger.debug(f"Salesforce translator: transformed request for model {request.get('model', '')}")
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
        normalized = {"choices": [], "usage": {}}
        # Salesforce returns generationDetails.generations; OpenAI uses choices
        if "generationDetails" in response:
            gd = response["generationDetails"]
            gens = gd.get("generations", [])
            params = gd.get("parameters", {})
            usage = params.get("usage", {})
            normalized["usage"] = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }
            # Last assistant message is the model reply
            for g in reversed(gens):
                if g.get("role") == "assistant":
                    normalized["choices"] = [{"index": 0, "message": {"content": g.get("content", "")}, "finish_reason": "stop"}]
                    break
            if "id" in response:
                normalized["id"] = response["id"]
            if "model" in params:
                normalized["model"] = params["model"]
            logger.debug("Salesforce translator: normalized generationDetails response")
            return normalized
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
