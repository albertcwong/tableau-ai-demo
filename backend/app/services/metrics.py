"""Metrics tracking for agent performance."""
import logging
import time
from typing import Dict, Any, Optional
from collections import defaultdict
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class NodeMetrics:
    """Metrics for a single graph node."""
    node_name: str
    call_count: int = 0
    total_time: float = 0.0
    error_count: int = 0
    last_called: Optional[datetime] = None
    
    @property
    def average_time(self) -> float:
        """Calculate average execution time."""
        return self.total_time / self.call_count if self.call_count > 0 else 0.0
    
    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        return (self.error_count / self.call_count * 100) if self.call_count > 0 else 0.0


@dataclass
class AgentMetrics:
    """Metrics for an agent type."""
    agent_type: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_time: float = 0.0
    node_metrics: Dict[str, NodeMetrics] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        return (self.successful_executions / self.total_executions * 100) if self.total_executions > 0 else 0.0
    
    @property
    def average_time(self) -> float:
        """Calculate average execution time."""
        return self.total_time / self.total_executions if self.total_executions > 0 else 0.0


class MetricsCollector:
    """Collects and tracks agent performance metrics."""
    
    def __init__(self):
        self.agent_metrics: Dict[str, AgentMetrics] = defaultdict(lambda: AgentMetrics(agent_type=""))
        self._lock = False  # Simple flag for thread safety (can be upgraded to threading.Lock if needed)
    
    def record_node_execution(
        self,
        agent_type: str,
        node_name: str,
        execution_time: float,
        success: bool = True
    ) -> None:
        """Record a node execution."""
        if agent_type not in self.agent_metrics:
            self.agent_metrics[agent_type] = AgentMetrics(agent_type=agent_type)
        
        agent_metric = self.agent_metrics[agent_type]
        
        # Update node metrics
        if node_name not in agent_metric.node_metrics:
            agent_metric.node_metrics[node_name] = NodeMetrics(node_name=node_name)
        
        node_metric = agent_metric.node_metrics[node_name]
        node_metric.call_count += 1
        node_metric.total_time += execution_time
        node_metric.last_called = datetime.now()
        
        if not success:
            node_metric.error_count += 1
        
        logger.debug(f"Recorded {agent_type}.{node_name}: {execution_time:.3f}s (success: {success})")
    
    def record_agent_execution(
        self,
        agent_type: str,
        execution_time: float,
        success: bool = True
    ) -> None:
        """Record an agent execution."""
        if agent_type not in self.agent_metrics:
            self.agent_metrics[agent_type] = AgentMetrics(agent_type=agent_type)
        
        agent_metric = self.agent_metrics[agent_type]
        agent_metric.total_executions += 1
        agent_metric.total_time += execution_time
        
        if success:
            agent_metric.successful_executions += 1
        else:
            agent_metric.failed_executions += 1
        
        logger.info(f"Recorded {agent_type} execution: {execution_time:.3f}s (success: {success})")
    
    def get_agent_metrics(self, agent_type: str) -> Optional[AgentMetrics]:
        """Get metrics for a specific agent type."""
        return self.agent_metrics.get(agent_type)
    
    def get_all_metrics(self) -> Dict[str, AgentMetrics]:
        """Get all agent metrics."""
        return dict(self.agent_metrics)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        summary = {
            "agents": {},
            "overall": {
                "total_executions": 0,
                "total_successful": 0,
                "total_failed": 0,
                "total_time": 0.0
            }
        }
        
        for agent_type, metrics in self.agent_metrics.items():
            summary["agents"][agent_type] = {
                "total_executions": metrics.total_executions,
                "success_rate": metrics.success_rate,
                "average_time": metrics.average_time,
                "nodes": {
                    node_name: {
                        "call_count": node_metric.call_count,
                        "average_time": node_metric.average_time,
                        "error_rate": node_metric.error_rate
                    }
                    for node_name, node_metric in metrics.node_metrics.items()
                }
            }
            
            summary["overall"]["total_executions"] += metrics.total_executions
            summary["overall"]["total_successful"] += metrics.successful_executions
            summary["overall"]["total_failed"] += metrics.failed_executions
            summary["overall"]["total_time"] += metrics.total_time
        
        if summary["overall"]["total_executions"] > 0:
            summary["overall"]["success_rate"] = (
                summary["overall"]["total_successful"] / 
                summary["overall"]["total_executions"] * 100
            )
            summary["overall"]["average_time"] = (
                summary["overall"]["total_time"] / 
                summary["overall"]["total_executions"]
            )
        
        return summary
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.agent_metrics.clear()
        logger.info("Metrics reset")


# Global metrics collector
_global_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector."""
    return _global_metrics


def track_node_execution(agent_type: str, node_name: str):
    """Decorator to track node execution time."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                execution_time = time.time() - start_time
                _global_metrics.record_node_execution(
                    agent_type=agent_type,
                    node_name=node_name,
                    execution_time=execution_time,
                    success=success
                )
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                execution_time = time.time() - start_time
                _global_metrics.record_node_execution(
                    agent_type=agent_type,
                    node_name=node_name,
                    execution_time=execution_time,
                    success=success
                )
        
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
