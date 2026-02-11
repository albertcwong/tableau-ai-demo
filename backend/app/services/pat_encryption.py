"""Encryption service for Tableau Personal Access Token storage."""
import base64
import logging
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_fernet_key() -> bytes:
    """Get or derive Fernet encryption key."""
    if settings.TABLEAU_PAT_ENCRYPTION_KEY:
        try:
            return settings.TABLEAU_PAT_ENCRYPTION_KEY.encode() if isinstance(
                settings.TABLEAU_PAT_ENCRYPTION_KEY, str
            ) else settings.TABLEAU_PAT_ENCRYPTION_KEY
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
    cipher = Fernet(_get_fernet_key())
    encrypted = cipher.encrypt(pat_secret.encode())
    return encrypted.decode()


def decrypt_pat(encrypted_secret: str) -> str:
    """Decrypt PAT secret from storage."""
    cipher = Fernet(_get_fernet_key())
    decrypted = cipher.decrypt(encrypted_secret.encode())
    return decrypted.decode()
