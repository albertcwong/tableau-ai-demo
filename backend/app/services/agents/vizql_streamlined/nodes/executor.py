"""Executor node for executing VizQL queries."""
import logging
from typing import Dict, Any
from datetime import datetime

from langchain_core.runnables.config import ensure_config

from app.services.agents.vizql_streamlined.state import StreamlinedVizQLState
from app.services.agents.query_executor import execute_query_with_retry
from app.services.tableau.client import TableauClient, TableauAPIError
from app.services.metrics import track_node_execution
from app.services.cache import get_cache
from app.services.query_optimizer import simplify_query_for_large_dataset

logger = logging.getLogger(__name__)


@track_node_execution("vizql_streamlined", "executor")
async def execute_query_node(state: StreamlinedVizQLState) -> Dict[str, Any]:
    """
    Execute validated VizQL query.
    
    Uses retry logic and caching for reliability.
    """
    query = state.get("query_draft")
    
    if not query:
        logger.error("No query to execute")
        execution_attempt = state.get("execution_attempt", 1)
        return {
            **state,
            "execution_status": "failed",
            "execution_errors": ["No query to execute"],
            "execution_attempt": execution_attempt,
            "error": "No query to execute"
        }
    
    try:
        # Tableau client from config (not in state - not serializable)
        config = ensure_config()
        tableau_client = config.get("configurable", {}).get("tableau_client") or TableauClient()
        
        # Execute using VizQL Data Service API
        datasource_id = query.get("datasource", {}).get("datasourceLuid")
        
        if not datasource_id:
            logger.error("Missing datasource LUID in query")
            execution_attempt = state.get("execution_attempt", 1)
            return {
                **state,
                "execution_status": "failed",
                "execution_errors": ["Missing datasource LUID in query"],
                "execution_attempt": execution_attempt,
                "error": "Missing datasource LUID in query"
            }
        
        logger.info(f"Executing query for datasource: {datasource_id}")
        
        # Optimize query for large datasets
        schema = state.get("schema")
        estimated_rows = None
        if schema:
            estimated_rows = 10000  # Default estimate
        
        optimized_query = simplify_query_for_large_dataset(query, estimated_rows)
        if optimized_query != query:
            logger.info("Query optimized for large dataset")
        
        # Track execution attempt
        execution_attempt = state.get("execution_attempt", 1)
        
        # Track execution attempt in reasoning steps
        reasoning_steps = state.get("reasoning_steps", [])
        reasoning_steps.append({
            "node": "execute_query",
            "timestamp": datetime.utcnow().isoformat(),
            "thought": f"Executing query for datasource: {datasource_id}",
            "execution_attempt": execution_attempt
        })
        
        # Execute query with retry and caching
        results = await execute_query_with_retry(tableau_client, optimized_query)
        
        row_count = results.get('row_count', 0)
        logger.info(f"Query executed successfully. Retrieved {row_count} rows")
        
        return {
            **state,
            "query_results": results,
            "execution_status": "success",
            "execution_errors": None,
            "execution_attempt": execution_attempt,
            "reasoning_steps": reasoning_steps,
            "current_thought": f"Query executed successfully. Retrieved {row_count} rows"
        }
    except Exception as e:
        logger.error(f"Error executing query: {e}", exc_info=True)
        
        # Track execution attempt
        execution_attempt = state.get("execution_attempt", 1)
        
        # Track execution attempt in reasoning steps (even on failure)
        reasoning_steps = state.get("reasoning_steps", [])
        reasoning_steps.append({
            "node": "execute_query",
            "timestamp": datetime.utcnow().isoformat(),
            "thought": f"Query execution failed: {str(e)[:100]}",
            "execution_attempt": execution_attempt,
            "error": True
        })
        
        # Extract detailed error message
        error_message = str(e)
        # If it's a TableauAPIError, the message should already include Tableau server details
        # For httpx errors, try to extract more details
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            try:
                error_detail = e.response.text
                if error_detail and error_detail not in error_message:
                    error_message = f"{error_message}: {error_detail[:500]}"
            except Exception:
                pass
        
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
                    "execution_status": "success",
                    "execution_errors": [f"Execution failed but using cached result: {error_message}"],
                    "current_thought": f"Query execution failed, using cached result with {cached_result.get('row_count', 0)} rows"
                }
        except Exception as cache_error:
            logger.warning(f"Failed to get cached result: {cache_error}")
        
        return {
            **state,
            "execution_status": "failed",
            "execution_errors": [error_message],
            "execution_attempt": execution_attempt,
            "reasoning_steps": reasoning_steps,
            "error": f"Query execution failed: {error_message}"
        }
