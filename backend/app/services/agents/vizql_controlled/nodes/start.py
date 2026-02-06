"""Start node - initialize workflow."""
import logging
from typing import Dict, Any

from app.services.agents.vizql_controlled.state import VizQLGraphState

logger = logging.getLogger(__name__)


async def start_node(state: VizQLGraphState) -> Dict[str, Any]:
    """
    Initialize workflow and notify client.
    
    Duration: < 10ms
    """
    logger.info("Starting VizQL query graph")
    
    return {
        **state,
        "current_thought": "Starting query analysis...",
        "attempt": state.get("attempt", 1)
    }