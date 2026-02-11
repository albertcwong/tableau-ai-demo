"""Get schema node - fetch and cache datasource metadata."""
import logging
from typing import Dict, Any

from app.services.agents.vizql_controlled.state import VizQLGraphState
from app.services.tableau.client import TableauClient, TableauClientError
from app.services.agents.vizql.schema_enrichment import SchemaEnrichmentService

logger = logging.getLogger(__name__)


async def get_schema_node(state: VizQLGraphState) -> Dict[str, Any]:
    """
    Fetch and cache datasource metadata.
    
    Operations:
    1. Check if schema already in state (from previous node)
    2. If not, fetch from Tableau API
    3. Enrich with pre-computed statistics
    4. Cache for session
    
    Duration: 500-2000ms (with caching: < 50ms)
    """
    datasource_id = state.get("datasource_id")
    site_id = state.get("site_id")
    
    if not datasource_id:
        return {
            **state,
            "schema_error": "Missing datasource_id",
            "current_thought": "Error: Missing datasource ID"
        }
    
    # Check if schema already in state
    if state.get("schema") and state.get("metadata_stats"):
        logger.info("Schema already in state, skipping fetch")
        return {
            **state,
            "current_thought": "Using cached schema..."
        }
    
    logger.info(f"Fetching schema for datasource: {datasource_id}")
    
    try:
        tableau_client = state.get("tableau_client") or TableauClient()
        schema_service = SchemaEnrichmentService(tableau_client)
        
        # Fetch enriched schema with statistics
        enriched_schema = await schema_service.enrich_datasource_schema(
            datasource_id=datasource_id,
            force_refresh=False,
            include_statistics=True
        )
        
        # Extract metadata stats (cardinality, samples, min/max per field)
        metadata_stats = {}
        for field in enriched_schema.get("fields", []):
            field_caption = field.get("fieldCaption")
            if field_caption:
                metadata_stats[field_caption] = {
                    "cardinality": field.get("cardinality"),
                    "samples": field.get("sample_values", [])[:10],  # Limit samples
                    "min": field.get("min"),
                    "max": field.get("max"),
                    "null_percentage": field.get("null_percentage")
                }
        
        logger.info(f"Schema fetched: {len(enriched_schema.get('fields', []))} fields")
        
        return {
            **state,
            "schema": enriched_schema,
            "metadata_stats": metadata_stats,
            "current_thought": "Fetching datasource schema..."
        }
        
    except TableauClientError as e:
        error_msg = f"Tableau API error: {str(e)}"
        logger.error(error_msg)
        return {
            **state,
            "schema_error": error_msg,
            "current_thought": f"Error: {error_msg}"
        }
    except Exception as e:
        error_msg = f"Failed to fetch schema: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            **state,
            "schema_error": error_msg,
            "current_thought": f"Error: {error_msg}"
        }