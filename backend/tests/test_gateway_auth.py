"""Tests for gateway authentication adapters."""
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path

from app.services.gateway.auth.direct import DirectAuthenticator
from app.services.gateway.auth.salesforce import SalesforceAuthenticator
from app.services.gateway.auth.vertex import VertexAuthenticator
from app.services.gateway.cache import TokenCache
from app.services.gateway.router import ProviderContext


# ===== Direct Authenticator Tests =====

@pytest.mark.asyncio
async def test_direct_auth_with_bearer():
    """Test direct auth extracts API key from Bearer header."""
    auth = DirectAuthenticator()
    token = await auth.get_token("Bearer sk-test123")
    assert token == "sk-test123"


@pytest.mark.asyncio
async def test_direct_auth_without_bearer():
    """Test direct auth works without Bearer prefix."""
    auth = DirectAuthenticator()
    token = await auth.get_token("sk-test123")
    assert token == "sk-test123"


@pytest.mark.asyncio
async def test_direct_auth_missing_header():
    """Test direct auth raises error when header is missing."""
    auth = DirectAuthenticator()
    with pytest.raises(ValueError, match="Authorization header required"):
        await auth.get_token(None)


@pytest.mark.asyncio
async def test_direct_auth_empty_token():
    """Test direct auth raises error when token is empty."""
    auth = DirectAuthenticator()
    with pytest.raises(ValueError, match="API key not found"):
        await auth.get_token("Bearer ")


@pytest.mark.asyncio
async def test_direct_auth_refresh():
    """Test direct auth refresh returns same token."""
    auth = DirectAuthenticator()
    token1 = await auth.get_token("Bearer sk-test123")
    token2 = await auth.refresh_token("Bearer sk-test123")
    assert token1 == token2 == "sk-test123"


# ===== Salesforce Authenticator Tests =====

@pytest.fixture
def mock_private_key_file(tmp_path):
    """Create a mock private key file."""
    key_file = tmp_path / "test-key.pem"
    key_file.write_text("""-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA1234567890abcdefghijklmnopqrstuvwxyz
-----END RSA PRIVATE KEY-----""")
    return str(key_file)


@pytest.fixture
def salesforce_config(mock_private_key_file):
    """Salesforce configuration for testing."""
    return {
        "client_id": "test-client-id",
        "private_key_path": mock_private_key_file,
        "username": "test@example.com",
    }


@pytest.fixture
def mock_httpx_post():
    """Mock httpx.AsyncClient.post for token exchange."""
    with patch("app.services.gateway.auth.salesforce.httpx.AsyncClient") as mock_client:
        client_instance = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "00D1234567890abcdef",
            "instance_url": "https://test.salesforce.com",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        mock_response.raise_for_status = Mock()
        client_instance.post.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = client_instance
        mock_client.return_value.__aexit__.return_value = None
        yield client_instance


@pytest.mark.asyncio
async def test_salesforce_auth_generate_jwt(salesforce_config, mock_httpx_post):
    """Test Salesforce auth generates JWT and exchanges for token."""
    with patch("app.services.gateway.auth.salesforce.token_cache") as mock_cache:
        mock_cache.get.return_value = None  # No cached token
        mock_cache.set.return_value = True
        
        auth = SalesforceAuthenticator(**salesforce_config)
        token = await auth.get_token()
        
        assert token == "00D1234567890abcdef"
        # Verify JWT was generated and exchanged
        assert mock_httpx_post.post.called


@pytest.mark.asyncio
async def test_salesforce_auth_uses_cache(salesforce_config, mock_httpx_post):
    """Test Salesforce auth uses cached token when available."""
    with patch("app.services.gateway.auth.salesforce.token_cache") as mock_cache:
        mock_cache.get.return_value = {
            "token": "cached-token-123",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        }
        
        auth = SalesforceAuthenticator(**salesforce_config)
        token = await auth.get_token()
        
        assert token == "cached-token-123"
        # Should not call token exchange
        assert not mock_httpx_post.post.called


@pytest.mark.asyncio
async def test_salesforce_auth_refresh(salesforce_config, mock_httpx_post):
    """Test Salesforce auth refresh clears cache and gets new token."""
    with patch("app.services.gateway.auth.salesforce.token_cache") as mock_cache:
        mock_cache.get.return_value = None
        mock_cache.delete.return_value = True
        mock_cache.set.return_value = True
        
        auth = SalesforceAuthenticator(**salesforce_config)
        token = await auth.refresh_token()
        
        assert token == "00D1234567890abcdef"
        # Verify cache was cleared
        mock_cache.delete.assert_called_once_with("salesforce", salesforce_config["client_id"])


@pytest.mark.asyncio
async def test_salesforce_auth_missing_credentials():
    """Test Salesforce auth raises error when credentials are missing."""
    with pytest.raises(ValueError, match="SALESFORCE_CLIENT_ID is required"):
        SalesforceAuthenticator(client_id="")


@pytest.mark.asyncio
async def test_salesforce_auth_missing_key_file(salesforce_config):
    """Test Salesforce auth raises error when key file doesn't exist."""
    config = salesforce_config.copy()
    config["private_key_path"] = "/nonexistent/key.pem"
    
    with pytest.raises(FileNotFoundError):
        auth = SalesforceAuthenticator(**config)
        await auth.get_token()


# ===== Vertex Authenticator Tests =====

@pytest.fixture
def mock_service_account_file(tmp_path):
    """Create a mock service account JSON file."""
    sa_file = tmp_path / "vertex-sa.json"
    sa_data = {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "test-key-id",
        "private_key": "-----BEGIN PRIVATE KEY-----\ntest-key\n-----END PRIVATE KEY-----",
        "client_email": "test@test-project.iam.gserviceaccount.com",
        "client_id": "123456789",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    sa_file.write_text(json.dumps(sa_data))
    return str(sa_file)


@pytest.fixture
def vertex_config(mock_service_account_file):
    """Vertex AI configuration for testing."""
    return {
        "project_id": "test-project",
        "location": "us-central1",
        "service_account_path": mock_service_account_file,
    }


@pytest.fixture
def mock_google_credentials():
    """Mock Google service account credentials."""
    with patch("app.services.gateway.auth.vertex.service_account.Credentials") as mock_creds:
        creds_instance = Mock()
        creds_instance.valid = True
        creds_instance.token = "ya29.test-token-123"
        creds_instance.expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        creds_instance.refresh = Mock()
        mock_creds.from_service_account_info.return_value = creds_instance
        yield creds_instance


@pytest.mark.asyncio
async def test_vertex_auth_get_token(vertex_config, mock_google_credentials):
    """Test Vertex auth gets token from service account."""
    with patch("app.services.gateway.auth.vertex.token_cache") as mock_cache:
        mock_cache.get.return_value = None  # No cached token
        mock_cache.set.return_value = True
        
        auth = VertexAuthenticator(**vertex_config)
        token = await auth.get_token()
        
        assert token == "ya29.test-token-123"


@pytest.mark.asyncio
async def test_vertex_auth_uses_cache(vertex_config, mock_google_credentials):
    """Test Vertex auth uses cached token when available."""
    with patch("app.services.gateway.auth.vertex.token_cache") as mock_cache:
        mock_cache.get.return_value = {
            "token": "cached-vertex-token",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        }
        
        auth = VertexAuthenticator(**vertex_config)
        token = await auth.get_token()
        
        assert token == "cached-vertex-token"


@pytest.mark.asyncio
async def test_vertex_auth_refresh(vertex_config, mock_google_credentials):
    """Test Vertex auth refresh clears cache and gets new token."""
    with patch("app.services.gateway.auth.vertex.token_cache") as mock_cache:
        mock_cache.get.return_value = None
        mock_cache.delete.return_value = True
        mock_cache.set.return_value = True
        
        auth = VertexAuthenticator(**vertex_config)
        token = await auth.refresh_token()
        
        assert token == "ya29.test-token-123"
        # Verify cache was cleared
        mock_cache.delete.assert_called_once_with("vertex", vertex_config["project_id"])


@pytest.mark.asyncio
async def test_vertex_auth_missing_credentials():
    """Test Vertex auth raises error when credentials are missing."""
    with pytest.raises(ValueError, match="VERTEX_PROJECT_ID is required"):
        VertexAuthenticator(project_id="")


@pytest.mark.asyncio
async def test_vertex_auth_missing_sa_file(vertex_config):
    """Test Vertex auth raises error when service account file doesn't exist."""
    config = vertex_config.copy()
    config["service_account_path"] = "/nonexistent/sa.json"
    
    with pytest.raises(FileNotFoundError):
        auth = VertexAuthenticator(**config)
        await auth.get_token()


# ===== Token Cache Tests =====

@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    mock_redis = Mock()
    mock_redis.get.return_value = None
    mock_redis.setex.return_value = True
    mock_redis.delete.return_value = True
    mock_redis.scan_iter.return_value = []
    return mock_redis


def test_token_cache_get_miss(mock_redis_client):
    """Test token cache returns None on cache miss."""
    cache = TokenCache(mock_redis_client)
    result = cache.get("test-provider", "test-id")
    assert result is None
    mock_redis_client.get.assert_called_once_with("token:test-provider:test-id")


def test_token_cache_get_hit(mock_redis_client):
    """Test token cache returns cached token."""
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    cached_data = json.dumps({
        "token": "test-token-123",
        "expires_at": expires_at.isoformat(),
        "cached_at": datetime.now(timezone.utc).isoformat()
    })
    mock_redis_client.get.return_value = cached_data.encode()
    
    cache = TokenCache(mock_redis_client)
    result = cache.get("test-provider", "test-id")
    
    assert result is not None
    assert result["token"] == "test-token-123"


def test_token_cache_get_expired(mock_redis_client):
    """Test token cache returns None for expired token."""
    # Token expired 10 minutes ago
    expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    cached_data = json.dumps({
        "token": "expired-token",
        "expires_at": expires_at.isoformat(),
    })
    mock_redis_client.get.return_value = cached_data.encode()
    
    cache = TokenCache(mock_redis_client)
    result = cache.get("test-provider", "test-id")
    
    assert result is None
    # Should delete expired token
    mock_redis_client.delete.assert_called_once_with("token:test-provider:test-id")


def test_token_cache_set_with_expires_at(mock_redis_client):
    """Test token cache sets token with expiration datetime."""
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    
    cache = TokenCache(mock_redis_client)
    result = cache.set(
        "test-provider",
        "test-id",
        "test-token",
        expires_at=expires_at
    )
    
    assert result is True
    # Verify setex was called with calculated TTL (1 hour - 5 min buffer = 55 min)
    mock_redis_client.setex.assert_called_once()
    call_args = mock_redis_client.setex.call_args
    assert call_args[0][0] == "token:test-provider:test-id"
    assert 3300 <= call_args[0][1] <= 3600  # TTL should be ~55 minutes


def test_token_cache_set_with_expires_in(mock_redis_client):
    """Test token cache sets token with expiration seconds."""
    cache = TokenCache(mock_redis_client)
    result = cache.set(
        "test-provider",
        "test-id",
        "test-token",
        expires_in_seconds=3600
    )
    
    assert result is True
    mock_redis_client.setex.assert_called_once()


def test_token_cache_delete(mock_redis_client):
    """Test token cache deletes token."""
    cache = TokenCache(mock_redis_client)
    result = cache.delete("test-provider", "test-id")
    
    assert result is True
    mock_redis_client.delete.assert_called_once_with("token:test-provider:test-id")


def test_token_cache_clear_provider(mock_redis_client):
    """Test token cache clears all tokens for provider."""
    mock_redis_client.scan_iter.return_value = [
        b"token:test-provider:id1",
        b"token:test-provider:id2"
    ]
    
    cache = TokenCache(mock_redis_client)
    deleted = cache.clear_provider("test-provider")
    
    assert deleted == 2
    mock_redis_client.delete.assert_called_once_with(
        b"token:test-provider:id1",
        b"token:test-provider:id2"
    )
