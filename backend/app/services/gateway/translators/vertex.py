"""Vertex AI translator - convert to contents/parts format."""
import logging
from typing import Dict, Any, Tuple, Optional
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
        
        # Convert regular messages to contents format
        contents = []
        for msg in regular_messages:
            role = self._convert_role(msg.get("role", "user"))
            content = msg.get("content", "")
            
            contents.append({
                "role": role,
                "parts": [{"text": content}]
            })
        
        # Build payload
        payload = {
            "contents": contents
        }
        
        # Add system instruction if present
        if system_messages:
            # Vertex AI uses systemInstruction field
            system_content = "\n".join([msg.get("content", "") for msg in system_messages])
            payload["systemInstruction"] = {
                "parts": [{"text": system_content}]
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
        
        logger.debug(f"Vertex AI translator: transformed request for model {model_name}")
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
