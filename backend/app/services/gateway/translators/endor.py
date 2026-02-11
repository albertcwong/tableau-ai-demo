"""Endor translator - transforms to/from Endor native format."""
import logging
from typing import Dict, Any, Tuple, Optional
from app.services.gateway.translators.base import BaseTranslator
from app.services.gateway.router import ProviderContext

logger = logging.getLogger(__name__)

# Endor API endpoints
# /v2/completions - single prompt, no tool support
# /v2/chat/completions - structured messages, supports tool_config
ENDOR_BASE_URL = "https://api.endor.apple.com"


class EndorTranslator(BaseTranslator):
    """Translator for Apple Endor API (native format, passthrough)."""
    
    def transform_request(
        self,
        request: Dict[str, Any],
        context: Optional[ProviderContext] = None
    ) -> Tuple[str, Dict[str, Any], Dict[str, str]]:
        """
        Transform OpenAI-compatible request to Endor format.
        
        Args:
            request: OpenAI-compatible request dict
            context: Provider context (contains endpoint URL)
            
        Returns:
            Tuple of (url, payload, headers)
        """
        # Chat completions support messages + tool_config; plain completions do not
        base_url = context.endpoint if context and context.endpoint else ENDOR_BASE_URL
        stream = request.get("stream", False)
        if stream:
            url = f"{base_url.rstrip('/')}/v2/chat/completions/stream"
        else:
            url = f"{base_url.rstrip('/')}/v2/chat/completions"
        
        # Extract model
        model_id = request.get("model", "")
        
        # Build generation_config from OpenAI parameters
        generation_config = {}
        if "temperature" in request:
            generation_config["temperature"] = request["temperature"]
        if "top_p" in request:
            generation_config["top_p"] = request["top_p"]
        if "max_tokens" in request:
            generation_config["max_tokens"] = request["max_tokens"]
        if "stop" in request:
            stop_words = request["stop"]
            if isinstance(stop_words, str):
                stop_words = [stop_words]
            generation_config["stop_words"] = stop_words
        generation_config.setdefault("top_k", 0)
        generation_config.setdefault("frequency_penalty", 1)
        generation_config.setdefault("logprobs", 0)
        generation_config.setdefault("reasoning_effort", "low")
        generation_config.setdefault("enable_thinking", True)
        generation_config.setdefault("thinking_budget", 0)
        
        # Chat completions always use messages; add tool_config when tools/functions present
        tools = request.get("tools") or []
        if not tools and request.get("functions"):
            tools = [{"type": "function", "function": f} for f in request["functions"]]
        endor_messages = self._messages_to_endor_format(request.get("messages", []))
        payload = {
            "model_id": model_id,
            "messages": endor_messages,
            "generation_config": generation_config
        }
        if tools:
            payload["tool_config"] = {"tools": tools}
        
        # Headers - will be augmented with A3 token by authenticator
        if stream:
            headers = {
                "Content-Type": "application/json",
                "Accept": "text/event-stream, application/json"
            }
        else:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        
        logger.debug(f"Endor translator: transformed request for model {model_id}")
        return url, payload, headers
    
    def _messages_to_endor_format(self, messages: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """Convert OpenAI messages to Endor format with contents array."""
        out = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                text = "".join(
                    c.get("text", "") if isinstance(c, dict) else str(c)
                    for c in content
                )
            else:
                text = str(content)
            out.append({"role": msg.get("role", "user"), "contents": [{"text": text}]})
        return out

    def normalize_response(
        self,
        response: Dict[str, Any],
        context: Optional[ProviderContext] = None
    ) -> Dict[str, Any]:
        """
        Normalize Endor response to OpenAI-compatible format.
        
        Endor format:
        {
            "model": "...",
            "id": "...",
            "created": ...,
            "object": "text_completion",
            "choices": [{"index": 0, "text": "...", "logprobs": null}]
        }
        
        OpenAI format:
        {
            "id": "...",
            "object": "chat.completion",
            "created": ...,
            "model": "...",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "..."}, "finish_reason": "stop"}],
            "usage": {...}
        }
        
        Args:
            response: Endor response dict
            context: Provider context (optional)
            
        Returns:
            OpenAI-compatible response dict
        """
        # Extract Endor fields
        model = response.get("model", "")
        response_id = response.get("id", "")
        created = response.get("created", 0)
        choices = response.get("choices", [])
        
        # Convert choices from Endor format to OpenAI format
        # Chat completions: choice.message.text, choice.message.reasoning_content
        # Plain completions: choice.text
        openai_choices = []
        for choice in choices:
            msg = choice.get("message", {})
            text = msg.get("text", "") or msg.get("content", "") or choice.get("text", "")
            text = text or msg.get("reasoning_content", "")
            index = choice.get("index", 0)
            openai_choices.append({
                "index": index,
                "message": {
                    "role": "assistant",
                    "content": text
                },
                "finish_reason": "stop"
            })
        
        # Build OpenAI-compatible response
        return {
            "id": response_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": openai_choices,
            "usage": {
                "prompt_tokens": 0,  # Endor doesn't provide token counts
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
    
    def normalize_stream_chunk(
        self,
        chunk: Dict[str, Any],
        context: Optional[ProviderContext] = None
    ) -> Dict[str, Any]:
        """
        Normalize Endor streaming chunk (passthrough - using native format).
        
        Args:
            chunk: Endor streaming chunk
            context: Provider context (optional)
            
        Returns:
            Endor streaming chunk (unchanged - passthrough)
        """
        # Passthrough - return Endor native format
        return chunk
