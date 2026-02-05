"""Schema fetch node for retrieving datasource schema."""
import logging
from typing import Dict, Any

from app.services.agents.vizql.state import VizQLAgentState
from app.services.tableau.client import TableauClient
from app.services.agents.vizql.schema_enrichment import SchemaEnrichmentService
from app.services.cache import cached
from app.services.metrics import track_node_execution

logger = logging.getLogger(__name__)


@cached("schema", ttl_seconds=600)  # Cache schemas for 10 minutes
async def _fetch_schema_cached(datasource_id: str) -> Dict[str, Any]:
    """Cached schema fetch function (fallback to basic schema)."""
    tableau_client = TableauClient()
    return await tableau_client.get_datasource_schema(datasource_id)


@track_node_execution("vizql", "schema_fetch")
async def fetch_schema_node(state: VizQLAgentState) -> Dict[str, Any]:
    """
    Fetch datasource schema using Tableau API.
    
    Attempts to use enriched schema from SchemaEnrichmentService if available.
    Falls back to basic schema if enrichment fails or is unavailable.
    
    This is an "Act" step in ReAct.
    Uses caching to avoid repeated API calls.
    """
    try:
        datasource_ids = state.get("context_datasources", [])
        
        if not datasource_ids:
            logger.warning("No datasource in context for schema fetch")
            return {
                **state,
                "error": "No datasource in context. Please add a datasource first.",
                "schema": None
            }
        
        # Use first datasource
        datasource_id = datasource_ids[0]
        
        logger.info(f"Fetching schema for datasource: {datasource_id}")
        
        # Try to use enriched schema first (from cache if available)
        # Skip statistics to avoid slow API calls - we only need schema structure
        enriched_schema = None
        try:
            # Check cache directly first for fastest access (avoids creating TableauClient)
            from app.core.cache import redis_client
            import json
            cache_key = f"enriched_schema:{datasource_id}"
            
            try:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    if isinstance(cached_data, bytes):
                        cached_data = cached_data.decode('utf-8')
                    enriched_schema = json.loads(cached_data)
                    logger.info(
                        f"✓ Using cached enriched schema for {datasource_id}: "
                        f"{len(enriched_schema.get('fields', []))} fields "
                        f"({len(enriched_schema.get('measures', []))} measures, "
                        f"{len(enriched_schema.get('dimensions', []))} dimensions)"
                    )
            except Exception as cache_error:
                logger.debug(f"Cache check failed: {cache_error}, will fetch fresh")
            
            # If not in cache, fetch enriched schema (without statistics for speed)
            if not enriched_schema:
                logger.info(f"Enriched schema not in cache, fetching from API (without statistics)...")
                tableau_client = TableauClient()
                enrichment_service = SchemaEnrichmentService(tableau_client)
                enriched_schema = await enrichment_service.enrich_datasource_schema(
                    datasource_id,
                    force_refresh=False,
                    include_statistics=False  # Skip statistics to speed up schema fetch
                )
                logger.info(
                    f"✓ Fetched enriched schema: {len(enriched_schema.get('fields', []))} fields "
                    f"({len(enriched_schema.get('measures', []))} measures, "
                    f"{len(enriched_schema.get('dimensions', []))} dimensions)"
                )
        except Exception as e:
            logger.warning(
                f"Schema enrichment failed, falling back to basic schema: {e}"
            )
            # Fallback to basic schema
            enriched_schema = None
        
        # If enrichment failed, use basic schema
        if not enriched_schema:
            logger.info("Using basic schema (enrichment unavailable)")
            schema_response = await _fetch_schema_cached(datasource_id)
            
            return {
                **state,
                "schema": schema_response,
                "enriched_schema": None,  # Mark as not enriched
                "current_thought": f"Fetched basic schema with {len(schema_response.get('columns', []))} columns",
                "tool_calls": state.get("tool_calls", []) + [{
                    "tool": "get_datasource_schema",
                    "args": {"datasource_id": datasource_id},
                    "result": "success",
                    "column_count": len(schema_response.get("columns", [])),
                    "enriched": False
                }]
            }
        
        # Use enriched schema
        # Convert enriched schema to backward-compatible format for existing code
        schema_response = {
            "columns": [
                {
                    "name": field.get("fieldCaption", ""),
                    "type": field.get("dataType", "UNKNOWN"),
                    "role": field.get("fieldRole", "UNKNOWN"),
                    "description": field.get("description", ""),
                    "is_measure": field.get("fieldRole") == "MEASURE",
                    "is_dimension": field.get("fieldRole") == "DIMENSION",
                }
                for field in enriched_schema.get("fields", [])
                if not field.get("hidden")
            ]
        }
        
        return {
            **state,
            "schema": schema_response,  # Backward-compatible format
            "enriched_schema": enriched_schema,  # Full enriched schema
            "current_thought": (
                f"Fetched enriched schema with {len(enriched_schema.get('fields', []))} fields "
                f"({len(enriched_schema.get('measures', []))} measures, "
                f"{len(enriched_schema.get('dimensions', []))} dimensions)"
            ),
            "tool_calls": state.get("tool_calls", []) + [{
                "tool": "get_datasource_schema",
                "args": {"datasource_id": datasource_id},
                "result": "success",
                "column_count": len(enriched_schema.get("fields", [])),
                "enriched": True,
                "measure_count": len(enriched_schema.get("measures", [])),
                "dimension_count": len(enriched_schema.get("dimensions", []))
            }]
        }
    except Exception as e:
        logger.error(f"Error fetching schema: {e}", exc_info=True)
        return {
            **state,
            "error": f"Failed to fetch schema: {str(e)}",
            "schema": None,
            "enriched_schema": None,
            "tool_calls": state.get("tool_calls", []) + [{
                "tool": "get_datasource_schema",
                "args": {"datasource_id": datasource_ids[0] if datasource_ids else None},
                "result": "error",
                "error": str(e)
            }]
        }
