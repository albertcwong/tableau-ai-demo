"""Tests for unified AI client."""
import pytest
from unittest.mock import AsyncMock, Mock, patch
import json
import httpx
from app.services.ai.client import (
    UnifiedAIClient,
    AIClientError,
    AIGatewayError,
    AINetworkError
)
from app.services.ai.models import ChatResponse, StreamChunk, FunctionCall


@pytest.fixture
def ai_client():
    """Create UnifiedAIClient instance for testing."""
    return UnifiedAIClient(gateway_url="http://localhost:8001")


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient."""
    with patch("app.services.ai.client.httpx.AsyncClient") as mock_client_class:
        client_instance = AsyncMock()
        mock_client_class.return_value = client_instance
        yield client_instance


@pytest.mark.asyncio
async def test_chat_via_gateway(ai_client, mock_httpx_client):
    """Test chat sends request to gateway."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello"}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 20, "prompt_tokens": 10, "completion_tokens": 10},
        "model": "gpt-4"
    }
    mock_httpx_client.request.return_value = mock_response
    
    response = await ai_client.chat(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hi"}]
    )
    
    assert response.content == "Hello"
    assert response.tokens_used == 20
    assert response.prompt_tokens == 10
    assert response.completion_tokens == 10
    assert response.model == "gpt-4"
    assert response.finish_reason == "stop"
    
    # Verify request was made to gateway
    call_args = mock_httpx_client.request.call_args
    assert call_args.kwargs["method"] == "POST"
    assert "/v1/chat/completions" in call_args.kwargs["url"]
    assert call_args.kwargs["json"]["model"] == "gpt-4"


@pytest.mark.asyncio
async def test_chat_with_parameters(ai_client, mock_httpx_client):
    """Test chat with temperature and max_tokens."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Response"}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 30},
        "model": "gpt-4"
    }
    mock_httpx_client.request.return_value = mock_response
    
    await ai_client.chat(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hi"}],
        temperature=0.7,
        max_tokens=100
    )
    
    call_args = mock_httpx_client.request.call_args
    payload = call_args.kwargs["json"]
    assert payload["temperature"] == 0.7
    assert payload["max_tokens"] == 100


@pytest.mark.asyncio
async def test_chat_function_calling(ai_client, mock_httpx_client):
    """Test chat with function calling."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": None,
                "function_call": {
                    "name": "list_datasources",
                    "arguments": "{}"
                }
            },
            "finish_reason": "function_call"
        }],
        "usage": {"total_tokens": 50},
        "model": "gpt-4"
    }
    mock_httpx_client.request.return_value = mock_response
    
    functions = [{
        "name": "list_datasources",
        "parameters": {"type": "object", "properties": {}}
    }]
    
    response = await ai_client.chat(
        model="gpt-4",
        messages=[{"role": "user", "content": "List datasources"}],
        functions=functions
    )
    
    assert response.function_call is not None
    assert response.function_call.name == "list_datasources"
    assert response.function_call.arguments == "{}"
    assert response.finish_reason == "function_call"
    
    # Verify functions were sent in request
    call_args = mock_httpx_client.request.call_args
    assert "functions" in call_args.kwargs["json"]


@pytest.mark.asyncio
async def test_chat_gateway_error_4xx(ai_client, mock_httpx_client):
    """Test chat handles 4xx gateway errors (no retry)."""
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        "error": {"message": "Invalid request"}
    }
    mock_response.text = '{"error": {"message": "Invalid request"}}'
    mock_httpx_client.request.return_value = mock_response
    
    with pytest.raises(AIGatewayError, match="Invalid request"):
        await ai_client.chat(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hi"}]
        )
    
    # Should not retry on 4xx
    assert mock_httpx_client.request.call_count == 1


@pytest.mark.asyncio
async def test_chat_gateway_error_5xx_retry(ai_client, mock_httpx_client):
    """Test chat retries on 5xx gateway errors."""
    ai_client.max_retries = 3
    
    # First two attempts fail, third succeeds
    error_response = Mock()
    error_response.status_code = 500
    error_response.text = "Server Error"
    
    success_response = Mock()
    success_response.status_code = 200
    success_response.json.return_value = {
        "choices": [{"message": {"content": "Success"}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 10},
        "model": "gpt-4"
    }
    
    mock_httpx_client.request.side_effect = [error_response, error_response, success_response]
    
    response = await ai_client.chat(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hi"}]
    )
    
    assert response.content == "Success"
    assert mock_httpx_client.request.call_count == 3


@pytest.mark.asyncio
async def test_chat_network_error_retry(ai_client, mock_httpx_client):
    """Test chat retries on network errors."""
    ai_client.max_retries = 2
    
    # First attempt fails, second succeeds
    mock_httpx_client.request.side_effect = [
        httpx.RequestError("Network error"),
        Mock(status_code=200, json=lambda: {
            "choices": [{"message": {"content": "Success"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 10},
            "model": "gpt-4"
        })
    ]
    
    response = await ai_client.chat(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hi"}]
    )
    
    assert response.content == "Success"
    assert mock_httpx_client.request.call_count == 2


@pytest.mark.asyncio
async def test_chat_timeout_retry(ai_client, mock_httpx_client):
    """Test chat retries on timeout."""
    ai_client.max_retries = 2
    
    mock_httpx_client.request.side_effect = [
        httpx.TimeoutException("Request timeout"),
        Mock(status_code=200, json=lambda: {
            "choices": [{"message": {"content": "Success"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 10},
            "model": "gpt-4"
        })
    ]
    
    response = await ai_client.chat(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hi"}]
    )
    
    assert response.content == "Success"
    assert mock_httpx_client.request.call_count == 2


@pytest.mark.asyncio
async def test_chat_no_choices_error(ai_client, mock_httpx_client):
    """Test chat handles response with no choices."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [],
        "usage": {"total_tokens": 0},
        "model": "gpt-4"
    }
    mock_httpx_client.request.return_value = mock_response
    
    with pytest.raises(AIGatewayError, match="No choices in response"):
        await ai_client.chat(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hi"}]
        )


@pytest.mark.asyncio
async def test_stream_chat(ai_client, mock_httpx_client):
    """Test streaming chat."""
    # Mock streaming response
    mock_response = AsyncMock()
    mock_response.status_code = 200
    
    # Simulate SSE stream
    async def aiter_lines():
        yield "data: {\"choices\": [{\"delta\": {\"content\": \"Hello\"}}]}\n\n"
        yield "data: {\"choices\": [{\"delta\": {\"content\": \" world\"}}]}\n\n"
        yield "data: [DONE]\n\n"
    
    mock_response.aiter_lines = aiter_lines
    mock_httpx_client.request.return_value = mock_response
    
    chunks = []
    async for chunk in ai_client.stream_chat(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hi"}]
    ):
        chunks.append(chunk.content)
    
    assert chunks == ["Hello", " world"]


@pytest.mark.asyncio
async def test_stream_chat_with_function_call(ai_client, mock_httpx_client):
    """Test streaming chat with function call."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    
    async def aiter_lines():
        yield 'data: {"choices": [{"delta": {"function_call": {"name": "list_datasources"}}}]}\n\n'
        yield 'data: {"choices": [{"delta": {"function_call": {"arguments": "{}"}}}]}\n\n'
        yield 'data: [DONE]\n\n'
    
    mock_response.aiter_lines = aiter_lines
    mock_httpx_client.request.return_value = mock_response
    
    chunks = []
    async for chunk in ai_client.stream_chat(
        model="gpt-4",
        messages=[{"role": "user", "content": "List datasources"}],
        functions=[{"name": "list_datasources", "parameters": {}}]
    ):
        chunks.append(chunk)
    
    assert len(chunks) == 2
    assert chunks[0].function_call is not None
    assert chunks[0].function_call.name == "list_datasources"


@pytest.mark.asyncio
async def test_stream_chat_stream_flag(ai_client, mock_httpx_client):
    """Test stream_chat sets stream=True in request."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    
    async def aiter_lines():
        yield "data: [DONE]\n\n"
    
    mock_response.aiter_lines = aiter_lines
    mock_httpx_client.request.return_value = mock_response
    
    async for _ in ai_client.stream_chat(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hi"}]
    ):
        pass
    
    call_args = mock_httpx_client.request.call_args
    assert call_args.kwargs["stream"] is True
    assert call_args.kwargs["json"]["stream"] is True


@pytest.mark.asyncio
async def test_cross_provider_consistency(ai_client, mock_httpx_client):
    """Test that all providers return consistent format."""
    models = ["gpt-4", "gemini-pro", "sfdc-xgen", "claude-3-opus"]
    
    for model in models:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": f"Response from {model}"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 20},
            "model": model
        }
        mock_httpx_client.request.return_value = mock_response
        
        response = await ai_client.chat(
            model=model,
            messages=[{"role": "user", "content": "Hi"}]
        )
        
        assert response.content == f"Response from {model}"
        assert response.model == model


@pytest.mark.asyncio
async def test_client_context_manager(ai_client, mock_httpx_client):
    """Test client works as async context manager."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello"}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 10},
        "model": "gpt-4"
    }
    mock_httpx_client.request.return_value = mock_response
    
    async with ai_client as client:
        response = await client.chat(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hi"}]
        )
        assert response.content == "Hello"
    
    # Verify close was called
    mock_httpx_client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_client_close(ai_client, mock_httpx_client):
    """Test client close method."""
    await ai_client.close()
    mock_httpx_client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_client_api_key_header(ai_client, mock_httpx_client):
    """Test client adds API key to headers."""
    client = UnifiedAIClient(gateway_url="http://localhost:8001", api_key="test-key")
    
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello"}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 10},
        "model": "gpt-4"
    }
    mock_httpx_client.request.return_value = mock_response
    
    await client.chat(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hi"}]
    )
    
    call_args = mock_httpx_client.request.call_args
    headers = call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-key"


@pytest.mark.asyncio
async def test_client_api_key_override(ai_client, mock_httpx_client):
    """Test client can override API key per request."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello"}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 10},
        "model": "gpt-4"
    }
    mock_httpx_client.request.return_value = mock_response
    
    await ai_client.chat(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hi"}],
        api_key="override-key"
    )
    
    call_args = mock_httpx_client.request.call_args
    headers = call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer override-key"


@pytest.mark.asyncio
async def test_chat_additional_kwargs(ai_client, mock_httpx_client):
    """Test chat passes additional kwargs to gateway."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello"}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 10},
        "model": "gpt-4"
    }
    mock_httpx_client.request.return_value = mock_response
    
    await ai_client.chat(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hi"}],
        top_k=40,
        stop=["END"]
    )
    
    call_args = mock_httpx_client.request.call_args
    payload = call_args.kwargs["json"]
    assert payload["top_k"] == 40
    assert payload["stop"] == ["END"]
