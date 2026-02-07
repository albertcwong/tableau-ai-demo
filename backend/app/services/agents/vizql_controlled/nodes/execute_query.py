"""Execute query node - execute VizQL query against Tableau."""
import logging
from typing import Dict, Any
import httpx

from app.services.agents.vizql_controlled.state import VizQLGraphState
from app.services.tableau.client import TableauClient, TableauClientError, TableauAPIError
from app.services.retry import retry_with_backoff, RetryConfig

logger = logging.getLogger(__name__)


async def execute_query_node(state: VizQLGraphState) -> Dict[str, Any]:
    """
    Execute VizQL query against Tableau.
    
    Operations:
    1. Send query to Tableau VizQL Data Service
    2. Parse response
    3. Extract columns, data, row_count
    
    Duration: 500-10000ms (depends on query complexity)
    """
    validated_query = state.get("validated_query")
    attempt = state.get("attempt", 1)
    
    if not validated_query:
        return {
            **state,
            "execution_status": "failed",
            "execution_errors": ["No validated query to execute"],
            "attempt": attempt + 1,
            "current_thought": "Error: No query to execute"
        }
    
    datasource_id = validated_query.get("datasource", {}).get("datasourceLuid")
    if not datasource_id:
        return {
            **state,
            "execution_status": "failed",
            "execution_errors": ["Missing datasource LUID in query"],
            "attempt": attempt + 1,
            "current_thought": "Error: Missing datasource ID"
        }
    
    logger.info(f"Executing query for datasource: {datasource_id} (attempt {attempt})")
    
    try:
        tableau_client = TableauClient()
        
        # Execute query with retry
        retry_config = RetryConfig(
            max_attempts=2,  # Quick retry for transient errors
            initial_delay=1.0,
            max_delay=5.0,
            exponential_base=2.0
        )
        
        try:
            # Log the query structure before execution for debugging
            logger.info(f"Executing query structure: datasource={validated_query.get('datasource')}, "
                       f"has_query={bool(validated_query.get('query'))}, "
                       f"has_options={bool(validated_query.get('options'))}")
            
            results = await retry_with_backoff(
                tableau_client.execute_vds_query,
                validated_query,
                config=retry_config,
                retryable_exceptions=(TableauAPIError, TimeoutError, ConnectionError)
            )
        except TimeoutError:
            return {
                **state,
                "execution_status": "failed",
                "execution_errors": ["Query timeout (>30s)"],
                "timeout_error": "Query execution timed out",
                "current_thought": "Error: Query timeout"
            }
        except (TableauClientError, TableauAPIError, httpx.HTTPStatusError) as e:
            # Extract detailed error message
            # TableauAPIError already includes detailed message from Tableau server
            error_msg = str(e)
            
            # For httpx.HTTPStatusError, try to extract more details
            if isinstance(e, httpx.HTTPStatusError):
                try:
                    if e.response:
                        error_detail = e.response.text
                        if error_detail and error_detail not in error_msg:
                            error_msg = f"HTTP {e.response.status_code}: {error_detail[:500]}"
                        elif not error_detail:
                            error_msg = f"HTTP {e.response.status_code}: {error_msg}"
                except:
                    pass
            elif isinstance(e, TableauAPIError):
                # TableauAPIError already contains detailed message from Tableau server
                # Just use the error message as-is
                pass
            elif hasattr(e, 'response') and hasattr(e.response, 'text'):
                try:
                    error_detail = e.response.text
                    if error_detail and error_detail not in error_msg:
                        error_msg = f"{error_msg}: {error_detail[:500]}"
                except:
                    pass
            
            logger.error(f"Tableau API error: {error_msg}")
            logger.error(f"Query that failed: {validated_query}")
            
            # Check if it's an auth error
            if "auth" in error_msg.lower() or "unauthorized" in error_msg.lower() or "401" in error_msg:
                return {
                    **state,
                    "execution_status": "failed",
                    "execution_errors": [error_msg],
                    "auth_error": error_msg,
                    "current_thought": "Error: Authentication failed"
                }
            # Check if it's a 400 (bad request) - likely query format issue
            if "400" in error_msg or "bad request" in error_msg.lower():
                return {
                    **state,
                    "execution_status": "failed",
                    "execution_errors": [f"Invalid query format: {error_msg}"],
                    "attempt": attempt + 1,
                    "current_thought": f"Query format error: {error_msg}"
                }
            # Otherwise treat as syntax error (can retry)
            return {
                **state,
                "execution_status": "failed",
                "execution_errors": [error_msg],
                "attempt": attempt + 1,
                "current_thought": f"Execution failed: {error_msg}"
            }
        
        # Extract data in expected format
        raw_data = {
            "columns": results.get("columns", []),
            "data": results.get("data", []),
            "row_count": results.get("row_count", 0)
        }
        
        logger.info(f"Query executed successfully. Retrieved {raw_data['row_count']} rows")
        
        return {
            **state,
            "raw_data": raw_data,
            "execution_status": "success",
            "current_thought": f"Executing query... Retrieved {raw_data['row_count']} rows"
        }
        
    except Exception as e:
        error_msg = f"Unexpected error executing query: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            **state,
            "execution_status": "failed",
            "execution_errors": [error_msg],
            "attempt": attempt + 1,
            "current_thought": f"Error: {error_msg}"
        }