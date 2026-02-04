"""Executor node for executing VizQL queries."""
import logging
from typing import Dict, Any

from app.services.agents.vizql.state import VizQLAgentState
from app.services.tableau.client import TableauClient, TableauAPIError
from app.services.retry import retry_with_backoff, RetryConfig
from app.services.metrics import track_node_execution
from app.services.cache import get_cache
from app.services.query_optimizer import simplify_query_for_large_dataset

logger = logging.getLogger(__name__)


async def _execute_query_with_retry(tableau_client: TableauClient, query: Dict[str, Any]) -> Dict[str, Any]:
    """Execute query with retry logic and graceful degradation."""
    # Check cache first
    cache = get_cache()
    import json
    query_key = f"query_result:{json.dumps(query, sort_keys=True)}"
    cached_result = cache.get(query_key)
    
    if cached_result:
        logger.info("Using cached query result")
        return cached_result
    
    # Retry configuration for API calls
    retry_config = RetryConfig(
        max_attempts=3,
        initial_delay=1.0,
        max_delay=10.0,
        exponential_base=2.0
    )
    
    # Execute with retry
    try:
        results = await retry_with_backoff(
            tableau_client.execute_vds_query,
            query,
            config=retry_config,
            retryable_exceptions=(TableauAPIError, TimeoutError, ConnectionError)
        )
        
        # Cache successful results for 5 minutes
        cache.set(query_key, results, ttl_seconds=300)
        
        return results
    except Exception as e:
        logger.error(f"Query execution failed after retries: {e}")
        
        # Graceful degradation: try simplified query
        try:
            logger.info("Attempting graceful degradation with simplified query")
            simplified_query = simplify_query_for_large_dataset(query, estimated_rows=100000)
            simplified_key = f"query_result:{json.dumps(simplified_query, sort_keys=True)}"
            
            # Check cache for simplified query
            cached_simplified = cache.get(simplified_key)
            if cached_simplified:
                logger.info("Using cached simplified query result")
                return cached_simplified
            
            # Try simplified query with single retry
            simple_retry_config = RetryConfig(max_attempts=1, initial_delay=1.0)
            results = await retry_with_backoff(
                tableau_client.execute_vds_query,
                simplified_query,
                config=simple_retry_config,
                retryable_exceptions=(TableauAPIError, TimeoutError, ConnectionError)
            )
            
            logger.info("Simplified query executed successfully")
            cache.set(simplified_key, results, ttl_seconds=300)
            return results
            
        except Exception as degrade_error:
            logger.error(f"Graceful degradation also failed: {degrade_error}")
            raise e  # Raise original error


@track_node_execution("vizql", "executor")
async def execute_query_node(state: VizQLAgentState) -> Dict[str, Any]:
    """
    Execute validated VizQL query.
    
    This is an "Act" step in ReAct.
    Uses retry logic and caching for reliability.
    """
    query = state.get("query_draft")
    
    if not query:
        logger.error("No query to execute")
        return {
            **state,
            "execution_error": "No query to execute",
            "error": "No query to execute"
        }
    
    try:
        # Initialize Tableau client
        tableau_client = TableauClient()
        
        # Execute using VizQL Data Service API
        datasource_id = query.get("datasource", {}).get("datasourceLuid")
        
        if not datasource_id:
            logger.error("Missing datasource LUID in query")
            return {
                **state,
                "execution_error": "Missing datasource LUID in query",
                "error": "Missing datasource LUID in query"
            }
        
        logger.info(f"Executing query for datasource: {datasource_id}")
        
        # Optimize query for large datasets
        # Check schema to estimate size (if available)
        schema = state.get("schema")
        estimated_rows = None
        if schema:
            # Rough estimate based on schema complexity
            # In production, you might have row count metadata
            estimated_rows = 10000  # Default estimate
        
        optimized_query = simplify_query_for_large_dataset(query, estimated_rows)
        if optimized_query != query:
            logger.info("Query optimized for large dataset")
        
        # Execute query with retry and caching
        results = await _execute_query_with_retry(tableau_client, optimized_query)
        
        row_count = results.get('row_count', 0)
        logger.info(f"Query executed successfully. Retrieved {row_count} rows")
        
        return {
            **state,
            "query_results": results,
            "execution_error": None,
            "current_thought": f"Query executed successfully. Retrieved {row_count} rows",
            "tool_calls": state.get("tool_calls", []) + [{
                "tool": "execute_vds_query",
                "args": {"query": query},
                "result": "success",
                "row_count": row_count
            }]
        }
    except Exception as e:
        logger.error(f"Error executing query: {e}", exc_info=True)
        
        # Try to get cached result as fallback
        try:
            cache = get_cache()
            import json
            query_key = f"query_result:{json.dumps(query, sort_keys=True)}"
            cached_result = cache.get(query_key)
            
            if cached_result:
                logger.info("Using cached result as fallback after execution error")
                return {
                    **state,
                    "query_results": cached_result,
                    "execution_error": f"Execution failed but using cached result: {str(e)}",
                    "current_thought": f"Query execution failed, using cached result with {cached_result.get('row_count', 0)} rows"
                }
        except Exception as cache_error:
            logger.warning(f"Failed to get cached result: {cache_error}")
        return {
            **state,
            "execution_error": str(e),
            "error": f"Query execution failed: {str(e)}",
            "tool_calls": state.get("tool_calls", []) + [{
                "tool": "execute_vds_query",
                "args": {"query": query},
                "result": "error",
                "error": str(e)
            }]
        }
