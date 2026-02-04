"""Redis cache configuration."""
import time
import redis
from redis.exceptions import ConnectionError, TimeoutError
from redis.connection import ConnectionPool
from app.core.config import settings

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds


def create_redis_client_with_retry():
    """Create Redis client with retry logic for connection failures."""
    retries = 0
    while retries < MAX_RETRIES:
        try:
            pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=settings.REDIS_POOL_SIZE,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            client = redis.Redis(
                connection_pool=pool,
                decode_responses=False,  # Return bytes for compatibility
            )
            # Test connection
            client.ping()
            return client
        except (ConnectionError, TimeoutError) as e:
            retries += 1
            if retries >= MAX_RETRIES:
                raise ConnectionError(
                    f"Failed to connect to Redis after {MAX_RETRIES} retries: {e}"
                )
            time.sleep(RETRY_DELAY * retries)  # Exponential backoff
    raise ConnectionError("Failed to create Redis client")


# Create Redis client with retry logic
try:
    redis_client = create_redis_client_with_retry()
except ConnectionError:
    # Fallback: create client without retry (for development)
    redis_client = redis.from_url(
        settings.REDIS_URL,
        decode_responses=False,
        socket_connect_timeout=5,
        socket_timeout=5,
    )


def get_cache():
    """Dependency for getting Redis cache client."""
    return redis_client


def check_cache_health() -> bool:
    """Check Redis cache connection health."""
    try:
        redis_client.ping()
        return True
    except Exception:
        return False
