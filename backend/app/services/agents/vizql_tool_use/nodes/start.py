"""Start node for tool-use VizQL agent - no-op to trigger immediate state update."""
import logging
from typing import Dict, Any

from app.services.agents.vizql_tool_use.state import VizQLToolUseState

logger = logging.getLogger(__name__)


async def start_node(state: VizQLToolUseState) -> Dict[str, Any]:
    """
    No-op start node that immediately yields state update.
    
    This allows the UI to start showing reasoning steps counter/timer
    immediately when the graph execution begins.
    """
    logger.info("=== START NODE ===")
    logger.info(f"User query: {state.get('user_query', '')[:100]}")
    
    # Return state unchanged, optionally add a starting thought
    return {
        **state,
        "current_thought": "Starting query analysis..."
    }
