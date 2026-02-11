"""Schema enrichment service using VizQL read-metadata endpoint."""
import asyncio
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
        
        Core schema pull = Metadata only (VizQL + Metadata API with role). No stats.
        Enrichment = Stats gathering only (value_counts, cardinality, min, max, median, null_percentage).
        
        Args:
            datasource_id: Datasource LUID
            force_refresh: If True, bypass cache and refresh from API
            include_statistics: If True, fetch stats (enrichment). If False, return core schema only.
            
        Returns:
            Schema dictionary with fields, measures, dimensions, and field_map.
            If include_statistics=True, also includes stats (cardinality, sample_values, value_counts, min, max, median, null_percentage).
        """
        # Step 1: Get core schema (metadata only)
        core_schema = await self._get_core_schema(datasource_id, force_refresh)
        
        # Step 2: Optionally enrich with stats
        if include_statistics:
            return await self._enrich_schema_with_stats(datasource_id, core_schema, force_refresh)
        
        return core_schema
    
    async def _get_core_schema(
        self,
        datasource_id: str,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch core schema: VizQL metadata + Metadata API (role, descriptions, formulas).
        No stats queries - this is the base metadata pull.
        
        Args:
            datasource_id: Datasource LUID
            force_refresh: If True, bypass cache
            
        Returns:
            Core schema dictionary with fields, measures, dimensions, field_map.
            No stats fields (cardinality, sample_values, value_counts, min, max, median, null_percentage).
        """
        # Check cache first for core schema (no stats)
        cache_key = f"schema:{datasource_id}"
        
        if not force_refresh:
            try:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    if isinstance(cached_data, bytes):
                        cached_data = cached_data.decode('utf-8')
                    core_schema = json.loads(cached_data)
                    logger.info(f"Using cached core schema for {datasource_id} (no API calls - use force_refresh to see raw GraphQL/read-metadata)")
                    return core_schema
            except Exception as e:
                logger.warning(f"Cache read failed, fetching fresh: {e}")
        
        logger.info(f"Fetching core schema for datasource {datasource_id}")
        
        try:
            # Call VizQL /read-metadata for field details (dataType, defaultAggregation, etc.)
            metadata = await self.tableau_client.read_metadata(datasource_id)
            
            # Call Metadata API to get role, descriptions, formulas
            metadata_api_fields = await self.tableau_client.get_metadata_api_fields(datasource_id)
            
            # Log sample field to debug structure
            if metadata.get("data") and len(metadata.get("data", [])) > 0:
                sample_field = metadata["data"][0]
                logger.debug(f"Sample field metadata: {json.dumps(sample_field, indent=2)}")
            
            logger.info(f"Retrieved {len(metadata_api_fields)} fields from Metadata API")
            if not metadata_api_fields:
                logger.warning(
                    "Metadata API returned no fields; using VizQL columnClass fallback for role"
                )
            
            # Process metadata into core schema format
            core_schema = {
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
                
                # Get field metadata from Metadata API for role, descriptions, formulas
                # Match by fieldCaption, fieldName, or case-insensitive
                metadata_field = (
                    metadata_api_fields.get(field_caption)
                    or metadata_api_fields.get(field_name)
                    or metadata_api_fields.get(field_caption.lower() if field_caption else "")
                    or metadata_api_fields.get(field_name.lower() if field_name else "")
                )
                
                # Use Metadata API role as source of truth; fallback to VizQL columnClass when missing
                metadata_role = None
                if metadata_field and metadata_field.get("role"):
                    metadata_role = metadata_field.get("role").upper()
                
                if metadata_role == "MEASURE":
                    field_role = "MEASURE"
                    is_measure = True
                    is_dimension = False
                elif metadata_role == "DIMENSION":
                    field_role = "DIMENSION"
                    is_measure = False
                    is_dimension = True
                else:
                    # Fallback: VizQL columnClass when Metadata API role unavailable
                    column_class = (field_meta.get("columnClass") or "").strip().upper()
                    default_agg = (field_meta.get("defaultAggregation") or "").upper()
                    data_type = (field_meta.get("dataType") or "").upper()
                    is_numeric = data_type in ("INTEGER", "REAL", "DOUBLE", "FLOAT")
                    has_agg = default_agg in ("SUM", "AVG", "MEDIAN", "COUNT", "COUNTD", "MIN", "MAX", "STDEV", "VAR", "AGG")
                    if column_class == "MEASURE" or (is_numeric and has_agg and not column_class):
                        field_role = "MEASURE"
                        is_measure = True
                        is_dimension = False
                        logger.debug(f"Field {field_caption}: using columnClass/numeric fallback → MEASURE")
                    elif column_class in ("COLUMN", "BIN", "GROUP"):
                        field_role = "DIMENSION"
                        is_measure = False
                        is_dimension = True
                    else:
                        logger.warning(
                            f"Field {field_caption}: no Metadata API role "
                            f"(columnClass={column_class}, dataType={data_type}, defaultAgg={default_agg})"
                        )
                        field_role = "DIMENSION"
                        is_measure = False
                        is_dimension = True
                
                logger.debug(
                    f"Field {field_caption}: metadataRole={metadata_role}, "
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
                
                default_agg = field_meta.get("defaultAggregation", "")
                data_type = field_meta.get("dataType", "UNKNOWN")
                
                field_info = {
                    "fieldCaption": field_caption,
                    "fieldName": field_name,
                    "dataType": data_type,
                    "fieldRole": field_role,
                    "fieldType": field_meta.get("fieldType", "UNKNOWN"),
                    "defaultAggregation": default_agg,
                    "columnClass": field_meta.get("columnClass", ""),
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
                
                # No stats fields in core schema - these are added during enrichment
                core_schema["fields"].append(field_info)
                
                # Create lowercase lookup map for case-insensitive matching
                field_lower = field_caption.lower()
                core_schema["field_map"][field_lower] = field_info
                
                # Categorize by role
                if is_measure:
                    core_schema["measures"].append(field_caption)
                elif is_dimension:
                    core_schema["dimensions"].append(field_caption)
                else:
                    logger.warning(f"Field {field_caption} could not be categorized (role={field_role})")
            
            # Cache core schema
            try:
                cache_value = json.dumps(core_schema)
                redis_client.setex(cache_key, CACHE_TTL_SECONDS, cache_value)
                logger.info(
                    f"Core schema cached: {len(core_schema['fields'])} fields "
                    f"({len(core_schema['measures'])} measures, {len(core_schema['dimensions'])} dimensions)"
                )
            except Exception as e:
                logger.warning(f"Failed to cache core schema: {e}")
            
            return core_schema
            
        except TableauClientError as e:
            logger.error(f"Tableau client error fetching core schema: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching core schema: {e}", exc_info=True)
            raise
    
    async def _enrich_schema_with_stats(
        self,
        datasource_id: str,
        core_schema: Dict[str, Any],
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Enrich core schema with statistics (value_counts, cardinality, min, max, median, null_percentage).
        This is the enrichment step - queries VizQL for sample values and computes stats.
        
        Args:
            datasource_id: Datasource LUID
            core_schema: Core schema from _get_core_schema
            force_refresh: If True, bypass cache
            
        Returns:
            Enriched schema with stats added to each field.
        """
        # Check cache for enriched schema (with stats)
        cache_key = f"enriched_schema:{datasource_id}"
        
        if not force_refresh:
            try:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    if isinstance(cached_data, bytes):
                        cached_data = cached_data.decode('utf-8')
                    enriched = json.loads(cached_data)
                    logger.info(f"Using cached enriched schema (with stats) for {datasource_id}")
                    return enriched
            except Exception as e:
                logger.warning(f"Cache read failed, fetching fresh stats: {e}")
        
        logger.info(f"Enriching schema with statistics for datasource {datasource_id}")
        
        # Create a copy of core schema to add stats to
        enriched = json.loads(json.dumps(core_schema))  # Deep copy
        
        # Initialize stats fields for all fields
        for field_info in enriched["fields"]:
            field_info["cardinality"] = None
            field_info["sample_values"] = []
            field_info["value_counts"] = []
            field_info["min"] = None
            field_info["max"] = None
            field_info["median"] = None
            field_info["null_percentage"] = None
        
        # Fetch field statistics concurrently (sample datapoints, cardinality, min/max)
        if enriched["fields"]:
            async def fetch_stats(fi: Dict[str, Any]) -> tuple:
                cap = fi["fieldCaption"]
                try:
                    s = await self.tableau_client.get_field_statistics(
                        datasource_id, cap, fi.get("dataType", ""), fi.get("fieldRole") == "MEASURE"
                    )
                    return (cap, s)
                except Exception as e:
                    logger.debug(f"Stats for {cap}: {e}")
                    return (cap, {})

            tasks = [fetch_stats(f) for f in enriched["fields"]]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    continue
                cap, stats = r
                for fi in enriched["fields"]:
                    if fi["fieldCaption"] == cap:
                        fi["cardinality"] = stats.get("cardinality")
                        fi["sample_values"] = stats.get("sample_values", [])
                        fi["value_counts"] = stats.get("value_counts", [])
                        fi["min"] = stats.get("min")
                        fi["max"] = stats.get("max")
                        fi["median"] = stats.get("median")
                        fi["null_percentage"] = stats.get("null_percentage")
                        break
            
            stats_count = sum(1 for f in enriched["fields"] if f.get("cardinality") is not None or f.get("min") is not None)
            logger.info(f"Fetched statistics for {stats_count} fields (cardinality, min/max, sample values)")
        
        # Cache enriched schema (with stats)
        try:
            cache_value = json.dumps(enriched)
            redis_client.setex(cache_key, CACHE_TTL_SECONDS, cache_value)
            logger.info(
                f"Enriched schema (with stats) cached: {len(enriched['fields'])} fields "
                f"({len(enriched['measures'])} measures, {len(enriched['dimensions'])} dimensions)"
            )
        except Exception as e:
            logger.warning(f"Failed to cache enriched schema: {e}")
        
        return enriched
    
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
