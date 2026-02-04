"""Agentic capabilities: intent recognition, planning, and tool orchestration."""
import logging
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import re

from app.services.ai.client import UnifiedAIClient
from app.services.ai.tools import get_tools, execute_tool, format_tool_result, TOOL_REGISTRY
from app.services.tableau.client import TableauClient

logger = logging.getLogger(__name__)


class Intent(Enum):
    """User intent classification."""
    LIST_DATASOURCES = "list_datasources"
    LIST_VIEWS = "list_views"
    QUERY_DATASOURCE = "query_datasource"
    EMBED_VIEW = "embed_view"
    GENERAL_QUESTION = "general_question"
    UNKNOWN = "unknown"


class Agent:
    """Agent for handling conversational interactions with Tableau."""
    
    def __init__(
        self,
        ai_client: Optional[UnifiedAIClient] = None,
        tableau_client: Optional[TableauClient] = None,
        model: str = "gpt-4",
        api_key: Optional[str] = None
    ):
        """Initialize agent.
        
        Args:
            ai_client: Optional AI client instance
            tableau_client: Optional Tableau client instance (reused across tool calls)
            model: AI model to use for reasoning
            api_key: Optional API key for AI client
        """
        self.ai_client = ai_client
        self.tableau_client = tableau_client
        self.model = model
        self.api_key = api_key
        self.conversation_history: List[Dict[str, str]] = []
    
    def add_message(self, role: str, content: str):
        """Add message to conversation history.
        
        Args:
            role: Message role ("user", "assistant", "system")
            content: Message content
        """
        self.conversation_history.append({"role": role, "content": content})
    
    def get_context(self) -> List[Dict[str, str]]:
        """Get conversation context."""
        return self.conversation_history.copy()
    
    def classify_intent(self, query: str) -> Intent:
        """
        Classify user intent from query.
        
        Uses keyword matching and simple heuristics. In production, this could
        use a fine-tuned classifier or LLM-based classification.
        
        Args:
            query: User query string
            
        Returns:
            Intent enum value
        """
        query_lower = query.lower()
        
        # List datasources intent
        if any(phrase in query_lower for phrase in [
            "list datasource", "show datasource", "what datasource",
            "available datasource", "datasources", "data sources",
            "list data", "show data"
        ]):
            return Intent.LIST_DATASOURCES
        
        # List views intent
        if any(phrase in query_lower for phrase in [
            "list view", "show view", "what view", "available view",
            "list dashboard", "show dashboard", "dashboards",
            "list visualization", "show visualization", "visualizations",
            "views"
        ]):
            return Intent.LIST_VIEWS
        
        # Query datasource intent
        if any(phrase in query_lower for phrase in [
            "query", "filter", "get data", "show data from",
            "analyze", "find", "search", "where", "select"
        ]):
            return Intent.QUERY_DATASOURCE
        
        # Embed view intent
        if any(phrase in query_lower for phrase in [
            "embed", "show view", "display", "view", "open dashboard",
            "show dashboard", "visualize"
        ]):
            # Check if there's a view ID or name mentioned
            if re.search(r'view[_\s]*id|dashboard[_\s]*id|view[_\s]*name', query_lower):
                return Intent.EMBED_VIEW
        
        # General question (no specific action)
        if any(phrase in query_lower for phrase in [
            "what is", "what are", "how", "why", "explain", "tell me about"
        ]):
            return Intent.GENERAL_QUESTION
        
        return Intent.UNKNOWN
    
    def create_plan(self, query: str, intent: Optional[Intent] = None) -> List[Dict[str, Any]]:
        """
        Create a multi-step plan for executing user query.
        
        Args:
            query: User query string
            intent: Optional pre-classified intent (will classify if not provided)
            
        Returns:
            List of plan steps, each with "action" and "arguments"
        """
        if intent is None:
            intent = self.classify_intent(query)
        
        plan = []
        
        if intent == Intent.LIST_DATASOURCES:
            plan.append({
                "action": "list_datasources",
                "arguments": {},
                "description": "List all available datasources"
            })
        
        elif intent == Intent.LIST_VIEWS:
            # Check if datasource is mentioned in query
            datasource_id = self._extract_datasource_reference(query)
            plan.append({
                "action": "list_views",
                "arguments": {"datasource_id": datasource_id} if datasource_id else {},
                "description": f"List views{f' for datasource {datasource_id}' if datasource_id else ''}"
            })
        
        elif intent == Intent.QUERY_DATASOURCE:
            # Extract datasource ID and filters from query
            datasource_id = self._extract_datasource_reference(query)
            filters = self._extract_filters(query)
            
            if not datasource_id:
                # First step: list datasources to find the right one
                plan.append({
                    "action": "list_datasources",
                    "arguments": {},
                    "description": "List datasources to identify target"
                })
                # Second step will be determined after first step
                plan.append({
                    "action": "query_datasource",
                    "arguments": {"filters": filters} if filters else {},
                    "description": "Query the selected datasource",
                    "requires_previous_result": True
                })
            else:
                plan.append({
                    "action": "query_datasource",
                    "arguments": {
                        "datasource_id": datasource_id,
                        "filters": filters
                    } if filters else {"datasource_id": datasource_id},
                    "description": f"Query datasource {datasource_id}"
                })
        
        elif intent == Intent.EMBED_VIEW:
            view_id = self._extract_view_reference(query)
            filters = self._extract_filters(query)
            
            if not view_id:
                # First step: list views to find the right one
                plan.append({
                    "action": "list_views",
                    "arguments": {},
                    "description": "List views to identify target"
                })
                plan.append({
                    "action": "embed_view",
                    "arguments": {"filters": filters} if filters else {},
                    "description": "Embed the selected view",
                    "requires_previous_result": True
                })
            else:
                plan.append({
                    "action": "embed_view",
                    "arguments": {
                        "view_id": view_id,
                        "filters": filters
                    } if filters else {"view_id": view_id},
                    "description": f"Embed view {view_id}"
                })
        
        else:
            # General question or unknown - no specific plan
            plan.append({
                "action": "general_response",
                "arguments": {"query": query},
                "description": "Respond to general question"
            })
        
        return plan
    
    def _extract_datasource_reference(self, query: str) -> Optional[str]:
        """Extract datasource ID or name from query."""
        # Look for datasource ID pattern (UUID or alphanumeric)
        id_match = re.search(r'datasource[_\s]*id[:\s]+([a-zA-Z0-9\-]+)', query, re.IGNORECASE)
        if id_match:
            return id_match.group(1)
        
        # Look for datasource name in quotes
        name_match = re.search(r'datasource[:\s]+["\']([^"\']+)["\']', query, re.IGNORECASE)
        if name_match:
            return name_match.group(1)
        
        # Check conversation history for recent datasource mentions
        for msg in reversed(self.conversation_history):
            if msg["role"] == "assistant":
                # Look for datasource IDs in previous responses
                id_match = re.search(r'ID:\s*([a-zA-Z0-9\-]+)', msg["content"])
                if id_match:
                    return id_match.group(1)
        
        return None
    
    def _extract_view_reference(self, query: str) -> Optional[str]:
        """Extract view ID or name from query."""
        # Look for view ID pattern
        id_match = re.search(r'view[_\s]*id[:\s]+([a-zA-Z0-9\-]+)', query, re.IGNORECASE)
        if id_match:
            return id_match.group(1)
        
        # Look for view name in quotes
        name_match = re.search(r'view[:\s]+["\']([^"\']+)["\']', query, re.IGNORECASE)
        if name_match:
            return name_match.group(1)
        
        # Check conversation history
        for msg in reversed(self.conversation_history):
            if msg["role"] == "assistant":
                id_match = re.search(r'ID:\s*([a-zA-Z0-9\-]+)', msg["content"])
                if id_match:
                    return id_match.group(1)
        
        return None
    
    def _extract_filters(self, query: str) -> Optional[Dict[str, str]]:
        """Extract filter conditions from query."""
        filters = {}
        
        # Look for common filter patterns
        # Year filter
        year_match = re.search(r'(?:year|yr)[:\s=]+(\d{4})', query, re.IGNORECASE)
        if year_match:
            filters["year"] = year_match.group(1)
        
        # Region filter
        region_match = re.search(r'region[:\s=]+([A-Za-z]+)', query, re.IGNORECASE)
        if region_match:
            filters["region"] = region_match.group(1)
        
        # Generic key:value patterns
        kv_matches = re.findall(r'(\w+)[:\s=]+([A-Za-z0-9]+)', query, re.IGNORECASE)
        for key, value in kv_matches:
            if key.lower() not in ["year", "yr", "region"]:  # Avoid duplicates
                filters[key.lower()] = value
        
        return filters if filters else None
    
    def can_resolve_reference(self, reference: str) -> bool:
        """
        Check if a reference like "the first one" can be resolved from context.
        
        Args:
            reference: Reference string (e.g., "the first one", "that datasource")
            
        Returns:
            True if reference can be resolved
        """
        # Simple heuristic: check if we have recent tool results
        for msg in reversed(self.conversation_history):
            if msg["role"] == "assistant":
                # Check if message contains structured data (IDs, lists)
                if re.search(r'ID:\s*[a-zA-Z0-9\-]+', msg["content"]):
                    return True
        return False
    
    async def execute_plan(
        self,
        plan: List[Dict[str, Any]],
        previous_result: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Execute a multi-step plan.
        
        Args:
            plan: List of plan steps
            previous_result: Result from previous step (for chained operations)
            
        Returns:
            Dictionary with results from all steps
        """
        results = []
        
        for i, step in enumerate(plan):
            action = step["action"]
            arguments = step.get("arguments", {}).copy()
            
            # Handle steps that require previous result
            if step.get("requires_previous_result") and previous_result:
                # Extract ID from previous result
                if isinstance(previous_result, list) and len(previous_result) > 0:
                    # Use first item's ID
                    first_item = previous_result[0]
                    if isinstance(first_item, dict):
                        if "id" in first_item:
                            # Determine which ID field to use based on action
                            if action == "query_datasource":
                                arguments["datasource_id"] = first_item["id"]
                            elif action == "embed_view":
                                arguments["view_id"] = first_item["id"]
            
            # Execute tool
            if action in TOOL_REGISTRY:
                tool_result = await execute_tool(
                    tool_name=action,
                    arguments=arguments,
                    tableau_client=self.tableau_client
                )
                results.append({
                    "step": i + 1,
                    "action": action,
                    "result": tool_result
                })
                
                # Update previous_result for next step
                if tool_result["status"] == "success":
                    previous_result = tool_result["data"]
            elif action == "general_response":
                # Use AI to respond to general question
                if not self.ai_client:
                    from app.services.ai.client import UnifiedAIClient
                    from app.core.config import settings
                    self.ai_client = UnifiedAIClient(
                        gateway_url=settings.GATEWAY_BASE_URL,
                        api_key=self.api_key
                    )
                
                query = arguments.get("query", "")
                response = await self.ai_client.chat(
                    model=self.model,
                    messages=self.get_context() + [{"role": "user", "content": query}]
                )
                
                results.append({
                    "step": i + 1,
                    "action": action,
                    "result": {
                        "status": "success",
                        "data": {"content": response.content}
                    }
                })
            else:
                results.append({
                    "step": i + 1,
                    "action": action,
                    "result": {
                        "status": "error",
                        "message": f"Unknown action: {action}"
                    }
                })
        
        return {
            "plan": plan,
            "results": results,
            "success": all(r["result"]["status"] == "success" for r in results)
        }
    
    async def process_query(
        self,
        query: str,
        use_function_calling: bool = True
    ) -> Dict[str, Any]:
        """
        Process a user query with agentic capabilities.
        
        Args:
            query: User query string
            use_function_calling: Whether to use LLM function calling (True) or intent-based planning (False)
            
        Returns:
            Dictionary with response content and metadata
        """
        self.add_message("user", query)
        
        if use_function_calling:
            # Use LLM function calling
            return await self._process_with_function_calling(query)
        else:
            # Use intent-based planning
            return await self._process_with_intent(query)
    
    async def _process_with_function_calling(self, query: str) -> Dict[str, Any]:
        """Process query using LLM function calling."""
        if not self.ai_client:
            from app.services.ai.client import UnifiedAIClient
            from app.core.config import settings
            self.ai_client = UnifiedAIClient(
                gateway_url=settings.GATEWAY_BASE_URL,
                api_key=self.api_key
            )
        
        tools = get_tools()
        messages = self.get_context()
        
        # First call: let LLM decide which tools to use
        response = await self.ai_client.chat(
            model=self.model,
            messages=messages,
            functions=[tool["function"] for tool in tools],
            function_call="auto"
        )
        
        # Handle function calls
        if response.function_call:
            function_name = response.function_call.name
            import json
            try:
                arguments = json.loads(response.function_call.arguments)
            except json.JSONDecodeError:
                arguments = {}
            
            # Execute tool
            tool_result = await execute_tool(
                tool_name=function_name,
                arguments=arguments,
                tableau_client=self.tableau_client
            )
            
            # Format result
            formatted_result = format_tool_result(tool_result)
            
            # Add tool result to conversation
            messages.append({
                "role": "assistant",
                "content": None,
                "function_call": {
                    "name": function_name,
                    "arguments": response.function_call.arguments
                }
            })
            messages.append({
                "role": "function",
                "name": function_name,
                "content": formatted_result
            })
            
            # Second call: let LLM generate final response
            final_response = await self.ai_client.chat(
                model=self.model,
                messages=messages
            )
            
            self.add_message("assistant", final_response.content)
            
            return {
                "content": final_response.content,
                "tool_used": function_name,
                "tool_result": tool_result,
                "tokens_used": response.tokens_used + final_response.tokens_used
            }
        else:
            # No function call, just return response
            self.add_message("assistant", response.content)
            return {
                "content": response.content,
                "tokens_used": response.tokens_used
            }
    
    async def _process_with_intent(self, query: str) -> Dict[str, Any]:
        """Process query using intent-based planning."""
        intent = self.classify_intent(query)
        plan = self.create_plan(query, intent)
        
        # Execute plan
        execution_result = await self.execute_plan(plan)
        
        # Format response
        if execution_result["success"]:
            # Combine all tool results
            result_parts = []
            for step_result in execution_result["results"]:
                if step_result["result"]["status"] == "success":
                    formatted = format_tool_result(step_result["result"])
                    result_parts.append(formatted)
            
            content = "\n\n".join(result_parts)
        else:
            # Handle errors
            errors = [
                step_result["result"].get("message", "Unknown error")
                for step_result in execution_result["results"]
                if step_result["result"]["status"] == "error"
            ]
            content = f"I encountered an error: {'; '.join(errors)}"
        
        self.add_message("assistant", content)
        
        return {
            "content": content,
            "intent": intent.value,
            "plan": plan,
            "execution_result": execution_result
        }
