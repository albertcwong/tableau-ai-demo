"""Tableau REST API client with Connected Apps JWT authentication."""
import asyncio
import jwt
import uuid
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Any
from urllib.parse import urljoin

import httpx
import os
import ssl
from pathlib import Path
from app.core.config import settings, PROJECT_ROOT

# Set up logger for this module
logger = logging.getLogger(__name__)


class TableauClientError(Exception):
    """Base exception for Tableau client errors."""
    pass


class TableauAuthenticationError(TableauClientError):
    """Authentication-related errors."""
    pass


class TableauAPIError(TableauClientError):
    """API request errors."""
    pass


class TableauClient:
    """Client for interacting with Tableau REST API using Connected Apps JWT authentication."""
    
    def __init__(
        self,
        server_url: Optional[str] = None,
        site_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        username: Optional[str] = None,
        secret_id: Optional[str] = None,
        is_uat: bool = False,
        api_version: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        verify_ssl: Optional[bool] = None,
        initial_token: Optional[str] = None,
        initial_site_id: Optional[str] = None,
        initial_site_content_url: Optional[str] = None,
        on_401_invalidate: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize Tableau client.
        
        Args:
            server_url: Tableau server URL (defaults to settings)
            site_id: Tableau site ID (defaults to settings)
            client_id: Connected App client ID or UAT client ID (defaults to settings)
            client_secret: Connected App secret value or UAT secret (defaults to settings)
            username: Username for JWT (defaults to settings or client_id)
            secret_id: Secret ID for JWT 'kid' header (defaults to settings or client_id)
            is_uat: Whether to use Unified Access Token (UAT) instead of Connected App (defaults to False)
            api_version: Tableau REST API version (e.g., "3.21", "3.27") (defaults to settings)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.server_url = server_url or settings.TABLEAU_SERVER_URL
        self.site_id = site_id or settings.TABLEAU_SITE_ID
        self.client_id = client_id or settings.TABLEAU_CLIENT_ID
        self.client_secret = client_secret or settings.TABLEAU_CLIENT_SECRET
        # Secret ID for JWT 'kid' header - use provided value, then settings, then default to client_id
        self.secret_id = secret_id or settings.TABLEAU_SECRET_ID or self.client_id
        # Username defaults to client_id if not provided, but can be overridden via settings or parameter
        self.username = username or settings.TABLEAU_USERNAME or self.client_id
        self.is_uat = is_uat
        self.api_version = api_version or settings.TABLEAU_API_VERSION
        self.timeout = timeout
        self.max_retries = max_retries
        
        if not self.server_url:
            raise ValueError("Tableau server URL is required")
        # client_id and client_secret required only for Connected App auth; PAT auth does not need them
        
        # Ensure server URL doesn't end with /
        self.server_url = self.server_url.rstrip('/')
        
        # Base API URL with configurable version
        self.api_base = urljoin(self.server_url, f'/api/{self.api_version}/')
        
        # Auth state
        self.auth_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.site_content_url: Optional[str] = None
        self._pat_auth: bool = False  # True when authenticated via PAT (no refresh)
        self._standard_auth: bool = False  # True when authenticated via username/password (no refresh)
        self._on_401_invalidate: Optional[Callable[[], None]] = on_401_invalidate
        # Pre-seeded from cache (avoids sign-in when token reuse)
        if initial_token:
            self.auth_token = initial_token
            self.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=8)
            if initial_site_id:
                self.site_id = initial_site_id
            if initial_site_content_url:
                self.site_content_url = initial_site_content_url
            # Detect PAT auth from client_id placeholder
            if client_id == "pat-placeholder":
                self._pat_auth = True
            elif client_id == "standard-placeholder":
                self._standard_auth = True
        
        # SSL verification setting
        # If verify_ssl=False (from config skip_ssl_verify), skip verification
        if verify_ssl is False:
            self.verify_ssl = False
        elif settings.TABLEAU_SSL_CERT_PATH:
            cert_path = Path(settings.TABLEAU_SSL_CERT_PATH).expanduser()
            if not cert_path.is_absolute():
                cert_path = PROJECT_ROOT / cert_path
            cert_path = cert_path.resolve()
            if cert_path.exists():
                ssl_context = ssl.create_default_context(cafile=str(cert_path))
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_REQUIRED
                self.verify_ssl = ssl_context
            else:
                raise ValueError(
                    f"Tableau SSL certificate file not found: {cert_path} "
                    f"(resolved from: {settings.TABLEAU_SSL_CERT_PATH})"
                )
        else:
            self.verify_ssl = settings.TABLEAU_VERIFY_SSL if verify_ssl is None else verify_ssl
        
        # HTTP client with SSL configuration
        self._client = httpx.AsyncClient(
            timeout=timeout,
            verify=self.verify_ssl,
        )
    
    def _generate_jwt(self, expires_in_minutes: int = 10) -> str:
        """
        Generate JWT token for Connected Apps or Unified Access Token authentication.
        
        The JWT must include access scopes that determine which REST methods can be called.
        See: https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_ref_authentication.htm
        
        Args:
            expires_in_minutes: Token expiration time in minutes (max 10)
            
        Returns:
            Encoded JWT token string
        """
        if expires_in_minutes > 10:
            expires_in_minutes = 10
        
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=expires_in_minutes)
        iat = int(now.timestamp())  # Issued at time
        
        # JWT payload
        payload = {
            "iss": self.client_id,  # Issuer (client ID)
            "sub": self.username,  # Subject (username) - must match Connected App user
            "aud": "tableau",  # Audience
            "exp": int(exp.timestamp()),  # Expiration
            "iat": iat,  # Issued at time
            "jti": str(uuid.uuid4()),  # Unique token ID
            "scp": ["tableau:views:embed", "tableau:content:read"],  # Scopes
        }
        
        # JWT headers - Tableau Connected Apps expect specific header format
        # The 'kid' (Key ID) must match the Secret ID from the Connected App configuration
        # This is often different from the Client ID
        headers = {
            "alg": "HS256",
            "typ": "JWT",
            "kid": self.secret_id,  # Key ID (Secret ID, not Client ID)
        }
        
        # Encode JWT using HS256 algorithm
        token = jwt.encode(
            payload,
            self.client_secret,
            algorithm="HS256",
            headers=headers
        )
        
        # Debug logging (without exposing the full token)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Generated JWT - Client ID: {self.client_id}, "
                f"Subject: {self.username}, "
                f"Expires: {exp.isoformat()}, "
                f"Scopes: {payload['scp']}"
            )
            # Decode to verify (without verification) for debugging
            try:
                decoded = jwt.decode(token, options={"verify_signature": False})
                logger.debug(f"JWT payload: {decoded}")
            except Exception as e:
                logger.warning(f"Could not decode JWT for debugging: {e}")
        
        return token
    
    async def sign_in(self) -> Dict[str, Any]:
        """
        Authenticate with Tableau using JWT (Connected App or Unified Access Token).
        
        Returns:
            Dictionary with authentication details including token and site info
            
        Raises:
            TableauAuthenticationError: If authentication fails
        """
        if not self.client_id or not self.client_secret:
            raise ValueError("Tableau client ID and client secret are required for Connected App authentication")
        logger.info("=" * 80)
        logger.info("STARTING TABLEAU SIGN-IN PROCESS")
        logger.info(f"Server URL: {self.server_url}")
        logger.info(f"API Base: {self.api_base}")
        logger.info(f"Site ID (configured): {self.site_id}")
        logger.info(f"Client ID: {self.client_id}")
        logger.info(f"Username: {self.username}")
        logger.info(f"API Version: {self.api_version}")
        logger.info(f"Is UAT: {self.is_uat}")
        logger.debug("=" * 80)
        logger.debug("Starting Tableau sign-in process (DEBUG)")
        logger.debug(f"Server URL: {self.server_url}")
        logger.debug(f"API Base: {self.api_base}")
        logger.debug(f"Site ID (configured): {self.site_id}")
        logger.debug(f"Client ID: {self.client_id}")
        logger.debug(f"Username: {self.username}")
        logger.debug(f"API Version: {self.api_version}")
        logger.debug(f"Is UAT: {self.is_uat}")
        
        jwt_token = self._generate_jwt()
        logger.info(f"Generated JWT token (length: {len(jwt_token)})")
        logger.debug(f"Generated JWT token (length: {len(jwt_token)})")
        
        # Sign in endpoint
        sign_in_url = urljoin(self.api_base, 'auth/signin')
        logger.info(f"Sign-in URL: {sign_in_url}")
        logger.debug(f"Sign-in URL: {sign_in_url}")
        
        # Build credentials payload for JWT authentication
        credentials = {
            "jwt": jwt_token,
            "site": {
                "contentUrl": self.site_id or ""
            }
        }
        
        # Add isUat flag for Unified Access Tokens (API 3.27+, Tableau Cloud only)
        if self.is_uat:
            credentials["isUat"] = True
            logger.info("Using UAT (Unified Access Token) authentication")
            logger.debug("Using UAT (Unified Access Token) authentication")
        
        payload = {
            "credentials": credentials
        }
        
        logger.info(f"Sign-in payload (site.contentUrl): '{credentials['site']['contentUrl']}'")
        logger.debug(f"Sign-in payload (site.contentUrl): '{credentials['site']['contentUrl']}'")
        
        try:
            # Tableau REST API accepts JSON but returns XML by default
            # Request JSON format in Accept header
            logger.info("Sending POST request to Tableau sign-in endpoint...")
            logger.debug("Sending POST request to Tableau sign-in endpoint...")
            response = await self._client.post(
                sign_in_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            )
            logger.debug(f"Received response: Status {response.status_code}")
            response.raise_for_status()
            
            # Log response details
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            logger.debug(f"Response content-type: {response.headers.get('content-type', 'unknown')}")
            logger.debug(f"Response length: {len(response.text)} bytes")
            
            # Log full response payload
            logger.info("=" * 80)
            logger.info("SIGN-IN RESPONSE PAYLOAD:")
            logger.info(f"Status: {response.status_code}")
            logger.info(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            logger.info(f"Full response text:")
            logger.info(response.text)
            logger.info("=" * 80)
            
            # Also log first 500 chars for quick reference
            logger.debug(f"Response text (first 500 chars): {response.text[:500]}")
            
            # Try JSON first (we're requesting JSON with Accept header)
            data = None
            response_format = None
            try:
                logger.debug("Attempting to parse response as JSON...")
                if response.text.strip():
                    data = response.json()
                    response_format = "JSON"
                    logger.debug("✓ Successfully parsed JSON response")
                    logger.debug(f"JSON data top-level keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
                    logger.info("PARSED JSON PAYLOAD:")
                    logger.info(f"{data}")
                    logger.debug(f"Full JSON structure: {data}")
                else:
                    logger.warning("Response body is empty")
                    raise ValueError("Empty response body")
            except (ValueError, Exception) as json_error:
                # We're requesting JSON with Accept header, so XML should be unexpected
                # Log error details and raise exception
                content_type = response.headers.get('content-type', 'unknown')
                logger.error(f"✗ JSON parsing failed despite requesting JSON format")
                logger.error(f"  Error: {json_error}")
                logger.error(f"  Response Content-Type: {content_type}")
                logger.error(f"  Response status: {response.status_code}")
                logger.error(f"  Response text (first 1000 chars): {response.text[:1000]}")
                
                # Only attempt XML parsing as last resort if content-type indicates XML
                if 'xml' in content_type.lower():
                    logger.warning("Response is XML despite Accept: application/json header. Attempting XML parsing as fallback...")
                    import xml.etree.ElementTree as ET
                    try:
                        if not response.text.strip():
                            raise TableauAuthenticationError(
                                f"Empty response from Tableau Server. Status: {response.status_code}"
                            )
                        root = ET.fromstring(response.text)
                        # Parse XML response
                        credentials_elem = root.find('.//{http://tableau.com/api}credentials')
                        if credentials_elem is not None:
                            token_elem = credentials_elem.find('.//{http://tableau.com/api}token')
                            site_elem = credentials_elem.find('.//{http://tableau.com/api}site')
                            
                            # Extract site ID (UUID) and contentUrl from site element
                            site_id = None
                            content_url = None
                            if site_elem is not None:
                                # Site ID is typically an 'id' attribute (UUID)
                                site_id = site_elem.get("id") or site_elem.get("Id") or site_elem.get("ID")
                                # contentUrl can be an attribute or text content
                                content_url = site_elem.get("contentUrl") or site_elem.get("contenturl")
                                if not content_url and site_elem.text:
                                    content_url = site_elem.text.strip() if site_elem.text.strip() else None
                            
                            data = {
                                "credentials": {
                                    "token": token_elem.text if token_elem is not None else None,
                                    "site": {
                                        "id": site_id,
                                        "contentUrl": content_url
                                    }
                                }
                            }
                            
                            logger.warning(f"Parsed XML fallback - Token present: {token_elem is not None}, Site ID: '{site_id}', Site contentUrl: '{content_url}'")
                            response_format = "XML"
                        else:
                            # Try parsing as generic XML
                            data = self._parse_xml_response(response.text)
                            if "credentials" not in data:
                                logger.error(f"Parsed XML structure: {data}")
                                logger.error(f"XML root tag: {root.tag}")
                                raise ValueError(f"Unexpected XML response format. Root: {root.tag}, Content: {response.text[:500]}")
                            response_format = "XML"
                    except ET.ParseError as xml_error:
                        raise TableauAuthenticationError(
                            f"Failed to parse response as JSON (requested) or XML (fallback). "
                            f"Status: {response.status_code}, Content-Type: {content_type}, "
                            f"Response: {response.text[:500]}"
                        ) from xml_error
                else:
                    # Not XML, so this is unexpected - raise error
                    raise TableauAuthenticationError(
                        f"Expected JSON response but received {content_type}. "
                        f"Status: {response.status_code}, "
                        f"Response: {response.text[:500]}"
                    ) from json_error
            
            if not data:
                logger.error("No data received from sign-in response")
                raise TableauAuthenticationError("No data received from sign-in response")
            
            logger.debug("=" * 80)
            logger.debug("Extracting credentials from response")
            logger.debug(f"Response format: {response_format or 'XML'}")
            logger.debug(f"Full data structure: {data}")
            
            # Extract token and site info
            # Expected JSON structure:
            # {
            #   "credentials": {
            #     "site": {
            #       "id": "uuid",
            #       "contentUrl": ""  # can be empty string
            #     },
            #     "token": "..."
            #   }
            # }
            credentials = data.get("credentials", {})
            logger.debug(f"Credentials keys: {list(credentials.keys()) if isinstance(credentials, dict) else 'not a dict'}")
            
            self.auth_token = credentials.get("token")
            logger.debug(f"Extracted auth_token: {'[PRESENT]' if self.auth_token else '[MISSING]'} (length: {len(self.auth_token) if self.auth_token else 0})")
            
            site_info = credentials.get("site", {})
            logger.info("-" * 80)
            logger.info("EXTRACTING SITE ID FROM RESPONSE")
            logger.info(f"  Site info type: {type(site_info)}")
            logger.info(f"  Site info keys: {list(site_info.keys()) if isinstance(site_info, dict) else 'not a dict'}")
            logger.info(f"  Site info full content: {site_info}")
            logger.debug(f"Site info: {site_info}")
            logger.debug(f"Site info type: {type(site_info)}")
            logger.debug(f"Site info keys: {list(site_info.keys()) if isinstance(site_info, dict) else 'not a dict'}")
            
            # Extract site ID (UUID) - this is the primary identifier
            # For JSON responses: site object has "id" field directly (per Tableau API docs)
            # For XML responses: _xml_element_to_dict adds attributes directly without @ prefix
            logger.debug("-" * 80)
            logger.debug("Extracting site ID and contentUrl")
            site_id_from_response = None
            content_url = None
            
            if isinstance(site_info, dict):
                logger.debug(f"Site info is a dict, checking for 'id' field...")
                # Extract site ID - should be at site_info["id"] for JSON responses
                if "id" in site_info:
                    site_id_from_response = site_info["id"]
                    logger.info(f"✓ Found site_id via 'id' key: '{site_id_from_response}'")
                    logger.debug(f"✓ Found site_id via 'id' key: '{site_id_from_response}'")
                elif "@id" in site_info:
                    site_id_from_response = site_info["@id"]
                    logger.info(f"✓ Found site_id via '@id' key: '{site_id_from_response}'")
                    logger.debug(f"✓ Found site_id via '@id' key: '{site_id_from_response}'")
                elif "Id" in site_info:
                    site_id_from_response = site_info["Id"]
                    logger.info(f"✓ Found site_id via 'Id' key: '{site_id_from_response}'")
                    logger.debug(f"✓ Found site_id via 'Id' key: '{site_id_from_response}'")
                elif "ID" in site_info:
                    site_id_from_response = site_info["ID"]
                    logger.info(f"✓ Found site_id via 'ID' key: '{site_id_from_response}'")
                    logger.debug(f"✓ Found site_id via 'ID' key: '{site_id_from_response}'")
                else:
                    logger.warning(f"✗ Site ID not found in site_info. Available keys: {list(site_info.keys())}")
                    logger.info(f"✗ Site ID not found in site_info. Available keys: {list(site_info.keys())}")
                
                # Extract contentUrl - can be empty string "" in JSON responses
                # Use explicit check for None to preserve empty strings
                logger.debug("Checking for contentUrl...")
                if "contentUrl" in site_info:
                    content_url = site_info["contentUrl"]
                    logger.debug(f"✓ Found contentUrl via 'contentUrl' key: '{content_url}'")
                elif "@contentUrl" in site_info:
                    content_url = site_info["@contentUrl"]
                    logger.debug(f"✓ Found contentUrl via '@contentUrl' key: '{content_url}'")
                elif "contenturl" in site_info:
                    content_url = site_info["contenturl"]
                    logger.debug(f"✓ Found contentUrl via 'contenturl' key: '{content_url}'")
                elif "ContentUrl" in site_info:
                    content_url = site_info["ContentUrl"]
                    logger.debug(f"✓ Found contentUrl via 'ContentUrl' key: '{content_url}'")
                else:
                    logger.debug("✗ contentUrl not found in site_info")
                    content_url = None
                
                logger.debug(f"Final extracted values - site_id: '{site_id_from_response}', contentUrl: '{content_url}'")
            else:
                logger.error(f"Site info is not a dict! Type: {type(site_info)}, Value: {site_info}")
            
            # Store original configured site_id before potentially overwriting
            original_configured_site_id = self.site_id
            logger.debug("-" * 80)
            logger.debug("Determining final site_id to use")
            logger.debug(f"Site ID from response: '{site_id_from_response}'")
            logger.debug(f"Original configured site_id: '{original_configured_site_id}'")
            
            # Use site ID from response if available, otherwise keep configured site_id
            if site_id_from_response:
                self.site_id = site_id_from_response
                logger.info(f"✓ Using site ID from authentication response: '{self.site_id}'")
            elif original_configured_site_id:
                # Keep the configured site_id if response doesn't have one
                logger.info(f"⚠ Site ID not in response, using configured site_id: '{original_configured_site_id}'")
                # self.site_id is already set from __init__, no need to change it
            else:
                # Last resort: try contentUrl as site identifier (some Tableau setups use contentUrl as site ID)
                if content_url:
                    self.site_id = content_url
                    logger.warning(f"⚠ No site ID found in response, using contentUrl as site ID: '{self.site_id}'")
                else:
                    logger.error("✗ No site ID found in authentication response and none configured.")
                    logger.error(f"Response data keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
                    logger.error(f"Credentials keys: {list(credentials.keys()) if isinstance(credentials, dict) else 'not a dict'}")
                    logger.error(f"Site info: {site_info}")
                    logger.error(f"Full response data: {data}")
                    raise TableauAuthenticationError(
                        "Could not determine site ID from authentication response. "
                        "Please ensure TABLEAU_SITE_ID is set in environment or site ID is present in auth response."
                    )
            
            # Set content URL
            self.site_content_url = content_url or self.site_id
            
            # Log final site info - comprehensive success logging
            logger.info("=" * 80)
            logger.info("✓ AUTHENTICATION SUCCESSFUL")
            logger.info(f"  Site ID (UUID) from response: '{site_id_from_response}'")
            logger.info(f"  Site ID (UUID) configured: '{original_configured_site_id}'")
            logger.info(f"  Final Site ID (UUID) being used: '{self.site_id}'")
            logger.info(f"  Site content URL: '{self.site_content_url}'")
            logger.info(f"  Auth token present: {'YES' if self.auth_token else 'NO'}")
            if self.auth_token:
                logger.info(f"  Auth token length: {len(self.auth_token)}")
            logger.info("=" * 80)
            logger.debug("=" * 80)
            logger.debug(f"✓ Authenticated to Tableau successfully")
            logger.debug(f"  Site ID (UUID): '{self.site_id}'")
            logger.debug(f"  Site content URL: '{self.site_content_url}'")
            logger.debug(f"  Auth token: {'[PRESENT]' if self.auth_token else '[MISSING]'}")
            logger.debug("=" * 80)
            
            # Set expiration (default to 8 minutes to be safe)
            self.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=8)
            
            if not self.auth_token:
                raise TableauAuthenticationError("No token received from sign-in response")
            
            return {
                "token": self.auth_token,
                "site_content_url": self.site_content_url,
                "expires_at": self.token_expires_at.isoformat(),
            }
            
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            # Try to parse XML error response for better error messages
            try:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(e.response.text)
                error_elem = root.find('.//{http://tableau.com/api}error')
                if error_elem is not None:
                    code = error_elem.get('code', '')
                    summary = error_elem.find('.//{http://tableau.com/api}summary')
                    detail = error_elem.find('.//{http://tableau.com/api}detail')
                    summary_text = summary.text if summary is not None else ''
                    detail_text = detail.text if detail is not None else ''
                    error_detail = f"Code {code}: {summary_text} - {detail_text}"
            except:
                pass
            
            # Log debug info (without exposing secrets)
            logger.error(
                f"Tableau authentication failed: {e.response.status_code} - {error_detail}. "
                f"Server: {self.server_url}, Site: {self.site_id or '(empty/default)'}, "
                f"Client ID: {self.client_id}, Username (sub): {self.username}"
            )
            
            raise TableauAuthenticationError(
                f"Authentication failed: {e.response.status_code} - {error_detail}"
            ) from e
        except httpx.RequestError as e:
            raise TableauAuthenticationError(f"Network error during authentication: {str(e)}") from e

    async def sign_in_with_pat(self, pat_name: str, pat_secret: str) -> Dict[str, Any]:
        """
        Authenticate with Tableau using Personal Access Token.

        Args:
            pat_name: PAT name
            pat_secret: PAT secret value

        Returns:
            Dictionary with authentication details including token and site info
        """
        sign_in_url = urljoin(self.api_base, 'auth/signin')
        credentials = {
            "personalAccessTokenName": pat_name,
            "personalAccessTokenSecret": pat_secret,
            "site": {"contentUrl": self.site_id or ""}
        }
        payload = {"credentials": credentials}
        try:
            response = await self._client.post(
                sign_in_url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            creds = data.get("credentials", {})
            self.auth_token = creds.get("token")
            site_info = creds.get("site", {})
            self.site_content_url = site_info.get("contentUrl") or site_info.get("contenturl")
            if site_info.get("id"):
                self.site_id = site_info["id"]
            self.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=8)
            if not self.auth_token:
                raise TableauAuthenticationError("No token received from PAT sign-in")
            self._pat_auth = True
            return {
                "token": self.auth_token,
                "site_content_url": self.site_content_url,
                "expires_at": self.token_expires_at.isoformat(),
                "site": site_info,
                "user": creds.get("user", {}),
                "credentials": creds,
            }
        except httpx.HTTPStatusError as e:
            raise TableauAuthenticationError(
                f"PAT authentication failed: {e.response.status_code} - {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise TableauAuthenticationError(f"Network error during PAT authentication: {str(e)}") from e

    async def sign_in_with_password(self, username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate with Tableau using username and password.

        Args:
            username: Tableau username
            password: Tableau password

        Returns:
            Dictionary with authentication details including token and site info
        """
        sign_in_url = urljoin(self.api_base, 'auth/signin')
        credentials = {
            "name": username,
            "password": password,
            "site": {"contentUrl": self.site_id or ""}
        }
        payload = {"credentials": credentials}
        try:
            response = await self._client.post(
                sign_in_url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            creds = data.get("credentials", {})
            self.auth_token = creds.get("token")
            site_info = creds.get("site", {})
            self.site_content_url = site_info.get("contentUrl") or site_info.get("contenturl")
            if site_info.get("id"):
                self.site_id = site_info["id"]
            # Token valid ~240 min (Server) / 120 min (Cloud)
            self.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=240)
            if not self.auth_token:
                raise TableauAuthenticationError("No token received from standard sign-in")
            self._standard_auth = True
            return {
                "token": self.auth_token,
                "site_content_url": self.site_content_url,
                "expires_at": self.token_expires_at.isoformat(),
                "site": site_info,
                "user": creds.get("user", {}),
                "credentials": creds,
            }
        except httpx.HTTPStatusError as e:
            raise TableauAuthenticationError(
                f"Standard authentication failed: {e.response.status_code} - {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise TableauAuthenticationError(f"Network error during standard authentication: {str(e)}") from e

    async def switch_site(self, content_url: str) -> Dict[str, Any]:
        """
        Switch to another site without re-authenticating. Tableau Server only (not Cloud).

        Args:
            content_url: Site content URL to switch to (empty string for default site)

        Returns:
            Dictionary with new credentials including token and site info
        """
        if not self.auth_token:
            raise TableauAuthenticationError("Not authenticated. Call sign_in first.")
        switch_url = urljoin(self.api_base, 'auth/switchSite')
        payload = {"site": {"contentUrl": content_url or ""}}
        try:
            response = await self._client.post(
                switch_url,
                json=payload,
                headers={
                    "X-Tableau-Auth": self.auth_token,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
            )
            response.raise_for_status()
            data = response.json()
            creds = data.get("credentials", {})
            self.auth_token = creds.get("token")
            site_info = creds.get("site", {})
            self.site_content_url = site_info.get("contentUrl") or site_info.get("contenturl")
            if site_info.get("id"):
                self.site_id = site_info["id"]
            self.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=240)
            if not self.auth_token:
                raise TableauAuthenticationError("No token received from switch-site")
            return {
                "token": self.auth_token,
                "site_content_url": self.site_content_url,
                "site": site_info,
                "user": creds.get("user", {}),
                "credentials": creds,
            }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 405:
                raise TableauAuthenticationError(
                    "Switch site is not available on Tableau Cloud. This feature is Tableau Server only."
                ) from e
            raise TableauAuthenticationError(
                f"Switch site failed: {e.response.status_code} - {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise TableauAuthenticationError(f"Network error during switch-site: {str(e)}") from e

    async def list_sites(self, page_size: int = 100, page_number: int = 1) -> List[Dict[str, Any]]:
        """
        List sites the user has access to. Requires valid auth token.

        Returns:
            List of site dictionaries with id, name, contentUrl
        """
        await self._ensure_authenticated()
        endpoint = "sites"
        params = {"pageSize": page_size, "pageNumber": page_number}
        response = await self._request("GET", endpoint, params=params)
        sites = response.get("sites", {}).get("site", [])
        items = sites if isinstance(sites, list) else [sites] if sites else []
        return [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "contentUrl": s.get("contentUrl") or s.get("contenturl"),
            }
            for s in items
        ]

    async def _ensure_authenticated(self) -> None:
        """Ensure client is authenticated, signing in if necessary."""
        if not self.auth_token or not self.token_expires_at:
            if self._pat_auth:
                raise TableauAuthenticationError("PAT session expired. Please reconnect.")
            if self._standard_auth:
                raise TableauAuthenticationError("Standard session expired. Please reconnect.")
            logger.info("No auth token found, calling sign_in()...")
            await self.sign_in()
            return
        # PAT and standard auth cannot refresh; user must reconnect when token expires
        if self._pat_auth or self._standard_auth:
            return
        # Refresh if token expires within 1 minute
        if datetime.now(timezone.utc) >= (self.token_expires_at - timedelta(minutes=1)):
            logger.info("Auth token expiring soon, refreshing via sign_in()...")
            await self.sign_in()
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests."""
        if not self.auth_token:
            raise TableauAuthenticationError("Not authenticated. Call sign_in() first.")
        
        return {
            "X-Tableau-Auth": self.auth_token,
            "Content-Type": "application/json",
            "Accept": "application/json",  # Request JSON format
        }
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        retry_on_auth_error: bool = True,
    ) -> Dict[str, Any]:
        """
        Make authenticated API request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (relative to api_base)
            params: Query parameters
            json_data: JSON body data
            retry_on_auth_error: Whether to retry on 401 errors
            
        Returns:
            Response JSON data
            
        Raises:
            TableauAPIError: If request fails after retries
        """
        await self._ensure_authenticated()
        
        # Construct URL - site_id should always be present after authentication
        endpoint_clean = endpoint.lstrip('/')
        base_url = self.api_base.rstrip('/')
        url = f"{base_url}/{endpoint_clean}"
        headers = self._get_auth_headers()
        
        # Debug logging
        logger.debug(f"Making {method} request to: {url}, Site ID: '{self.site_id}'")
        auth_retries = 0
        max_auth_retries = 2  # Re-auth up to 2 times on 401 (Tableau invalidates token on new sign-in)
        
        for attempt in range(self.max_retries):
            try:
                response = await self._client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json_data,
                )
                
                # Handle 401 - token invalidated (e.g. new sign-in). Re-auth and retry.
                if response.status_code == 401 and retry_on_auth_error and auth_retries < max_auth_retries:
                    logger.info("Tableau returned 401 (token likely invalidated), re-authenticating...")
                    if self._on_401_invalidate:
                        self._on_401_invalidate()
                    self.auth_token = None
                    self.token_expires_at = None
                    await self._ensure_authenticated()
                    headers = self._get_auth_headers()
                    auth_retries += 1
                    continue
                
                response.raise_for_status()
                
                # We're requesting JSON with Accept header, so expect JSON response
                content_type = response.headers.get('content-type', 'unknown')
                logger.debug(f"Response Content-Type: {content_type}")
                
                try:
                    json_data = response.json()
                    logger.debug(f"✓ Successfully parsed JSON response")
                    return json_data
                except Exception as json_error:
                    # Only attempt XML parsing if content-type indicates XML
                    if 'xml' in content_type.lower():
                        logger.warning(f"✗ JSON parsing failed but Content-Type is XML. Attempting XML parsing as fallback...")
                        logger.warning(f"  Error: {json_error}")
                        logger.warning(f"  Response text (first 500 chars): {response.text[:500]}")
                        import xml.etree.ElementTree as ET
                        return self._parse_xml_response(response.text)
                    else:
                        # Unexpected format - log and raise
                        logger.error(f"✗ JSON parsing failed and Content-Type is not XML: {content_type}")
                        logger.error(f"  Error: {json_error}")
                        logger.error(f"  Response text (first 500 chars): {response.text[:500]}")
                        raise TableauAPIError(
                            f"Expected JSON response but received {content_type}. "
                            f"Status: {response.status_code}, "
                            f"Response: {response.text[:500]}"
                        ) from json_error
                
            except httpx.HTTPStatusError as e:
                if attempt == self.max_retries - 1:
                    raise TableauAPIError(
                        f"API request failed after {self.max_retries} attempts: "
                        f"{e.response.status_code} - {e.response.text}"
                    ) from e
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)
                
            except httpx.RequestError as e:
                if attempt == self.max_retries - 1:
                    raise TableauAPIError(f"Network error: {str(e)}") from e
                await asyncio.sleep(2 ** attempt)
        
        raise TableauAPIError("Request failed after all retries")
    
    async def get_datasources(
        self,
        project_id: Optional[str] = None,
        page_size: int = 100,
        page_number: int = 1,
        name_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get list of datasources with pagination.
        
        Args:
            project_id: Optional project ID to filter by
            page_size: Number of results per page (max 1000)
            page_number: Page number (1-indexed)
            name_filter: Optional search term for name (wildcard: *term*)
            
        Returns:
            Dict with 'items' (list of datasource dicts) and 'pagination' (pageNumber, pageSize, totalAvailable)
        """
        params = {
            "pageSize": min(page_size, 1000),
            "pageNumber": page_number,
        }
        
        filters = []
        if project_id:
            filters.append(f"projectId:eq:{project_id}")
        if name_filter:
            # Escape * in user input, then wrap with * for contains search
            escaped = name_filter.replace("*", "\\*")
            filters.append(f"name:eq:*{escaped}*")
        
        if filters:
            params["filter"] = ",".join(filters)
        
        # Ensure authenticated first (this will call sign_in if needed)
        # _request also calls _ensure_authenticated, but we need site_id before building endpoint
        await self._ensure_authenticated()
        
        # Use site_id (UUID) from auth response - this is the primary identifier
        # site_id should be set from the sign_in response
        site_id = self.site_id or ""
        
        logger.info("-" * 80)
        logger.info("GET_DATASOURCES CALL")
        logger.info(f"  Site ID being used: '{site_id}'")
        logger.info(f"  Project ID filter: '{project_id}'")
        logger.info(f"  Name filter: '{name_filter}'")
        logger.info(f"  Page size: {page_size}, Page number: {page_number}")
        
        if not site_id:
            logger.error(f"Site ID not available after authentication. Current site_id: '{self.site_id}'")
            raise ValueError("Site ID not available. Ensure authentication completed successfully.")
        
        endpoint = f"sites/{site_id}/datasources"
        logger.info(f"  Endpoint: {endpoint}")
        logger.info("-" * 80)
        
        response = await self._request("GET", endpoint, params=params)
        
        # Parse pagination
        pagination_info = self._parse_pagination(response)
        
        # Extract datasources
        datasources = response.get("datasources", {}).get("datasource", [])
        items = datasources if isinstance(datasources, list) else [datasources] if datasources else []
        
        # If totalAvailable not in pagination, use len(items) as fallback (single page)
        if pagination_info["totalAvailable"] is None:
            pagination_info["totalAvailable"] = len(items)
        
        return {
            "items": items,
            "pagination": pagination_info
        }
    
    async def get_views(
        self,
        datasource_id: Optional[str] = None,
        workbook_id: Optional[str] = None,
        page_size: int = 100,
        page_number: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Get list of views.
        
        Args:
            datasource_id: Optional datasource ID to filter by
            workbook_id: Optional workbook ID to filter by
            page_size: Number of results per page (max 1000)
            page_number: Page number (1-indexed)
            
        Returns:
            List of view dictionaries
        """
        params = {
            "pageSize": min(page_size, 1000),
            "pageNumber": page_number,
        }
        
        filters = []
        if datasource_id:
            filters.append(f"datasourceId:eq:{datasource_id}")
        # Note: workbookId filter is not supported by Tableau API, will filter client-side
        
        if filters:
            params["filter"] = ",".join(filters)
        
        # Ensure authenticated first (this will call sign_in if needed)
        await self._ensure_authenticated()
        
        # Use site_id (UUID) from auth response
        site_id = self.site_id or ""
        
        logger.info("-" * 80)
        logger.info("GET_VIEWS CALL")
        logger.info(f"  Site ID being used: '{site_id}'")
        logger.info(f"  Datasource ID filter: '{datasource_id}'")
        logger.info(f"  Workbook ID filter: '{workbook_id}' (will filter client-side)")
        logger.info(f"  Page size: {page_size}, Page number: {page_number}")
        
        if not site_id:
            logger.error(f"Site ID not available after authentication. Current site_id: '{self.site_id}'")
            raise ValueError("Site ID not available. Ensure authentication completed successfully.")
        
        endpoint = f"sites/{site_id}/views"
        logger.info(f"  Endpoint: {endpoint}")
        logger.info("-" * 80)
        
        # If filtering by workbook_id, fetch all views and filter client-side
        # (Tableau API doesn't support workbookId filter)
        if workbook_id:
            logger.info(f"Fetching all views and filtering by workbook_id: {workbook_id}")
            # Fetch more views to ensure we get all relevant ones
            params["pageSize"] = 1000
        
        try:
            response = await self._request("GET", endpoint, params=params)
        except TableauAPIError as e:
            # If filter fails and we're not filtering by workbook_id, re-raise
            if not workbook_id:
                raise
            # If filtering by workbook_id failed, try without filter and filter client-side
            error_msg = str(e).lower()
            if "workbookid" in error_msg or "filter" in error_msg or "400065" in str(e):
                logger.warning(f"Views API filter failed, fetching all views and filtering client-side: {e}")
                params.pop("filter", None)  # Remove filter if present
                response = await self._request("GET", endpoint, params=params)
            else:
                raise
        
        views = response.get("views", {}).get("view", [])
        views_list = views if isinstance(views, list) else [views] if views else []
        
        # Filter by workbook_id client-side if needed
        if workbook_id:
            def matches_workbook(view: Dict[str, Any], wb_id: str) -> bool:
                """Check if view belongs to the specified workbook."""
                # Try different response formats
                workbook = view.get("workbook")
                if isinstance(workbook, dict):
                    return workbook.get("id") == wb_id
                elif isinstance(workbook, str):
                    return workbook == wb_id
                # Try direct workbookId/workbook_id fields
                return view.get("workbookId") == wb_id or view.get("workbook_id") == wb_id
            
            views_list = [v for v in views_list if matches_workbook(v, workbook_id)]
            logger.info(f"Filtered to {len(views_list)} views in workbook {workbook_id}")
        
        return views_list
    
    async def query_datasource(
        self,
        datasource_id: str,
        filters: Optional[Dict[str, Any]] = None,
        columns: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Query a datasource using Tableau Data API.
        
        Note: This uses the Data API which may require different authentication.
        For now, this is a placeholder that can be extended.
        
        Args:
            datasource_id: Datasource ID to query
            filters: Optional filters to apply
            columns: Optional list of columns to return
            limit: Optional limit on number of rows
            
        Returns:
            Query result with data, columns, and row count
        """
        # Tableau Data API endpoint
        site_id = self.site_id or ""
        
        if not site_id:
            raise ValueError("Site ID not available. Ensure authentication completed successfully.")
        
        endpoint = f"sites/{site_id}/datasources/{datasource_id}/data"
        
        params = {}
        if limit:
            params["limit"] = limit
        
        # Build filter query if provided
        if filters:
            filter_parts = [f"{k}:eq:{v}" for k, v in filters.items()]
            params["filter"] = ",".join(filter_parts)
        
        response = await self._request("GET", endpoint, params=params)
        
        # Parse response
        data_rows = response.get("data", {}).get("rows", [])
        columns_info = response.get("columns", {}).get("column", [])
        
        column_names = [col.get("name") for col in columns_info] if columns_info else []
        
        # Filter columns if specified
        if columns:
            column_indices = [i for i, name in enumerate(column_names) if name in columns]
            data_rows = [[row[i] for i in column_indices] for row in data_rows]
            column_names = [name for name in column_names if name in columns]
        
        return {
            "data": data_rows,
            "columns": column_names,
            "row_count": len(data_rows),
        }
    
    async def get_view_embed_url(
        self,
        view_id: str,
        filters: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Get embedding URL for a view.
        
        Args:
            view_id: View ID
            filters: Optional filters to apply (e.g., {"Region": "West"})
            params: Optional URL parameters
            
        Returns:
            Dictionary with embed_url and token
        """
        logger.info("-" * 80)
        logger.info("GET_VIEW_EMBED_URL CALL")
        logger.info(f"  View ID: '{view_id}'")
        logger.info(f"  Filters: {filters}")
        logger.info(f"  Params: {params}")
        
        # Ensure authenticated first
        await self._ensure_authenticated()
        
        # Get view details first
        site_id = self.site_id or ""
        
        if not site_id:
            logger.error(f"Site ID not available after authentication. Current site_id: '{self.site_id}'")
            raise ValueError("Site ID not available. Ensure authentication completed successfully.")
        
        logger.info(f"  Site ID being used: '{site_id}'")
        endpoint = f"sites/{site_id}/views/{view_id}"
        logger.info(f"  Endpoint: {endpoint}")
        
        try:
            view_response = await self._request("GET", endpoint)
            logger.info(f"  View response keys: {list(view_response.keys()) if isinstance(view_response, dict) else 'not a dict'}")
            logger.debug(f"  Full view response: {view_response}")
            
            view = view_response.get("view", {})
            logger.info(f"  View object keys: {list(view.keys()) if isinstance(view, dict) else 'not a dict'}")
            logger.debug(f"  Full view object: {view}")
            
            # Extract workbook_id - can be nested as workbook.id or workbookId.id
            workbook_id = None
            workbook = view.get("workbook", {})
            if isinstance(workbook, dict):
                workbook_id = workbook.get("id")
                logger.info(f"  Found workbook_id via workbook.id: '{workbook_id}'")
            elif isinstance(workbook, str):
                workbook_id = workbook
                logger.info(f"  Found workbook_id as string: '{workbook_id}'")
            
            # Also try workbookId (camelCase)
            if not workbook_id:
                workbook_obj = view.get("workbookId", {})
                if isinstance(workbook_obj, dict):
                    workbook_id = workbook_obj.get("id")
                    logger.info(f"  Found workbook_id via workbookId.id: '{workbook_id}'")
                elif isinstance(workbook_obj, str):
                    workbook_id = workbook_obj
                    logger.info(f"  Found workbook_id via workbookId (string): '{workbook_id}'")
            
            # Extract contentUrl
            view_content_url = view.get("contentUrl") or view.get("contenturl") or view.get("ContentUrl")
            logger.info(f"  View contentUrl: '{view_content_url}'")
            
            if not workbook_id:
                logger.error(f"Could not find workbook_id in view response. View keys: {list(view.keys())}")
                logger.error(f"Full view object: {view}")
                raise TableauAPIError(f"Could not determine workbook ID for view {view_id}")
            
            if not view_content_url:
                logger.error(f"Could not find contentUrl in view response. View keys: {list(view.keys())}")
                logger.error(f"Full view object: {view}")
                raise TableauAPIError(f"Could not determine content URL for view {view_id}")
            
            # Remove '/sheets/' segment from contentUrl if present
            # Tableau contentUrl may include '/sheets/' (e.g., 'Superstore/sheets/Overview')
            # but embed URL should not have '/sheets/' (e.g., 'Superstore/Overview')
            cleaned_content_url = view_content_url.replace('/sheets/', '/')
            if cleaned_content_url != view_content_url:
                logger.info(f"  Removed '/sheets/' from contentUrl: '{view_content_url}' -> '{cleaned_content_url}'")
            
            # Build embed URL
            embed_base = urljoin(self.server_url, f"/views/{cleaned_content_url}")
            logger.info(f"  Original contentUrl: '{view_content_url}'")
            logger.info(f"  Cleaned contentUrl: '{cleaned_content_url}'")
            logger.info(f"  Embed base URL: '{embed_base}'")
            
            query_params = []
            if filters:
                for key, value in filters.items():
                    query_params.append(f"{key}={value}")
            if params:
                for key, value in params.items():
                    query_params.append(f"{key}={value}")
            
            embed_url = embed_base
            if query_params:
                embed_url += "?" + "&".join(query_params)
            
            # Generate a fresh JWT token for embedding
            # The REST API token (self.auth_token) is not suitable for embedding
            # We need to generate a new JWT with embedding scopes
            embed_jwt_token = self._generate_jwt(expires_in_minutes=10)
            logger.info(f"  Generated JWT token for embedding (length: {len(embed_jwt_token)})")
            logger.info(f"  Final embed URL: '{embed_url}'")
            logger.info("-" * 80)
            
            return {
                "url": embed_url,
                "token": embed_jwt_token,  # Use JWT token, not REST API token
                "view_id": view_id,
                "workbook_id": workbook_id,
            }
        except Exception as e:
            logger.error(f"Error getting embed URL for view {view_id}: {e}")
            logger.exception("Full traceback:")
            raise
    
    def _parse_xml_response(self, xml_text: str) -> Dict[str, Any]:
        """
        Parse Tableau XML response into JSON-like dictionary.
        
        Args:
            xml_text: XML response text from Tableau API
            
        Returns:
            Dictionary representation of XML data
        """
        import xml.etree.ElementTree as ET
        
        try:
            root = ET.fromstring(xml_text)
            return self._xml_element_to_dict(root)
        except ET.ParseError as e:
            raise TableauAPIError(f"Failed to parse XML response: {e}")
    
    def _xml_element_to_dict(self, element) -> Dict[str, Any]:
        """
        Convert XML element to dictionary recursively.
        
        Args:
            element: XML element to convert
            
        Returns:
            Dictionary representation
        """
        result = {}
        
        # Add attributes
        if element.attrib:
            result.update(element.attrib)
        
        # Add text content if present and no children
        if element.text and element.text.strip() and len(element) == 0:
            return element.text.strip()
        
        # Process children
        for child in element:
            tag = child.tag.split('}')[-1]  # Remove namespace prefix
            child_data = self._xml_element_to_dict(child)
            
            # Handle multiple children with same tag
            if tag in result:
                if not isinstance(result[tag], list):
                    result[tag] = [result[tag]]
                result[tag].append(child_data)
            else:
                result[tag] = child_data
        
        return result
    
    def _parse_pagination(self, response: Dict[str, Any]) -> Dict[str, int]:
        """
        Parse pagination info from Tableau API response.
        
        Pagination can be at top level or under tsResponse.
        XML format: <pagination pageNumber="1" pageSize="100" totalAvailable="158"/>
        JSON format: {"pagination": {"pageNumber": 1, "pageSize": 100, "totalAvailable": 158}}
        
        Args:
            response: Response dict (may have tsResponse wrapper)
            
        Returns:
            Dict with pageNumber, pageSize, totalAvailable (or defaults if missing)
        """
        # Unwrap tsResponse if present
        data = response.get("tsResponse", response) if "tsResponse" in response else response
        
        pagination = data.get("pagination", {})
        
        # Handle XML format: pagination attributes are at top level of pagination dict
        # Handle JSON format: pagination is an object with keys
        if isinstance(pagination, dict):
            page_number = int(pagination.get("pageNumber") or pagination.get("@pageNumber") or 1)
            page_size = int(pagination.get("pageSize") or pagination.get("@pageSize") or 100)
            total_available = pagination.get("totalAvailable") or pagination.get("@totalAvailable")
            if total_available is not None:
                total_available = int(total_available)
        else:
            # Fallback if pagination is not a dict
            page_number = 1
            page_size = 100
            total_available = None
        
        return {
            "pageNumber": page_number,
            "pageSize": page_size,
            "totalAvailable": total_available
        }
    
    async def get_projects(
        self,
        parent_project_id: Optional[str] = None,
        page_size: int = 100,
        page_number: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Get list of projects.
        
        Args:
            parent_project_id: Optional parent project ID to filter by (for nested projects)
            page_size: Number of results per page (max 1000)
            page_number: Page number (1-indexed)
            
        Returns:
            List of project dictionaries
        """
        params = {
            "pageSize": min(page_size, 1000),
            "pageNumber": page_number,
        }
        
        if parent_project_id:
            params["filter"] = f"parentProjectId:eq:{parent_project_id}"
        
        await self._ensure_authenticated()
        site_id = self.site_id or ""
        
        if not site_id:
            raise ValueError("Site ID not available. Ensure authentication completed successfully.")
        
        endpoint = f"sites/{site_id}/projects"
        response = await self._request("GET", endpoint, params=params)
        
        logger.info("-" * 80)
        logger.info("GET_PROJECTS CALL")
        logger.info(f"  Site ID being used: '{site_id}'")
        logger.info(f"  Parent Project ID filter: '{parent_project_id}'")
        logger.info(f"  Page size: {page_size}, Page number: {page_number}")
        logger.debug(f"  Response keys: {list(response.keys()) if isinstance(response, dict) else 'not a dict'}")
        logger.debug(f"  Full response: {response}")
        logger.info("-" * 80)
        
        # Handle both XML (parsed to dict) and JSON response formats
        # According to Tableau REST API docs, response can be:
        # XML format: {"tsResponse": {"projects": {"project": [...]}}}
        # JSON format: {"projects": {"project": [...]}} or {"tsResponse": {"projects": {"project": [...]}}}
        
        # First, unwrap tsResponse if present
        if "tsResponse" in response:
            response = response["tsResponse"]
            logger.debug("  Unwrapped tsResponse wrapper")
        
        # Extract projects data
        if "projects" not in response:
            logger.warning(f"  No 'projects' key found in response. Keys: {list(response.keys())}")
            return []
        
        projects_data = response["projects"]
        
        # Extract project list - can be single dict or list
        if isinstance(projects_data, dict):
            project_list = projects_data.get("project", [])
        elif isinstance(projects_data, list):
            project_list = projects_data
        else:
            logger.warning(f"  Unexpected projects_data type: {type(projects_data)}")
            return []
        
        # Normalize to list (Tableau API can return single object or array)
        if isinstance(project_list, list):
            projects = project_list
        elif isinstance(project_list, dict):
            projects = [project_list]
        else:
            projects = []
        
        logger.info(f"  Found {len(projects)} projects")
        return projects
    
    async def get_project_contents(
        self,
        project_id: str,
    ) -> Dict[str, Any]:
        """
        Get contents of a project (datasources, workbooks, nested projects).
        
        Args:
            project_id: Project ID to get contents for
            
        Returns:
            Dictionary with datasources, workbooks, and nested projects
        """
        await self._ensure_authenticated()
        site_id = self.site_id or ""
        
        if not site_id:
            raise ValueError("Site ID not available. Ensure authentication completed successfully.")
        
        # Get all datasources and filter by project_id client-side
        # (Some Tableau API versions don't support projectId filter for datasources)
        logger.info(f"Fetching all datasources and filtering by project_id: {project_id}")
        all_datasources_result = await self.get_datasources(page_size=1000)
        all_datasources = all_datasources_result["items"]
        
        def matches_project(obj: Dict[str, Any], proj_id: str) -> bool:
            """Check if object belongs to the specified project."""
            # Try different response formats
            project = obj.get("project")
            if isinstance(project, dict):
                return project.get("id") == proj_id
            elif isinstance(project, str):
                return project == proj_id
            # Try direct projectId/project_id fields
            return obj.get("projectId") == proj_id or obj.get("project_id") == proj_id
        
        datasources = [ds for ds in all_datasources if matches_project(ds, project_id)]
        logger.info(f"Filtered to {len(datasources)} datasources in project {project_id}")
        
        # Get workbooks in project (workbooks API may support projectId filter)
        try:
            workbooks_result = await self.get_workbooks(project_id=project_id, page_size=1000)
            workbooks = workbooks_result["items"]
        except TableauAPIError as e:
            # If workbooks filter fails, fetch all and filter client-side
            error_msg = str(e).lower()
            if "projectid" in error_msg or "filter" in error_msg or "400065" in str(e):
                logger.warning(f"Workbooks API doesn't support projectId filter, filtering client-side: {e}")
                all_workbooks_result = await self.get_workbooks(page_size=1000)
                all_workbooks = all_workbooks_result["items"]
                workbooks = [wb for wb in all_workbooks if matches_project(wb, project_id)]
                logger.info(f"Filtered to {len(workbooks)} workbooks in project {project_id}")
            else:
                raise
        
        # Get nested projects
        nested_projects = await self.get_projects(parent_project_id=project_id, page_size=1000)
        
        return {
            "project_id": project_id,
            "datasources": datasources,
            "workbooks": workbooks,
            "projects": nested_projects,
        }
    
    async def get_workbooks(
        self,
        project_id: Optional[str] = None,
        page_size: int = 100,
        page_number: int = 1,
        name_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get list of workbooks with pagination.
        
        Args:
            project_id: Optional project ID to filter by
            page_size: Number of results per page (max 1000)
            page_number: Page number (1-indexed)
            name_filter: Optional search term for name (wildcard: *term*)
            
        Returns:
            Dict with 'items' (list of workbook dicts) and 'pagination' (pageNumber, pageSize, totalAvailable)
        """
        params = {
            "pageSize": min(page_size, 1000),
            "pageNumber": page_number,
        }
        
        filters = []
        if project_id:
            filters.append(f"projectId:eq:{project_id}")
        if name_filter:
            # Escape * in user input, then wrap with * for contains search
            escaped = name_filter.replace("*", "\\*")
            filters.append(f"name:eq:*{escaped}*")
        
        if filters:
            params["filter"] = ",".join(filters)
        
        await self._ensure_authenticated()
        site_id = self.site_id or ""
        
        if not site_id:
            raise ValueError("Site ID not available. Ensure authentication completed successfully.")
        
        endpoint = f"sites/{site_id}/workbooks"
        response = await self._request("GET", endpoint, params=params)
        
        logger.debug(f"Workbooks response keys: {list(response.keys()) if isinstance(response, dict) else 'not a dict'}")
        
        # Parse pagination
        pagination_info = self._parse_pagination(response)
        
        # Handle both XML (parsed to dict) and JSON response formats
        # Unwrap tsResponse if present
        if "tsResponse" in response:
            response = response["tsResponse"]
        
        # Extract workbooks data
        if "workbooks" not in response:
            logger.warning(f"No 'workbooks' key found in response. Keys: {list(response.keys())}")
            return {"items": [], "pagination": pagination_info}
        
        workbooks_data = response["workbooks"]
        
        # Extract workbook list - can be single dict or list
        if isinstance(workbooks_data, dict):
            workbook_list = workbooks_data.get("workbook", [])
        elif isinstance(workbooks_data, list):
            workbook_list = workbooks_data
        else:
            logger.warning(f"Unexpected workbooks_data type: {type(workbooks_data)}")
            return {"items": [], "pagination": pagination_info}
        
        # Normalize to list
        if isinstance(workbook_list, list):
            workbooks = workbook_list
        elif isinstance(workbook_list, dict):
            workbooks = [workbook_list]
        else:
            workbooks = []
        
        # If totalAvailable not in pagination, use len(items) as fallback (single page)
        if pagination_info["totalAvailable"] is None:
            pagination_info["totalAvailable"] = len(workbooks)
        
        logger.info(f"Found {len(workbooks)} workbooks")
        return {
            "items": workbooks,
            "pagination": pagination_info
        }
    
    async def get_workbook_views(
        self,
        workbook_id: str,
        page_size: int = 100,
        page_number: int = 1,
        name_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get views within a workbook with pagination.
        
        Uses the workbook-specific endpoint: GET /api/api-version/sites/site-id/workbooks/workbook-id/views
        
        Args:
            workbook_id: Workbook ID
            page_size: Number of results per page (max 1000)
            page_number: Page number (1-indexed)
            name_filter: Optional search term for view name/caption (wildcard: *term*)
            
        Returns:
            Dict with 'items' (list of view dicts) and 'pagination' (pageNumber, pageSize, totalAvailable)
        """
        await self._ensure_authenticated()
        site_id = self.site_id or ""
        
        if not site_id:
            raise ValueError("Site ID not available. Ensure authentication completed successfully.")
        
        # Use the workbook-specific views endpoint
        endpoint = f"sites/{site_id}/workbooks/{workbook_id}/views"
        
        params = {
            "pageSize": min(page_size, 1000),
            "pageNumber": page_number,
        }
        
        if name_filter:
            # Escape * in user input, then wrap with * for contains search
            # Use name field (caption filtering may require separate filter syntax)
            escaped = name_filter.replace("*", "\\*")
            params["filter"] = f"name:eq:*{escaped}*"
        
        logger.info("-" * 80)
        logger.info("GET_WORKBOOK_VIEWS CALL")
        logger.info(f"  Site ID: '{site_id}'")
        logger.info(f"  Workbook ID: '{workbook_id}'")
        logger.info(f"  Name filter: '{name_filter}'")
        logger.info(f"  Endpoint: {endpoint}")
        logger.info(f"  Page size: {page_size}, Page number: {page_number}")
        logger.info("-" * 80)
        
        response = await self._request("GET", endpoint, params=params)
        
        # Parse pagination
        pagination_info = self._parse_pagination(response)
        
        # Handle both XML (parsed to dict) and JSON response formats
        # Unwrap tsResponse if present
        if "tsResponse" in response:
            response = response["tsResponse"]
        
        # Extract views data
        views_data = response.get("views", {})
        
        # Extract view list - can be single dict or list
        if isinstance(views_data, dict):
            view_list = views_data.get("view", [])
        elif isinstance(views_data, list):
            view_list = views_data
        else:
            logger.warning(f"Unexpected views_data type: {type(views_data)}")
            return {"items": [], "pagination": pagination_info}
        
        # Normalize to list
        if isinstance(view_list, list):
            views = view_list
        elif isinstance(view_list, dict):
            views = [view_list]
        else:
            views = []
        
        # If totalAvailable not in pagination, use len(items) as fallback (single page)
        if pagination_info["totalAvailable"] is None:
            pagination_info["totalAvailable"] = len(views)
        
        logger.info(f"Found {len(views)} views for workbook {workbook_id}")
        return {
            "items": views,
            "pagination": pagination_info
        }
    
    async def get_view(self, view_id: str) -> Dict[str, Any]:
        """
        Get view metadata.
        
        Args:
            view_id: View ID (LUID; commas/suffixes like ,1:1 are stripped)
            
        Returns:
            Dictionary with view information
        """
        await self._ensure_authenticated()
        site_id = self.site_id or ""
        
        if not site_id:
            raise ValueError("Site ID not available.")
        
        clean_view_id = view_id.split(",")[0].strip() if "," in view_id else view_id
        endpoint = f"sites/{site_id}/views/{clean_view_id}"
        response = await self._request("GET", endpoint)
        
        view_data = response.get("view", {})
        return view_data
    
    async def get_view_data(
        self,
        view_id: str,
        max_rows: int = 1000,
        filters: Optional[Dict[str, str | List[str]]] = None
    ) -> Dict[str, Any]:
        """
        Get data from a view using Tableau Data API.
        
        Uses: GET /api/api-version/sites/site-id/views/view-id/data
        
        Note: This endpoint returns CSV format, not JSON, so we need to handle it specially.
        Supports view filters via vf_fieldname=value query params.
        
        Args:
            view_id: View ID (LUID; commas/suffixes like ,1:1 are stripped)
            max_rows: Maximum number of rows to return
            filters: Optional dict of field_name -> value or list of values.
                     e.g. {"Region": "West"} or {"Category": ["Technology", "Furniture"]}
            
        Returns:
            Dictionary with columns and data
        """
        await self._ensure_authenticated()
        site_id = self.site_id or ""
        
        if not site_id:
            raise ValueError("Site ID not available.")
        
        # Strip invalid suffixes (e.g. ,1:1) - Tableau LUIDs are alphanumeric
        clean_view_id = view_id.split(",")[0].strip() if "," in view_id else view_id
        
        endpoint = f"sites/{site_id}/views/{clean_view_id}/data"
        params: Dict[str, Any] = {"maxAge": 0}  # Get fresh data
        
        if filters:
            for field_name, value in filters.items():
                vf_key = f"vf_{field_name}"
                if isinstance(value, list):
                    params[vf_key] = ",".join(str(v) for v in value)
                else:
                    params[vf_key] = str(value)
        
        try:
            # The /views/{view_id}/data endpoint returns CSV, not JSON
            # So we need to make a direct request instead of using _request()
            endpoint_clean = endpoint.lstrip('/')
            base_url = self.api_base.rstrip('/')
            url = f"{base_url}/{endpoint_clean}"
            headers = self._get_auth_headers()
            
            logger.debug(f"Making GET request to view data endpoint: {url}")
            response = await self._client.get(
                url,
                headers=headers,
                params=params,
            )
            
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', 'unknown')
            logger.debug(f"Response Content-Type: {content_type}")
            
            # Parse CSV response
            # Tableau returns CSV format: "Column1,Column2\nValue1,Value2\n..."
            csv_text = response.text
            
            if not csv_text or not csv_text.strip():
                return {"columns": [], "data": [], "row_count": 0}
            
            # Parse CSV string
            import csv
            from io import StringIO
            
            # Use csv module to properly handle quoted values and commas within fields
            csv_reader = csv.reader(StringIO(csv_text))
            lines = list(csv_reader)
            
            if len(lines) < 1:
                return {"columns": [], "data": [], "row_count": 0}
            
            # First line is headers
            columns = [col.strip() for col in lines[0]]
            
            # Remaining lines are data (limit to max_rows)
            data_rows = []
            for line in lines[1:max_rows+1]:
                if line:  # Skip empty lines
                    data_rows.append([val.strip() if val else "" for val in line])
            
            logger.debug(f"Parsed CSV: {len(columns)} columns, {len(data_rows)} rows")
            
            return {
                "columns": columns,
                "data": data_rows,
                "row_count": len(data_rows)
            }
        except Exception as e:
            logger.error(f"Error getting view data for {view_id}: {e}")
            raise TableauAPIError(f"Failed to get view data: {str(e)}")
    
    async def get_datasource_schema(
        self,
        datasource_id: str,
    ) -> Dict[str, Any]:
        """
        Get schema information for a datasource using VizQL Data Service API.
        
        Args:
            datasource_id: Datasource LUID
            
        Returns:
            Dictionary with column information (name, data type, etc.)
        """
        await self._ensure_authenticated()
        
        # Use VizQL Data Service API to get metadata
        # VDS API uses /api/v1/ regardless of REST API version
        # VDS API does NOT include site_id in the path (unlike REST API endpoints)
        vds_url = urljoin(self.server_url, '/api/v1/vizql-data-service/read-metadata')
        
        # Request body for read-metadata according to VDS API docs
        request_body = {
            "datasource": {
                "datasourceLuid": datasource_id
            }
        }
        
        logger.info("-" * 80)
        logger.info("GET_DATASOURCE_SCHEMA CALL")
        logger.info(f"  Datasource LUID: '{datasource_id}'")
        logger.info(f"  VDS URL: {vds_url}")
        logger.info("-" * 80)
        
        # Make direct request to VDS endpoint (bypass api_base)
        headers = self._get_auth_headers()
        response = await self._client.post(
            vds_url,
            headers=headers,
            json=request_body,
            timeout=self.timeout,
        )
        response.raise_for_status()
        response_data = response.json()
        
        # Handle tsResponse wrapper if present
        if "tsResponse" in response_data:
            response_data = response_data["tsResponse"]
        
        response = response_data
        
        # Parse metadata response according to VDS API docs
        # Response has "data" array with field objects and optional "extraData" with parameters
        schema = []
        
        if "data" in response:
            fields = response["data"]
            if isinstance(fields, list):
                for field in fields:
                    if isinstance(field, dict):
                        # Determine if measure or dimension based on columnClass (primary indicator)
                        column_class = field.get("columnClass", "")
                        default_agg = field.get("defaultAggregation", "")
                        
                        # Use columnClass as primary indicator
                        # MEASURE = measure, COLUMN/BIN/GROUP = dimension
                        if column_class == "MEASURE":
                            is_measure = True
                            is_dimension = False
                        elif column_class in ["COLUMN", "BIN", "GROUP"]:
                            is_measure = False
                            is_dimension = True
                        else:
                            # Fallback: use defaultAggregation if columnClass not available or unknown
                            # Fields with aggregations are typically measures, but dimensions can have aggregations too
                            # So we check if it's a numeric type with aggregation
                            data_type = field.get("dataType", "")
                            is_numeric = data_type in ["INTEGER", "REAL"]
                            has_aggregation = default_agg in ["SUM", "AVG", "MEDIAN", "COUNT", "COUNTD", "MIN", "MAX", "STDEV", "VAR", "AGG"]
                            
                            # If numeric with aggregation and no explicit columnClass, likely a measure
                            # Otherwise, treat as dimension if it has columnClass values, or unknown
                            if is_numeric and has_aggregation and not column_class:
                                is_measure = True
                                is_dimension = False
                            elif column_class in ["CALCULATION", "TABLE_CALCULATION"]:
                                # Calculated fields need to be checked by their formula/aggregation
                                is_measure = has_aggregation and is_numeric
                                is_dimension = not is_measure
                            else:
                                # Default to dimension for unknown types
                                is_measure = False
                                is_dimension = True
                        
                        schema.append({
                            "name": field.get("fieldCaption") or field.get("fieldName", ""),
                            "data_type": field.get("dataType", ""),
                            "remote_type": field.get("dataType", ""),  # VDS uses dataType
                            "is_measure": is_measure,
                            "is_dimension": is_dimension,
                            "default_aggregation": default_agg,
                            "column_class": column_class,
                            "formula": field.get("formula"),  # For calculations
                        })
        else:
            logger.warning(f"Unexpected metadata response structure. Keys: {list(response.keys())}")
        
        logger.info(f"  Found {len(schema)} columns in schema")
        return {
            "datasource_id": datasource_id,
            "columns": schema,
        }
    
    async def get_datasource_sample(
        self,
        datasource_id: str,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get sample data from a datasource using VizQL Data Service API.
        
        Args:
            datasource_id: Datasource LUID
            limit: Number of rows to return (max 1000)
            
        Returns:
            Dictionary with columns and sample data rows
        """
        await self._ensure_authenticated()
        
        # First, get metadata to know what fields are available
        schema = await self.get_datasource_schema(datasource_id)
        
        if not schema.get("columns"):
            raise TableauAPIError(f"No columns found in datasource {datasource_id}")
        
        # Use first few columns for sample (prefer dimensions, then measures)
        columns = schema["columns"]
        dimension_fields = [col for col in columns if col.get("is_dimension")]
        measure_fields = [col for col in columns if col.get("is_measure")]
        
        # Select fields for sample query (up to 10 fields)
        sample_fields = []
        field_count = 0
        
        # Add dimensions first (up to 5)
        for col in dimension_fields[:5]:
            field_caption = col.get("name", "")
            if field_caption:
                sample_fields.append({
                    "fieldCaption": field_caption
                })
                field_count += 1
        
        # Add measures with aggregation (up to 5)
        for col in measure_fields[:5]:
            field_caption = col.get("name", "")
            default_agg = col.get("default_aggregation", "SUM")
            if field_caption:
                field_obj = {
                    "fieldCaption": field_caption
                }
                # Add function if it's a measure and has a default aggregation
                if default_agg and default_agg != "NONE" and default_agg != "COUNT":
                    field_obj["function"] = default_agg
                sample_fields.append(field_obj)
                field_count += 1
        
        if not sample_fields:
            # Fallback: use first few columns regardless of type
            for col in columns[:10]:
                field_caption = col.get("name", "")
                if field_caption:
                    sample_fields.append({
                        "fieldCaption": field_caption
                    })
        
        # Use VizQL Data Service API to query datasource
        # VDS API uses /api/v1/ regardless of REST API version
        # VDS API does NOT include site_id in the path (unlike REST API endpoints)
        vds_url = urljoin(self.server_url, '/api/v1/vizql-data-service/query-datasource')
        
        # Request body for query-datasource according to VDS API docs
        request_body = {
            "datasource": {
                "datasourceLuid": datasource_id
            },
            "query": {
                "fields": sample_fields
            },
            "options": {
                "returnFormat": "OBJECTS",  # Human-readable format
                "disaggregate": False
            }
        }
        
        logger.info("-" * 80)
        logger.info("GET_DATASOURCE_SAMPLE CALL")
        logger.info(f"  Datasource LUID: '{datasource_id}'")
        logger.info(f"  Limit: {limit}")
        logger.info(f"  Fields to query: {len(sample_fields)}")
        logger.info(f"  VDS URL: {vds_url}")
        logger.info("-" * 80)
        
        # Make direct request to VDS endpoint (bypass api_base)
        headers = self._get_auth_headers()
        response = await self._client.post(
            vds_url,
            headers=headers,
            json=request_body,
            timeout=self.timeout,
        )
        response.raise_for_status()
        response_data = response.json()
        
        # Handle tsResponse wrapper if present
        if "tsResponse" in response_data:
            response_data = response_data["tsResponse"]
        
        response = response_data
        
        # Parse query response according to VDS API docs
        # Response has "data" array with objects (if returnFormat=OBJECTS) or arrays (if returnFormat=ARRAYS)
        data_rows = []
        column_names = []
        
        if "data" in response:
            raw_data = response["data"]
            if isinstance(raw_data, list) and len(raw_data) > 0:
                first_row = raw_data[0]
                
                if isinstance(first_row, dict):
                    # OBJECTS format - convert to arrays
                    # Get column names from first row (maintain order)
                    column_names = list(first_row.keys())
                    logger.debug(f"  Converting OBJECTS format: {len(column_names)} columns")
                    
                    # Convert each object to an array maintaining column order
                    data_rows = []
                    for row in raw_data:
                        if isinstance(row, dict):
                            # Convert dict to list maintaining column order
                            row_array = [row.get(col_name) for col_name in column_names]
                            data_rows.append(row_array)
                        else:
                            logger.warning(f"  Skipping non-dict row: {type(row)}")
                    
                elif isinstance(first_row, list):
                    # ARRAYS format - already arrays
                    logger.debug("  Using ARRAYS format (already arrays)")
                    column_names = [field.get("fieldCaption", f"Column_{i+1}") for i, field in enumerate(sample_fields)]
                    # Ensure column count matches
                    if len(first_row) != len(column_names):
                        column_names = [f"Column_{i+1}" for i in range(len(first_row))]
                    data_rows = raw_data
                else:
                    logger.warning(f"  Unexpected first row type: {type(first_row)}")
                    data_rows = []
            else:
                logger.warning(f"  No data or empty data array. Response keys: {list(response.keys())}")
        else:
            logger.warning(f"  No 'data' key in response. Response keys: {list(response.keys())}")
        
        # Limit rows if needed
        if limit and len(data_rows) > limit:
            data_rows = data_rows[:limit]
        
        # Ensure all rows are lists (not dicts)
        data_rows = [
            row if isinstance(row, list) else list(row.values()) if isinstance(row, dict) else []
            for row in data_rows
        ]
        
        logger.info(f"  Found {len(data_rows)} rows and {len(column_names)} columns")
        logger.debug(f"  First row sample: {data_rows[0] if data_rows else 'empty'}")
        
        return {
            "datasource_id": datasource_id,
            "columns": column_names,
            "data": data_rows,
            "row_count": len(data_rows),
            "query": request_body,
        }
    
    async def execute_vds_query(
        self,
        query_obj: Dict[str, Any],
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute a VizQL Data Service query.
        
        Args:
            query_obj: VizQL Data Service query object with structure:
                {
                    "datasource": {"datasourceLuid": "..."},
                    "query": {
                        "fields": [...],
                        "filters": [...]
                    },
                    "options": {...}
                }
            limit: Optional row limit (overrides query options if provided)
            
        Returns:
            Dictionary with columns, data, and row_count
        """
        await self._ensure_authenticated()
        
        # Ensure query has required structure
        if "datasource" not in query_obj:
            raise ValueError("Query missing 'datasource' field")
        if "query" not in query_obj:
            raise ValueError("Query missing 'query' field")
        if "fields" not in query_obj["query"] or not query_obj["query"]["fields"]:
            raise ValueError("Query must have at least one field in 'query.fields' array")
        
        # Note: VDS API does not support 'limit' in options - it must be handled client-side
        # Remove limit from options if it exists (it's not a valid VDS API option)
        if "options" in query_obj and "limit" in query_obj["options"]:
            del query_obj["options"]["limit"]
            logger.debug(f"Removed invalid 'limit' from options (VDS API doesn't support it)")
        
        # Ensure options have defaults - always use OBJECTS format for reliable column ordering
        if "options" not in query_obj:
            query_obj["options"] = {
                "returnFormat": "OBJECTS",
                "disaggregate": False
            }
        else:
            # Force OBJECTS format to ensure column names are included in response
            if query_obj["options"].get("returnFormat") != "OBJECTS":
                logger.warning(
                    f"Query requested returnFormat '{query_obj['options'].get('returnFormat')}', "
                    f"but forcing OBJECTS format for reliable column ordering"
                )
            query_obj["options"]["returnFormat"] = "OBJECTS"
        
        # Use VizQL Data Service API
        # VDS API does NOT include site_id in the path (unlike REST API endpoints)
        vds_url = urljoin(self.server_url, '/api/v1/vizql-data-service/query-datasource')
        
        logger.info("-" * 80)
        logger.info("EXECUTE_VDS_QUERY CALL")
        logger.info(f"  Datasource LUID: '{query_obj['datasource'].get('datasourceLuid')}'")
        logger.info(f"  Fields: {len(query_obj.get('query', {}).get('fields', []))}")
        logger.info(f"  Filters: {len(query_obj.get('query', {}).get('filters', []))}")
        logger.info(f"  VDS URL: {vds_url}")
        logger.info(f"  Query object keys: {list(query_obj.keys())}")
        logger.info(f"  Full query object: {query_obj}")
        logger.info("-" * 80)
        
        # Make request - ensure X-Tableau-Auth header is present (required by VDS API)
        headers = self._get_auth_headers()
        if "X-Tableau-Auth" not in headers:
            raise TableauAuthenticationError("X-Tableau-Auth header missing from request headers")
        logger.info(f"  Auth header present: {'X-Tableau-Auth' in headers}")
        logger.info(f"  Auth token length: {len(headers.get('X-Tableau-Auth', ''))}")
        logger.debug(f"  Full request headers: {dict(headers)}")
        
        response = await self._client.post(
            vds_url,
            headers=headers,
            json=query_obj,
            timeout=self.timeout,
        )
        
        # Extract error message from Tableau response if request failed
        if response.status_code != 200:
            logger.error(f"VDS API returned status {response.status_code}")
            error_message = None
            try:
                error_body = response.text
                logger.error(f"Response body: {error_body}")
                
                # Try to extract error message from response
                # Tableau errors can be in various formats (JSON, XML, plain text)
                try:
                    # Try parsing as JSON first
                    error_json = response.json()
                    # Look for common error message fields
                    if isinstance(error_json, dict):
                        # Try multiple common error message locations in order of preference
                        error_obj = error_json.get("error")
                        if isinstance(error_obj, dict):
                            error_message = error_obj.get("message") or error_obj.get("detail") or error_obj.get("error")
                        elif isinstance(error_obj, str):
                            error_message = error_obj
                        else:
                            error_message = None
                        
                        # Fallback to other common fields
                        if not error_message:
                            error_message = (
                                error_json.get("message") or
                                error_json.get("detail") or
                                error_json.get("errorMessage") or
                                error_json.get("error_message") or
                                error_body
                            )
                    else:
                        error_message = error_body
                except (ValueError, json.JSONDecodeError):
                    # Not JSON, use the raw error body
                    # Could be XML or plain text - use as-is
                    error_message = error_body
                
                # Clean up error message (limit length, remove excessive whitespace)
                if error_message:
                    error_message = error_message.strip()
                    if len(error_message) > 1000:
                        error_message = error_message[:1000] + "..."
            except Exception as e:
                logger.warning(f"Failed to extract error message: {e}")
                error_message = f"HTTP {response.status_code}"
            
            # Raise TableauAPIError with detailed error message from Tableau
            if error_message:
                raise TableauAPIError(f"Tableau server error (HTTP {response.status_code}): {error_message}")
            else:
                raise TableauAPIError(f"Tableau server error: HTTP {response.status_code}")
        
        response.raise_for_status()
        response_data = response.json()
        
        # Handle tsResponse wrapper if present
        if "tsResponse" in response_data:
            response_data = response_data["tsResponse"]
        
        # Parse query response
        data_rows = []
        column_names = []
        
        # Apply limit client-side if provided (VDS API doesn't support limit in options)
        
        if "data" in response_data:
            raw_data = response_data["data"]
            if isinstance(raw_data, list) and len(raw_data) > 0:
                first_row = raw_data[0]
                
                if isinstance(first_row, dict):
                    # OBJECTS format - column names are in each row's keys
                    column_names = list(first_row.keys())
                    logger.debug(f"OBJECTS format: extracted {len(column_names)} columns: {column_names}")
                    for row in raw_data:
                        if isinstance(row, dict):
                            row_array = [row.get(col_name) for col_name in column_names]
                            data_rows.append(row_array)
                
                elif isinstance(first_row, list):
                    # ARRAYS format - need to determine column order
                    logger.warning("Received ARRAYS format response - column order may not match query fields order")
                    
                    # First, check if response includes column metadata
                    if "columns" in response_data:
                        # Response includes explicit column order
                        column_names = response_data["columns"]
                        logger.info(f"Using column order from response metadata: {column_names}")
                    elif "metadata" in response_data and "columns" in response_data["metadata"]:
                        column_names = response_data["metadata"]["columns"]
                        logger.info(f"Using column order from metadata: {column_names}")
                    else:
                        # Fallback: try to infer from query fields, but warn about potential mismatch
                        fields = query_obj.get("query", {}).get("fields", [])
                        if fields and len(fields) == len(first_row):
                            # Map query fields to column names, preserving order from query
                            column_names = [
                                field.get("fieldCaption", f"Column_{i+1}")
                                for i, field in enumerate(fields)
                            ]
                            logger.warning(
                                f"ARRAYS format: inferring column order from query fields. "
                                f"This may not match Tableau's actual column order. "
                                f"Columns: {column_names}, Row sample: {first_row[:3]}"
                            )
                        else:
                            # Last resort: generic column names
                            column_names = [f"Column_{i+1}" for i in range(len(first_row))]
                            logger.error(
                                f"ARRAYS format: Cannot determine column order. "
                                f"Using generic names. Query had {len(fields)} fields, "
                                f"but row has {len(first_row)} values. Row sample: {first_row[:3]}"
                            )
                    
                    # Ensure column count matches
                    if len(first_row) != len(column_names):
                        logger.error(
                            f"Column count mismatch: {len(column_names)} columns but {len(first_row)} values in row. "
                            f"Using generic column names."
                        )
                        column_names = [f"Column_{i+1}" for i in range(len(first_row))]
                    
                    data_rows = raw_data
        
        # Apply limit if specified
        if limit and len(data_rows) > limit:
            data_rows = data_rows[:limit]
        
        logger.info(f"  Found {len(data_rows)} rows and {len(column_names)} columns")
        logger.info(f"  Column names: {column_names}")
        if data_rows and len(data_rows) > 0:
            logger.debug(f"  First row sample: {data_rows[0][:3] if len(data_rows[0]) >= 3 else data_rows[0]}")
            logger.debug(f"  First row full: {data_rows[0]}")
        
        # Validate column count matches data
        if data_rows and len(data_rows) > 0:
            expected_cols = len(data_rows[0])
            if len(column_names) != expected_cols:
                logger.error(
                    f"Column count mismatch: {len(column_names)} column names but "
                    f"{expected_cols} values per row. This will cause data misalignment!"
                )
        
        return {
            "columns": column_names,
            "data": data_rows,
            "row_count": len(data_rows),
        }
    
    async def read_metadata(self, datasource_id: str) -> Dict[str, Any]:
        """
        Request data source metadata from VizQL Data Service API.
        
        Uses the /read-metadata endpoint to get field information including:
        - fieldCaption (exact field names)
        - dataType (INTEGER, REAL, STRING, etc.)
        - fieldRole (MEASURE, DIMENSION)
        - defaultAggregation
        - description
        - aliases
        
        Args:
            datasource_id: Datasource LUID
            
        Returns:
            Dictionary with 'data' array containing FieldMetadata objects
            
        Raises:
            TableauAPIError: If API request fails
        """
        await self._ensure_authenticated()
        
        # VizQL Data Service API base URL
        # Note: urljoin replaces path if second arg starts with '/', so we need to construct manually
        server_base = self.server_url.rstrip('/')
        metadata_url = f"{server_base}/api/v1/vizql-data-service/read-metadata"
        
        # Request payload
        # Note: Some Tableau server versions don't support the 'options' field
        # Using minimal payload with just datasource identifier
        payload = {
            "datasource": {
                "datasourceLuid": datasource_id
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Tableau-Auth": self.auth_token
        }
        
        try:
            logger.info(f"Read-metadata request: {json.dumps(payload, indent=2)}")
            logger.info(f"Requesting metadata for datasource {datasource_id}")
            response = await self._client.post(
                metadata_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            
            response.raise_for_status()
            result = response.json()
            logger.info(f"Read-metadata raw response: {json.dumps(result, indent=2)}")
            logger.info(f"Successfully retrieved metadata: {len(result.get('data', []))} fields")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"VizQL metadata API error: {e.response.status_code} - {e.response.text}")
            raise TableauAPIError(f"Failed to read metadata: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"Error reading metadata: {e}")
            raise TableauAPIError(f"Error reading metadata: {str(e)}")
    
    async def get_metadata_api_fields(self, datasource_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get field role information from Tableau Metadata API (GraphQL).
        
        Uses the Metadata API to get accurate field roles (MEASURE/DIMENSION)
        since VizQL Data Service API doesn't always provide this reliably.
        
        Args:
            datasource_id: Datasource LUID
            
        Returns:
            Dictionary mapping field names/captions to field metadata with role information
        """
        await self._ensure_authenticated()
        
        # Metadata API GraphQL endpoint
        server_base = self.server_url.rstrip('/')
        graphql_url = f"{server_base}/api/metadata/graphql"
        
        # GraphQL query to get published datasource fields
        # Using minimal fields that are known to exist in Tableau Metadata API
        # Note: Some fields may not be available in all API versions
        query = """
        query GetDatasourceFields($luid: String!) {
            publishedDatasources(filter: {luid: $luid}) {
                id
                luid
                name
                fields {
                    id
                    name
                    fullyQualifiedName
                    description
                    __typename
                    ... on DataField {
                        role
                    }
                    ... on CalculatedField {
                        formula
                    }
                }
            }
        }
        """
        
        payload = {
            "query": query,
            "variables": {
                "luid": datasource_id
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Tableau-Auth": self.auth_token
        }
        
        try:
            logger.info(f"Metadata API GraphQL request: {json.dumps(payload, indent=2)}")
            logger.info(f"Querying Metadata API for field roles for datasource {datasource_id}")
            response = await self._client.post(
                graphql_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            
            response.raise_for_status()
            result = response.json()
            logger.info(f"Metadata API GraphQL raw response: {json.dumps(result, indent=2)}")
            # Check for GraphQL errors
            if "errors" in result:
                error_messages = [err.get("message", "Unknown error") for err in result["errors"]]
                logger.warning(f"GraphQL errors: {error_messages}")
                return {}
            
            # Extract fields from response
            field_map = {}
            datasources = result.get("data", {}).get("publishedDatasources", [])
            
            if not datasources:
                logger.warning(
                    f"No datasource found with LUID {datasource_id} in Metadata API. "
                    f"Response keys: {list(result.get('data', {}).keys())}"
                )
                return {}

            datasource = datasources[0]
            raw_fields = datasource.get("fields", [])
            # fields is [[Field]!]! - array of arrays (per table), flatten
            fields = []
            for item in raw_fields:
                if isinstance(item, list):
                    fields.extend(item)
                else:
                    fields.append(item)

            if not fields:
                logger.warning(
                    f"No fields in Metadata API datasource. raw_fields type={type(raw_fields)}, "
                    f"len={len(raw_fields)}, sample={raw_fields[:2] if raw_fields else []}"
                )
                return {}
            
            for field in fields:
                field_name = field.get("name", "")
                field_type = field.get("__typename", "")  # Use __typename to identify field type
                
                if not field_name:
                    continue
                
                field_info = {
                    "description": field.get("description"),
                }
                
                # Extract formula if this is a calculated field
                # Formula is available for CalculatedField types
                # Also check aggregation property which may contain the formula
                if "formula" in field:
                    field_info["formula"] = field.get("formula")
                elif "aggregation" in field:
                    # Some calculated fields store formula in aggregation property
                    aggregation_value = field.get("aggregation")
                    if isinstance(aggregation_value, str):
                        field_info["formula"] = aggregation_value
                    elif isinstance(aggregation_value, dict) and "formula" in aggregation_value:
                        field_info["formula"] = aggregation_value.get("formula")
                
                # Store field type
                if field_type:
                    field_info["fieldType"] = field_type
                
                # Use role directly from DataField interface (source of truth)
                role = field.get("role")
                if role:
                    field_info["role"] = role.upper()  # Normalize to uppercase (DIMENSION, MEASURE, UNKNOWN)
                
                # Map by field name (exact + case-insensitive for VizQL matching)
                field_map[field_name] = field_info
                if field_name:
                    field_map[field_name.lower()] = field_info
                # Also index by fullyQualifiedName and its last segment (e.g. "Table].[Sales" -> "Sales")
                fqn = field.get("fullyQualifiedName") or ""
                if fqn:
                    field_map[fqn] = field_info
                    last_seg = fqn.split("].")[-1].split(".")[-1].strip("[]")
                    if last_seg and last_seg not in field_map:
                        field_map[last_seg] = field_info
            
            logger.info(f"Retrieved {len(raw_fields)} raw field groups, {len(fields)} fields from Metadata API")
            if not field_map and fields:
                logger.warning(
                    f"All {len(fields)} Metadata API fields had empty name. "
                    f"Sample field keys: {list(fields[0].keys()) if fields else []}"
                )
            return field_map
            
        except httpx.HTTPStatusError as e:
            logger.warning(f"Metadata API error: {e.response.status_code} - {e.response.text}")
            # Don't raise - return empty dict so enrichment can continue with VizQL data only
            return {}
        except Exception as e:
            logger.warning(f"Error querying Metadata API: {e}")
            # Don't raise - return empty dict so enrichment can continue with VizQL data only
            return {}
    
    async def get_field_statistics(
        self, 
        datasource_id: str, 
        field_caption: str,
        data_type: str,
        is_measure: bool
    ) -> Dict[str, Any]:
        """
        Get statistics for a single field: cardinality, sample values, min/max/null%.
        
        Args:
            datasource_id: Datasource LUID
            field_caption: Field caption/name
            data_type: Field data type (INTEGER, REAL, STRING, etc.)
            is_measure: Whether field is a measure
            
        Returns:
            Dictionary with statistics: cardinality, sample_values, min, max, null_percentage
        """
        await self._ensure_authenticated()
        
        server_base = self.server_url.rstrip('/')
        query_url = f"{server_base}/api/v1/vizql-data-service/query-datasource"
        
        stats = {
            "cardinality": None,
            "sample_values": [],
            "value_counts": [],
            "min": None,
            "max": None,
            "median": None,
            "null_percentage": None
        }
        
        try:
            # Build query for this field
            field_query = {"fieldCaption": field_caption}
            
            # For measures, use default aggregation; for dimensions, get value counts
            if is_measure:
                # Get aggregated stats (min, max, count, median)
                query_payload = {
                    "datasource": {"datasourceLuid": datasource_id},
                    "query": {
                        "fields": [
                            {"fieldCaption": field_caption, "function": "MIN"},
                            {"fieldCaption": field_caption, "function": "MAX"},
                            {"fieldCaption": field_caption, "function": "COUNT"},
                            {"fieldCaption": field_caption, "function": "MEDIAN"}
                        ]
                    },
                    "options": {"returnFormat": "OBJECTS", "disaggregate": False}
                }
            else:
                # For dimensions: get value_counts via aggregated query with TOP filter
                query_payload = {
                    "datasource": {"datasourceLuid": datasource_id},
                    "query": {
                        "fields": [
                            {"fieldCaption": field_caption},
                            {"fieldCaption": field_caption, "function": "COUNT"}
                        ],
                        "filters": [
                            {
                                "field": {"fieldCaption": field_caption},
                                "filterType": "TOP",
                                "howMany": 100,
                                "direction": "TOP",
                                "fieldToMeasure": {
                                    "fieldCaption": field_caption,
                                    "function": "COUNT"
                                }
                            }
                        ]
                    },
                    "options": {"returnFormat": "OBJECTS", "disaggregate": False}
                }
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Tableau-Auth": self.auth_token
            }
            
            response = await self._client.post(
                query_url,
                json=query_payload,
                headers=headers,
                timeout=self.timeout,
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.debug(f"Statistics query response for {field_caption}: {json.dumps(result, indent=2)[:500]}")
            
            # Parse results - VizQL returns data in "data" array
            if "data" in result and len(result["data"]) > 0:
                first_row = result["data"][0]
                
                if not is_measure:
                    # For dimensions: parse value_counts from aggregated query response
                    value_counts = []
                    count_key = None
                    field_key = None
                    
                    # Parse value_counts from aggregated query (already sorted by count desc)
                    if len(result["data"]) > 0:
                        # Find the COUNT key and field key in first row
                        first_row = result["data"][0]
                        if isinstance(first_row, dict):
                            field_caption_lower = field_caption.lower()
                            for key in first_row.keys():
                                key_lower = key.lower()
                                # COUNT key: contains "count" and may contain field caption
                                if "count" in key_lower:
                                    if count_key is None:  # Take first COUNT key found
                                        count_key = key
                                # Field key: matches field caption (exact or contains)
                                elif field_caption_lower == key_lower or field_caption_lower in key_lower:
                                    if field_key is None:
                                        field_key = key
                            
                            # Fallback: if field_key not found, try first non-count key
                            if not field_key and len(first_row) > 0:
                                for key in first_row.keys():
                                    if "count" not in key.lower():
                                        field_key = key
                                        break
                            
                            # Extract value_counts from all rows
                            for row in result["data"]:
                                if isinstance(row, dict):
                                    # Try field_key first, then fallback to first non-count key
                                    value = None
                                    if field_key:
                                        value = row.get(field_key)
                                    else:
                                        # Fallback: find first non-count key
                                        for k, v in row.items():
                                            if "count" not in k.lower():
                                                value = v
                                                break
                                    
                                    count = None
                                    if count_key:
                                        count = row.get(count_key)
                                    else:
                                        # Fallback: find first count key
                                        for k, v in row.items():
                                            if "count" in k.lower():
                                                count = v
                                                break
                                    
                                    if value is not None and count is not None:
                                        try:
                                            count_int = int(count) if isinstance(count, (int, float)) else int(str(count))
                                            value_counts.append({"value": str(value), "count": count_int})
                                        except (ValueError, TypeError):
                                            pass
                    
                    stats["value_counts"] = value_counts  # Up to 100, already sorted by count desc
                    # Derive sample_values from top 10 value_counts
                    stats["sample_values"] = [vc["value"] for vc in value_counts[:10]]
                    
                    # Get cardinality using a separate COUNTD query (aggregated, not disaggregated)
                    # This ensures we get the total distinct count, not per-row counts
                    try:
                        countd_query = {
                            "datasource": {"datasourceLuid": datasource_id},
                            "query": {
                                "fields": [{"fieldCaption": field_caption, "function": "COUNTD"}]
                            },
                            "options": {"returnFormat": "OBJECTS", "disaggregate": False}
                        }
                        
                        countd_response = await self._client.post(
                            query_url,
                            json=countd_query,
                            headers=headers,
                            timeout=self.timeout,
                        )
                        countd_response.raise_for_status()
                        countd_result = countd_response.json()
                        
                        logger.debug(f"COUNTD query response for {field_caption}: {json.dumps(countd_result, indent=2)[:500]}")
                        
                        if "data" in countd_result and len(countd_result["data"]) > 0:
                            first_row = countd_result["data"][0]
                            if isinstance(first_row, dict):
                                # COUNTD result should be in the first row, first value
                                # Key might be something like "COUNTD(Field Name)" or just the value
                                for key, value in first_row.items():
                                    try:
                                        # Try to parse as number
                                        if isinstance(value, (int, float)) and value >= 0:
                                            stats["cardinality"] = int(value)
                                            logger.debug(f"Found cardinality for {field_caption}: {stats['cardinality']}")
                                            break
                                        # Also try string values that look like numbers
                                        elif isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit():
                                            num_val = float(value)
                                            if num_val >= 0:
                                                stats["cardinality"] = int(num_val)
                                                logger.debug(f"Found cardinality (from string) for {field_caption}: {stats['cardinality']}")
                                                break
                                    except (ValueError, TypeError):
                                        pass
                                
                                # If still not found, try first value in dict regardless of key
                                if stats["cardinality"] is None and len(first_row) > 0:
                                    first_value = list(first_row.values())[0]
                                    try:
                                        if isinstance(first_value, (int, float)) and first_value >= 0:
                                            stats["cardinality"] = int(first_value)
                                            logger.debug(f"Found cardinality (first value) for {field_caption}: {stats['cardinality']}")
                                    except (ValueError, TypeError):
                                        pass
                    except Exception as e:
                        logger.debug(f"Could not get cardinality via separate query for {field_caption}: {e}")
                
                else:
                    # For measures: extract min/max/median from aggregated results
                    if data_type in ["INTEGER", "REAL", "DOUBLE", "FLOAT"]:
                        min_val = None
                        max_val = None
                        median_val = None
                        
                        # Results might be in first row with MIN/MAX/MEDIAN as keys
                        if isinstance(first_row, dict):
                            for key, value in first_row.items():
                                key_lower = key.lower()
                                if "min" in key_lower and "median" not in key_lower and value is not None:
                                    try:
                                        min_val = float(value) if value != "" else None
                                    except (ValueError, TypeError):
                                        pass
                                elif "max" in key_lower and value is not None:
                                    try:
                                        max_val = float(value) if value != "" else None
                                    except (ValueError, TypeError):
                                        pass
                                elif "median" in key_lower and value is not None:
                                    try:
                                        median_val = float(value) if value != "" else None
                                    except (ValueError, TypeError):
                                        pass
                        
                        stats["min"] = min_val
                        stats["max"] = max_val
                        stats["median"] = median_val
                        
                        # Get null percentage: try Number of Records to get total_rows
                        # null_percentage = (total_rows - non_null_count) / total_rows * 100
                        # non_null_count = COUNT(field) from measure query
                        non_null_count = None
                        # Extract COUNT from measure query result
                        if isinstance(first_row, dict):
                            for key, value in first_row.items():
                                if "count" in key.lower() and "countd" not in key.lower():
                                    try:
                                        non_null_count = int(value) if isinstance(value, (int, float)) else int(str(value))
                                        break
                                    except (ValueError, TypeError):
                                        pass
                        
                        if non_null_count is not None:
                            try:
                                # Try to get total_rows from Number of Records
                                number_of_records_query = {
                                    "datasource": {"datasourceLuid": datasource_id},
                                    "query": {
                                        "fields": [
                                            {"fieldCaption": "Number of Records", "function": "SUM"}
                                        ]
                                    },
                                    "options": {"returnFormat": "OBJECTS", "disaggregate": False}
                                }
                                
                                records_response = await self._client.post(
                                    query_url,
                                    json=number_of_records_query,
                                    headers=headers,
                                    timeout=self.timeout,
                                )
                                records_response.raise_for_status()
                                records_result = records_response.json()
                                
                                if "data" in records_result and len(records_result["data"]) > 0:
                                    records_row = records_result["data"][0]
                                    if isinstance(records_row, dict):
                                        total_rows = None
                                        for key, value in records_row.items():
                                            if "sum" in key.lower() or "number" in key.lower():
                                                try:
                                                    total_rows = int(value) if isinstance(value, (int, float)) else int(str(value))
                                                    break
                                                except (ValueError, TypeError):
                                                    pass
                                        
                                        if total_rows and total_rows > 0:
                                            null_count = total_rows - non_null_count
                                            stats["null_percentage"] = (null_count / total_rows) * 100
                                            logger.debug(f"Calculated null_percentage for {field_caption}: {stats['null_percentage']:.2f}%")
                            except Exception as e:
                                logger.debug(f"Could not get null percentage for {field_caption} (Number of Records not available): {e}")
            
        except Exception as e:
            logger.debug(f"Could not get statistics for field {field_caption}: {e}")
            # Don't raise - return partial stats
        
        logger.debug(f"Statistics for {field_caption}: {stats}")
        return stats

    async def list_supported_functions(self, datasource_id: str) -> List[Dict[str, Any]]:
        """
        List supported Tableau functions for a datasource.
        
        Uses the /list-supported-functions endpoint to get datasource-specific
        function support information.
        
        Args:
            datasource_id: Datasource LUID
            
        Returns:
            List of SupportedFunction objects with name and overloads
            
        Raises:
            TableauAPIError: If API request fails
        """
        await self._ensure_authenticated()
        
        # VizQL Data Service API base URL
        # Note: urljoin replaces path if second arg starts with '/', so we need to construct manually
        server_base = self.server_url.rstrip('/')
        functions_url = f"{server_base}/api/v1/vizql-data-service/list-supported-functions"
        
        # Request payload
        payload = {
            "datasource": {
                "datasourceLuid": datasource_id
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Tableau-Auth": self.auth_token
        }
        
        try:
            logger.info(f"Requesting supported functions for datasource {datasource_id}")
            response = await self._client.post(
                functions_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Result is an array of SupportedFunction objects
            logger.info(f"Successfully retrieved {len(result)} supported functions")
            return result if isinstance(result, list) else []
            
        except httpx.HTTPStatusError as e:
            logger.error(f"VizQL functions API error: {e.response.status_code} - {e.response.text}")
            raise TableauAPIError(f"Failed to list supported functions: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"Error listing supported functions: {e}")
            raise TableauAPIError(f"Error listing supported functions: {str(e)}")
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
