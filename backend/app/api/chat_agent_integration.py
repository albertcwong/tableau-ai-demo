"""Chat API integration with Agent Service - builds request and maps response."""
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from app.services.agent_service import (
    AgentInvocationRequest,
    AgentContext,
    AgentConfigurable,
    AgentService,
    AgentAdapters,
)
from app.services.agent_service.adapters import TableauAdapterImpl

logger = logging.getLogger(__name__)


def _normalize_msg(m: Any) -> Dict[str, Any]:
    """Extract role, content, extra_metadata from dict or Message ORM object."""
    if isinstance(m, dict):
        role = m.get("role", "user")
        content = m.get("content", "")
        meta = m.get("extra_metadata")
    else:
        role = getattr(m, "role", "user")
        content = getattr(m, "content", "") or ""
        meta = getattr(m, "extra_metadata", None)
    if hasattr(role, "value"):
        role = role.value.lower()
    elif isinstance(role, str):
        role = role.lower()
    else:
        role = "user"
    msg_dict: Dict[str, Any] = {"role": role, "content": content}
    if meta and isinstance(meta, dict):
        if meta.get("vizql_query"):
            msg_dict["query_draft"] = meta["vizql_query"]
        if meta.get("query_results"):
            msg_dict["query_results"] = meta["query_results"]
    return msg_dict


def build_agent_request(
    *,
    agent_type: str,
    user_query: str,
    datasource_ids: List[str],
    view_ids: List[str],
    message_history: List[Any],
    model: str,
    provider: str,
    conversation_id: int,
    embedded_state: Optional[Dict] = None,
    summary_mode: str = "full",
    tableau_auth_type: str = "connected_app",
    agent_version: Optional[str] = None,
    max_build_retries: Optional[int] = None,
    max_execution_retries: Optional[int] = None,
    site_id: str = "",
    stream: bool = False,
) -> AgentInvocationRequest:
    """Build AgentInvocationRequest from chat context. message_history can be dicts or Message ORM objects."""
    msg_list = [_normalize_msg(m) for m in message_history]

    agent_config: Dict[str, Any] = {}
    if agent_type == "vizql":
        if max_build_retries is not None:
            agent_config["max_build_retries"] = max_build_retries
        if max_execution_retries is not None:
            agent_config["max_execution_retries"] = max_execution_retries
    if agent_type in ("summary", "multi_agent"):
        agent_config["summary_mode"] = summary_mode
        agent_config["tableau_auth_type"] = tableau_auth_type

    return AgentInvocationRequest(
        agent_type=agent_type,
        version=agent_version,
        user_query=user_query,
        context=AgentContext(
            datasource_ids=datasource_ids,
            view_ids=view_ids,
            embedded_state=embedded_state,
        ),
        message_history=msg_list,
        configurable=AgentConfigurable(
            model=model,
            provider=provider,
            site_id=site_id,
            conversation_id=conversation_id,
            agent_config=agent_config,
        ),
        stream=stream,
    )


def build_adapters(tableau_client: Any, llm_client: Any = None) -> AgentAdapters:
    """Build AgentAdapters from clients."""
    tableau = TableauAdapterImpl(tableau_client) if tableau_client else None
    return AgentAdapters(tableau_client=tableau or tableau_client, llm_client=llm_client)


async def invoke_agent(
    request: AgentInvocationRequest,
    adapters: AgentAdapters,
) -> Any:
    """Invoke agent (non-streaming). Returns AgentInvocationResponse."""
    return await AgentService.invoke(request, adapters)


async def invoke_agent_stream(
    request: AgentInvocationRequest,
    adapters: AgentAdapters,
) -> AsyncIterator[str]:
    """Invoke agent with streaming. Yields SSE-formatted chunks."""
    async for chunk in AgentService.invoke_stream(request, adapters):
        yield chunk


def parse_stream_chunk(chunk: str) -> tuple:
    """Parse SSE chunk, return (message_type, content_data, metadata)."""
    if not chunk or not chunk.startswith("data: ") or "[DONE]" in chunk:
        return None, None, None
    try:
        import json
        body = chunk[6:].split("\n")[0]
        j = json.loads(body)
        mt = j.get("message_type")
        c = j.get("content", {})
        data = c.get("data", "") if isinstance(c, dict) else ""
        meta = j.get("metadata") or {}
        if mt == "metadata" and isinstance(c, dict) and isinstance(c.get("data"), dict):
            meta = c["data"]
        return mt, data, meta
    except Exception:
        return None, None, None
