"""Tests for Redis cache."""
from app.core.cache import redis_client


def test_redis_connection():
    """Test Redis connection."""
    assert redis_client.ping() is True


def test_redis_set_get():
    """Test Redis set and get operations."""
    redis_client.set("test_key", "test_value", ex=60)
    result = redis_client.get("test_key")
    assert result == b"test_value"
    # Cleanup
    redis_client.delete("test_key")
