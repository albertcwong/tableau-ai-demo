"""Build Tableau OAuth 2.0 Trust JWTs when Auth0 cannot set aud/sub (restricted claims)."""
import base64
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

logger = logging.getLogger(__name__)

TABLEAU_SCOPES = ["tableau:content:read", "tableau:views:embed"]


def _load_private_key(key_path: Optional[str] = None, key_content: Optional[str] = None) -> Optional[RSAPrivateKey]:
    """Load RSA private key from PEM file or content."""
    if key_content:
        try:
            data = key_content.encode()
            key = serialization.load_pem_private_key(data, password=None, backend=default_backend())
            return key if isinstance(key, RSAPrivateKey) else None
        except Exception as e:
            logger.error("Failed to load EAS JWT key from content: %s", e)
            return None
    if key_path:
        path = Path(key_path)
        if not path.exists():
            logger.warning("EAS JWT key path does not exist: %s", key_path)
            return None
        try:
            data = path.read_bytes()
            key = serialization.load_pem_private_key(data, password=None, backend=default_backend())
            return key if isinstance(key, RSAPrivateKey) else None
        except Exception as e:
            logger.error("Failed to load EAS JWT key: %s", e)
            return None
    return None


def _int_to_b64(n: int) -> str:
    """Encode int to base64url (no padding)."""
    by = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(by).rstrip(b"=").decode("ascii")


def get_jwks(key_path: Optional[str] = None, key_content: Optional[str] = None, kid: str = "tableau-eas-1") -> Optional[dict]:
    """Return JWKS for our signing key so Tableau can validate JWTs."""
    key = _load_private_key(key_path=key_path, key_content=key_content)
    if not key:
        return None
    pub = key.public_key()
    return {
        "keys": [{
            "kty": "RSA",
            "kid": kid,
            "use": "sig",
            "alg": "RS256",
            "n": _int_to_b64(pub.public_numbers().n),
            "e": _int_to_b64(pub.public_numbers().e),
        }]
    }


def build_tableau_jwt(
    issuer: str,
    sub: str,
    key_path: Optional[str] = None,
    key_content: Optional[str] = None,
    kid: str = "tableau-eas-1",
    exp_minutes: int = 10,
    aud: str = "tableau",
) -> Optional[str]:
    """Build a JWT for Tableau OAuth 2.0 Trust with correct aud and sub."""
    key = _load_private_key(key_path=key_path, key_content=key_content)
    if not key:
        return None
    now = datetime.now(timezone.utc)
    payload = {
        "iss": issuer.rstrip("/"),
        "aud": aud,
        "sub": sub,
        "scp": TABLEAU_SCOPES,
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=exp_minutes)).timestamp()),
    }
    try:
        token = jwt.encode(
            payload,
            key,
            algorithm="RS256",
            headers={"kid": kid, "typ": "JWT"},
        )
        return token if isinstance(token, str) else token.decode()
    except Exception as e:
        logger.error("Failed to build Tableau JWT: %s", e)
        return None
