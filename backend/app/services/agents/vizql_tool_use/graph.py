"""Tool-use VizQL agent graph - simplified 2-step approach."""
import logging
from langgraph.graph import StateGraph, END

from app.services.agents.vizql_tool_use.state import VizQLToolUseState
from app.services.agents.vizql_tool_use.nodes.start import start_node
from app.services.agents.vizql_tool_use.nodes.get_data import get_data_node
from app.services.agents.vizql_tool_use.nodes.summarize import summarize_node

logger = logging.getLogger(__name__)


def create_vizql_tool_use_agent():
    """
    Create simplified 2-step tool-use VizQL agent.
    
    Flow:
    1. start: No-op node to trigger immediate state update for UI
    2. get_data: Use tools to retrieve data
    3. summarize: Format data into natural language response
    
    No routing, no complex conditional edges - just a linear flow where
    the LLM decides which tools to use in step 2.
    """
    workflow = StateGraph(VizQLToolUseState)
    
    # Add nodes
    workflow.add_node("start", start_node)
    workflow.add_node("get_data", get_data_node)
    workflow.add_node("summarize", summarize_node)
    
    # Define linear flow
    workflow.set_entry_point("start")
    workflow.add_edge("start", "get_data")
    workflow.add_edge("get_data", "summarize")
    workflow.add_edge("summarize", END)
    
    logger.info("Tool-use VizQL agent graph created")
    
    return workflow.compile()


# Singleton instance
_agent_instance = None


def get_vizql_tool_use_agent():
    """Get singleton instance of tool-use VizQL agent."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = create_vizql_tool_use_agent()
    return _agent_instance
