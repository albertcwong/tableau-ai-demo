"""Encryption service for Tableau Personal Access Token storage."""
import base64
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_fernet_key() -> bytes:
    """Get or derive Fernet encryption key."""
    if settings.TABLEAU_PAT_ENCRYPTION_KEY:
        try:
            # TABLEAU_PAT_ENCRYPTION_KEY should be a base64-encoded Fernet key (32 bytes, base64 = 44 chars)
            key_str = settings.TABLEAU_PAT_ENCRYPTION_KEY
            if isinstance(key_str, str):
                # Try to decode as base64 first (if it's already base64-encoded)
                try:
                    decoded = base64.urlsafe_b64decode(key_str)
                    if len(decoded) == 32:
                        # Valid Fernet key
                        return base64.urlsafe_b64encode(decoded)
                    else:
                        logger.warning(f"TABLEAU_PAT_ENCRYPTION_KEY decoded to {len(decoded)} bytes, expected 32")
                except Exception:
                    # Not base64, treat as raw string and encode
                    pass
                return key_str.encode()
            else:
                return key_str
        except Exception as e:
            logger.error(f"Invalid TABLEAU_PAT_ENCRYPTION_KEY: {e}")
    # Derive key from SECRET_KEY if no dedicated key configured
    secret = (settings.SECRET_KEY or "default-secret").encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"tableau_pat_salt",
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret))
    return key


def encrypt_pat(pat_secret: str) -> str:
    """Encrypt PAT secret for storage."""
    try:
        cipher = Fernet(_get_fernet_key())
        encrypted = cipher.encrypt(pat_secret.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Failed to encrypt PAT: {e}")
        raise ValueError(f"PAT encryption failed: {e}") from e


def decrypt_pat(encrypted_secret: str) -> str:
    """Decrypt PAT secret from storage."""
    try:
        cipher = Fernet(_get_fernet_key())
        decrypted = cipher.decrypt(encrypted_secret.encode())
        return decrypted.decode()
    except InvalidToken as e:
        logger.error(
            f"Failed to decrypt PAT: Invalid token. "
            f"This usually means the encryption key changed (SECRET_KEY or TABLEAU_PAT_ENCRYPTION_KEY). "
            f"Error: {e}"
        )
        raise ValueError(
            "Failed to decrypt stored PAT. The encryption key may have changed. "
            "If SECRET_KEY or TABLEAU_PAT_ENCRYPTION_KEY was modified, existing PATs cannot be decrypted. "
            "Please reconfigure your PATs."
        ) from e
    except Exception as e:
        logger.error(f"Failed to decrypt PAT: {e}")
        raise ValueError(f"PAT decryption failed: {e}") from e


def encrypt_secret(secret: str) -> str:
    """Encrypt secret for storage (PAT, EAS client secret, etc.)."""
    return encrypt_pat(secret)


def decrypt_secret(encrypted_secret: str) -> str:
    """Decrypt secret from storage."""
    return decrypt_pat(encrypted_secret)
