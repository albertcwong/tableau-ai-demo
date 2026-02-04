"""Master Agent Router for intent classification and agent orchestration."""
import logging
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

from app.services.agents.vds_agent import VDSAgent
from app.services.agents.summary_agent import SummaryAgent
from app.services.ai.agent import Agent as AnalystAgent
from app.services.ai.client import UnifiedAIClient
from app.services.tableau.client import TableauClient

logger = logging.getLogger(__name__)


class AgentIntent(Enum):
    """Agent intent classification."""
    ANALYST = "analyst_agent"
    VIZQL = "vds_agent"
    SUMMARY = "summary_agent"
    MULTI_AGENT = "multi_agent"


class AgentRouter:
    """Router for selecting and orchestrating agents based on user intent."""
    
    def __init__(
        self,
        ai_client: Optional[UnifiedAIClient] = None,
        tableau_client: Optional[TableauClient] = None,
        model: str = "gpt-4",
        api_key: Optional[str] = None
    ):
        """Initialize agent router.
        
        Args:
            ai_client: Optional AI client instance
            tableau_client: Optional Tableau client instance
            model: AI model to use
            api_key: Optional API key for AI client
        """
        self.ai_client = ai_client
        self.tableau_client = tableau_client
        self.model = model
        self.api_key = api_key
        
        # Initialize agents
        self.analyst_agent = AnalystAgent(
            ai_client=ai_client,
            tableau_client=tableau_client,
            model=model,
            api_key=api_key
        )
        self.vds_agent = VDSAgent(
            ai_client=ai_client,
            tableau_client=tableau_client,
            model=model,
            api_key=api_key
        )
        self.summary_agent = SummaryAgent(
            ai_client=ai_client,
            tableau_client=tableau_client,
            model=model,
            api_key=api_key
        )
    
    def classify(self, user_query: str) -> str:
        """Classify user intent and return agent name.
        
        Args:
            user_query: User query string
            
        Returns:
            Agent name (analyst_agent, vds_agent, summary_agent)
        """
        intent = self.classify_intent(user_query)
        return intent.value
    
    def classify_intent(self, user_query: str) -> AgentIntent:
        """Classify user intent.
        
        Args:
            user_query: User query string
            
        Returns:
            AgentIntent enum value
        """
        query_lower = user_query.lower()
        
        # VizQL-specific keywords
        vizql_keywords = [
            "vizql", "construct query", "build query", "query syntax",
            "write a query", "create query", "generate query",
            "datasource schema", "schema", "field types"
        ]
        
        # Summary/export keywords
        summary_keywords = [
            "summarize", "export", "batch export", "multi-view",
            "aggregate", "combine views", "cross-view", "report",
            "generate report", "download data", "export data"
        ]
        
        # Multi-agent keywords (requires multiple agents)
        multi_keywords = [
            "query and summarize", "export and analyze",
            "construct query and execute", "build query then summarize"
        ]
        
        # Check for multi-agent intent first
        if any(keyword in query_lower for keyword in multi_keywords):
            return AgentIntent.MULTI_AGENT
        
        # Check for VizQL intent
        if any(keyword in query_lower for keyword in vizql_keywords):
            return AgentIntent.VIZQL
        
        # Check for summary intent
        if any(keyword in query_lower for keyword in summary_keywords):
            return AgentIntent.SUMMARY
        
        # Default to analyst agent
        return AgentIntent.ANALYST
    
    def select_agent(self, user_query: str):
        """Select appropriate agent for query.
        
        Args:
            user_query: User query string
            
        Returns:
            Agent instance
        """
        intent = self.classify_intent(user_query)
        
        if intent == AgentIntent.VIZQL:
            return self.vds_agent
        elif intent == AgentIntent.SUMMARY:
            return self.summary_agent
        elif intent == AgentIntent.MULTI_AGENT:
            # Return router itself for multi-agent workflows
            return self
        else:
            return self.analyst_agent
    
    async def execute_workflow(
        self,
        user_query: str,
        steps: Optional[List[Tuple[str, str]]] = None
    ) -> Dict[str, Any]:
        """Execute a multi-agent workflow.
        
        Args:
            user_query: User query string
            steps: Optional list of (agent_name, action) tuples.
                   If None, will infer from query.
            
        Returns:
            Dictionary with results from all steps
        """
        if steps is None:
            steps = self._infer_workflow_steps(user_query)
        
        results = {}
        previous_result = None
        
        for agent_name, action in steps:
            agent = self._get_agent_by_name(agent_name)
            
            if agent_name == "vds_agent" and action == "construct_query":
                # Extract datasource context from previous result or query
                datasource_context = self._extract_datasource_context(user_query, previous_result)
                result = agent.construct_query(user_query, datasource_context)
                results["query"] = result
                previous_result = result
            
            elif agent_name == "analyst_agent" and action == "execute_query":
                # Execute query using analyst agent
                if previous_result and "vizql" in previous_result:
                    # Use the constructed query
                    query_text = f"Execute this query: {previous_result.get('vizql', '')}"
                else:
                    query_text = user_query
                
                result = await agent.process_query(query_text)
                results["data"] = result
                previous_result = result
            
            elif agent_name == "summary_agent" and action == "summarize_results":
                # Summarize previous results
                if previous_result:
                    view_ids = self._extract_view_ids(previous_result)
                    if view_ids:
                        result = await agent.export_views(view_ids)
                        summary = await agent.aggregate_across_views(view_ids)
                        results["summary"] = {
                            "export": result,
                            "aggregation": summary
                        }
                    else:
                        # Summarize data directly
                        summary_text = await agent._generate_summary_text({
                            "datasets": [{"data": previous_result.get("data", []), "row_count": len(previous_result.get("data", []))}],
                            "total_rows": len(previous_result.get("data", [])),
                            "view_count": 1
                        })
                        results["summary"] = {"text": summary_text}
                else:
                    results["summary"] = {"error": "No data to summarize"}
            
            else:
                # Generic agent execution
                if hasattr(agent, "process_query"):
                    result = await agent.process_query(user_query)
                    results[agent_name] = result
                else:
                    results[agent_name] = {"error": f"Unknown action {action} for {agent_name}"}
        
        return results
    
    def _get_agent_by_name(self, agent_name: str):
        """Get agent instance by name."""
        if agent_name == "analyst_agent":
            return self.analyst_agent
        elif agent_name == "vds_agent":
            return self.vds_agent
        elif agent_name == "summary_agent":
            return self.summary_agent
        else:
            raise ValueError(f"Unknown agent: {agent_name}")
    
    def _infer_workflow_steps(self, user_query: str) -> List[Tuple[str, str]]:
        """Infer workflow steps from user query."""
        query_lower = user_query.lower()
        steps = []
        
        # Check for query construction + execution
        if "construct" in query_lower or "build" in query_lower:
            if "query" in query_lower:
                steps.append(("vds_agent", "construct_query"))
                if "execute" in query_lower or "run" in query_lower:
                    steps.append(("analyst_agent", "execute_query"))
        
        # Check for execution + summarization
        if "query" in query_lower and "summarize" in query_lower:
            steps.append(("analyst_agent", "execute_query"))
            steps.append(("summary_agent", "summarize_results"))
        
        # Default: just execute with analyst
        if not steps:
            steps.append(("analyst_agent", "execute_query"))
        
        return steps
    
    def _extract_datasource_context(self, query: str, previous_result: Any) -> Dict[str, Any]:
        """Extract datasource context from query or previous result."""
        context = {
            "id": None,
            "columns": [],
            "measures": [],
            "dimensions": [],
            "schema": {}
        }
        
        # Try to extract from previous result
        if previous_result and isinstance(previous_result, dict):
            if "datasource_id" in previous_result:
                context["id"] = previous_result["datasource_id"]
            if "columns" in previous_result:
                context["columns"] = previous_result["columns"]
        
        # Try to extract from query
        import re
        ds_match = re.search(r'datasource[_\s]*id[:\s]+([a-zA-Z0-9\-]+)', query, re.IGNORECASE)
        if ds_match:
            context["id"] = ds_match.group(1)
        
        return context
    
    def _extract_view_ids(self, result: Any) -> List[str]:
        """Extract view IDs from result."""
        view_ids = []
        
        if isinstance(result, dict):
            if "view_id" in result:
                view_ids.append(result["view_id"])
            if "views" in result:
                for view in result["views"]:
                    if isinstance(view, dict) and "id" in view:
                        view_ids.append(view["id"])
            if "tool_result" in result and isinstance(result["tool_result"], dict):
                data = result["tool_result"].get("data", [])
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "id" in item:
                            view_ids.append(item["id"])
        
        return view_ids
    
    async def route_and_execute(self, user_query: str) -> Dict[str, Any]:
        """Route query to appropriate agent and execute.
        
        Args:
            user_query: User query string
            
        Returns:
            Dictionary with agent response and metadata
        """
        intent = self.classify_intent(user_query)
        
        if intent == AgentIntent.MULTI_AGENT:
            return await self.execute_workflow(user_query)
        
        agent = self.select_agent(user_query)
        
        if agent == self.vds_agent:
            # VizQL agent needs datasource context
            datasource_context = self._extract_datasource_context(user_query, None)
            result = agent.construct_query(user_query, datasource_context)
            return {
                "agent": "vds_agent",
                "intent": intent.value,
                "result": result
            }
        
        elif agent == self.summary_agent:
            # Summary agent needs view IDs
            view_ids = self._extract_view_ids_from_query(user_query)
            if view_ids:
                result = await agent.export_views(view_ids)
                return {
                    "agent": "summary_agent",
                    "intent": intent.value,
                    "result": result
                }
            else:
                return {
                    "agent": "summary_agent",
                    "intent": intent.value,
                    "error": "No view IDs found in query"
                }
        
        else:
            # Analyst agent
            result = await agent.process_query(user_query)
            return {
                "agent": "analyst_agent",
                "intent": intent.value,
                "result": result
            }
    
    def _extract_view_ids_from_query(self, query: str) -> List[str]:
        """Extract view IDs from query."""
        import re
        view_ids = []
        
        # Look for view ID patterns
        id_matches = re.findall(r'view[_\s]*id[:\s]+([a-zA-Z0-9\-]+)', query, re.IGNORECASE)
        view_ids.extend(id_matches)
        
        # Look for UUIDs that might be view IDs
        uuid_matches = re.findall(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', query, re.IGNORECASE)
        view_ids.extend(uuid_matches)
        
        return list(set(view_ids))  # Remove duplicates
