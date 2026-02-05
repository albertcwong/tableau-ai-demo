"""Schema enrichment service using VizQL read-metadata endpoint."""
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import timedelta

from app.services.tableau.client import TableauClient, TableauClientError
from app.core.cache import redis_client
from app.services.agents.vizql.semantic_rules import suggest_aggregation

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 3600  # 1 hour


class SchemaEnrichmentService:
    """Enriches datasource schemas with VizQL metadata."""
    
    def __init__(self, tableau_client: TableauClient):
        self.tableau_client = tableau_client
    
    async def enrich_datasource_schema(
        self, 
        datasource_id: str, 
        force_refresh: bool = False,
        include_statistics: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch and enrich datasource schema.
        
        Uses /read-metadata endpoint to get:
        - fieldCaption (exact field names)
        - dataType (INTEGER, REAL, STRING, etc.)
        - fieldRole (MEASURE, DIMENSION)
        - defaultAggregation
        - description
        - aliases
        
        Args:
            datasource_id: Datasource LUID
            force_refresh: If True, bypass cache and refresh from API
            
        Returns:
            Enriched schema dictionary with fields, measures, dimensions, and field_map
        """
        # Check cache first
        cache_key = f"enriched_schema:{datasource_id}"
        
        if not force_refresh:
            try:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    # Redis returns bytes, decode to string then parse JSON
                    if isinstance(cached_data, bytes):
                        cached_data = cached_data.decode('utf-8')
                    enriched = json.loads(cached_data)
                    logger.info(f"Using cached enriched schema for {datasource_id}")
                    return enriched
            except Exception as e:
                logger.warning(f"Cache read failed, fetching fresh: {e}")
        
        logger.info(f"Enriching schema for datasource {datasource_id}")
        
        try:
            # Call VizQL /read-metadata for field details (dataType, defaultAggregation, etc.)
            metadata = await self.tableau_client.read_metadata(datasource_id)
            
            # Call Metadata API to get accurate field roles
            metadata_api_fields = await self.tableau_client.get_metadata_api_fields(datasource_id)
            
            # Log sample field to debug structure
            if metadata.get("data") and len(metadata.get("data", [])) > 0:
                sample_field = metadata["data"][0]
                logger.debug(f"Sample field metadata: {json.dumps(sample_field, indent=2)}")
            
            logger.info(f"Retrieved {len(metadata_api_fields)} fields from Metadata API for role enrichment")
            
            # Process metadata into enriched format
            enriched = {
                "datasource_id": datasource_id,
                "fields": [],
                "field_map": {},  # Fast lookup by fieldCaption (lowercase)
                "measures": [],
                "dimensions": []
            }
            
            for field_meta in metadata.get("data", []):
                field_caption = field_meta.get("fieldCaption", "")
                field_name = field_meta.get("fieldName", "")
                if not field_caption:
                    continue
                
                # Get field metadata from Metadata API for descriptions/formulas
                # Match by fieldCaption (preferred) or fieldName
                metadata_field = None
                if field_caption in metadata_api_fields:
                    metadata_field = metadata_api_fields[field_caption]
                elif field_name in metadata_api_fields:
                    metadata_field = metadata_api_fields[field_name]
                
                # Determine field role using columnClass-based logic (same as get_datasource_schema)
                # This ensures consistency with UI sidepanel categorization
                # See docs/FIELD_ROLE_DETERMINATION_LOGIC.md for details
                column_class = field_meta.get("columnClass", "")
                default_agg = field_meta.get("defaultAggregation", "")
                data_type = field_meta.get("dataType", "")
                
                # Primary indicator: columnClass
                if column_class == "MEASURE":
                    field_role = "MEASURE"
                    is_measure = True
                    is_dimension = False
                elif column_class in ["COLUMN", "BIN", "GROUP"]:
                    field_role = "DIMENSION"
                    is_measure = False
                    is_dimension = True
                else:
                    # Fallback logic: use dataType and defaultAggregation
                    is_numeric = data_type in ["INTEGER", "REAL"]
                    has_aggregation = default_agg in ["SUM", "AVG", "MEDIAN", "COUNT", "COUNTD", "MIN", "MAX", "STDEV", "VAR", "AGG"]
                    
                    if is_numeric and has_aggregation and not column_class:
                        field_role = "MEASURE"
                        is_measure = True
                        is_dimension = False
                    elif column_class in ["CALCULATION", "TABLE_CALCULATION"]:
                        # Calculated fields: measure if has aggregation and is numeric
                        is_measure = has_aggregation and is_numeric
                        is_dimension = not is_measure
                        field_role = "MEASURE" if is_measure else "DIMENSION"
                    else:
                        # Default to dimension for unknown types
                        field_role = "DIMENSION"
                        is_measure = False
                        is_dimension = True
                
                logger.debug(
                    f"Field {field_caption}: columnClass={column_class}, "
                    f"dataType={data_type}, defaultAgg={default_agg}, "
                    f"→ role={field_role}"
                )
                
                # Use Metadata API description if available, otherwise use VizQL
                description = field_meta.get("description", "")
                if metadata_field and metadata_field.get("description"):
                    description = metadata_field["description"]
                
                # Use Metadata API formula if available, otherwise use VizQL
                formula = field_meta.get("formula")
                if metadata_field and metadata_field.get("formula"):
                    formula = metadata_field["formula"]
                
                field_info = {
                    "fieldCaption": field_caption,
                    "fieldName": field_name,
                    "dataType": field_meta.get("dataType", "UNKNOWN"),
                    "fieldRole": field_role,
                    "fieldType": field_meta.get("fieldType", "UNKNOWN"),
                    "defaultAggregation": default_agg,
                    "columnClass": column_class,
                    "description": description,
                    "formula": formula,
                    "hidden": field_meta.get("hidden", False)
                }
                
                # Add suggested aggregation if not provided and field is a measure
                if not field_info["defaultAggregation"] and field_info["fieldRole"] == "MEASURE":
                    field_info["suggestedAggregation"] = suggest_aggregation(
                        field_caption, 
                        field_info["dataType"],
                        field_info["fieldRole"]
                    )
                elif field_info["defaultAggregation"]:
                    # Use default aggregation as suggested
                    field_info["suggestedAggregation"] = field_info["defaultAggregation"]
                
                # Add aliases if present
                if field_meta.get("aliases"):
                    field_info["aliases"] = field_meta.get("aliases")
                
                # Get field statistics if requested
                if include_statistics:
                    try:
                        stats = await self.tableau_client.get_field_statistics(
                            datasource_id,
                            field_caption,
                            data_type,
                            is_measure
                        )
                        field_info["cardinality"] = stats.get("cardinality")
                        field_info["sample_values"] = stats.get("sample_values", [])
                        field_info["min"] = stats.get("min")
                        field_info["max"] = stats.get("max")
                        field_info["null_percentage"] = stats.get("null_percentage")
                    except Exception as e:
                        logger.debug(f"Could not get statistics for {field_caption}: {e}")
                        # Continue without statistics
                        field_info["cardinality"] = None
                        field_info["sample_values"] = []
                        field_info["min"] = None
                        field_info["max"] = None
                        field_info["null_percentage"] = None
                else:
                    field_info["cardinality"] = None
                    field_info["sample_values"] = []
                    field_info["min"] = None
                    field_info["max"] = None
                    field_info["null_percentage"] = None
                
                enriched["fields"].append(field_info)
                
                # Create lowercase lookup map for case-insensitive matching
                field_lower = field_caption.lower()
                enriched["field_map"][field_lower] = field_info
                
                # Categorize by role using the determined is_measure/is_dimension flags
                if is_measure:
                    enriched["measures"].append(field_caption)
                elif is_dimension:
                    enriched["dimensions"].append(field_caption)
                else:
                    logger.warning(f"Field {field_caption} could not be categorized (role={field_role})")
            
            # Cache enriched schema
            try:
                cache_value = json.dumps(enriched)
                redis_client.setex(cache_key, CACHE_TTL_SECONDS, cache_value)
                logger.info(
                    f"Enriched schema cached: {len(enriched['fields'])} fields "
                    f"({len(enriched['measures'])} measures, {len(enriched['dimensions'])} dimensions)"
                )
            except Exception as e:
                logger.warning(f"Failed to cache enriched schema: {e}")
            
            return enriched
            
        except TableauClientError as e:
            logger.error(f"Tableau client error enriching schema: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error enriching schema: {e}", exc_info=True)
            raise
    
    async def get_supported_functions(self, datasource_id: str) -> List[Dict[str, Any]]:
        """
        Fetch datasource-specific supported functions.
        
        Args:
            datasource_id: Datasource LUID
            
        Returns:
            List of supported function objects with name and overloads
        """
        cache_key = f"supported_functions:{datasource_id}"
        
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                if isinstance(cached_data, bytes):
                    cached_data = cached_data.decode('utf-8')
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Cache read failed for functions, fetching fresh: {e}")
        
        try:
            functions = await self.tableau_client.list_supported_functions(datasource_id)
            
            # Cache functions
            try:
                cache_value = json.dumps(functions)
                redis_client.setex(cache_key, CACHE_TTL_SECONDS, cache_value)
            except Exception as e:
                logger.warning(f"Failed to cache supported functions: {e}")
            
            return functions
            
        except TableauClientError as e:
            logger.error(f"Tableau client error fetching functions: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching functions: {e}", exc_info=True)
            raise
