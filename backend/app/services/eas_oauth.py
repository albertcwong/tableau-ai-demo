"""EAS OAuth 2.0 service for Tableau Connected Apps OAuth 2.0 Trust."""
import json
import logging
import secrets
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from app.services.pat_encryption import decrypt_secret

logger = logging.getLogger(__name__)

DEFAULT_SCOPES = "openid profile email"
OAUTH_STATE_TTL = 600  # 10 minutes


def _oauth_state_key(state: str) -> str:
    return f"oauth_state:{state}"


def store_oauth_state(state: str, config_id: int, user_id: int) -> None:
    """Store OAuth state in Redis for CSRF validation."""
    try:
        from app.core.cache import redis_client
        payload = json.dumps({"config_id": config_id, "user_id": user_id})
        key = _oauth_state_key(state)
        redis_client.setex(key, OAUTH_STATE_TTL, payload.encode())
    except Exception as e:
        logger.warning(f"Failed to store OAuth state (Redis): {e}")
        raise


def get_and_clear_oauth_state(state: str) -> Optional[tuple[int, int]]:
    """Get and delete OAuth state; return (config_id, user_id) or None."""
    try:
        from app.core.cache import redis_client
        key = _oauth_state_key(state)
        data = redis_client.get(key)
        redis_client.delete(key)
        if not data:
            return None
        obj = json.loads(data.decode())
        return (int(obj["config_id"]), int(obj["user_id"]))
    except Exception as e:
        logger.warning(f"Failed to get OAuth state: {e}")
        return None


async def _get_config_endpoints(config: Any) -> tuple[str, str]:
    """Get auth and token endpoints from config or discovery."""
    auth_endpoint = getattr(config, "eas_authorization_endpoint", None) or ""
    token_endpoint = getattr(config, "eas_token_endpoint", None) or ""
    if auth_endpoint and token_endpoint:
        return auth_endpoint, token_endpoint
    issuer = (getattr(config, "eas_issuer_url", None) or "").rstrip("/")
    if not issuer:
        raise ValueError("eas_issuer_url is required")
    discovery_url = f"{issuer}/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(discovery_url)
        resp.raise_for_status()
        data = resp.json()
        return data.get("authorization_endpoint", ""), data.get("token_endpoint", "")


def generate_state() -> str:
    """Generate cryptographically random state for OAuth CSRF protection."""
    return secrets.token_urlsafe(32)


async def get_authorization_url(
    config: "TableauServerConfig",
    redirect_uri: str,
    state: str,
) -> str:
    """Build EAS OAuth authorize URL."""
    auth_endpoint, _ = await _get_config_endpoints(config)
    client_id = getattr(config, "eas_client_id", None) or ""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": DEFAULT_SCOPES,
        "state": state,
    }
    sub_claim = (getattr(config, "eas_sub_claim_field", None) or "email").strip()
    if sub_claim:
        params["sub_claim"] = sub_claim
    return f"{auth_endpoint}?{urlencode(params)}"


async def exchange_code_for_jwt(
    code: str,
    config: "TableauServerConfig",
    redirect_uri: str,
) -> str:
    """Exchange auth code for tokens; return id_token (JWT)."""
    _, token_endpoint = await _get_config_endpoints(config)
    logger.info("Token endpoint: %s", token_endpoint)
    client_id = getattr(config, "eas_client_id", None) or ""
    enc_secret = getattr(config, "eas_client_secret", None) or ""
    client_secret = decrypt_secret(enc_secret) if enc_secret else ""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        logger.info("Token response status=%d", resp.status_code)
        if resp.status_code >= 400:
            logger.error("Token exchange error: %s", resp.text)
        resp.raise_for_status()
        data = resp.json()
        jwt_token = data.get("id_token") or data.get("access_token")
        if not jwt_token:
            logger.error("Token response keys: %s", list(data.keys()))
            raise ValueError("EAS did not return id_token or JWT access_token")
        return jwt_token
