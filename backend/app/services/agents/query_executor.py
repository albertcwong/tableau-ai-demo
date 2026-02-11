"""Shared query execution with retry and caching."""
import json
import logging
from typing import Dict, Any

from app.services.tableau.client import TableauClient, TableauAPIError
from app.services.retry import retry_with_backoff, RetryConfig
from app.services.cache import get_cache
from app.services.query_optimizer import simplify_query_for_large_dataset

logger = logging.getLogger(__name__)


async def execute_query_with_retry(tableau_client: TableauClient, query: Dict[str, Any]) -> Dict[str, Any]:
    """Execute query with retry logic and graceful degradation."""
    cache = get_cache()
    query_key = f"query_result:{json.dumps(query, sort_keys=True)}"
    cached_result = cache.get(query_key)
    if cached_result:
        logger.info("Using cached query result")
        return cached_result

    retry_config = RetryConfig(
        max_attempts=3,
        initial_delay=1.0,
        max_delay=10.0,
        exponential_base=2.0,
    )
    try:
        results = await retry_with_backoff(
            tableau_client.execute_vds_query,
            query,
            config=retry_config,
            retryable_exceptions=(TableauAPIError, TimeoutError, ConnectionError),
        )
        cache.set(query_key, results, ttl_seconds=300)
        return results
    except Exception as e:
        logger.error(f"Query execution failed after retries: {e}")
        try:
            logger.info("Attempting graceful degradation with simplified query")
            simplified_query = simplify_query_for_large_dataset(query, estimated_rows=100000)
            simplified_key = f"query_result:{json.dumps(simplified_query, sort_keys=True)}"
            cached_simplified = cache.get(simplified_key)
            if cached_simplified:
                logger.info("Using cached simplified query result")
                return cached_simplified
            simple_retry_config = RetryConfig(max_attempts=1, initial_delay=1.0)
            results = await retry_with_backoff(
                tableau_client.execute_vds_query,
                simplified_query,
                config=simple_retry_config,
                retryable_exceptions=(TableauAPIError, TimeoutError, ConnectionError),
            )
            logger.info("Simplified query executed successfully")
            cache.set(simplified_key, results, ttl_seconds=300)
            return results
        except Exception as degrade_error:
            logger.error(f"Graceful degradation also failed: {degrade_error}")
            raise e
