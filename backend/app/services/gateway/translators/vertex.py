"""Vertex AI translator - convert to contents/parts format."""
import json
import logging
from typing import Dict, Any, Tuple, Optional, List
from app.services.gateway.translators.base import BaseTranslator
from app.services.gateway.router import ProviderContext
from app.core.config import settings

logger = logging.getLogger(__name__)


class VertexTranslator(BaseTranslator):
    """Translator for Vertex AI (Gemini) API."""
    
    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None
    ):
        """Initialize Vertex AI translator.
        
        Args:
            project_id: GCP project ID (defaults to settings)
            location: GCP location (defaults to settings)
        """
        self.project_id = project_id or settings.VERTEX_PROJECT_ID
        self.location = location or settings.VERTEX_LOCATION
    
    def _build_vertex_url(self, model_name: str) -> str:
        """Build Vertex AI API URL.
        
        Format: https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:predict
        
        Args:
            model_name: Model name (e.g., "gemini-pro")
            
        Returns:
            Vertex AI API URL
        """
        # Vertex AI uses a different endpoint structure
        # For chat completions: projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent
        base_url = f"https://{self.location}-aiplatform.googleapis.com/v1"
        url = (
            f"{base_url}/projects/{self.project_id}/locations/{self.location}/"
            f"publishers/google/models/{model_name}:generateContent"
        )
        return url
    
    def _convert_role(self, role: str) -> str:
        """Convert OpenAI role to Vertex AI role.
        
        OpenAI: user, assistant, system
        Vertex AI: user, model
        
        Args:
            role: OpenAI role
            
        Returns:
            Vertex AI role
        """
        if role in ["user", "system"]:
            return "user"
        elif role == "assistant":
            return "model"
        else:
            # Default to user for unknown roles
            return "user"

    def _content_to_parts(self, content: Any, allow_images: bool = True) -> List[Dict[str, Any]]:
        """Convert OpenAI content (str or list of parts) to Vertex/Gemini parts.
        
        Args:
            content: OpenAI content (string or list of {type, text/image_url})
            allow_images: If False, strip images (e.g. for systemInstruction)
            
        Returns:
            List of Vertex parts: [{"text": "..."}] or [{"inline_data": {...}}]
        """
        if isinstance(content, str):
            return [{"text": content}] if content.strip() else []
        if not isinstance(content, list):
            return [{"text": str(content)}]
        parts = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and "text" in item:
                if item["text"].strip():
                    parts.append({"text": item["text"]})
            elif allow_images and item.get("type") == "image_url" and "image_url" in item:
                url = item["image_url"].get("url", "")
                if url.startswith("data:image"):
                    try:
                        header, b64 = url.split(",", 1)
                        mime = "image/png"
                        if "jpeg" in header or "jpg" in header:
                            mime = "image/jpeg"
                        parts.append({"inline_data": {"mime_type": mime, "data": b64}})
                    except Exception:
                        logger.warning("Vertex: failed to parse image_url")
        return parts if parts else [{"text": " "}]

    def transform_request(
        self,
        request: Dict[str, Any],
        context: Optional[ProviderContext] = None
    ) -> Tuple[str, Dict[str, Any], Dict[str, str]]:
        """
        Transform OpenAI request to Vertex AI format.
        
        Vertex AI format:
        {
            "contents": [
                {"role": "user", "parts": [{"text": "..."}]},
                {"role": "model", "parts": [{"text": "..."}]}
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1024
            }
        }
        
        Args:
            request: OpenAI-compatible request dict
            context: Provider context (optional)
            
        Returns:
            Tuple of (url, payload, headers)
        """
        model_name = request.get("model", "")
        
        # Use context if provided
        project_id = context.project_id if context and context.project_id else self.project_id
        location = context.location if context and context.location else self.location
        
        # Build URL
        if project_id and location:
            base_url = f"https://{location}-aiplatform.googleapis.com/v1"
            url = (
                f"{base_url}/projects/{project_id}/locations/{location}/"
                f"publishers/google/models/{model_name}:generateContent"
            )
        else:
            # Fallback URL (will fail if credentials are wrong)
            url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/{model_name}:generateContent"
        
        # Separate system messages from regular messages
        system_messages = [msg for msg in request.get("messages", []) if msg.get("role") == "system"]
        regular_messages = [msg for msg in request.get("messages", []) if msg.get("role") != "system"]
        
        # Convert regular messages to contents format (support multimodal)
        contents = []
        for msg in regular_messages:
            role = self._convert_role(msg.get("role", "user"))
            content = msg.get("content", "")
            parts = self._content_to_parts(content, allow_images=True)
            contents.append({"role": role, "parts": parts})
        
        # Build payload
        payload = {
            "contents": contents
        }
        
        # Add system instruction if present (text only; systemInstruction cannot have images)
        if system_messages:
            all_parts = []
            for msg in system_messages:
                c = msg.get("content", "")
                all_parts.extend(self._content_to_parts(c, allow_images=False))
            text_parts = [p.get("text", "") for p in all_parts if "text" in p]
            system_text = "\n".join(t for t in text_parts if t.strip())
            payload["systemInstruction"] = {
                "parts": [{"text": system_text}] if system_text.strip() else [{"text": " "}]
            }
        
        # Add generation config
        generation_config = {}
        if "temperature" in request:
            generation_config["temperature"] = request["temperature"]
        if "max_tokens" in request:
            generation_config["maxOutputTokens"] = request["max_tokens"]
        if "top_p" in request:
            generation_config["topP"] = request["top_p"]
        if "top_k" in request:
            generation_config["topK"] = request["top_k"]
        if "stop" in request:
            generation_config["stopSequences"] = request["stop"] if isinstance(request["stop"], list) else [request["stop"]]
        
        if generation_config:
            payload["generationConfig"] = generation_config
        
        # Headers
        headers = {
            "Content-Type": "application/json"
        }

        # Log translated payload for debugging (images truncated)
        def _sanitize_for_log(obj: Any) -> Any:
            if isinstance(obj, dict):
                if "inline_data" in obj:
                    d = obj["inline_data"]
                    b64 = d.get("data", "")
                    return {"inline_data": {"mime_type": d.get("mime_type"), "data": f"<{len(b64)} chars>"}}
                return {k: _sanitize_for_log(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_sanitize_for_log(x) for x in obj]
            return obj

        log_payload = _sanitize_for_log(payload)
        si = payload.get("systemInstruction") or {}
        si_text = (si.get("parts", [{}])[0].get("text", "") if si.get("parts") else "")
        logger.info(
            "Vertex translated: systemInstruction_len=%d preview=%s",
            len(si_text),
            repr(si_text[:500]) + ("..." if len(si_text) > 500 else ""),
        )
        for ci, cont in enumerate(log_payload.get("contents", [])):
            for pi, part in enumerate(cont.get("parts", [])):
                if "text" in part:
                    t = part["text"]
                    logger.info("Vertex contents[%d].parts[%d] text len=%d preview=%s", ci, pi, len(t), repr(t[:300]) + ("..." if len(t) > 300 else ""))
                elif "inline_data" in part:
                    logger.info("Vertex contents[%d].parts[%d] inline_data %s", ci, pi, part["inline_data"])
        # Log raw incoming messages structure (to verify image_url parts arrived)
        for i, msg in enumerate(request.get("messages", [])):
            c = msg.get("content", "")
            if isinstance(c, list):
                part_types = [p.get("type") for p in c if isinstance(p, dict)]
                has_img = any(t == "image_url" for t in part_types)
                logger.info("Vertex incoming msg[%d] role=%s content=list len=%d part_types=%s has_image_url=%s", i, msg.get("role"), len(c), part_types, has_img)
            else:
                logger.info("Vertex incoming msg[%d] role=%s content=str len=%d", i, msg.get("role"), len(str(c)))

        return url, payload, headers
    
    def normalize_response(
        self,
        response: Dict[str, Any],
        context: Optional[ProviderContext] = None
    ) -> Dict[str, Any]:
        """
        Normalize Vertex AI response to OpenAI format.
        
        Vertex AI response format:
        {
            "candidates": [{
                "content": {
                    "parts": [{"text": "..."}]
                },
                "finishReason": "STOP"
            }],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 20,
                "totalTokenCount": 30
            }
        }
        
        OpenAI format:
        {
            "choices": [{"message": {"content": "..."}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 30}
        }
        
        Args:
            response: Vertex AI response dict
            context: Provider context (optional)
            
        Returns:
            OpenAI-compatible response dict
        """
        normalized = {
            "choices": [],
            "usage": {}
        }
        
        # Normalize candidates to choices
        if "candidates" in response:
            for idx, candidate in enumerate(response["candidates"]):
                content = candidate.get("content", {})
                parts = content.get("parts", [])
                
                # Extract text from parts (Gemini may return function_call in parts instead of text)
                text_parts = [part.get("text", "") for part in parts if "text" in part]
                content_text = "".join(text_parts)
                if not content_text and parts:
                    part_keys = [list(p.keys()) for p in parts[:3]]
                    logger.warning(f"Vertex: empty text from {len(parts)} parts, part_keys={part_keys}")
                
                # Convert finish reason
                finish_reason = candidate.get("finishReason", "STOP").lower()
                if finish_reason == "stop":
                    finish_reason = "stop"
                elif finish_reason == "max_tokens":
                    finish_reason = "length"
                else:
                    finish_reason = "stop"  # Default
                
                normalized_choice = {
                    "index": idx,
                    "message": {
                        "role": "assistant",
                        "content": content_text
                    },
                    "finish_reason": finish_reason
                }
                normalized["choices"].append(normalized_choice)
        
        # Normalize usage metadata
        if "usageMetadata" in response:
            usage = response["usageMetadata"]
            normalized["usage"] = {
                "prompt_tokens": usage.get("promptTokenCount", 0),
                "completion_tokens": usage.get("candidatesTokenCount", 0),
                "total_tokens": usage.get("totalTokenCount", 0)
            }
        
        # Copy other fields
        if "model" in response:
            normalized["model"] = response["model"]
        
        logger.debug("Vertex AI translator: normalized response")
        return normalized
    
    def normalize_stream_chunk(
        self,
        chunk: Dict[str, Any],
        context: Optional[ProviderContext] = None
    ) -> Dict[str, Any]:
        """
        Normalize Vertex AI streaming chunk to OpenAI format.
        
        Args:
            chunk: Vertex AI streaming chunk
            context: Provider context (optional)
            
        Returns:
            OpenAI-compatible streaming chunk
        """
        # Vertex AI streaming chunks have similar structure
        # Extract delta from candidates[0].content.parts
        if "candidates" in chunk and len(chunk["candidates"]) > 0:
            candidate = chunk["candidates"][0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            
            # Extract text delta
            text_parts = [part.get("text", "") for part in parts if "text" in part]
            delta_text = "".join(text_parts)
            
            return {
                "id": chunk.get("id", ""),
                "object": "chat.completion.chunk",
                "created": chunk.get("created", 0),
                "model": chunk.get("model", ""),
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": delta_text
                    },
                    "finish_reason": candidate.get("finishReason")
                }]
            }
        
        # Fallback: normalize as regular response
        return self.normalize_response(chunk, context)
