"""Unified AI client that talks to gateway."""
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, AsyncIterator
import httpx
from app.services.ai.models import ChatResponse, ChatMessage, FunctionCall, StreamChunk
from app.core.config import settings

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1  # seconds
MAX_RETRY_DELAY = 10  # seconds


class AIClientError(Exception):
    """Base exception for AI client errors."""
    pass


class AIGatewayError(AIClientError):
    """Exception for gateway errors."""
    pass


class AINetworkError(AIClientError):
    """Exception for network errors."""
    pass


class UnifiedAIClient:
    """Unified AI client that communicates with the gateway."""
    
    def __init__(
        self,
        gateway_url: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = MAX_RETRIES
    ):
        """Initialize unified AI client.
        
        Args:
            gateway_url: Gateway base URL (defaults to settings.BACKEND_API_URL; gateway is embedded)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.gateway_url = (gateway_url or settings.BACKEND_API_URL).rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        
        # HTTP client
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True
        )
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers.
        
        Returns:
            Headers dict (gateway resolves credentials from ProviderConfig)
        """
        return {
            "Content-Type": "application/json"
        }
    
    async def _request_with_retry(
        self,
        method: str,
        url: str,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        stream: bool = False
    ) -> httpx.Response:
        """Make HTTP request with retry logic.
        
        Args:
            method: HTTP method
            url: Request URL
            json_data: JSON payload
            headers: Request headers
            stream: Whether this is a streaming request (not used in httpx, handled separately)
            
        Returns:
            HTTP response
            
        Raises:
            AIGatewayError: For gateway errors
            AINetworkError: For network errors
        """
        headers = headers or {}
        
        for attempt in range(self.max_retries):
            try:
                # httpx doesn't accept stream parameter in request(), handle streaming separately
                response = await self._client.request(
                    method=method,
                    url=url,
                    json=json_data,
                    headers=headers
                )
                
                # Check for HTTP errors
                if response.status_code >= 400:
                    error_msg = f"Gateway error: {response.status_code}"
                    try:
                        error_data = response.json()
                        # FastAPI returns {"detail": "error message"}
                        if "detail" in error_data:
                            error_msg = error_data["detail"]
                        elif "error" in error_data:
                            # Some APIs use {"error": {"message": "..."}}
                            error_msg = error_data.get("error", {}).get("message", error_msg)
                        else:
                            error_msg = f"{error_msg} - {response.text[:200]}"
                    except (KeyError, TypeError, AttributeError) as e:
                        # Expected errors when parsing error response JSON - use fallback
                        logger.debug(f"Could not parse error response JSON: {e}")
                        error_msg = f"{error_msg} - {response.text[:200]}"
                    except Exception as e:
                        # Log unexpected errors but use fallback
                        logger.warning(f"Unexpected error parsing error response: {e}", exc_info=True)
                        error_msg = f"{error_msg} - {response.text[:200]}"
                    
                    # Don't retry on 4xx errors (client errors)
                    if 400 <= response.status_code < 500:
                        raise AIGatewayError(error_msg)
                    
                    # Retry on 5xx errors (server errors)
                    if attempt == self.max_retries - 1:
                        raise AIGatewayError(f"{error_msg} (after {self.max_retries} attempts)")
                    
                    # Exponential backoff
                    delay = min(INITIAL_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                    logger.warning(f"Gateway error {response.status_code}, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})")
                    await asyncio.sleep(delay)
                    continue
                
                return response
                
            except httpx.TimeoutException as e:
                if attempt == self.max_retries - 1:
                    raise AINetworkError(f"Request timeout after {self.max_retries} attempts") from e
                delay = min(INITIAL_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                logger.warning(f"Request timeout, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})")
                await asyncio.sleep(delay)
                
            except httpx.RequestError as e:
                if attempt == self.max_retries - 1:
                    raise AINetworkError(f"Network error after {self.max_retries} attempts: {e}") from e
                delay = min(INITIAL_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                logger.warning(f"Network error, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries}): {e}")
                await asyncio.sleep(delay)
        
        raise AINetworkError("Failed to complete request after retries")
    
    def _parse_chat_response(self, response_data: Dict[str, Any]) -> ChatResponse:
        """Parse gateway response into ChatResponse.
        
        Args:
            response_data: Gateway response dict
            
        Returns:
            ChatResponse object
        """
        choices = response_data.get("choices", [])
        if not choices:
            # Log raw response for debugging provider/gateway issues
            err_detail = ""
            if "error" in response_data:
                err = response_data.get("error", {})
                err_detail = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            elif "detail" in response_data:
                err_detail = str(response_data["detail"])
            logger.warning(
                "No choices in gateway response: %s",
                json.dumps({k: v for k, v in response_data.items() if k != "usage"})[:500]
            )
            raise AIGatewayError(
                err_detail or "No choices in response (provider may have filtered or timed out)"
            )
        
        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "") or message.get("text", "")
        
        # Parse function call if present (handle both old and new formats)
        function_call = None
        if "function_call" in message:
            fc_data = message["function_call"]
            function_call = FunctionCall(
                name=fc_data.get("name", ""),
                arguments=fc_data.get("arguments", "{}")
            )
        elif "tool_calls" in message and message.get("tool_calls"):
            # New format: tool_calls array - extract first tool call
            tool_calls = message.get("tool_calls", [])
            if tool_calls:
                tc = tool_calls[0]
                function_data = tc.get("function", {})
                function_call = FunctionCall(
                    name=function_data.get("name", ""),
                    arguments=function_data.get("arguments", "{}")
                )
        
        # Parse usage
        usage = response_data.get("usage", {})
        tokens_used = usage.get("total_tokens", 0)
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        
        return ChatResponse(
            content=content,
            model=response_data.get("model", ""),
            tokens_used=tokens_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=choice.get("finish_reason", "stop"),
            function_call=function_call,
            raw_response=response_data
        )
    
    async def chat(
        self,
        model: str,
        provider: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_call: Optional[str] = None,
        **kwargs
    ) -> ChatResponse:
        """
        Send chat completion request to gateway.
        
        Args:
            model: Model name (e.g., "gpt-4", "gemini-pro", "sfdc-xgen")
            provider: Provider name (e.g., "openai", "apple", "vertex")
            messages: List of message dicts with "role" and "content"
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            functions: List of function definitions for function calling
            function_call: Function call mode ("auto", "none", or {"name": "function_name"})
            **kwargs: Additional parameters passed to gateway
            
        Returns:
            ChatResponse object
            
        Raises:
            AIGatewayError: For gateway errors
            AINetworkError: For network errors
        """
        # Build request payload
        payload = {
            "model": model,
            "provider": provider,
            "messages": messages
        }
        
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if top_p is not None:
            payload["top_p"] = top_p
        if functions is not None:
            payload["functions"] = functions
        if function_call is not None:
            payload["function_call"] = function_call
        if "tools" in kwargs:
            payload["tools"] = kwargs.pop("tools")
        if "tool_choice" in kwargs:
            payload["tool_choice"] = kwargs.pop("tool_choice")
        payload.update(kwargs)
        
        url = f"{self.gateway_url}/api/v1/gateway/v1/chat/completions"
        headers = self._get_headers()
        
        logger.debug(f"Sending chat request to gateway: model={model}, messages={len(messages)}")
        logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
        logger.debug(f"Request headers: {dict((k, v[:20] + '...' if len(v) > 20 else v) if k == 'Authorization' else (k, v) for k, v in headers.items())}")
        
        try:
            response = await self._request_with_retry(
                method="POST",
                url=url,
                json_data=payload,
                headers=headers
            )
            
            response_data = response.json()
            chat_response = self._parse_chat_response(response_data)
            
            logger.info(
                f"Chat completion successful: model={model}, tokens={chat_response.tokens_used}, "
                f"content_len={len(chat_response.content or '')}, finish_reason={chat_response.finish_reason}"
            )
            return chat_response
            
        except (AIGatewayError, AINetworkError):
            raise
        except Exception as e:
            raise AIClientError(f"Unexpected error in chat completion: {e}") from e
    
    async def stream_chat(
        self,
        model: str,
        provider: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_call: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        Send streaming chat completion request to gateway.
        
        Args:
            model: Model name
            provider: Provider name (e.g., "openai", "apple", "vertex")
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            functions: List of function definitions
            function_call: Function call mode
            **kwargs: Additional parameters
            
        Yields:
            StreamChunk objects
            
        Raises:
            AIGatewayError: For gateway errors
            AINetworkError: For network errors
        """
        # Build request payload
        payload = {
            "model": model,
            "provider": provider,
            "messages": messages,
            "stream": True
        }
        
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if top_p is not None:
            payload["top_p"] = top_p
        if functions is not None:
            payload["functions"] = functions
        if function_call is not None:
            payload["function_call"] = function_call
        
        payload.update(kwargs)
        
        url = f"{self.gateway_url}/api/v1/gateway/v1/chat/completions"
        headers = self._get_headers()
        
        logger.debug(f"Sending streaming chat request to gateway: model={model}")
        logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
        logger.debug(f"Request headers: {dict((k, v[:20] + '...' if len(v) > 20 else v) if k == 'Authorization' else (k, v) for k, v in headers.items())}")
        
        try:
            # Use httpx.stream() for streaming requests
            async with self._client.stream(
                method="POST",
                url=url,
                json=payload,
                headers=headers
            ) as response:
                # Check for HTTP errors before streaming
                if response.status_code >= 400:
                    error_msg = f"Gateway error: {response.status_code}"
                    try:
                        error_text = await response.aread()
                        error_json = json.loads(error_text.decode())
                        # FastAPI returns {"detail": "error message"}
                        if "detail" in error_json:
                            error_msg = error_json["detail"]
                        elif "error" in error_json:
                            # Some APIs use {"error": {"message": "..."}}
                            error_msg = error_json.get("error", {}).get("message", error_msg)
                        else:
                            error_msg = f"{error_msg} - {error_text.decode()[:200]}"
                    except Exception as e:
                        logger.warning(f"Failed to parse error response: {e}")
                        error_msg = f"{error_msg}"
                    raise AIGatewayError(error_msg)
                
                # Parse Server-Sent Events stream
                line_count = 0
                chunk_count = 0
                logger.info("Starting to parse SSE stream from gateway")
                async for line in response.aiter_lines():
                    line_count += 1
                    if not line.strip():
                        continue
                    
                    logger.info(f"AI client received SSE line {line_count}: {line[:200]}")
                    
                    # SSE format: "data: {...}" or "data: [DONE]"
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        
                        if data_str.strip() == "[DONE]":
                            logger.info("AI client received [DONE] marker")
                            break
                        
                        try:
                            chunk_data = json.loads(data_str)
                            logger.info(f"AI client parsed chunk data {chunk_count + 1}: {json.dumps(chunk_data)[:300]}")
                            
                            # Parse chunk
                            choices = chunk_data.get("choices", [])
                            if choices:
                                choice = choices[0]
                                delta = choice.get("delta", {})
                                content = delta.get("content", "")
                                
                                logger.info(f"AI client extracted content from chunk {chunk_count + 1}: '{content[:100]}' (length: {len(content)})")
                                
                                # Parse function call delta if present
                                function_call = None
                                if "function_call" in delta:
                                    fc_data = delta["function_call"]
                                    function_call = FunctionCall(
                                        name=fc_data.get("name", ""),
                                        arguments=fc_data.get("arguments", "")
                                    )
                                
                                chunk = StreamChunk(
                                    content=content,
                                    finish_reason=choice.get("finish_reason"),
                                    function_call=function_call,
                                    raw_chunk=chunk_data
                                )
                                
                                chunk_count += 1
                                yield chunk
                            else:
                                logger.warning(f"No choices in chunk: {chunk_data}")
                                
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse SSE chunk: {e}, line: {line[:100]}")
                            continue
                    else:
                        logger.info(f"AI client non-data SSE line {line_count}: {line[:100]}")
                
                logger.info(f"AI client stream parsing complete: {line_count} lines processed, {chunk_count} chunks yielded")
            
            logger.info(f"Streaming chat completion finished: model={model}")
            
        except (AIGatewayError, AINetworkError):
            raise
        except Exception as e:
            raise AIClientError(f"Unexpected error in streaming chat completion: {e}") from e
    
    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
