"""Tool definitions for VizQL agent."""
import logging
from typing import Dict, Any, List, Optional

from app.services.tableau.client import TableauClient
from app.services.agents.vizql.schema_enrichment import SchemaEnrichmentService
from app.core.config import settings

logger = logging.getLogger(__name__)


class VizQLTools:
    """Collection of tools for VizQL data retrieval."""
    
    def __init__(
        self,
        site_id: str,
        datasource_id: str,
        tableau_client: Optional[TableauClient] = None,
        message_history: Optional[List[Dict]] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None
    ):
        self.site_id = site_id
        self.datasource_id = datasource_id
        self.message_history = message_history or []
        self.tableau_client = tableau_client or TableauClient()
        self.schema_service = SchemaEnrichmentService(self.tableau_client)
        self.model = model  # Store model for LLM calls
        self.provider = provider or "openai"  # Store provider for LLM calls
    
    async def get_datasource_metadata(
        self,
        include_statistics: bool = True
    ) -> Dict[str, Any]:
        """
        Get datasource schema with optional statistics.
        
        Use this tool when:
        - User asks "how many [field]?" (check cardinality)
        - User asks "min/max [field]?" (check statistics)
        - User asks "what fields are available?"
        - You need to understand schema before building query
        
        Args:
            include_statistics: Include cardinality, min/max, sample values
        
        Returns:
            {
                "fields": [...],
                "measures": [...],
                "dimensions": [...],
                "statistics": {
                    "field_name": {
                        "cardinality": 123,
                        "min": 0,
                        "max": 1000,
                        "sample_values": [...]
                    }
                }
            }
        """
        logger.info(f"Tool: get_datasource_metadata(include_statistics={include_statistics})")
        logger.info(f"Datasource ID: {self.datasource_id}, Site ID: {self.site_id}")
        
        try:
            enriched_schema = await self.schema_service.enrich_datasource_schema(
                datasource_id=self.datasource_id,
                include_statistics=include_statistics
            )
            
            # Validate enriched_schema structure
            if not enriched_schema:
                logger.error("get_datasource_metadata: Empty schema returned")
                return {"error": "Empty schema returned from enrichment service"}
            
            # Check if it's an error response
            if isinstance(enriched_schema, dict) and "error" in enriched_schema:
                logger.error(f"get_datasource_metadata: Error in schema: {enriched_schema.get('error')}")
                return enriched_schema
            
            # Ensure schema field exists
            if "schema" not in enriched_schema and "fields" not in enriched_schema:
                logger.warning(f"get_datasource_metadata: Schema structure unexpected. Keys: {list(enriched_schema.keys())}")
                # Try to construct schema from fields if available
                if "fields" in enriched_schema or "measures" in enriched_schema or "dimensions" in enriched_schema:
                    enriched_schema["schema"] = {
                        "columns": enriched_schema.get("fields", []) + 
                                   enriched_schema.get("measures", []) + 
                                   enriched_schema.get("dimensions", [])
                    }
                    logger.info("get_datasource_metadata: Constructed schema from fields/measures/dimensions")
                else:
                    logger.error("get_datasource_metadata: No schema or fields found in enriched_schema")
                    return {"error": "Schema structure invalid: missing 'schema' and 'fields'"}
            
            logger.info(f"get_datasource_metadata: Success. Schema keys: {list(enriched_schema.keys())}")
            if "schema" in enriched_schema and isinstance(enriched_schema["schema"], dict):
                logger.info(f"Schema columns count: {len(enriched_schema['schema'].get('columns', []))}")
            
            return enriched_schema
            
        except Exception as e:
            logger.error(f"Error in get_datasource_metadata: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def build_query(
        self,
        measures: List[str],
        dimensions: Optional[List[str]] = None,
        filters: Optional[List[Dict]] = None,
        topN: Optional[Dict] = None,
        sorting: Optional[List[Dict]] = None,
        calculations: Optional[List[Dict]] = None,
        bins: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Build a VizQL query JSON.
        
        Use this tool when:
        - Need to aggregate data (sum, average, count)
        - Need to group by dimensions
        - Need to filter or apply Top N
        - Need calculations or bins
        
        Args:
            measures: List of measure field names (e.g., ["Sales", "Profit"])
            dimensions: List of dimension field names (e.g., ["Region", "Category"])
            filters: List of filter definitions
            topN: Top N filter definition {"n": 10, "by": "measure_name", "direction": "top"}
            sorting: List of sort definitions
            calculations: List of calculated field definitions
            bins: List of bin definitions
        
        Returns:
            {
                "query": {...},  # VizQL JSON
                "is_valid": True
            }
        """
        logger.info(f"Tool: build_query(measures={measures}, dimensions={dimensions}, filters={filters}, topN={topN})")
        
        try:
            # Get enriched schema first
            logger.info(f"build_query: Fetching datasource metadata for schema")
            enriched_schema = await self.get_datasource_metadata(include_statistics=False)
            
            # Check if get_datasource_metadata returned an error
            if isinstance(enriched_schema, dict) and "error" in enriched_schema:
                error_msg = enriched_schema.get("error", "Unknown error fetching schema")
                logger.error(f"build_query: Failed to get schema: {error_msg}")
                return {
                    "query": None,
                    "is_valid": False,
                    "error": f"Cannot build query: {error_msg}"
                }
            
            # Extract schema from enriched_schema
            schema = enriched_schema.get("schema") or enriched_schema.get("fields") or {}
            
            # Validate schema is available
            if not schema or (isinstance(schema, dict) and not schema.get("columns") and not enriched_schema.get("fields")):
                logger.error(f"build_query: Schema not available. enriched_schema keys: {list(enriched_schema.keys())}")
                return {
                    "query": None,
                    "is_valid": False,
                    "error": "Schema not available. Cannot build query. Please ensure the datasource is accessible."
                }
            
            logger.info(f"build_query: Schema retrieved successfully. Fields: {len(schema.get('columns', []) if isinstance(schema, dict) else enriched_schema.get('fields', []))}")
            
            # Build a minimal state for query builder
            from app.services.agents.vizql.state import VizQLAgentState
            
            # Convert topN dict to expected format for context builder
            topN_state = None
            if topN:
                # Map tool-use format to context builder format
                # Tool-use format: {"n": 10, "by": "measure_name", "direction": "top"}
                # Context builder expects: {"enabled": True, "howMany": 10, "dimensionField": "...", "measureField": "...", "direction": "TOP"}
                measure_field = topN.get("by")  # The measure to rank by
                dimension_field = dimensions[0] if dimensions else None  # First dimension is what we're ranking
                
                topN_state = {
                    "enabled": True,
                    "howMany": topN.get("n", 10),
                    "dimensionField": dimension_field,
                    "measureField": measure_field,
                    "direction": topN.get("direction", "top").upper()  # Convert to uppercase for consistency
                }
                logger.info(f"build_query: Converted topN format - howMany={topN_state['howMany']}, dimensionField={dimension_field}, measureField={measure_field}, direction={topN_state['direction']}")
            
            # Create temporary state for query builder
            temp_state: VizQLAgentState = {
                "user_query": f"Build query with measures={measures}, dimensions={dimensions}",
                "schema": schema,  # Use extracted schema
                "enriched_schema": enriched_schema,
                "context_datasources": [self.datasource_id],
                "required_measures": measures,
                "required_dimensions": dimensions or [],
                "required_filters": filters or {},
                "topN": topN_state or {"enabled": False},
                "sorting": sorting or [],
                "calculations": calculations or [],
                "bins": bins or [],
                "model": self.model or "gpt-4",  # Use model from tool-use state or default
                "provider": self.provider  # Pass provider from tool-use state
            }
            logger.info(f"build_query: Passing model={self.model or 'gpt-4'} and provider={self.provider} to query builder")
            
            # Use existing query builder node
            from app.services.agents.vizql.nodes.query_builder import build_query_node
            
            result_state = await build_query_node(temp_state)
            
            query = result_state.get("query_draft")
            
            if not query:
                error = result_state.get("error", "Unknown error building query")
                return {
                    "query": None,
                    "is_valid": False,
                    "error": error
                }
            
            return {
                "query": query,
                "is_valid": True  # Basic validation passed in build
            }
            
        except Exception as e:
            logger.error(f"Error in build_query: {e}", exc_info=True)
            return {
                "query": None,
                "is_valid": False,
                "error": str(e)
            }
    
    async def validate_query(self, query: Dict) -> Dict[str, Any]:
        """
        Validate a VizQL query.
        
        Use this tool:
        - After building a query
        - To check for errors before execution
        
        Args:
            query: VizQL JSON query
        
        Returns:
            {
                "is_valid": True,
                "errors": [],
                "warnings": []
            }
        """
        logger.info("Tool: validate_query")
        
        try:
            # Get schema for validation
            enriched_schema = await self.get_datasource_metadata(include_statistics=False)
            
            # Create temporary state for validator
            from app.services.agents.vizql.state import VizQLAgentState
            
            temp_state: VizQLAgentState = {
                "query_draft": query,
                "schema": enriched_schema.get("schema", {}),
                "enriched_schema": enriched_schema
            }
            
            # Use existing validator node
            from app.services.agents.vizql.nodes.validator import validate_query_node
            
            result_state = await validate_query_node(temp_state)
            
            return {
                "is_valid": result_state.get("is_valid", False),
                "errors": result_state.get("validation_errors", []),
                "warnings": result_state.get("validation_suggestions", [])
            }
            
        except Exception as e:
            logger.error(f"Error in validate_query: {e}", exc_info=True)
            return {
                "is_valid": False,
                "errors": [str(e)],
                "warnings": []
            }
    
    async def query_datasource(self, query: Dict) -> Dict[str, Any]:
        """
        Execute a VizQL query and return results.
        
        Use this tool:
        - After building and optionally validating a query
        - When data aggregation/filtering is needed
        
        Args:
            query: VizQL JSON query
        
        Returns:
            {
                "columns": ["Region", "SUM(Sales)"],
                "data": [
                    ["East", 12345],
                    ["West", 23456],
                    ...
                ],
                "row_count": 10
            }
        """
        logger.info("Tool: query_datasource")
        
        try:
            # Use executor's query execution logic
            from app.services.agents.vizql.nodes.executor import _execute_query_with_retry
            
            results = await _execute_query_with_retry(self.tableau_client, query)
            
            return {
                "columns": results.get("columns", []),
                "data": results.get("data", []),
                "row_count": len(results.get("data", []))
            }
            
        except Exception as e:
            logger.error(f"Error in query_datasource: {e}", exc_info=True)
            return {
                "columns": [],
                "data": [],
                "row_count": 0,
                "error": str(e)
            }
    
    async def get_previous_results(self) -> Optional[Dict[str, Any]]:
        """
        Get the previous assistant message content and metadata.
        
        NOTE: This tool does NOT return full data arrays - only the natural language
        response content and metadata (row_count, columns). The LLM should read the 
        previous message content naturally to understand what was shown to the user.
        
        Use this tool when:
        - User references "the previous results", "that data", etc.
        - You need to see what was shown in the last response
        
        Returns:
            {
                "previous_message_content": "...",  # Full content from previous assistant message
                "row_count": 10,  # Number of rows returned (metadata only)
                "columns": [...],  # Column names (metadata only)
                "original_query": "...",  # VizQL query if available
            }
            or None if no previous results found
        """
        logger.info("Tool: get_previous_results")
        
        try:
            previous_message_content = None
            previous_metadata = None
            
            # Find last assistant message
            for msg in reversed(self.message_history):
                if msg.get("role") == "assistant":
                    previous_message_content = msg.get("content", "")
                    
                    # Capture metadata if available (row_count, columns) - but NOT full data
                    if "data_metadata" in msg and msg["data_metadata"]:
                        previous_metadata = msg["data_metadata"]
                    
                    if previous_message_content:
                        break
            
            if previous_message_content:
                result = {
                    "previous_message_content": previous_message_content[:2000],  # Limit to 2000 chars
                }
                
                # Add metadata if available
                if previous_metadata:
                    result["row_count"] = previous_metadata.get("row_count", 0)
                    result["columns"] = previous_metadata.get("columns", [])
                
                # Add original query if available
                for msg in reversed(self.message_history):
                    if msg.get("role") == "assistant" and "original_query" in msg:
                        result["original_query"] = msg.get("original_query", "")
                        break
                
                logger.info(f"get_previous_results returning message content ({len(previous_message_content)} chars) and metadata")
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Error in get_previous_results: {e}", exc_info=True)
            return None
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions for LLM function calling.
        
        Returns OpenAI-style function definitions (functions parameter format).
        """
        return [
            {
                "name": "get_datasource_metadata",
                "description": "Get datasource schema with statistics (cardinality, min/max, sample values). Use this for questions about field availability, cardinality ('how many X?'), or min/max values.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "include_statistics": {
                            "type": "boolean",
                            "description": "Whether to include statistics (cardinality, min/max, samples)",
                            "default": True
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "build_query",
                "description": "Build a VizQL query for data aggregation/filtering. Use this when you need to SUM, AVG, COUNT, group by dimensions, apply filters, or get Top N results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "measures": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Measure field names (e.g., ['Sales', 'Profit'])"
                        },
                        "dimensions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Dimension field names (e.g., ['Region', 'Category'])"
                        },
                        "filters": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Filter definitions"
                        },
                        "topN": {
                            "type": "object",
                            "description": "Top N filter: {n: 10, by: 'measure_name', direction: 'top'}"
                        },
                        "sorting": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Sort definitions"
                        },
                        "calculations": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Calculated field definitions"
                        },
                        "bins": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Bin definitions"
                        }
                    },
                    "required": ["measures"]
                }
            },
            {
                "name": "validate_query",
                "description": "Validate a VizQL query before execution. Use this after building a query to check for errors.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "object",
                            "description": "VizQL JSON query to validate"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "query_datasource",
                "description": "Execute a VizQL query and get results. Use this after building (and optionally validating) a query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "object",
                            "description": "VizQL JSON query to execute"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_previous_results",
                "description": "Get results from the previous query in the conversation. Use this when user asks to reformat/operate on previous results.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with arguments."""
        # Validate required arguments
        if tool_name == "query_datasource" and "query" not in arguments:
            raise ValueError("query_datasource requires a 'query' argument. Call build_query first to create a query.")
        elif tool_name == "build_query" and "measures" not in arguments:
            raise ValueError("build_query requires a 'measures' argument.")
        elif tool_name == "validate_query" and "query" not in arguments:
            raise ValueError("validate_query requires a 'query' argument.")
        
        if tool_name == "get_datasource_metadata":
            return await self.get_datasource_metadata(**arguments)
        elif tool_name == "build_query":
            return await self.build_query(**arguments)
        elif tool_name == "validate_query":
            return await self.validate_query(**arguments)
        elif tool_name == "query_datasource":
            return await self.query_datasource(**arguments)
        elif tool_name == "get_previous_results":
            return await self.get_previous_results()
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
