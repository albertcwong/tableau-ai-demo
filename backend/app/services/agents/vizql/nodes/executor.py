"""Executor node for executing VizQL queries."""
import logging
from typing import Dict, Any

from app.services.agents.vizql.state import VizQLAgentState
from app.services.agents.query_executor import execute_query_with_retry
from app.services.tableau.client import TableauClient, TableauAPIError
from app.services.metrics import track_node_execution
from app.services.cache import get_cache
from app.services.query_optimizer import simplify_query_for_large_dataset

logger = logging.getLogger(__name__)


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
        # Use state's tableau_client (user's selected config) or fallback to env
        tableau_client = state.get("tableau_client") or TableauClient()
        
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
        results = await execute_query_with_retry(tableau_client, optimized_query)
        
        row_count = results.get('row_count', 0)
        logger.info(f"Query executed successfully. Retrieved {row_count} rows")
        
        return {
            **state,
            "query_results": results,
            "execution_error": None,
            "execution_error_query": None,  # Clear failed query on success
            "tableau_error_message": None,  # Clear error message on success
            "error": None,  # Clear general error on success
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
                    "execution_error": f"Execution failed but using cached result: {error_message}",
                    "current_thought": f"Query execution failed, using cached result with {cached_result.get('row_count', 0)} rows"
                }
        except Exception as cache_error:
            logger.warning(f"Failed to get cached result: {cache_error}")
        # Extract detailed Tableau error message if available
        tableau_error = error_message
        if isinstance(e, TableauAPIError):
            # TableauAPIError already contains detailed message from Tableau server
            tableau_error = str(e)
        elif hasattr(e, 'response') and hasattr(e.response, 'text'):
            try:
                error_detail = e.response.text
                if error_detail:
                    tableau_error = error_detail[:1000]  # Limit length
            except Exception:
                pass
        
        return {
            **state,
            "execution_error": error_message,
            "execution_error_query": query,  # Store the query that failed
            "tableau_error_message": tableau_error,  # Store detailed Tableau error
            "error": f"Query execution failed: {error_message}",
            "tool_calls": state.get("tool_calls", []) + [{
                "tool": "execute_vds_query",
                "args": {"query": query},
                "result": "error",
                "error": error_message
            }]
        }
