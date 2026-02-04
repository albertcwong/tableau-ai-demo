"""Agent memory service for tracking queries and results."""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


class SessionMemory:
    """Session-level memory for tracking recent queries and results."""
    
    def __init__(self, max_queries: int = 50):
        """
        Initialize session memory.
        
        Args:
            max_queries: Maximum number of queries to remember
        """
        self.max_queries = max_queries
        self.queries: deque = deque(maxlen=max_queries)
        self.results: Dict[str, Any] = {}  # query_id -> result
        self.datasources_used: set = set()
        self.views_used: set = set()
    
    def add_query(
        self,
        query_id: str,
        user_query: str,
        agent_type: str,
        datasource_ids: List[str] = None,
        view_ids: List[str] = None,
        result: Optional[Any] = None
    ) -> None:
        """Add a query to memory."""
        query_entry = {
            "query_id": query_id,
            "user_query": user_query,
            "agent_type": agent_type,
            "timestamp": datetime.now().isoformat(),
            "datasource_ids": datasource_ids or [],
            "view_ids": view_ids or []
        }
        
        self.queries.append(query_entry)
        
        if datasource_ids:
            self.datasources_used.update(datasource_ids)
        
        if view_ids:
            self.views_used.update(view_ids)
        
        if result:
            self.results[query_id] = result
        
        logger.debug(f"Added query to memory: {query_id} ({agent_type})")
    
    def get_recent_queries(self, limit: int = 10, agent_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent queries, optionally filtered by agent type."""
        queries = list(self.queries)
        
        if agent_type:
            queries = [q for q in queries if q.get("agent_type") == agent_type]
        
        return queries[-limit:]
    
    def get_query_result(self, query_id: str) -> Optional[Any]:
        """Get result for a specific query."""
        return self.results.get(query_id)
    
    def get_common_datasources(self) -> List[str]:
        """Get list of commonly used datasources."""
        return list(self.datasources_used)
    
    def get_common_views(self) -> List[str]:
        """Get list of commonly used views."""
        return list(self.views_used)
    
    def clear(self) -> None:
        """Clear all memory."""
        self.queries.clear()
        self.results.clear()
        self.datasources_used.clear()
        self.views_used.clear()
        logger.info("Session memory cleared")


class ConversationMemory:
    """Conversation-level memory for tracking context across messages."""
    
    def __init__(self, conversation_id: int):
        """Initialize conversation memory."""
        self.conversation_id = conversation_id
        self.session_memory = SessionMemory()
        self.context_summary: Optional[str] = None
        self.last_summarized_at: Optional[datetime] = None
    
    def add_message(
        self,
        query_id: str,
        user_query: str,
        agent_type: str,
        response: str,
        datasource_ids: List[str] = None,
        view_ids: List[str] = None
    ) -> None:
        """Add a message exchange to memory."""
        self.session_memory.add_query(
            query_id=query_id,
            user_query=user_query,
            agent_type=agent_type,
            datasource_ids=datasource_ids,
            view_ids=view_ids,
            result=response
        )
    
    def get_context_summary(self, force_refresh: bool = False) -> str:
        """
        Get conversation context summary.
        
        Args:
            force_refresh: Force refresh of summary even if recent
        
        Returns:
            Summary string
        """
        # Refresh if forced or if summary is older than 10 minutes
        should_refresh = force_refresh
        if self.last_summarized_at:
            age = datetime.now() - self.last_summarized_at
            if age > timedelta(minutes=10):
                should_refresh = True
        
        if should_refresh or not self.context_summary:
            self._generate_summary()
        
        return self.context_summary or "No context available."
    
    def _generate_summary(self) -> None:
        """Generate a summary of conversation context."""
        recent_queries = self.session_memory.get_recent_queries(limit=10)
        
        if not recent_queries:
            self.context_summary = "No recent queries in this conversation."
            return
        
        # Build summary
        summary_parts = [f"Conversation has {len(recent_queries)} recent queries."]
        
        # Group by agent type
        agent_counts = {}
        for q in recent_queries:
            agent_type = q.get("agent_type", "unknown")
            agent_counts[agent_type] = agent_counts.get(agent_type, 0) + 1
        
        if agent_counts:
            summary_parts.append(f"Agent usage: {', '.join(f'{k}: {v}' for k, v in agent_counts.items())}")
        
        # Common datasources/views
        common_datasources = self.session_memory.get_common_datasources()
        common_views = self.session_memory.get_common_views()
        
        if common_datasources:
            summary_parts.append(f"Datasources used: {len(common_datasources)}")
        if common_views:
            summary_parts.append(f"Views used: {len(common_views)}")
        
        self.context_summary = " ".join(summary_parts)
        self.last_summarized_at = datetime.now()
        logger.debug(f"Generated context summary for conversation {self.conversation_id}")


# Global conversation memory store
_conversation_memories: Dict[int, ConversationMemory] = {}


def get_conversation_memory(conversation_id: int) -> ConversationMemory:
    """Get or create conversation memory for a conversation."""
    if conversation_id not in _conversation_memories:
        _conversation_memories[conversation_id] = ConversationMemory(conversation_id)
    
    return _conversation_memories[conversation_id]


def clear_conversation_memory(conversation_id: int) -> None:
    """Clear memory for a conversation."""
    if conversation_id in _conversation_memories:
        del _conversation_memories[conversation_id]
        logger.info(f"Cleared memory for conversation {conversation_id}")
