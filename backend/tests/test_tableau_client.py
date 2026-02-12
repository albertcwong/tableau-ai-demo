"""Tests for Tableau REST API client."""
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import jwt
import httpx

from app.services.tableau.client import (
    TableauClient,
    TableauClientError,
    TableauAuthenticationError,
    TableauAPIError,
)


@pytest.fixture
def tableau_config():
    """Tableau configuration for testing."""
    return {
        "server_url": "https://tableau.test.com",
        "site_id": "test-site",
        "client_id": "test-client-id",
        "client_secret": "test-secret-value",
        "username": "test-user",
    }


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient."""
    with patch("app.services.tableau.client.httpx.AsyncClient") as mock_client:
        client_instance = AsyncMock()
        mock_client.return_value = client_instance
        yield client_instance


@pytest.fixture
def tableau_client(tableau_config, mock_httpx_client):
    """Create TableauClient instance for testing."""
    return TableauClient(**tableau_config)


@pytest.fixture
def tableau_client_uat(tableau_config, mock_httpx_client):
    """Create TableauClient instance with UAT enabled for testing."""
    return TableauClient(**tableau_config, is_uat=True)


@pytest.mark.asyncio
async def test_client_initialization(tableau_config):
    """Test client initialization with valid config."""
    client = TableauClient(**tableau_config)
    
    assert client.server_url == "https://tableau.test.com"
    assert client.site_id == "test-site"
    assert client.client_id == "test-client-id"
    assert client.client_secret == "test-secret-value"
    assert client.username == "test-user"
    assert client.auth_token is None


def test_client_initialization_missing_url():
    """Test client initialization fails without server URL."""
    with pytest.raises(ValueError, match="Tableau server URL is required"):
        TableauClient(server_url="")


def test_client_initialization_missing_client_id():
    """Test client initialization fails without client ID."""
    with pytest.raises(ValueError, match="Tableau client ID is required"):
        TableauClient(server_url="https://test.com", client_id="")


def test_client_initialization_missing_client_secret():
    """Test client initialization fails without client secret."""
    with pytest.raises(ValueError, match="Tableau client secret is required"):
        TableauClient(
            server_url="https://test.com",
            client_id="test-id",
            client_secret=""
        )


def test_generate_jwt(tableau_client):
    """Test JWT token generation."""
    token = tableau_client._generate_jwt()
    
    assert isinstance(token, str)
    assert len(token) > 0
    
    # Decode and verify token
    decoded = jwt.decode(token, tableau_client.client_secret, algorithms=["HS256"])
    assert decoded["iss"] == tableau_client.client_id
    assert decoded["aud"] == "tableau"
    assert decoded["sub"] == tableau_client.username
    assert "exp" in decoded
    assert "jti" in decoded


def test_generate_jwt_expires_in_max_10_minutes(tableau_client):
    """Test JWT expiration is capped at 10 minutes."""
    token = tableau_client._generate_jwt(expires_in_minutes=20)
    decoded = jwt.decode(token, tableau_client.client_secret, algorithms=["HS256"])
    
    exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = exp_time - now
    
    assert diff <= timedelta(minutes=10)


@pytest.mark.asyncio
async def test_sign_in_success(tableau_client, mock_httpx_client):
    """Test successful sign-in."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "credentials": {
            "token": "test-auth-token",
            "site": {
                "contentUrl": "test-site"
            }
        }
    }
    mock_response.raise_for_status = Mock()
    mock_httpx_client.post.return_value = mock_response
    
    result = await tableau_client.sign_in()
    
    assert result["token"] == "test-auth-token"
    assert result["site_content_url"] == "test-site"
    assert tableau_client.auth_token == "test-auth-token"
    assert tableau_client.site_content_url == "test-site"
    assert tableau_client.token_expires_at is not None
    
    # Verify JWT was generated and used in correct format
    call_args = mock_httpx_client.post.call_args
    assert call_args is not None
    payload = call_args.kwargs["json"]
    assert "credentials" in payload
    assert "jwt" in payload["credentials"]
    assert "site" in payload["credentials"]
    assert payload["credentials"]["site"]["contentUrl"] == "test-site"
    # Should not have isUat for Connected Apps (default)
    assert "isUat" not in payload["credentials"]


@pytest.mark.asyncio
async def test_sign_in_failure_http_error(tableau_client, mock_httpx_client):
    """Test sign-in failure with HTTP error."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
    
    error = httpx.HTTPStatusError("Unauthorized", request=Mock(), response=mock_response)
    mock_httpx_client.post.side_effect = error
    
    with pytest.raises(TableauAuthenticationError):
        await tableau_client.sign_in()


@pytest.mark.asyncio
async def test_sign_in_failure_network_error(tableau_client, mock_httpx_client):
    """Test sign-in failure with network error."""
    mock_httpx_client.post.side_effect = httpx.RequestError("Network error", request=Mock())
    
    with pytest.raises(TableauAuthenticationError):
        await tableau_client.sign_in()


@pytest.mark.asyncio
async def test_ensure_authenticated_no_token(tableau_client, mock_httpx_client):
    """Test _ensure_authenticated signs in when no token."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "credentials": {
            "token": "new-token",
            "site": {"contentUrl": "test-site"}
        }
    }
    mock_response.raise_for_status = Mock()
    mock_httpx_client.post.return_value = mock_response
    
    await tableau_client._ensure_authenticated()
    
    assert tableau_client.auth_token == "new-token"
    assert mock_httpx_client.post.called


@pytest.mark.asyncio
async def test_ensure_authenticated_refreshes_expired_token(tableau_client, mock_httpx_client):
    """Test _ensure_authenticated refreshes expired token."""
    tableau_client.auth_token = "old-token"
    tableau_client.token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    
    mock_response = Mock()
    mock_response.json.return_value = {
        "credentials": {
            "token": "refreshed-token",
            "site": {"contentUrl": "test-site"}
        }
    }
    mock_response.raise_for_status = Mock()
    mock_httpx_client.post.return_value = mock_response
    
    await tableau_client._ensure_authenticated()
    
    assert tableau_client.auth_token == "refreshed-token"
    assert mock_httpx_client.post.called


@pytest.mark.asyncio
async def test_sign_in_with_uat(tableau_client_uat, mock_httpx_client):
    """Test sign-in with Unified Access Token (isUat=True)."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "credentials": {
            "token": "uat-token",
            "site": {"contentUrl": "test-site"}
        }
    }
    mock_response.raise_for_status = Mock()
    mock_httpx_client.post.return_value = mock_response
    
    result = await tableau_client_uat.sign_in()
    
    assert result["token"] == "uat-token"
    
    # Verify isUat flag is set in payload
    call_args = mock_httpx_client.post.call_args
    payload = call_args.kwargs["json"]
    assert payload["credentials"]["isUat"] is True


@pytest.mark.asyncio
async def test_get_datasources_success(tableau_client, mock_httpx_client):
    """Test successful get_datasources call."""
    tableau_client.auth_token = "test-token"
    tableau_client.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    tableau_client.site_content_url = "test-site"
    
    mock_response = Mock()
    mock_response.json.return_value = {
        "datasources": {
            "datasource": [
                {"id": "ds-1", "name": "Sales Data"},
                {"id": "ds-2", "name": "Marketing Data"}
            ]
        }
    }
    mock_response.raise_for_status = Mock()
    mock_httpx_client.request.return_value = mock_response
    
    datasources = await tableau_client.get_datasources()
    
    assert len(datasources) == 2
    assert datasources[0]["name"] == "Sales Data"
    assert datasources[1]["name"] == "Marketing Data"
    
    # Verify request was made correctly
    call_args = mock_httpx_client.request.call_args
    assert call_args[0][0] == "GET"
    assert "test-site" in call_args[0][1]


@pytest.mark.asyncio
async def test_get_datasources_with_project_filter(tableau_client, mock_httpx_client):
    """Test get_datasources with project filter."""
    tableau_client.auth_token = "test-token"
    tableau_client.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    tableau_client.site_content_url = "test-site"
    
    mock_response = Mock()
    mock_response.json.return_value = {"datasources": {"datasource": []}}
    mock_response.raise_for_status = Mock()
    mock_httpx_client.request.return_value = mock_response
    
    await tableau_client.get_datasources(project_id="proj-123")
    
    call_args = mock_httpx_client.request.call_args
    assert "filter" in call_args.kwargs["params"]
    assert "proj-123" in call_args.kwargs["params"]["filter"]


@pytest.mark.asyncio
async def test_get_views_success(tableau_client, mock_httpx_client):
    """Test successful get_views call."""
    tableau_client.auth_token = "test-token"
    tableau_client.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    tableau_client.site_content_url = "test-site"
    
    mock_response = Mock()
    mock_response.json.return_value = {
        "views": {
            "view": [
                {"id": "v-1", "name": "Sales Dashboard"},
                {"id": "v-2", "name": "Marketing Dashboard"}
            ]
        }
    }
    mock_response.raise_for_status = Mock()
    mock_httpx_client.request.return_value = mock_response
    
    views = await tableau_client.get_views()
    
    assert len(views) == 2
    assert views[0]["name"] == "Sales Dashboard"


@pytest.mark.asyncio
async def test_get_views_with_datasource_filter(tableau_client, mock_httpx_client):
    """Test get_views with datasource filter."""
    tableau_client.auth_token = "test-token"
    tableau_client.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    tableau_client.site_content_url = "test-site"
    
    mock_response = Mock()
    mock_response.json.return_value = {"views": {"view": []}}
    mock_response.raise_for_status = Mock()
    mock_httpx_client.request.return_value = mock_response
    
    await tableau_client.get_views(datasource_id="ds-123")
    
    call_args = mock_httpx_client.request.call_args
    assert "filter" in call_args.kwargs["params"]
    assert "ds-123" in call_args.kwargs["params"]["filter"]


@pytest.mark.asyncio
async def test_query_datasource_success(tableau_client, mock_httpx_client):
    """Test successful query_datasource call."""
    tableau_client.auth_token = "test-token"
    tableau_client.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    tableau_client.site_content_url = "test-site"
    
    mock_response = Mock()
    mock_response.json.return_value = {
        "data": {
            "rows": [
                ["2024", "West", "1000"],
                ["2024", "East", "2000"]
            ]
        },
        "columns": {
            "column": [
                {"name": "Year"},
                {"name": "Region"},
                {"name": "Sales"}
            ]
        }
    }
    mock_response.raise_for_status = Mock()
    mock_httpx_client.request.return_value = mock_response
    
    result = await tableau_client.query_datasource("ds-123", filters={"year": "2024"})
    
    assert result["row_count"] == 2
    assert len(result["columns"]) == 3
    assert result["columns"][0] == "Year"


@pytest.mark.asyncio
async def test_get_view_data_with_filters(tableau_client, mock_httpx_client):
    """Test get_view_data passes vf_ params for filters."""
    tableau_client.auth_token = "test-token"
    tableau_client.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    tableau_client.site_content_url = "test-site"

    csv_response = Mock()
    csv_response.text = "Region,Sales\nWest,100\n"
    csv_response.headers = {"content-type": "text/csv"}
    csv_response.raise_for_status = Mock()
    mock_httpx_client.get = AsyncMock(return_value=csv_response)

    result = await tableau_client.get_view_data("v-123", filters={"Region": "West"})

    assert result["columns"] == ["Region", "Sales"]
    assert result["row_count"] == 1
    call_args = mock_httpx_client.get.call_args
    assert call_args.kwargs["params"]["vf_Region"] == "West"


@pytest.mark.asyncio
async def test_get_view_data_with_multi_value_filters(tableau_client, mock_httpx_client):
    """Test get_view_data passes vf_ params for multi-value filters as comma-separated."""
    tableau_client.auth_token = "test-token"
    tableau_client.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    tableau_client.site_content_url = "test-site"

    csv_response = Mock()
    csv_response.text = "Category,Sales\nTechnology,500\n"
    csv_response.headers = {"content-type": "text/csv"}
    csv_response.raise_for_status = Mock()
    mock_httpx_client.get = AsyncMock(return_value=csv_response)

    await tableau_client.get_view_data(
        "v-456",
        filters={"Category": ["Technology", "Furniture"]},
    )

    call_args = mock_httpx_client.get.call_args
    assert call_args.kwargs["params"]["vf_Category"] == "Technology,Furniture"


@pytest.mark.asyncio
async def test_get_view_embed_url_success(tableau_client, mock_httpx_client):
    """Test successful get_view_embed_url call."""
    tableau_client.auth_token = "test-token"
    tableau_client.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    tableau_client.site_content_url = "test-site"
    
    # Mock view details response
    view_response = Mock()
    view_response.json.return_value = {
        "view": {
            "id": "v-123",
            "contentUrl": "Sales/SalesDashboard",
            "workbookId": {"id": "wb-456"}
        }
    }
    view_response.raise_for_status = Mock()
    
    mock_httpx_client.request.return_value = view_response
    
    result = await tableau_client.get_view_embed_url("v-123", filters={"Region": "West"})
    
    assert "url" in result
    assert result["token"] == "test-token"
    assert result["view_id"] == "v-123"
    assert "SalesDashboard" in result["url"]
    assert "Region=West" in result["url"]


@pytest.mark.asyncio
async def test_request_retries_on_401(tableau_client, mock_httpx_client):
    """Test request retries and re-authenticates on 401."""
    tableau_client.auth_token = "old-token"
    tableau_client.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    tableau_client.site_content_url = "test-site"
    
    # First call returns 401, second succeeds
    error_response = Mock()
    error_response.status_code = 401
    error_response.text = "Unauthorized"
    error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "401", request=Mock(), response=error_response
    )
    
    success_response = Mock()
    success_response.json.return_value = {"datasources": {"datasource": []}}
    success_response.raise_for_status = Mock()
    
    # Mock sign-in
    sign_in_response = Mock()
    sign_in_response.json.return_value = {
        "credentials": {
            "token": "new-token",
            "site": {"contentUrl": "test-site"}
        }
    }
    sign_in_response.raise_for_status = Mock()
    
    mock_httpx_client.post.return_value = sign_in_response
    mock_httpx_client.request.side_effect = [error_response, success_response]
    
    result = await tableau_client.get_datasources()
    
    assert result == []
    assert tableau_client.auth_token == "new-token"
    assert mock_httpx_client.request.call_count == 2


@pytest.mark.asyncio
async def test_request_exponential_backoff(tableau_client, mock_httpx_client):
    """Test request uses exponential backoff on retries."""
    tableau_client.auth_token = "test-token"
    tableau_client.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    tableau_client.site_content_url = "test-site"
    tableau_client.max_retries = 3
    
    error_response = Mock()
    error_response.status_code = 500
    error_response.text = "Server Error"
    error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=Mock(), response=error_response
    )
    
    mock_httpx_client.request.side_effect = error_response
    
    with pytest.raises(TableauAPIError):
        await tableau_client.get_datasources()
    
    # Should have tried max_retries times
    assert mock_httpx_client.request.call_count == tableau_client.max_retries


@pytest.mark.asyncio
async def test_context_manager(tableau_client, mock_httpx_client):
    """Test client works as async context manager."""
    async with tableau_client:
        assert tableau_client._client is not None
    
    # Verify close was called
    mock_httpx_client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_close(tableau_client, mock_httpx_client):
    """Test close method."""
    await tableau_client.close()
    mock_httpx_client.aclose.assert_called_once()
