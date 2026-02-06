"""Tool for extracting queries from conversation history."""
import logging
from typing import Dict, Any, Optional, List
import difflib

logger = logging.getLogger(__name__)


def get_prior_query(
    message_history: List[Dict[str, Any]],
    current_query: str,
    similarity_threshold: float = 0.8
) -> Optional[Dict[str, Any]]:
    """
    Search message history for similar queries.
    
    Args:
        message_history: Conversation history (list of messages)
        current_query: Current user query
        current_query_lower: Lowercase version for comparison
        similarity_threshold: How similar queries must be (0.0-1.0)
        
    Returns:
        {
            "query": {...},  # Prior VizQL query
            "message": "...",  # Original user message
            "similarity_score": float
        } or None if no similar query found
    """
    if not message_history:
        return None
    
    current_query_lower = current_query.lower().strip()
    
    # Search backwards through history for queries
    best_match = None
    best_score = 0.0
    
    for i in range(len(message_history) - 1, -1, -1):
        msg = message_history[i]
        
        # Check if this message has a query_draft or query_results
        query_draft = None
        user_message = ""
        
        # Extract user message
        if isinstance(msg, dict):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
            elif "user_query" in msg:
                user_message = msg.get("user_query", "")
            
            # Extract query draft
            query_draft = msg.get("query_draft") or msg.get("query")
        
        if not query_draft or not user_message:
            continue
        
        # Simple similarity check using string matching
        user_message_lower = user_message.lower().strip()
        
        # Calculate similarity
        similarity = difflib.SequenceMatcher(
            None,
            current_query_lower,
            user_message_lower
        ).ratio()
        
        # Also check for keyword overlap
        current_words = set(current_query_lower.split())
        prior_words = set(user_message_lower.split())
        if current_words and prior_words:
            word_overlap = len(current_words & prior_words) / len(current_words | prior_words)
            # Combine both metrics
            combined_score = (similarity * 0.6) + (word_overlap * 0.4)
        else:
            combined_score = similarity
        
        if combined_score > best_score and combined_score >= similarity_threshold:
            best_score = combined_score
            best_match = {
                "query": query_draft,
                "message": user_message,
                "similarity_score": combined_score,
                "index": i
            }
    
    if best_match:
        logger.info(
            f"✓ Found similar query in history (score: {best_score:.2f}): "
            f"{best_match['message'][:50]}..."
        )
        return best_match
    
    logger.debug(f"No similar query found in history (threshold: {similarity_threshold})")
    return None
