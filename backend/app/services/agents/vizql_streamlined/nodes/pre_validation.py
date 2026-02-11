"""Pre-validation node: emits a reasoning step only when the query was rewritten by auto-corrections."""
import logging
from typing import Dict, Any

from app.services.agents.vizql_streamlined.state import StreamlinedVizQLState

logger = logging.getLogger(__name__)


async def pre_validation_node(state: StreamlinedVizQLState) -> Dict[str, Any]:
    """
    Pass-through node between build_query and validate_query.
    Emits current_thought and step_metadata only when query was rewritten by pre-validation corrections.
    """
    query_was_rewritten = state.get("query_was_rewritten", False)
    pre_validation_changes = state.get("pre_validation_changes", [])
    query_draft = state.get("query_draft")

    if not query_was_rewritten or not pre_validation_changes or not query_draft:
        # Pass through without adding a reasoning step (clear current_thought to avoid duplicate)
        return {**state, "current_thought": None}

    changes_str = ", ".join(pre_validation_changes)
    thought = f"Applied pre-validation corrections: {changes_str}"
    logger.info(thought)

    return {
        **state,
        "current_thought": thought,
        "step_metadata": {
            "query_draft": query_draft,
            "tool_result_summary": f"Pre-validation: {changes_str}",
        },
    }
