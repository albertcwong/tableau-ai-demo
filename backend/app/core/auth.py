"""Authentication utilities."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from app.core.config import settings

logger = logging.getLogger(__name__)

# Use bcrypt directly to avoid passlib initialization issues
# Bcrypt rounds (cost factor) - 12 is a good balance of security and performance
BCRYPT_ROUNDS = 12

# JWT settings
SECRET_KEY = getattr(settings, "SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    try:
        # bcrypt expects bytes
        password_bytes = plain_password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    if not password:
        raise ValueError("Password cannot be empty")
    
    # bcrypt has a 72 byte limit, so truncate if necessary
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        logger.warning(f"Password exceeds 72 bytes, truncating from {len(password_bytes)} bytes")
        password_bytes = password_bytes[:72]
    
    try:
        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(password_bytes, salt)
        # Return as string (bcrypt hash is ASCII-safe)
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error(f"Error hashing password: {e}")
        raise


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    logger.debug(f"Creating token with SECRET_KEY length: {len(SECRET_KEY)}, user_id: {data.get('sub')}")
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.debug(f"Token created successfully (length: {len(encoded_jwt)})")
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT access token."""
    logger.debug(f"Attempting to decode token with SECRET_KEY length: {len(SECRET_KEY)}")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.debug(f"Token decoded successfully: user_id={payload.get('sub')}, username={payload.get('username')}")
        return payload
    except JWTError as e:
        error_msg = str(e)
        error_type = type(e).__name__
        logger.warning(f"JWT decode error: {error_type}: {error_msg}")
        
        # Try to decode without verification to see what's in the token
        try:
            # python-jose requires key parameter even for unverified decode
            unverified = jwt.decode(token, SECRET_KEY, options={"verify_signature": False})
            logger.warning(f"Token content (unverified): user_id={unverified.get('sub')}, exp={unverified.get('exp')}, iat={unverified.get('iat')}")
            
            # Check if token is expired
            exp = unverified.get('exp')
            if exp:
                from datetime import datetime, timezone
                exp_time = datetime.fromtimestamp(exp, tz=timezone.utc)
                now = datetime.now(timezone.utc)
                if exp_time < now:
                    logger.warning(f"Token expired at {exp_time}, current time: {now}")
                else:
                    logger.warning(f"Token not expired (expires at {exp_time})")
            
            logger.warning(f"Current SECRET_KEY length: {len(SECRET_KEY)}, first 10 chars: {SECRET_KEY[:10]}...")
        except Exception as e2:
            logger.warning(f"Could not decode token even without verification: {e2}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error decoding token: {type(e).__name__}: {str(e)}")
        return None
