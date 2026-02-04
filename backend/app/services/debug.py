"""Debug utilities for viewing graph execution."""
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class GraphDebugger:
    """Debugger for tracking graph execution state."""
    
    def __init__(self):
        self.executions: List[Dict[str, Any]] = []
        self.max_executions = 100  # Keep last 100 executions
    
    def record_execution(
        self,
        execution_id: str,
        agent_type: str,
        initial_state: Dict[str, Any],
        final_state: Dict[str, Any],
        execution_time: float,
        node_states: List[Dict[str, Any]] = None
    ) -> None:
        """Record a graph execution for debugging."""
        execution_record = {
            "execution_id": execution_id,
            "agent_type": agent_type,
            "timestamp": datetime.now().isoformat(),
            "execution_time": execution_time,
            "initial_state": {
                k: v for k, v in initial_state.items()
                if k not in ["api_key"]  # Don't log sensitive data
            },
            "final_state": {
                k: v for k, v in final_state.items()
                if k not in ["api_key"]
            },
            "node_states": node_states or [],
            "success": final_state.get("error") is None
        }
        
        self.executions.append(execution_record)
        
        # Keep only recent executions
        if len(self.executions) > self.max_executions:
            self.executions.pop(0)
        
        logger.debug(f"Recorded execution {execution_id} for {agent_type}")
    
    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get execution record by ID."""
        for exec_record in self.executions:
            if exec_record["execution_id"] == execution_id:
                return exec_record
        return None
    
    def get_recent_executions(self, limit: int = 10, agent_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent executions, optionally filtered by agent type."""
        executions = list(self.executions)
        
        if agent_type:
            executions = [e for e in executions if e.get("agent_type") == agent_type]
        
        return executions[-limit:]
    
    def clear(self) -> None:
        """Clear all execution records."""
        self.executions.clear()
        logger.info("Debug execution records cleared")


# Global debugger instance
_global_debugger = GraphDebugger()


def get_debugger() -> GraphDebugger:
    """Get the global debugger instance."""
    return _global_debugger
