"""Agent Service interface - request/response contracts."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """Context for agent invocation (datasources, views, embedded state)."""
    datasource_ids: List[str] = Field(default_factory=list)
    view_ids: List[str] = Field(default_factory=list)
    embedded_state: Optional[Dict[str, Any]] = None


class AgentConfigurable(BaseModel):
    """Common config for all agents. Agent-specific options go in agent_config."""
    model: str = "gpt-4"
    provider: str = "openai"
    site_id: str = ""
    conversation_id: Optional[int] = None
    agent_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Agent-specific options. VizQL: max_build_retries, max_execution_retries. Summary/Multi: summary_mode, tableau_auth_type.",
    )


class AgentInvocationRequest(BaseModel):
    """Request to invoke an agent."""
    agent_type: str = Field(..., description="vizql, summary, or multi_agent")
    version: Optional[str] = Field(None, description="For vizql: v1, v2, v3")
    user_query: str = Field(..., min_length=1)
    context: AgentContext = Field(default_factory=AgentContext)
    message_history: List[Dict[str, Any]] = Field(default_factory=list)
    configurable: AgentConfigurable = Field(default_factory=AgentConfigurable)
    stream: bool = False


class AgentInvocationResponse(BaseModel):
    """Response from agent invocation. Agent-specific data in metadata."""
    content: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Agent-specific data. VizQL: vizql_query, query_results. Summary: view_images, executive_summary. Multi: agents_used, execution_trace.",
    )
