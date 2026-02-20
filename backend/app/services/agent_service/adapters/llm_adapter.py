"""LLM adapter protocol and implementation."""
from typing import Any, Dict, List, Optional, AsyncIterator, Protocol


class LLMAdapterProtocol(Protocol):
    """Protocol for LLM access - enables pluggable implementations."""

    async def chat(
        self,
        model: str,
        provider: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Any:
        """Chat completion. Returns object with .content, .tokens_used, .function_call."""
        ...

    async def chat_stream(
        self,
        model: str,
        provider: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[Any]:
        """Stream chat completion."""
        ...


class LLMAdapterImpl:
    """Adapter that wraps UnifiedAIClient."""

    def __init__(self, client: Any):
        self._client = client

    async def chat(
        self,
        model: str,
        provider: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Any:
        return await self._client.chat(
            model=model,
            provider=provider,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            functions=functions,
            **kwargs
        )

    async def chat_stream(
        self,
        model: str,
        provider: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[Any]:
        async for chunk in self._client.chat_stream(
            model=model,
            provider=provider,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        ):
            yield chunk
