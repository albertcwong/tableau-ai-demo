"""Endor translator - transforms to/from Endor native format."""
import json
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
        logger.debug(f"Endor payload: {len(endor_messages)} msgs, roles={[m.get('role') for m in endor_messages]}")
        
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
        """Convert OpenAI messages to Endor format. Endor uses 'tool' role with tool_result field."""
        out = []
        _empty = "."  # Endor rejects empty contents; use non-whitespace placeholder
        for i, msg in enumerate(messages):
            role = msg.get("role", "user")
            content = msg.get("content")
            if content is None:
                content = ""
            if isinstance(content, list):
                parts = []
                for c in content:
                    if isinstance(c, dict):
                        parts.append(c.get("text") or c.get("content") or "")
                    else:
                        parts.append(str(c))
                text = "".join(str(p) for p in parts)
            else:
                text = str(content) if content is not None else ""
            text = (text or "").strip()
            # For assistant with tool_calls or function_call and empty content: synthesize from tool/function name
            if not text and role == "assistant":
                if msg.get("tool_calls"):
                    names = [tc.get("function", {}).get("name", "") for tc in msg["tool_calls"] if tc.get("function")]
                    text = "Calling " + ", ".join(n for n in names if n) or _empty
                elif msg.get("function_call"):
                    fc = msg["function_call"]
                    name = fc.get("name", "") if isinstance(fc, dict) else ""
                    if not name and isinstance(fc, str):
                        try:
                            fc_obj = json.loads(fc)
                            name = fc_obj.get("name", "")
                        except Exception:
                            pass
                    text = f"Calling {name}" if name else _empty
            orig_empty = not text
            text = text or _empty
            if orig_empty:
                logger.info(f"Endor msg[{i}] role={role} had empty content, synthesized/placeholder len={len(text)}")
            if role == "function":
                out.append({"role": "tool", "tool_result": text})
            elif role == "tool":
                out.append({"role": "tool", "tool_result": text})
            else:
                out.append({"role": role, "contents": [{"text": text}]})
        return out

    def normalize_response(
        self,
        response: Dict[str, Any],
        context: Optional[ProviderContext] = None
    ) -> Dict[str, Any]:
        """
        Normalize Endor response to OpenAI-compatible format.
        
        Endor non-streaming format:
        {
            "generation_id": "...",
            "choices": [{"index": 0, "message": {"role": "assistant", "text": "..."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}
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
        # Endor non-streaming: generation_id, choices[].message.text, usage
        response_id = response.get("generation_id") or response.get("id", "")
        model = response.get("model", "")
        created = response.get("created", 0)
        choices = response.get("choices", [])
        usage = response.get("usage", {})
        
        openai_choices = []
        for choice in choices:
            msg = choice.get("message", {})
            text = msg.get("text", "") or msg.get("content", "") or choice.get("text", "")
            text = text or msg.get("reasoning_content", "")
            index = choice.get("index", 0)
            finish_reason = choice.get("finish_reason", "stop")
            # Build normalized message - include tool_calls when present (Endor may use tool_calls or tool_invocation)
            norm_msg: Dict[str, Any] = {"role": "assistant", "content": text}
            tool_calls = msg.get("tool_calls") or msg.get("tool_invocation") or msg.get("tool_invocations")
            if finish_reason == "tool_calls" or tool_calls:
                if not tool_calls:
                    logger.warning(f"Endor finish_reason=tool_calls but no tool_calls in message. msg_keys={list(msg.keys())}")
                elif isinstance(tool_calls, list) and tool_calls:
                    # OpenAI format: [{id, type, function: {name, arguments}}]
                    norm_msg["tool_calls"] = [
                        {
                            "id": tc.get("id", f"call_{i}"),
                            "type": tc.get("type", "function"),
                            "function": tc.get("function", {"name": tc.get("name", ""), "arguments": tc.get("arguments", "{}")})
                            if isinstance(tc.get("function"), dict) else {"name": tc.get("name", ""), "arguments": tc.get("arguments", "{}")}
                        }
                        for i, tc in enumerate(tool_calls)
                    ]
                    logger.info(f"Endor normalize: forwarding {len(norm_msg['tool_calls'])} tool_calls")
                elif isinstance(tool_calls, dict):
                    # Single tool call as dict
                    fn = tool_calls.get("function", tool_calls)
                    name = fn.get("name", "") if isinstance(fn, dict) else tool_calls.get("name", "")
                    args = fn.get("arguments", "{}") if isinstance(fn, dict) else tool_calls.get("arguments", "{}")
                    norm_msg["tool_calls"] = [{"id": "call_0", "type": "function", "function": {"name": name, "arguments": args if isinstance(args, str) else json.dumps(args)}}]
                    logger.info(f"Endor normalize: forwarding 1 tool_call (dict format): {name}")
            openai_choices.append({"index": index, "message": norm_msg, "finish_reason": finish_reason})
        
        return {
            "id": response_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": openai_choices,
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0)
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
