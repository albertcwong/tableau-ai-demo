"""Multi-agent orchestration system for agent-to-agent communication."""
import logging
from typing import Dict, Any, List, Optional, TypedDict, Annotated, Sequence, TYPE_CHECKING
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.services.agents.graph_factory import AgentGraphFactory
from app.services.agents.base_state import BaseAgentState

if TYPE_CHECKING:
    from app.services.tableau.client import TableauClient

logger = logging.getLogger(__name__)


class MultiAgentState(TypedDict):
    """State for multi-agent orchestration."""
    
    # Original query
    user_query: str
    
    # Agent execution plan
    execution_plan: List[Dict[str, Any]]
    completed_steps: List[int]  # Track completed steps for parallel execution
    
    # Results from each agent
    agent_results: Dict[str, Any]
    
    # Handoff data between agents
    handoff_data: Optional[Dict[str, Any]]
    
    # Final answer
    final_answer: Optional[str]
    error: Optional[str]
    
    # Metadata
    agents_used: List[str]
    execution_trace: List[Dict[str, Any]]
    
    # AI client configuration
    api_key: Optional[str]
    model: Optional[str]
    
    # Context
    context_datasources: List[str]
    context_views: List[str]

    # Tableau client (user's selected config from Connect flow)
    tableau_client: Optional["TableauClient"]


class MultiAgentOrchestrator:
    """Orchestrates multi-agent workflows with agent-to-agent communication."""
    
    def __init__(self, model: str = "gpt-4", provider: str = "openai"):
        """Initialize orchestrator.
        
        Args:
            model: Model to use for planning and coordination
            provider: Provider name (e.g., openai, apple)
        """
        self.model = model
        self.provider = provider
    
    async def plan_workflow(self, user_query: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Plan multi-agent workflow from user query.
        
        Args:
            user_query: User's query
            context: Context (datasources, views, etc.)
            
        Returns:
            List of workflow steps, each with agent_type and action
        """
        from app.services.ai.client import UnifiedAIClient
        from app.core.config import settings
        
        ai_client = UnifiedAIClient(
            gateway_url=settings.GATEWAY_BASE_URL
        )
        
        planning_prompt = f"""Analyze this user query and determine if it requires multiple agents to complete.

User Query: {user_query}

Available Agents:
- vizql: Constructs and executes VizQL queries
- summary: Summarizes and analyzes view data
- general: General purpose chat and analysis

Context:
- Datasources: {context.get('datasources', [])}
- Views: {context.get('views', [])}

Determine if this query requires:
1. A single agent (return single step)
2. Multiple agents in sequence (e.g., VizQL to query data, then Summary to analyze results)
3. Multiple agents in parallel (e.g., query multiple datasources simultaneously)

Return a JSON array of steps, each with:
- agent_type: "vizql", "summary", or "general"
- action: What this agent should do
- depends_on: Index of previous step this depends on (null if none)
- input_data: What data to pass from previous step (if any)

Example for "query sales by region and then summarize the results":
[
  {{
    "agent_type": "vizql",
    "action": "query sales data grouped by region",
    "depends_on": null,
    "input_data": null
  }},
  {{
    "agent_type": "summary",
    "action": "summarize the query results",
    "depends_on": 0,
    "input_data": "query_results"
  }}
]

Return ONLY the JSON array, no other text."""

        try:
            response = await ai_client.chat(
                model=self.model,
                provider=self.provider,
                messages=[
                    {"role": "system", "content": "You are a workflow planner for multi-agent systems. Return only valid JSON."},
                    {"role": "user", "content": planning_prompt}
                ]
            )
            
            import json
            plan = json.loads(response.content)
            return plan if isinstance(plan, list) else [plan]
        except Exception as e:
            logger.error(f"Error planning workflow: {e}")
            # Fallback: single agent workflow
            return [{
                "agent_type": "general",
                "action": user_query,
                "depends_on": None,
                "input_data": None
            }]
    
    async def execute_agent_step(
        self,
        agent_type: str,
        action: str,
        input_data: Optional[Dict[str, Any]],
        context: Dict[str, Any],
        tableau_client: Optional["TableauClient"] = None
    ) -> Dict[str, Any]:
        """Execute a single agent step.
        
        Args:
            agent_type: Type of agent to execute
            action: What the agent should do
            input_data: Data from previous steps
            context: Context (datasources, views)
            tableau_client: User's Tableau client (from Connect flow)
            
        Returns:
            Result from agent execution
        """
        logger.info(f"Executing {agent_type} agent: {action}")
        
        # Prepare state for agent
        if agent_type == "vizql":
            from app.core.config import settings
            from app.core.database import get_db
            from app.services.agent_config_service import AgentConfigService
            
            # Get default vizql version from DB config
            db = next(get_db())
            try:
                agent_config_service = AgentConfigService(db)
                vizql_version = agent_config_service.get_default_version('vizql') or 'v3'
                retry_settings = agent_config_service.get_agent_settings('vizql')
                max_build_retries = retry_settings.get('max_build_retries')
                max_execution_retries = retry_settings.get('max_execution_retries')
            finally:
                db.close()
            
            graph = AgentGraphFactory.create_vizql_graph(
                version=vizql_version,
                max_build_retries=max_build_retries,
                max_execution_retries=max_execution_retries
            )
            message_history = []
            if input_data:
                message_history = [{"role": "system", "content": f"Previous step results: {input_data}"}]
            
            # Initialize state based on version
            if vizql_version == "v3":
                state = {
                    "user_query": action,
                    "agent_type": "vizql",
                    "context_datasources": context.get("datasources", []),
                    "context_views": context.get("views", []),
                    "messages": message_history,
                    "tool_calls": [],
                    "tool_results": [],
                    "current_thought": None,
                    "final_answer": None,
                    "error": None,
                    "confidence": None,
                    "processing_time": None,
                    "model": self.model,
                    "provider": self.provider,
                    "site_id": (tableau_client.site_id or "") if tableau_client else settings.TABLEAU_SITE_ID,
                    "build_attempt": 1,
                    "execution_attempt": 1,
                    "query_version": 0,
                    "reasoning_steps": [],
                    "build_errors": None,
                    "execution_errors": None,
                    "enriched_schema": None,
                    "schema": None,
                }
            elif vizql_version == "v2":
                state = {
                    "user_query": action,
                    "message_history": message_history,
                    "site_id": (tableau_client.site_id or "") if tableau_client else settings.TABLEAU_SITE_ID,
                    "datasource_id": context.get("datasources", [None])[0] if context.get("datasources") else None,
                    "tableau_client": tableau_client,
                    "raw_data": None,
                    "tool_calls": [],
                    "final_answer": None,
                    "error": None,
                    "model": self.model,
                    "provider": self.provider,
                }
            else:  # v1
                state = {
                    "user_query": action,
                    "agent_type": "vizql",
                    "context_datasources": context.get("datasources", []),
                    "context_views": context.get("views", []),
                    "messages": [],
                    "tool_calls": [],
                    "tool_results": [],
                    "current_thought": None,
                    "final_answer": None,
                    "error": None,
                    "confidence": None,
                    "processing_time": None,
                    "model": self.model,
                    "provider": self.provider,
                    "schema": None,
                    "required_measures": [],
                    "required_dimensions": [],
                    "required_filters": {},
                    "query_draft": None,
                    "query_version": 0,
                    "is_valid": False,
                    "validation_errors": [],
                    "validation_suggestions": [],
                    "query_results": None,
                    "execution_error": None,
                }
            
            result = await graph.ainvoke(state)
            return {
                "agent_type": "vizql",
                "result": result.get("final_answer"),
                "query_results": result.get("query_results"),
                "state": result
            }
        
        elif agent_type == "summary":
            graph = AgentGraphFactory.create_summary_graph()
            state = {
                "user_query": action,
                "agent_type": "summary",
                "context_datasources": context.get("datasources", []),
                "context_views": context.get("views", []),
                "messages": [],
                "tool_calls": [],
                "tool_results": [],
                "current_thought": None,
                "final_answer": None,
                "error": None,
                "confidence": None,
                "processing_time": None,
                "model": self.model,
                "provider": self.provider,
            }
            
            # If we have query results from VizQL agent, use them
            if input_data and "query_results" in input_data:
                state["view_data"] = input_data["query_results"]
            
            config = {"configurable": {"thread_id": f"summary-{id(self)}", "tableau_client": tableau_client}}
            result = await graph.ainvoke(state, config=config)
            return {
                "agent_type": "summary",
                "result": result.get("final_answer"),
                "insights": result.get("key_insights", []),
                "state": result
            }
        
        else:
            # LLM fallback for non-vizql/summary steps (internal use only, not user-selectable)
            from app.services.ai.client import UnifiedAIClient
            from app.core.config import settings
            
            ai_client = UnifiedAIClient(
                gateway_url=settings.GATEWAY_BASE_URL
            )
            
            messages = [{"role": "user", "content": action}]
            if input_data:
                messages.insert(0, {
                    "role": "system",
                    "content": f"Previous step results: {input_data}"
                })
            
            response = await ai_client.chat(
                model=self.model,
                provider=self.provider,
                messages=messages
            )
            
            return {
                "agent_type": "llm_fallback",  # Internal fallback, not user-selectable
                "result": response.content,
                "state": {}
            }
    
    async def execute_workflow(
        self,
        user_query: str,
        context: Dict[str, Any],
        tableau_client: Optional["TableauClient"] = None
    ) -> Dict[str, Any]:
        """Execute a multi-agent workflow with support for parallel execution.
        
        Args:
            user_query: User's query
            context: Context (datasources, views)
            tableau_client: User's Tableau client (from Connect flow)
            
        Returns:
            Final result from workflow execution
        """
        # Plan workflow
        plan = await self.plan_workflow(user_query, context)
        
        logger.info(f"Planned workflow with {len(plan)} steps")
        
        # Build dependency graph
        dependency_graph = self._build_dependency_graph(plan)
        
        # Execute steps respecting dependencies (parallel where possible)
        results = {}
        execution_trace = []
        completed_steps = set()
        
        while len(completed_steps) < len(plan):
            # Find steps that can run in parallel (no dependencies or dependencies completed)
            ready_steps = [
                i for i, step in enumerate(plan)
                if i not in completed_steps
                and all(dep in completed_steps for dep in dependency_graph.get(i, []))
            ]
            
            if not ready_steps:
                # Circular dependency or error - execute remaining sequentially
                ready_steps = [i for i in range(len(plan)) if i not in completed_steps]
            
            # Execute ready steps in parallel
            import asyncio
            step_tasks = []
            for step_idx in ready_steps:
                step = plan[step_idx]
                
                # Get input data from dependent steps
                input_data = None
                if step.get("depends_on") is not None:
                    dep_idx = step["depends_on"]
                    if dep_idx in results:
                        input_data = results[dep_idx]
                
                # Create task for this step
                task = self.execute_agent_step(
                    agent_type=step["agent_type"],
                    action=step["action"],
                    input_data=input_data,
                    context=context,
                    tableau_client=tableau_client
                )
                step_tasks.append((step_idx, task))
            
            # Execute all ready steps in parallel
            if step_tasks:
                step_indices, tasks = zip(*step_tasks)
                step_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Store results
                for step_idx, step_result in zip(step_indices, step_results):
                    if isinstance(step_result, Exception):
                        logger.error(f"Error executing step {step_idx}: {step_result}")
                        results[step_idx] = {
                            "agent_type": plan[step_idx]["agent_type"],
                            "error": str(step_result),
                            "result": None
                        }
                    else:
                        results[step_idx] = step_result
                    
                    completed_steps.add(step_idx)
                    execution_trace.append({
                        "step": step_idx,
                        "agent_type": plan[step_idx]["agent_type"],
                        "action": plan[step_idx]["action"],
                        "result": (step_result.get("result", "") if not isinstance(step_result, Exception) else "Error")[:200],
                        "parallel": len(ready_steps) > 1
                    })
        
        # Combine results into final answer
        final_answer = self._combine_results(results, plan)
        
        return {
            "final_answer": final_answer,
            "execution_plan": plan,
            "agent_results": results,
            "execution_trace": execution_trace,
            "agents_used": [step["agent_type"] for step in plan]
        }
    
    def _build_dependency_graph(self, plan: List[Dict[str, Any]]) -> Dict[int, List[int]]:
        """Build dependency graph from execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Dictionary mapping step index to list of dependent step indices
        """
        graph = {}
        for i, step in enumerate(plan):
            deps = []
            if step.get("depends_on") is not None:
                deps.append(step["depends_on"])
            graph[i] = deps
        return graph
    
    def _combine_results(self, results: Dict[int, Dict[str, Any]], plan: List[Dict[str, Any]]) -> str:
        """Combine results from multiple agents into final answer.
        
        Args:
            results: Results from each step
            plan: Original execution plan
            
        Returns:
            Combined final answer
        """
        if len(results) == 1:
            return results[0].get("result", "No result available")
        
        # Combine multiple results
        combined_parts = []
        for i, step in enumerate(plan):
            if i in results:
                result = results[i]
                agent_type = step["agent_type"]
                combined_parts.append(
                    f"[{agent_type.upper()} Agent]: {result.get('result', 'No result')}"
                )
        
        return "\n\n".join(combined_parts)


def create_multi_agent_graph() -> StateGraph:
    """Create multi-agent orchestration graph.
    
    Returns:
        Compiled StateGraph for multi-agent orchestration
    """
    workflow = StateGraph(MultiAgentState)
    
    orchestrator = MultiAgentOrchestrator()
    
    async def plan_node(state: MultiAgentState) -> Dict[str, Any]:
        """Plan the workflow."""
        plan = await orchestrator.plan_workflow(
            state["user_query"],
            {
                "datasources": state.get("context_datasources", []),
                "views": state.get("context_views", [])
            }
        )
        return {
            "execution_plan": plan,
            "completed_steps": [],
            "agent_results": {},
            "execution_trace": []
        }
    
    async def execute_step_node(state: MultiAgentState) -> Dict[str, Any]:
        """Execute current step(s) - supports parallel execution."""
        plan = state["execution_plan"]
        completed_steps = set(state.get("completed_steps", []))
        agent_results = state.get("agent_results", {}).copy()
        execution_trace = state.get("execution_trace", []).copy()
        
        # Build dependency graph
        dependency_graph = {}
        for i, step in enumerate(plan):
            deps = []
            if step.get("depends_on") is not None:
                deps.append(step["depends_on"])
            dependency_graph[i] = deps
        
        # Find steps ready to execute (no dependencies or dependencies completed)
        ready_steps = [
            i for i, step in enumerate(plan)
            if i not in completed_steps
            and all(dep in completed_steps for dep in dependency_graph.get(i, []))
        ]
        
        if not ready_steps:
            # All steps complete or circular dependency
            if len(completed_steps) >= len(plan):
                return {"final_answer": "Workflow complete"}
            # Fallback: execute remaining sequentially
            ready_steps = [i for i in range(len(plan)) if i not in completed_steps]
        
        # Execute ready steps in parallel
        import asyncio
        step_tasks = []
        for step_idx in ready_steps:
            step = plan[step_idx]
            
            # Get input data from dependent step
            input_data = None
            if step.get("depends_on") is not None:
                dep_idx = step["depends_on"]
                if dep_idx in agent_results:
                    input_data = agent_results[dep_idx]
            
            # Create task
            task = orchestrator.execute_agent_step(
                agent_type=step["agent_type"],
                action=step["action"],
                input_data=input_data,
                context={
                    "datasources": state.get("context_datasources", []),
                    "views": state.get("context_views", [])
                },
                tableau_client=state.get("tableau_client")
            )
            step_tasks.append((step_idx, task))
        
        # Execute in parallel
        if step_tasks:
            step_indices, tasks = zip(*step_tasks)
            step_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Store results
            for step_idx, step_result in zip(step_indices, step_results):
                if isinstance(step_result, Exception):
                    logger.error(f"Error executing step {step_idx}: {step_result}")
                    agent_results[step_idx] = {
                        "agent_type": plan[step_idx]["agent_type"],
                        "error": str(step_result),
                        "result": None
                    }
                else:
                    agent_results[step_idx] = step_result
                
                completed_steps.add(step_idx)
                execution_trace.append({
                    "step": step_idx,
                    "agent_type": plan[step_idx]["agent_type"],
                    "action": plan[step_idx]["action"],
                    "result": (step_result.get("result", "") if not isinstance(step_result, Exception) else "Error")[:200],
                    "parallel": len(ready_steps) > 1
                })
        
        return {
            "agent_results": agent_results,
            "completed_steps": list(completed_steps),
            "execution_trace": execution_trace
        }
    
    async def combine_results_node(state: MultiAgentState) -> Dict[str, Any]:
        """Combine results into final answer."""
        final_answer = orchestrator._combine_results(
            state["agent_results"],
            state["execution_plan"]
        )
        return {"final_answer": final_answer}
    
    # Add nodes
    workflow.add_node("plan", plan_node)
    workflow.add_node("execute_step", execute_step_node)
    workflow.add_node("combine_results", combine_results_node)
    
    # Set entry point
    workflow.set_entry_point("plan")
    
    # Add edges
    workflow.add_edge("plan", "execute_step")
    
    def route_after_execution(state: MultiAgentState) -> str:
        """Route after execution - continue or combine."""
        completed_steps = set(state.get("completed_steps", []))
        if len(completed_steps) >= len(state["execution_plan"]):
            return "combine_results"
        return "execute_step"
    
    workflow.add_conditional_edges(
        "execute_step",
        route_after_execution,
        {
            "execute_step": "execute_step",
            "combine_results": "combine_results"
        }
    )
    
    workflow.add_edge("combine_results", END)
    
    # Compile with checkpointing
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
