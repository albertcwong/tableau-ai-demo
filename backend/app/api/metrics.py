"""Metrics API endpoints."""
from fastapi import APIRouter
from app.services.metrics import get_metrics
from app.services.cache import get_cache

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/agents")
async def get_agent_metrics():
    """Get agent performance metrics."""
    metrics = get_metrics()
    return metrics.get_summary()


@router.get("/cache")
async def get_cache_stats():
    """Get cache statistics."""
    cache = get_cache()
    return cache.get_stats()


@router.post("/cache/clear")
async def clear_cache():
    """Clear all cache entries."""
    cache = get_cache()
    cache.clear()
    return {"message": "Cache cleared"}


@router.post("/metrics/reset")
async def reset_metrics():
    """Reset all metrics."""
    metrics = get_metrics()
    metrics.reset()
    return {"message": "Metrics reset"}
