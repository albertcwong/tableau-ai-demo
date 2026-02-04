"""Tests for gateway request/response translators."""
import pytest
from app.services.gateway.translators.openai import OpenAITranslator
from app.services.gateway.translators.salesforce import SalesforceTranslator
from app.services.gateway.translators.vertex import VertexTranslator
from app.services.gateway.translators.normalizer import normalize_response, normalize_stream_chunk
from app.services.gateway.router import ProviderContext


# ===== OpenAI Translator Tests =====

def test_openai_translator_passthrough():
    """Test OpenAI translator passes through requests unchanged."""
    translator = OpenAITranslator()
    request = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.7
    }
    
    url, payload, headers = translator.transform_request(request)
    assert url == "https://api.openai.com/v1/chat/completions"
    assert payload == request  # Unchanged
    assert "Content-Type" in headers
    assert "x-sfdc-app-context" not in headers


def test_openai_translator_anthropic():
    """Test OpenAI translator handles Anthropic provider."""
    translator = OpenAITranslator()
    request = {
        "model": "claude-3-opus",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    context = ProviderContext(provider="anthropic", auth_type="direct", model_name="claude-3-opus")
    
    url, payload, headers = translator.transform_request(request, context)
    assert "anthropic.com" in url
    assert payload == request


def test_openai_translator_response_normalization():
    """Test OpenAI translator normalizes response (passthrough)."""
    translator = OpenAITranslator()
    response = {
        "choices": [{"message": {"content": "Hello"}}],
        "usage": {"total_tokens": 50}
    }
    
    normalized = translator.normalize_response(response)
    assert normalized == response  # Unchanged


def test_openai_translator_stream_chunk():
    """Test OpenAI translator normalizes streaming chunk."""
    translator = OpenAITranslator()
    chunk = {
        "id": "chatcmpl-123",
        "object": "chat.completion.chunk",
        "choices": [{"delta": {"content": "Hello"}}]
    }
    
    normalized = translator.normalize_stream_chunk(chunk)
    assert normalized == chunk  # Unchanged


# ===== Salesforce Translator Tests =====

def test_salesforce_translator_nested_params():
    """Test Salesforce translator creates nested parameters."""
    translator = SalesforceTranslator()
    request = {
        "model": "sfdc-xgen",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.8,
        "top_p": 0.95
    }
    
    url, payload, headers = translator.transform_request(request)
    assert url.endswith("/models/sfdc-xgen/chat-generations")
    assert "parameters" in payload
    assert payload["parameters"]["temperature"] == 0.8
    assert payload["parameters"]["top_p"] == 0.95
    assert payload["messages"] == request["messages"]
    assert headers["x-sfdc-app-context"] == "EinsteinGPT"


def test_salesforce_translator_no_params():
    """Test Salesforce translator works without parameters."""
    translator = SalesforceTranslator()
    request = {
        "model": "einstein-gpt",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    
    url, payload, headers = translator.transform_request(request)
    assert "parameters" not in payload or len(payload.get("parameters", {})) == 0
    assert payload["messages"] == request["messages"]
    assert headers["x-sfdc-app-context"] == "EinsteinGPT"


def test_salesforce_translator_response_normalization():
    """Test Salesforce translator normalizes response."""
    translator = SalesforceTranslator()
    response = {
        "choices": [{"message": {"content": "Hello from Einstein"}}],
        "usage": {"totalTokens": 60}
    }
    
    normalized = translator.normalize_response(response)
    assert normalized["choices"][0]["message"]["content"] == "Hello from Einstein"
    assert normalized["usage"]["total_tokens"] == 60


def test_salesforce_translator_response_with_all_fields():
    """Test Salesforce translator normalizes response with all fields."""
    translator = SalesforceTranslator()
    response = {
        "id": "chat-123",
        "model": "sfdc-xgen",
        "created": 1234567890,
        "choices": [{
            "index": 0,
            "message": {"content": "Hello"},
            "finish_reason": "stop"
        }],
        "usage": {
            "promptTokens": 10,
            "completionTokens": 20,
            "totalTokens": 30
        }
    }
    
    normalized = translator.normalize_response(response)
    assert normalized["id"] == "chat-123"
    assert normalized["model"] == "sfdc-xgen"
    assert normalized["created"] == 1234567890
    assert normalized["usage"]["prompt_tokens"] == 10
    assert normalized["usage"]["completion_tokens"] == 20
    assert normalized["usage"]["total_tokens"] == 30


def test_salesforce_translator_stream_chunk():
    """Test Salesforce translator normalizes streaming chunk."""
    translator = SalesforceTranslator()
    chunk = {
        "id": "chat-123",
        "created": 1234567890,
        "model": "sfdc-xgen",
        "choices": [{
            "index": 0,
            "delta": {"content": "Hello"},
            "finish_reason": None
        }]
    }
    
    normalized = translator.normalize_stream_chunk(chunk)
    assert normalized["object"] == "chat.completion.chunk"
    assert normalized["choices"][0]["delta"]["content"] == "Hello"


# ===== Vertex AI Translator Tests =====

def test_vertex_translator_contents_format():
    """Test Vertex AI translator converts to contents/parts format."""
    translator = VertexTranslator(project_id="test-project", location="us-central1")
    request = {
        "model": "gemini-pro",
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"}
        ],
        "temperature": 0.7,
        "max_tokens": 1024
    }
    
    url, payload, headers = translator.transform_request(request)
    assert "test-project" in url
    assert "us-central1" in url
    assert "gemini-pro" in url
    assert "contents" in payload
    assert len(payload["contents"]) == 3
    assert payload["contents"][0]["role"] == "user"
    assert payload["contents"][0]["parts"][0]["text"] == "Hello"
    assert payload["contents"][1]["role"] == "model"  # assistant → model
    assert payload["contents"][1]["parts"][0]["text"] == "Hi there"
    assert payload["generationConfig"]["temperature"] == 0.7
    assert payload["generationConfig"]["maxOutputTokens"] == 1024


def test_vertex_translator_system_messages():
    """Test Vertex AI translator handles system messages."""
    translator = VertexTranslator(project_id="test-project", location="us-central1")
    request = {
        "model": "gemini-pro",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"}
        ]
    }
    
    url, payload, headers = translator.transform_request(request)
    assert "systemInstruction" in payload
    assert payload["systemInstruction"]["parts"][0]["text"] == "You are a helpful assistant."
    # System message should not be in contents
    assert len(payload["contents"]) == 1
    assert payload["contents"][0]["role"] == "user"


def test_vertex_translator_role_conversion():
    """Test Vertex AI translator converts roles correctly."""
    translator = VertexTranslator()
    
    assert translator._convert_role("user") == "user"
    assert translator._convert_role("system") == "user"
    assert translator._convert_role("assistant") == "model"
    assert translator._convert_role("unknown") == "user"  # Default


def test_vertex_translator_response_normalization():
    """Test Vertex AI translator normalizes response."""
    translator = VertexTranslator()
    response = {
        "candidates": [{
            "content": {
                "parts": [{"text": "Hello from Gemini"}]
            },
            "finishReason": "STOP"
        }],
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 20,
            "totalTokenCount": 30
        }
    }
    
    normalized = translator.normalize_response(response)
    assert normalized["choices"][0]["message"]["content"] == "Hello from Gemini"
    assert normalized["choices"][0]["finish_reason"] == "stop"
    assert normalized["usage"]["prompt_tokens"] == 10
    assert normalized["usage"]["completion_tokens"] == 20
    assert normalized["usage"]["total_tokens"] == 30


def test_vertex_translator_response_multiple_candidates():
    """Test Vertex AI translator handles multiple candidates."""
    translator = VertexTranslator()
    response = {
        "candidates": [
            {
                "content": {"parts": [{"text": "First"}]},
                "finishReason": "STOP"
            },
            {
                "content": {"parts": [{"text": "Second"}]},
                "finishReason": "MAX_TOKENS"
            }
        ]
    }
    
    normalized = translator.normalize_response(response)
    assert len(normalized["choices"]) == 2
    assert normalized["choices"][0]["message"]["content"] == "First"
    assert normalized["choices"][1]["message"]["content"] == "Second"
    assert normalized["choices"][1]["finish_reason"] == "length"  # MAX_TOKENS → length


def test_vertex_translator_stream_chunk():
    """Test Vertex AI translator normalizes streaming chunk."""
    translator = VertexTranslator()
    chunk = {
        "candidates": [{
            "content": {
                "parts": [{"text": "Hello"}]
            },
            "finishReason": None
        }]
    }
    
    normalized = translator.normalize_stream_chunk(chunk)
    assert normalized["object"] == "chat.completion.chunk"
    assert normalized["choices"][0]["delta"]["content"] == "Hello"


def test_vertex_translator_generation_config():
    """Test Vertex AI translator includes all generation config options."""
    translator = VertexTranslator()
    request = {
        "model": "gemini-pro",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.7,
        "max_tokens": 1024,
        "top_p": 0.9,
        "top_k": 40,
        "stop": ["END", "STOP"]
    }
    
    url, payload, headers = translator.transform_request(request)
    config = payload["generationConfig"]
    assert config["temperature"] == 0.7
    assert config["maxOutputTokens"] == 1024
    assert config["topP"] == 0.9
    assert config["topK"] == 40
    assert config["stopSequences"] == ["END", "STOP"]


def test_vertex_translator_stop_string():
    """Test Vertex AI translator handles single stop string."""
    translator = VertexTranslator()
    request = {
        "model": "gemini-pro",
        "messages": [{"role": "user", "content": "Hello"}],
        "stop": "END"
    }
    
    url, payload, headers = translator.transform_request(request)
    assert payload["generationConfig"]["stopSequences"] == ["END"]


# ===== Response Normalizer Tests =====

def test_response_normalizer_openai():
    """Test response normalizer for OpenAI."""
    openai_response = {
        "choices": [{"message": {"content": "Hello"}}],
        "usage": {"total_tokens": 50}
    }
    
    normalized = normalize_response(openai_response, "openai")
    assert normalized["choices"][0]["message"]["content"] == "Hello"
    assert normalized["usage"]["total_tokens"] == 50


def test_response_normalizer_vertex():
    """Test response normalizer for Vertex AI."""
    vertex_response = {
        "candidates": [{
            "content": {
                "parts": [{"text": "Hello from Gemini"}]
            }
        }],
        "usageMetadata": {"totalTokenCount": 45}
    }
    
    normalized = normalize_response(vertex_response, "vertex")
    assert normalized["choices"][0]["message"]["content"] == "Hello from Gemini"
    assert normalized["usage"]["total_tokens"] == 45


def test_response_normalizer_salesforce():
    """Test response normalizer for Salesforce."""
    sfdc_response = {
        "choices": [{"message": {"content": "Hello from Einstein"}}],
        "usage": {"totalTokens": 60}
    }
    
    normalized = normalize_response(sfdc_response, "salesforce")
    assert normalized["choices"][0]["message"]["content"] == "Hello from Einstein"
    assert normalized["usage"]["total_tokens"] == 60


def test_response_normalizer_unknown_provider():
    """Test response normalizer falls back to OpenAI for unknown provider."""
    response = {
        "choices": [{"message": {"content": "Hello"}}]
    }
    
    # Should not raise error, uses OpenAI translator as fallback
    normalized = normalize_response(response, "unknown-provider")
    assert normalized["choices"][0]["message"]["content"] == "Hello"


def test_normalize_stream_chunk():
    """Test stream chunk normalizer."""
    chunk = {
        "candidates": [{
            "content": {"parts": [{"text": "Hello"}]}
        }]
    }
    
    normalized = normalize_stream_chunk(chunk, "vertex")
    assert normalized["object"] == "chat.completion.chunk"
    assert normalized["choices"][0]["delta"]["content"] == "Hello"


# ===== Integration Tests =====

def test_translator_with_context():
    """Test translators work with ProviderContext."""
    context = ProviderContext(
        provider="vertex",
        auth_type="service_account",
        model_name="gemini-pro",
        project_id="test-project",
        location="us-central1"
    )
    
    translator = VertexTranslator()
    request = {
        "model": "gemini-pro",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    
    url, payload, headers = translator.transform_request(request, context)
    assert "test-project" in url
    assert "us-central1" in url


def test_salesforce_translator_custom_base_url():
    """Test Salesforce translator with custom base URL."""
    translator = SalesforceTranslator(base_url="https://custom.salesforce.com/api")
    request = {
        "model": "sfdc-xgen",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    
    url, payload, headers = translator.transform_request(request)
    assert url.startswith("https://custom.salesforce.com/api")
