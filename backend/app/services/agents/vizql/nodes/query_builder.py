"""Query builder node for constructing VizQL queries."""
import json
import logging
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage

from app.services.agents.vizql.state import VizQLAgentState
from app.prompts.registry import prompt_registry
from app.services.ai.client import UnifiedAIClient
from app.core.config import settings
from app.services.metrics import track_node_execution

logger = logging.getLogger(__name__)


@track_node_execution("vizql", "query_builder")
async def build_query_node(state: VizQLAgentState) -> Dict[str, Any]:
    """
    Construct VizQL Data Service query from intent and schema.
    
    This is an "Act" step in ReAct.
    """
    try:
        schema = state.get("schema")
        if not schema:
            return {
                **state,
                "error": "Schema not available. Cannot build query.",
                "query_draft": None
            }
        
        datasource_ids = state.get("context_datasources", [])
        if not datasource_ids:
            return {
                **state,
                "error": "No datasource ID available.",
                "query_draft": None
            }
        
        datasource_id = datasource_ids[0]
        
        # Get query construction prompt with examples
        system_prompt = prompt_registry.get_prompt(
            "agents/vizql/query_construction.txt",
            variables={
                "schema": json.dumps(schema.get("columns", []), indent=2),
                "measures": state.get("required_measures", []),
                "dimensions": state.get("required_dimensions", []),
                "filters": json.dumps(state.get("required_filters", {}), indent=2),
                "aggregation": state.get("required_filters", {}).get("aggregation", "sum"),
                "datasource_id": datasource_id
            }
        )
        
        # Include few-shot examples
        examples = prompt_registry.get_examples("agents/vizql/examples.yaml")
        messages = prompt_registry.build_few_shot_prompt(
            system_prompt,
            examples,
            f"Build query for: {state['user_query']}"
        )
        
        # Initialize AI client with API key from state
        api_key = state.get("api_key")
        model = state.get("model", "gpt-4")
        
        ai_client = UnifiedAIClient(
            gateway_url=settings.GATEWAY_BASE_URL,
            api_key=api_key
        )
        
        # Call AI
        response = await ai_client.chat(
            model=model,
            messages=messages
        )
        
        # Parse query JSON
        try:
            content = response.content.strip()
            # Remove markdown code blocks if present
            if content.startswith("```"):
                lines = content.split("\n")
                # Find JSON block
                json_start = None
                json_end = None
                for i, line in enumerate(lines):
                    if "```json" in line.lower() or "```" in line:
                        if json_start is None:
                            json_start = i + 1
                        else:
                            json_end = i
                            break
                if json_start and json_end:
                    content = "\n".join(lines[json_start:json_end])
                elif json_start:
                    content = "\n".join(lines[json_start:-1])
            
            query_draft = json.loads(content)
            
            # Ensure query has required structure
            if "datasource" not in query_draft:
                query_draft["datasource"] = {"datasourceLuid": datasource_id}
            if "query" not in query_draft:
                query_draft["query"] = {}
            if "options" not in query_draft:
                query_draft["options"] = {
                    "returnFormat": "OBJECTS",
                    "disaggregate": False
                }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse query JSON: {e}. Response: {response.content}")
            return {
                **state,
                "error": f"Failed to parse query JSON: {str(e)}",
                "query_draft": None
            }
        
        query_version = state.get("query_version", 0) + 1
        
        return {
            **state,
            "query_draft": query_draft,
            "query_version": query_version,
            "current_thought": f"Built query version {query_version} with {len(query_draft.get('query', {}).get('fields', []))} fields"
        }
    except Exception as e:
        logger.error(f"Error building query: {e}", exc_info=True)
        return {
            **state,
            "error": f"Failed to build query: {str(e)}",
            "query_draft": None
        }
