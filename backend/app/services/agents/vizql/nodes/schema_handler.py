"""Schema query handler node for answering questions from schema metadata."""
import json
import logging
from typing import Dict, Any

from app.services.agents.vizql.state import VizQLAgentState
from app.prompts.registry import prompt_registry
from app.services.ai.client import UnifiedAIClient
from app.core.config import settings
from app.services.metrics import track_node_execution
from app.services.tableau.client import TableauClient
from app.services.agents.vizql.schema_enrichment import SchemaEnrichmentService

logger = logging.getLogger(__name__)


def format_enriched_schema_for_prompt(enriched_schema: Dict[str, Any]) -> str:
    """Format enriched schema into readable text for LLM."""
    if not enriched_schema:
        return "No schema available."
    
    lines = []
    lines.append("=" * 80)
    lines.append("ENRICHED SCHEMA METADATA WITH STATISTICS")
    lines.append("=" * 80)
    lines.append("")
    lines.append("**IMPORTANT:** This schema includes cardinality (distinct count) statistics.")
    lines.append("For 'how many [field]?' questions, find the field below and look for CARDINALITY.")
    lines.append("")
    lines.append(f"**Dataset Summary:**")
    lines.append(f"- Total fields: {len(enriched_schema.get('fields', []))}")
    lines.append(f"- Measures: {len(enriched_schema.get('measures', []))}")
    lines.append(f"- Dimensions: {len(enriched_schema.get('dimensions', []))}")
    lines.append("")
    
    # Highlight fields with cardinality (important for "how many" questions)
    fields_with_cardinality = []
    for field in enriched_schema.get("fields", []):
        if field.get("cardinality") is not None:
            fields_with_cardinality.append({
                "name": field.get("fieldCaption", "Unknown"),
                "cardinality": field.get("cardinality"),
                "role": field.get("fieldRole", "UNKNOWN")
            })
    
    if fields_with_cardinality:
        lines.append("**Fields with Cardinality (Distinct Count) Available:**")
        lines.append("These fields have cardinality statistics - use this to answer 'how many [field]?' questions:")
        for f in fields_with_cardinality[:20]:  # Show first 20
            lines.append(f"- {f['name']}: {f['cardinality']} distinct values ({f['role']})")
        lines.append("")
    else:
        lines.append("**Note:** No fields have cardinality statistics available in this schema.")
        lines.append("")
    
    lines.append("**All Fields with Statistics:**")
    lines.append("")
    
    for field in enriched_schema.get("fields", []):
        field_caption = field.get("fieldCaption", "Unknown")
        data_type = field.get("dataType", "UNKNOWN")
        field_role = field.get("fieldRole", "UNKNOWN")
        
        lines.append(f"### {field_caption}")
        lines.append(f"- Type: {data_type}")
        lines.append(f"- Role: {field_role}")
        
        # Add statistics if available - make cardinality VERY prominent
        cardinality = field.get("cardinality")
        if cardinality is not None:
            lines.append(f"")
            lines.append(f"**CARDINALITY (Distinct Count): {cardinality}**")
            lines.append(f"*This is the answer to 'how many {field_caption.lower()}?' questions*")
            lines.append(f"")
        else:
            # Explicitly note when cardinality is missing (helps debug)
            lines.append(f"- Cardinality: Not available")
        
        min_val = field.get("min")
        max_val = field.get("max")
        if min_val is not None and max_val is not None:
            lines.append(f"- Min: {min_val}")
            lines.append(f"- Max: {max_val}")
        
        sample_values = field.get("sample_values", [])
        if sample_values:
            sample_str = ", ".join(str(v) for v in sample_values[:10])
            lines.append(f"- Sample values: {sample_str}")
        
        null_pct = field.get("null_percentage")
        if null_pct is not None:
            lines.append(f"- Null percentage: {null_pct}%")
        
        description = field.get("description")
        if description:
            lines.append(f"- Description: {description}")
        
        lines.append("")
    
    return "\n".join(lines)


@track_node_execution("vizql", "schema_handler")
async def handle_schema_query_node(state: VizQLAgentState) -> Dict[str, Any]:
    """
    Answer questions using enriched schema metadata.
    
    No VizQL query needed - answers from cardinality, min/max, sample values, etc.
    
    If enriched_schema is not in state, fetches it first (similar to schema_fetch node).
    """
    try:
        user_query = state.get("user_query", "")
        enriched_schema = state.get("enriched_schema")
        
        # If schema not available, fetch it (needed for schema queries that route directly)
        if not enriched_schema:
            logger.info("Enriched schema not in state, fetching for schema query...")
            datasource_ids = state.get("context_datasources", [])
            
            if not datasource_ids:
                return {
                    **state,
                    "final_answer": "I need a datasource to answer schema questions. Please specify a datasource.",
                    "error": "No datasource in context"
                }
            
            datasource_id = datasource_ids[0]
            
            try:
                # Try to get from cache first
                from app.core.cache import redis_client
                cache_key = f"enriched_schema:{datasource_id}"
                cached_data = redis_client.get(cache_key)
                
                if cached_data:
                    if isinstance(cached_data, bytes):
                        cached_data = cached_data.decode('utf-8')
                    enriched_schema = json.loads(cached_data)
                    
                    # Check if cached schema has statistics
                    stats_count = sum(1 for f in enriched_schema.get("fields", []) if f.get("cardinality") is not None)
                    logger.info(f"✓ Using cached enriched schema: {stats_count} fields have cardinality")
                    
                    # If cached schema doesn't have statistics, fetch fresh with statistics
                    if stats_count == 0:
                        logger.info("Cached schema lacks statistics, fetching fresh schema with statistics...")
                        tableau_client = TableauClient()
                        enrichment_service = SchemaEnrichmentService(tableau_client)
                        enriched_schema = await enrichment_service.enrich_datasource_schema(
                            datasource_id,
                            force_refresh=True,  # Force refresh to get statistics
                            include_statistics=True
                        )
                        stats_count = sum(1 for f in enriched_schema.get("fields", []) if f.get("cardinality") is not None)
                        logger.info(f"✓ Fetched fresh enriched schema with statistics: {stats_count} fields have cardinality")
                else:
                    # Fetch enriched schema (WITH statistics for schema queries)
                    logger.info("Fetching enriched schema with statistics for schema query...")
                    tableau_client = TableauClient()
                    enrichment_service = SchemaEnrichmentService(tableau_client)
                    enriched_schema = await enrichment_service.enrich_datasource_schema(
                        datasource_id,
                        force_refresh=False,
                        include_statistics=True  # Include statistics for schema queries
                    )
                    # Verify statistics were included
                    stats_count = sum(1 for f in enriched_schema.get("fields", []) if f.get("cardinality") is not None)
                    logger.info(f"✓ Fetched enriched schema with statistics: {stats_count} fields have cardinality")
            except Exception as e:
                logger.error(f"Failed to fetch enriched schema: {e}", exc_info=True)
                return {
                    **state,
                    "final_answer": f"I couldn't fetch the schema metadata needed to answer this question: {str(e)}",
                    "error": f"Schema fetch failed: {str(e)}"
                }
        
        if not enriched_schema:
            return {
                **state,
                "final_answer": "I don't have access to the schema metadata needed to answer this question.",
                "error": "No enriched schema available"
            }
        
        # Debug: Check if cardinality is available
        fields_with_cardinality = [
            f.get("fieldCaption") for f in enriched_schema.get("fields", [])
            if f.get("cardinality") is not None
        ]
        logger.info(f"Schema has {len(fields_with_cardinality)} fields with cardinality: {fields_with_cardinality[:5]}")
        
        # Check if the requested field has cardinality
        user_query_lower = user_query.lower()
        if "customer" in user_query_lower:
            customer_fields = [
                f for f in enriched_schema.get("fields", [])
                if "customer" in f.get("fieldCaption", "").lower()
            ]
            for field in customer_fields:
                logger.info(f"Customer field '{field.get('fieldCaption')}' cardinality: {field.get('cardinality')}")
        
        # Format schema for prompt
        schema_text = format_enriched_schema_for_prompt(enriched_schema)
        
        # Log a sample of the formatted schema to verify cardinality is included
        if "customer" in user_query_lower:
            if "CARDINALITY" in schema_text or "cardinality" in schema_text.lower():
                logger.info("✓ Cardinality found in formatted schema")
            else:
                logger.warning("⚠ Cardinality NOT found in formatted schema!")
                # Log first 2000 chars of schema to debug
                logger.debug(f"Schema sample: {schema_text[:2000]}")
        
        # Get schema handler prompt
        system_prompt = prompt_registry.get_prompt(
            "agents/vizql/schema_query_handler.txt",
            variables={
                "user_query": user_query,
                "enriched_schema": schema_text
            }
        )
        
        # Initialize AI client
        api_key = state.get("api_key")
        model = state.get("model", "gpt-4")
        
        # Validate API key is present
        if not api_key:
            logger.error("API key missing from state - cannot make gateway request")
            return {
                **state,
                "error": "Failed to handle schema query: Authorization header required for direct authentication",
                "schema_answer": None
            }
        
        ai_client = UnifiedAIClient(
            gateway_url=settings.GATEWAY_BASE_URL,
            api_key=api_key
        )
        
        # Call LLM to generate answer
        messages = [
            {"role": "system", "content": "You are a helpful data analyst assistant that explains schema metadata."},
            {"role": "user", "content": system_prompt}
        ]
        
        response = await ai_client.chat(
            model=model,
            messages=messages,
            api_key=api_key
        )
        
        answer = response.content if response.content else "I couldn't generate an answer from the schema metadata."
        
        logger.info(f"Schema query answered: {len(answer)} characters")
        
        return {
            **state,
            "enriched_schema": enriched_schema,  # Store in state for future use
            "final_answer": answer,
            "schema_answer": answer,
            "current_thought": None  # Clear thought as we're done
        }
        
    except Exception as e:
        logger.error(f"Error handling schema query: {e}", exc_info=True)
        return {
            **state,
            "final_answer": f"Error answering schema question: {str(e)}",
            "error": str(e)
        }
