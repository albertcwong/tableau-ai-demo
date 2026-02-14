"""Summary agent graph implementation."""
import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.services.agents.summary.state import SummaryAgentState
from app.services.agents.summary.nodes.start import start_node
from app.services.agents.summary.nodes.get_data import get_data_node
from app.services.agents.summary.nodes.summarizer import summarize_node

logger = logging.getLogger(__name__)


def create_summary_graph() -> StateGraph:
    """
    Create Summary agent graph with tool-based data pipeline.
    Graph flow: start -> get_data (tools) -> summarizer -> END
    """
    workflow = StateGraph(SummaryAgentState)
    workflow.add_node("start", start_node)
    workflow.add_node("get_data", get_data_node)
    workflow.add_node("summarizer", summarize_node)
    workflow.set_entry_point("start")
    workflow.add_edge("start", "get_data")
    workflow.add_edge("get_data", "summarizer")
    workflow.add_edge("summarizer", END)
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
