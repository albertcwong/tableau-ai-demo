"""Tests for gateway router."""
import json
import pytest
from app.services.gateway.router import (
    resolve_context,
    ProviderContext,
    get_available_providers,
    get_available_models,
    load_model_mapping,
    get_model_mapping,
)


def test_resolve_context_openai():
    """Test resolving OpenAI model context."""
    context = resolve_context("gpt-4")
    assert context.provider == "openai"
    assert context.auth_type == "direct"
    assert context.model_name == "gpt-4"
    assert context.requires_trust_header is False


def test_resolve_context_anthropic():
    """Test resolving Anthropic model context."""
    context = resolve_context("claude-3-opus")
    assert context.provider == "anthropic"
    assert context.auth_type == "direct"
    assert context.model_name == "claude-3-opus"


def test_resolve_context_salesforce():
    """Test resolving Salesforce model context."""
    context = resolve_context("sfdc-xgen")
    assert context.provider == "salesforce"
    assert context.auth_type == "jwt_oauth"
    assert context.requires_trust_header is True


def test_resolve_context_vertex():
    """Test resolving Vertex AI model context."""
    context = resolve_context("gemini-pro")
    assert context.provider == "vertex"
    assert context.auth_type == "service_account"
    assert context.requires_trust_header is False


def test_resolve_context_unknown_model():
    """Test that unknown models raise ValueError."""
    with pytest.raises(ValueError, match="Unknown model"):
        resolve_context("invalid-model")


def test_resolve_context_empty_model():
    """Test that empty model name raises ValueError."""
    with pytest.raises(ValueError, match="Model name is required"):
        resolve_context("")


def test_resolve_context_none_model():
    """Test that None model name raises ValueError."""
    with pytest.raises(ValueError, match="Model name is required"):
        resolve_context(None)


def test_get_available_providers():
    """Test getting list of available providers."""
    providers = get_available_providers()
    assert isinstance(providers, list)
    assert len(providers) > 0
    assert "openai" in providers
    assert "anthropic" in providers
    assert "vertex" in providers
    assert "salesforce" in providers


def test_get_available_models():
    """Test getting list of available models."""
    models = get_available_models()
    assert isinstance(models, list)
    assert len(models) > 0
    assert "gpt-4" in models
    assert "claude-3-opus" in models
    assert "gemini-pro" in models


def test_get_available_models_filtered_by_provider():
    """Test getting models filtered by provider."""
    openai_models = get_available_models(provider="openai")
    assert isinstance(openai_models, list)
    assert all("gpt" in model.lower() for model in openai_models)
    
    vertex_models = get_available_models(provider="vertex")
    assert isinstance(vertex_models, list)
    assert all("gemini" in model.lower() for model in vertex_models)


def test_provider_context_dataclass():
    """Test ProviderContext dataclass."""
    context = ProviderContext(
        provider="openai",
        auth_type="direct",
        model_name="gpt-4"
    )
    assert context.provider == "openai"
    assert context.auth_type == "direct"
    assert context.model_name == "gpt-4"
    assert context.requires_trust_header is False


def test_provider_context_salesforce_fields(monkeypatch):
    """Test ProviderContext with Salesforce-specific fields."""
    monkeypatch.setenv("SALESFORCE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SALESFORCE_PRIVATE_KEY_PATH", "./test-key.pem")
    monkeypatch.setenv("SALESFORCE_USERNAME", "test@example.com")
    
    # Reload settings to pick up env vars
    from app.core.config import Settings
    settings = Settings()
    
    context = resolve_context("sfdc-xgen")
    assert context.provider == "salesforce"
    assert context.auth_type == "jwt_oauth"
    assert context.requires_trust_header is True
    # Note: These fields are set from settings, so they'll be empty in test
    # unless we mock the settings object


def test_provider_context_vertex_fields(monkeypatch):
    """Test ProviderContext with Vertex AI-specific fields."""
    monkeypatch.setenv("VERTEX_PROJECT_ID", "test-project")
    monkeypatch.setenv("VERTEX_LOCATION", "us-east1")
    monkeypatch.setenv("VERTEX_SERVICE_ACCOUNT_PATH", "./test-sa.json")
    
    # Reload settings to pick up env vars
    from app.core.config import Settings
    settings = Settings()
    
    context = resolve_context("gemini-pro")
    assert context.provider == "vertex"
    assert context.auth_type == "service_account"
    # Note: These fields are set from settings, so they'll be empty in test
    # unless we mock the settings object


def test_model_mapping_caching():
    """Test that model mapping is cached."""
    # Clear cache
    import app.services.gateway.router as router_module
    router_module._model_mapping_cache = None
    
    # First call should load
    mapping1 = get_model_mapping()
    
    # Second call should use cache
    mapping2 = get_model_mapping()
    
    # Should be the same object (cached)
    assert mapping1 is mapping2


def test_multiple_models_per_provider():
    """Test that multiple models can map to the same provider."""
    openai_models = get_available_models(provider="openai")
    assert len(openai_models) > 1
    
    # All should resolve to same provider
    for model in openai_models[:3]:  # Test first 3
        context = resolve_context(model)
        assert context.provider == "openai"
        assert context.auth_type == "direct"


def test_salesforce_trust_header():
    """Test that Salesforce models require trust header."""
    sfdc_models = get_available_models(provider="salesforce")
    
    for model in sfdc_models:
        context = resolve_context(model)
        assert context.requires_trust_header is True


def test_vertex_service_account_auth():
    """Test that Vertex models use service account auth."""
    vertex_models = get_available_models(provider="vertex")
    
    for model in vertex_models:
        context = resolve_context(model)
        assert context.auth_type == "service_account"


@pytest.mark.parametrize("model_name,expected_provider,expected_auth", [
    ("gpt-4", "openai", "direct"),
    ("gpt-3.5-turbo", "openai", "direct"),
    ("claude-3-opus", "anthropic", "direct"),
    ("claude-3-sonnet", "anthropic", "direct"),
    ("gemini-pro", "vertex", "service_account"),
    ("gemini-1.5-pro", "vertex", "service_account"),
    ("sfdc-xgen", "salesforce", "jwt_oauth"),
    ("einstein-gpt", "salesforce", "jwt_oauth"),
])
def test_model_resolution_parametrized(model_name, expected_provider, expected_auth):
    """Parametrized test for model resolution."""
    context = resolve_context(model_name)
    assert context.provider == expected_provider
    assert context.auth_type == expected_auth
