"""MCP Tools for authentication."""
import logging
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from app.core.config import settings, PROJECT_ROOT
from app.services.tableau.client import TableauClient, TableauAuthenticationError

logger = logging.getLogger(__name__)

# Import mcp from package __init__ to avoid circular import
try:
    from mcp_server import get_mcp
    mcp = get_mcp()
except ImportError:
    from mcp_server.server import mcp

# Credential storage path - MCP-specific credentials stored in mcp_server directory
# This keeps MCP credentials separate from service account files (vertex-sa.json, etc.)
MCP_SERVER_ROOT = Path(__file__).parent.parent
CREDENTIALS_DIR = MCP_SERVER_ROOT / "credentials"
CREDENTIALS_FILE = CREDENTIALS_DIR / ".mcp_auth.json"
ENCRYPTION_KEY_FILE = CREDENTIALS_DIR / ".mcp_key.key"


class CredentialStore:
    """Secure credential storage using Fernet encryption."""
    
    def __init__(self):
        """Initialize credential store with encryption key."""
        CREDENTIALS_DIR.mkdir(exist_ok=True)
        
        # Load or generate encryption key
        if ENCRYPTION_KEY_FILE.exists():
            with open(ENCRYPTION_KEY_FILE, "rb") as f:
                self.key = f.read()
        else:
            self.key = Fernet.generate_key()
            with open(ENCRYPTION_KEY_FILE, "wb") as f:
                f.write(self.key)
            # Set restrictive permissions
            os.chmod(ENCRYPTION_KEY_FILE, 0o600)
        
        self.cipher = Fernet(self.key)
    
    def save_credentials(self, service: str, credentials: Dict[str, Any]) -> None:
        """Save encrypted credentials for a service."""
        data = self._load_all()
        data[service] = credentials
        encrypted_data = self.cipher.encrypt(json.dumps(data).encode())
        
        with open(CREDENTIALS_FILE, "wb") as f:
            f.write(encrypted_data)
        os.chmod(CREDENTIALS_FILE, 0o600)
    
    def get_credentials(self, service: str) -> Optional[Dict[str, Any]]:
        """Get decrypted credentials for a service."""
        data = self._load_all()
        return data.get(service)
    
    def _load_all(self) -> Dict[str, Any]:
        """Load and decrypt all credentials."""
        if not CREDENTIALS_FILE.exists():
            return {}
        
        try:
            with open(CREDENTIALS_FILE, "rb") as f:
                encrypted_data = f.read()
            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            return {}


# Global credential store instance
_credential_store = CredentialStore()

# Global Tableau client instance (cached)
_tableau_client: Optional[TableauClient] = None


def get_tableau_client_from_credentials(
    server_url: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    username: Optional[str] = None,
) -> TableauClient:
    """Get or create Tableau client with credentials."""
    global _tableau_client
    
    # Use provided credentials or load from store
    if not server_url or not client_id or not client_secret:
        creds = _credential_store.get_credentials("tableau")
        if not creds:
            raise ValueError("Tableau credentials not found. Please authenticate first.")
        server_url = server_url or creds.get("server_url")
        client_id = client_id or creds.get("client_id")
        client_secret = client_secret or creds.get("client_secret")
        username = username or creds.get("username")
    
    # Create new client instance
    _tableau_client = TableauClient(
        server_url=server_url,
        client_id=client_id,
        client_secret=client_secret,
        username=username,
    )
    
    return _tableau_client


@mcp.tool()
async def auth_tableau_signin(
    server_url: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    username: Optional[str] = None,
    site_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Authenticate with Tableau using Connected Apps JWT.
    
    Credentials are stored securely and can be reused for subsequent operations.
    
    Args:
        server_url: Tableau server URL (optional, uses settings if not provided)
        client_id: Connected App client ID (optional, uses settings if not provided)
        client_secret: Connected App client secret (optional, uses settings if not provided)
        username: Username for JWT subject (optional, uses settings if not provided)
        site_id: Site ID (optional, uses settings if not provided)
    
    Returns:
        Dictionary with authentication status, token info, and expiration
    """
    try:
        # Use provided credentials or fall back to settings
        server_url = server_url or settings.TABLEAU_SERVER_URL
        client_id = client_id or settings.TABLEAU_CLIENT_ID
        client_secret = client_secret or settings.TABLEAU_CLIENT_SECRET
        username = username or settings.TABLEAU_USERNAME or client_id
        site_id = site_id or settings.TABLEAU_SITE_ID
        
        if not server_url or not client_id or not client_secret:
            return {
                "error": "Missing required credentials. Provide server_url, client_id, and client_secret, or configure them in settings.",
                "authenticated": False,
            }
        
        # Create client and authenticate
        client = TableauClient(
            server_url=server_url,
            site_id=site_id,
            client_id=client_id,
            client_secret=client_secret,
            username=username,
        )
        
        auth_result = await client.sign_in()
        
        # Store credentials securely
        _credential_store.save_credentials("tableau", {
            "server_url": server_url,
            "client_id": client_id,
            "client_secret": client_secret,
            "username": username,
            "site_id": site_id,
            "authenticated_at": datetime.now(timezone.utc).isoformat(),
        })
        
        # Update global client
        global _tableau_client
        _tableau_client = client
        
        return {
            "authenticated": True,
            "server_url": server_url,
            "site_id": auth_result.get("site", {}).get("id"),
            "user_id": auth_result.get("user", {}).get("id"),
            "token": auth_result.get("credentials", {}).get("token", "")[:20] + "...",  # Partial token for security
            "expires_at": auth_result.get("credentials", {}).get("expiresAt"),
        }
    except TableauAuthenticationError as e:
        logger.error(f"Tableau authentication error: {e}")
        return {
            "error": str(e),
            "authenticated": False,
        }
    except Exception as e:
        logger.error(f"Unexpected error during authentication: {e}")
        return {
            "error": f"Unexpected error: {str(e)}",
            "authenticated": False,
        }


@mcp.tool()
async def auth_get_token() -> Dict[str, Any]:
    """
    Get current authentication token information.
    
    Returns:
        Dictionary with token status and expiration info
    """
    try:
        creds = _credential_store.get_credentials("tableau")
        if not creds:
            return {
                "error": "Not authenticated. Please call auth_tableau_signin first.",
                "authenticated": False,
            }
        
        # Check if we have a valid client
        global _tableau_client
        if _tableau_client is None:
            return {
                "error": "Tableau client not initialized. Please call auth_tableau_signin first.",
                "authenticated": False,
            }
        
        # Try to get token info from client
        # Note: TableauClient doesn't expose token directly, but we can check if authenticated
        try:
            await _tableau_client._ensure_authenticated()
            return {
                "authenticated": True,
                "server_url": creds.get("server_url"),
                "site_id": creds.get("site_id"),
                "authenticated_at": creds.get("authenticated_at"),
            }
        except Exception as e:
            return {
                "error": f"Token validation failed: {str(e)}",
                "authenticated": False,
            }
    except Exception as e:
        logger.error(f"Error getting token: {e}")
        return {
            "error": str(e),
            "authenticated": False,
        }


@mcp.tool()
async def auth_refresh_token() -> Dict[str, Any]:
    """
    Refresh the authentication token.
    
    Returns:
        Dictionary with refreshed token status
    """
    try:
        creds = _credential_store.get_credentials("tableau")
        if not creds:
            return {
                "error": "Not authenticated. Please call auth_tableau_signin first.",
                "refreshed": False,
            }
        
        # Re-authenticate to get fresh token
        return await auth_tableau_signin(
            server_url=creds.get("server_url"),
            client_id=creds.get("client_id"),
            client_secret=creds.get("client_secret"),
            username=creds.get("username"),
            site_id=creds.get("site_id"),
        )
    except Exception as e:
        logger.error(f"Error refreshing token: {e}")
        return {
            "error": str(e),
            "refreshed": False,
        }
