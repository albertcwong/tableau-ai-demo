"""Tool for fetching datasource schema."""
import logging
from typing import Dict, Any, Optional
from app.services.tableau.client import TableauClient
from app.services.agents.vizql.schema_enrichment import SchemaEnrichmentService
from app.core.cache import redis_client
import json

logger = logging.getLogger(__name__)


async def get_datasource_schema(
    datasource_id: str,
    site_id: Optional[str] = None,
    use_enriched: bool = True
) -> Dict[str, Any]:
    """
    Fetch schema for datasource.
    
    Args:
        datasource_id: Datasource LUID
        site_id: Optional site ID (for authentication)
        use_enriched: Whether to use enriched schema if available
        
    Returns:
        {
            "columns": [...],
            "measures": [...],
            "dimensions": [...],
            "enriched": bool
        }
    """
    try:
        # Check cache first for enriched schema
        if use_enriched:
            cache_key = f"enriched_schema:{datasource_id}"
            try:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    if isinstance(cached_data, bytes):
                        cached_data = cached_data.decode('utf-8')
                    enriched_schema = json.loads(cached_data)
                    logger.info(
                        f"✓ Using cached enriched schema for {datasource_id}: "
                        f"{len(enriched_schema.get('fields', []))} fields"
                    )
                    # Return full enriched schema structure plus columns for backward compatibility
                    return {
                        "fields": enriched_schema.get("fields", []),  # Full field objects
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
                        ],
                        "measures": enriched_schema.get("measures", []),
                        "dimensions": enriched_schema.get("dimensions", []),
                        "field_map": enriched_schema.get("field_map", {}),
                        "enriched": True,
                        "datasource_id": datasource_id
                    }
            except Exception as cache_error:
                logger.debug(f"Cache check failed: {cache_error}, will fetch fresh")
        
        # Try to fetch enriched schema
        if use_enriched:
            try:
                tableau_client = TableauClient()
                enrichment_service = SchemaEnrichmentService(tableau_client)
                enriched_schema = await enrichment_service.enrich_datasource_schema(
                    datasource_id,
                    force_refresh=False,
                    include_statistics=False  # Skip statistics for speed
                )
                logger.info(
                    f"✓ Fetched enriched schema: {len(enriched_schema.get('fields', []))} fields"
                )
                # Return full enriched schema structure plus columns for backward compatibility
                return {
                    "fields": enriched_schema.get("fields", []),  # Full field objects
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
                    ],
                    "measures": enriched_schema.get("measures", []),
                    "dimensions": enriched_schema.get("dimensions", []),
                    "field_map": enriched_schema.get("field_map", {}),
                    "enriched": True,
                    "datasource_id": datasource_id
                }
            except Exception as e:
                logger.warning(f"Schema enrichment failed, falling back to basic schema: {e}")
        
        # Fallback to basic schema
        tableau_client = TableauClient()
        schema_response = await tableau_client.get_datasource_schema(datasource_id)
        
        return {
            "columns": schema_response.get("columns", []),
            "measures": [],
            "dimensions": [],
            "enriched": False,
            "datasource_id": datasource_id
        }
        
    except Exception as e:
        logger.error(f"Error fetching schema for {datasource_id}: {e}", exc_info=True)
        raise Exception(f"Failed to fetch schema: {str(e)}")
