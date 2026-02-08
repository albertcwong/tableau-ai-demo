"""Backend API client for MCP server."""
import logging
import httpx
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


async def call_backend_api(
    endpoint: str,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
    auth0_token: Optional[str] = None,
    timeout: float = 30.0
) -> Dict[str, Any]:
    """
    Call backend API with Auth0 token authentication.
    
    Args:
        endpoint: API endpoint path (e.g., "/api/v1/auth/me")
        method: HTTP method (GET, POST, PUT, DELETE)
        data: Request body data (for POST/PUT)
        auth0_token: Auth0 access token
        timeout: Request timeout in seconds
    
    Returns:
        Response JSON data
    
    Raises:
        httpx.HTTPError: If request fails
    """
    backend_url = settings.BACKEND_API_URL or "http://localhost:8000"
    url = f"{backend_url}{endpoint}"
    
    headers = {
        "Content-Type": "application/json",
    }
    
    if auth0_token:
        headers["Authorization"] = f"Bearer {auth0_token}"
    else:
        logger.warning(f"No Auth0 token provided for API call to {endpoint}")
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = await client.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                response = await client.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                response = await client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Backend API error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Backend API request error: {e}")
            raise
