"""Agent Service invoker - single entry point for agent execution."""
import logging
from typing import Any, AsyncIterator, Dict, Optional

from app.services.agent_service.interface import (
    AgentInvocationRequest,
    AgentInvocationResponse,
)

logger = logging.getLogger(__name__)


class AgentAdapters:
    """Injectable adapters for agent execution. Phase 2 will use protocol-based adapters."""

    def __init__(
        self,
        tableau_client: Any = None,
        llm_client: Any = None,
    ):
        self.tableau_client = tableau_client
        self.llm_client = llm_client


class AgentService:
    """Pluggable agent service - invokes agents via narrow interface."""

    @staticmethod
    async def invoke(
        request: AgentInvocationRequest,
        adapters: AgentAdapters,
    ) -> AgentInvocationResponse:
        """Invoke agent (non-streaming)."""
        if request.agent_type == "vizql":
            return await AgentService._invoke_vizql(request, adapters, stream=False)
        elif request.agent_type == "summary":
            return await AgentService._invoke_summary(request, adapters, stream=False)
        elif request.agent_type == "multi_agent":
            return await AgentService._invoke_multi_agent(request, adapters)
        raise ValueError(f"Unknown agent_type: {request.agent_type}")

    @staticmethod
    async def invoke_stream(
        request: AgentInvocationRequest,
        adapters: AgentAdapters,
    ) -> AsyncIterator[str]:
        """Invoke agent with streaming. Yields SSE-formatted chunks."""
        if request.agent_type == "vizql":
            async for chunk in AgentService._invoke_vizql_stream(request, adapters):
                yield chunk
        elif request.agent_type == "summary":
            async for chunk in AgentService._invoke_summary_stream(request, adapters):
                yield chunk
        elif request.agent_type == "multi_agent":
            # Multi-agent doesn't support streaming in same way - run and yield final
            result = await AgentService._invoke_multi_agent(request, adapters)
            from app.api.models import AgentMessageChunk, AgentMessageContent
            chunk = AgentMessageChunk(
                message_type="final_answer",
                content=AgentMessageContent(type="text", data=result.content or result.error or ""),
                timestamp=__import__("time").time(),
            )
            yield chunk.to_sse_format()
            yield "data: [DONE]\n\n"
        else:
            raise ValueError(f"Unknown agent_type: {request.agent_type}")

    @staticmethod
    async def _invoke_vizql(
        request: AgentInvocationRequest,
        adapters: AgentAdapters,
        stream: bool,
    ) -> AgentInvocationResponse:
        from app.services.agents.graph_factory import AgentGraphFactory

        ac = request.configurable.agent_config
        graph = AgentGraphFactory.create_vizql_graph(
            version=request.version or "v3",
            max_build_retries=ac.get("max_build_retries"),
            max_execution_retries=ac.get("max_execution_retries"),
        )
        ctx = request.context
        cfg = request.configurable

        message_history = []
        for m in request.message_history:
            msg_dict = {"role": m.get("role", "user"), "content": m.get("content", "")}
            message_history.append(msg_dict)

        if request.version == "v3":
            initial_state = {
                "user_query": request.user_query,
                "agent_type": "vizql",
                "context_datasources": ctx.datasource_ids,
                "context_views": ctx.view_ids,
                "messages": message_history,
                "tool_calls": [],
                "tool_results": [],
                "current_thought": None,
                "final_answer": None,
                "error": None,
                "confidence": None,
                "processing_time": None,
                "model": cfg.model,
                "provider": cfg.provider,
                "site_id": cfg.site_id,
                "build_attempt": 1,
                "execution_attempt": 1,
                "query_version": 0,
                "reasoning_steps": [],
                "build_errors": None,
                "execution_errors": None,
                "enriched_schema": None,
                "schema": None,
            }
        else:
            initial_state = {
                "user_query": request.user_query,
                "agent_type": "vizql",
                "context_datasources": ctx.datasource_ids,
                "context_views": ctx.view_ids,
                "messages": message_history,
                "tool_calls": [],
                "tool_results": [],
                "current_thought": None,
                "final_answer": None,
                "error": None,
                "confidence": None,
                "processing_time": None,
                "model": cfg.model,
                "provider": cfg.provider,
                "site_id": cfg.site_id,
                "schema": None,
                "required_measures": [],
                "required_dimensions": [],
                "required_filters": {},
                "query_draft": None,
                "query_version": 0,
                "is_valid": False,
                "validation_errors": [],
                "validation_suggestions": [],
                "query_results": None,
                "execution_error": None,
            }

        config = {"configurable": {"thread_id": f"vizql-{cfg.conversation_id or 0}", "tableau_client": adapters.tableau_client}}
        final_state = await graph.ainvoke(initial_state, config=config)

        content = final_state.get("final_answer") or final_state.get("formatted_response")
        if not content and final_state.get("error"):
            content = f"Error: {final_state['error']}"
        if not content and final_state.get("execution_error"):
            content = f"Execution error: {final_state['execution_error']}"

        vizql_query = final_state.get("query_draft") or final_state.get("query") or final_state.get("validated_query")
        query_results = final_state.get("query_results")
        metadata = {"reasoning_steps": final_state.get("reasoning_steps")}
        if vizql_query is not None:
            metadata["vizql_query"] = vizql_query
        if query_results is not None:
            metadata["query_results"] = query_results

        return AgentInvocationResponse(
            content=content or "Query execution completed.",
            error=final_state.get("error"),
            metadata=metadata,
        )

    @staticmethod
    async def _invoke_vizql_stream(
        request: AgentInvocationRequest,
        adapters: AgentAdapters,
    ) -> AsyncIterator[str]:
        from app.api.models import AgentMessageChunk, AgentMessageContent
        from app.services.agents.graph_factory import AgentGraphFactory

        ac = request.configurable.agent_config
        graph = AgentGraphFactory.create_vizql_graph(
            version=request.version or "v3",
            max_build_retries=ac.get("max_build_retries"),
            max_execution_retries=ac.get("max_execution_retries"),
        )
        ctx = request.context
        cfg = request.configurable

        message_history = []
        for m in request.message_history:
            msg_dict = {"role": m.get("role", "user"), "content": m.get("content", "")}
            if m.get("query_draft"):
                msg_dict["query_draft"] = m["query_draft"]
            if m.get("query_results"):
                msg_dict["query_results"] = m["query_results"]
            message_history.append(msg_dict)

        initial_state = {
            "user_query": request.user_query,
            "agent_type": "vizql",
            "context_datasources": ctx.datasource_ids,
            "context_views": ctx.view_ids,
            "messages": message_history,
            "tool_calls": [],
            "tool_results": [],
            "current_thought": None,
            "final_answer": None,
            "error": None,
            "confidence": None,
            "processing_time": None,
            "model": cfg.model,
            "provider": cfg.provider,
            "site_id": cfg.site_id,
            "build_attempt": 1,
            "execution_attempt": 1,
            "query_version": 0,
            "reasoning_steps": [],
            "build_errors": None,
            "execution_errors": None,
            "enriched_schema": None,
            "schema": None,
        }

        config = {"configurable": {"thread_id": f"vizql-{cfg.conversation_id or 0}", "tableau_client": adapters.tableau_client}}
        last_state = None
        last_final_answer = ""
        full_content = ""
        streamed_thoughts = set()
        reasoning_step_index = 0
        query_sent = False

        async for state_update in graph.astream(initial_state, config=config):
            for node_name, node_state in state_update.items():
                if isinstance(node_state, dict):
                    last_state = node_state

                if isinstance(node_state, dict) and node_state.get("current_thought"):
                    thought = node_state["current_thought"]
                    key = f"{node_name}_thought_attempt_{node_state.get('build_attempt', 1)}" if node_name == "build_query" else f"{node_name}_thought"
                    if key not in streamed_thoughts:
                        step_meta = dict(node_state.get("step_metadata") or {})
                        if node_name == "build_query":
                            if "query_draft" in node_state:
                                step_meta["query_draft"] = node_state.get("query_draft")
                            step_meta["build_attempt"] = node_state.get("build_attempt", 1)
                        chunk = AgentMessageChunk(
                            message_type="reasoning",
                            content=AgentMessageContent(type="text", data=thought),
                            step_name=node_name,
                            timestamp=__import__("time").time(),
                            step_index=reasoning_step_index,
                            metadata=step_meta or None,
                        )
                        reasoning_step_index += 1
                        yield chunk.to_sse_format()
                        streamed_thoughts.add(key)
                        full_content += " " + thought

                if isinstance(node_state, dict) and node_state.get("final_answer"):
                    answer = node_state["final_answer"]
                    if answer != last_final_answer:
                        new_content = answer[len(last_final_answer):] if last_final_answer else answer
                        if new_content:
                            chunk = AgentMessageChunk(
                                message_type="final_answer",
                                content=AgentMessageContent(type="text", data=new_content),
                                timestamp=__import__("time").time(),
                            )
                            yield chunk.to_sse_format()
                        last_final_answer = answer
                        full_content = answer

        if not full_content and last_state:
            final_answer = (
                last_state.get("final_answer")
                or last_state.get("formatted_response")
                or (f"Error: {last_state['error']}" if last_state.get("error") else None)
                or (f"Execution error: {last_state['execution_error']}" if last_state.get("execution_error") else None)
                or "Query execution completed."
            )
            if final_answer:
                chunk = AgentMessageChunk(
                    message_type="final_answer",
                    content=AgentMessageContent(type="text", data=final_answer),
                    timestamp=__import__("time").time(),
                )
                yield chunk.to_sse_format()

        vizql_query = None
        if last_state:
            for key in ["query_draft", "query", "validated_query"]:
                if last_state.get(key):
                    vizql_query = last_state[key]
                    break
        if vizql_query and not query_sent:
            chunk = AgentMessageChunk(
                message_type="metadata",
                content=AgentMessageContent(type="json", data={"vizql_query": vizql_query}),
                timestamp=__import__("time").time(),
            )
            yield chunk.to_sse_format()

    @staticmethod
    async def _invoke_summary(
        request: AgentInvocationRequest,
        adapters: AgentAdapters,
        stream: bool,
    ) -> AgentInvocationResponse:
        from app.services.agents.graph_factory import AgentGraphFactory

        graph = AgentGraphFactory.create_summary_graph()
        ctx = request.context
        cfg = request.configurable

        message_history = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in request.message_history]
        initial_state = {
            "user_query": request.user_query,
            "agent_type": "summary",
            "context_datasources": ctx.datasource_ids,
            "context_views": ctx.view_ids,
            "messages": message_history,
            "tool_calls": [],
            "tool_results": [],
            "current_thought": None,
            "final_answer": None,
            "error": None,
            "confidence": None,
            "processing_time": None,
            "model": cfg.model,
            "provider": cfg.provider,
            "embedded_state": ctx.embedded_state,
            "summary_mode": cfg.agent_config.get("summary_mode", "full"),
            "conversation_id": cfg.conversation_id,
            "tableau_auth_type": cfg.agent_config.get("tableau_auth_type", "connected_app"),
        }
        config = {"configurable": {"thread_id": f"summary-{cfg.conversation_id or 0}", "tableau_client": adapters.tableau_client}}
        final_state = await graph.ainvoke(initial_state, config=config)
        content = final_state.get("final_answer") or final_state.get("executive_summary") or final_state.get("detailed_analysis")
        if not content and final_state.get("error"):
            content = f"Error: {final_state['error']}"
        metadata = {}
        if final_state.get("view_images") is not None:
            metadata["view_images"] = final_state["view_images"]
        return AgentInvocationResponse(
            content=content or "Summary completed.",
            error=final_state.get("error"),
            metadata=metadata,
        )

    @staticmethod
    async def _invoke_summary_stream(
        request: AgentInvocationRequest,
        adapters: AgentAdapters,
    ) -> AsyncIterator[str]:
        from app.api.models import AgentMessageChunk, AgentMessageContent
        from app.services.agents.graph_factory import AgentGraphFactory

        graph = AgentGraphFactory.create_summary_graph()
        ctx = request.context
        cfg = request.configurable

        message_history = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in request.message_history]
        initial_state = {
            "user_query": request.user_query,
            "agent_type": "summary",
            "context_datasources": ctx.datasource_ids,
            "context_views": ctx.view_ids,
            "messages": message_history,
            "tool_calls": [],
            "tool_results": [],
            "current_thought": None,
            "final_answer": None,
            "error": None,
            "confidence": None,
            "processing_time": None,
            "model": cfg.model,
            "provider": cfg.provider,
            "embedded_state": ctx.embedded_state,
            "summary_mode": cfg.agent_config.get("summary_mode", "full"),
            "conversation_id": cfg.conversation_id,
            "tableau_auth_type": cfg.agent_config.get("tableau_auth_type", "connected_app"),
        }
        config = {"configurable": {"thread_id": f"summary-{cfg.conversation_id or 0}", "tableau_client": adapters.tableau_client}}
        last_state = None
        last_final_answer = ""
        streamed_thoughts = set()
        reasoning_step_index = 0

        async for state_update in graph.astream(initial_state, config=config):
            for node_name, node_state in state_update.items():
                if isinstance(node_state, dict):
                    last_state = node_state

                if isinstance(node_state, dict) and node_state.get("current_thought"):
                    thought = node_state["current_thought"]
                    key = f"{node_name}_thought"
                    if key not in streamed_thoughts:
                        step_meta = dict(node_state.get("step_metadata") or {})
                        view_images = step_meta.pop("view_images", None)
                        chunk = AgentMessageChunk(
                            message_type="reasoning",
                            content=AgentMessageContent(type="text", data=thought),
                            step_name=node_name,
                            timestamp=__import__("time").time(),
                            step_index=reasoning_step_index,
                            metadata=step_meta or None,
                        )
                        reasoning_step_index += 1
                        yield chunk.to_sse_format()
                        if view_images and node_name == "get_data":
                            meta_chunk = AgentMessageChunk(
                                message_type="metadata",
                                content=AgentMessageContent(type="json", data={"view_images": view_images, "step_index": reasoning_step_index - 1}),
                                timestamp=__import__("time").time(),
                            )
                            yield meta_chunk.to_sse_format()
                        streamed_thoughts.add(key)

                if isinstance(node_state, dict) and node_state.get("final_answer"):
                    answer = node_state["final_answer"]
                    if answer != last_final_answer:
                        new_content = answer[len(last_final_answer):] if last_final_answer else answer
                        if new_content:
                            chunk = AgentMessageChunk(
                                message_type="final_answer",
                                content=AgentMessageContent(type="text", data=new_content),
                                timestamp=__import__("time").time(),
                            )
                            yield chunk.to_sse_format()
                        last_final_answer = answer

        if not last_final_answer and last_state:
            final_answer = (
                last_state.get("final_answer")
                or last_state.get("executive_summary")
                or last_state.get("detailed_analysis")
                or (f"Error: {last_state['error']}" if last_state.get("error") else None)
                or "Summary completed."
            )
            if final_answer:
                chunk = AgentMessageChunk(
                    message_type="final_answer",
                    content=AgentMessageContent(type="text", data=final_answer),
                    timestamp=__import__("time").time(),
                )
                yield chunk.to_sse_format()

    @staticmethod
    async def _invoke_multi_agent(
        request: AgentInvocationRequest,
        adapters: AgentAdapters,
    ) -> AgentInvocationResponse:
        from app.services.agents.multi_agent import MultiAgentOrchestrator

        cfg = request.configurable
        ctx = request.context
        orchestrator = MultiAgentOrchestrator(model=cfg.model, provider=cfg.provider)
        ac = request.configurable.agent_config
        result = await orchestrator.execute_workflow(
            user_query=request.user_query,
            context={
                "datasources": ctx.datasource_ids,
                "views": ctx.view_ids,
                "embedded_state": ctx.embedded_state,
                "summary_mode": ac.get("summary_mode", "full"),
                "tableau_auth_type": ac.get("tableau_auth_type", "connected_app"),
            },
            tableau_client=adapters.tableau_client,
        )
        return AgentInvocationResponse(
            content=result.get("final_answer", "Workflow completed."),
            metadata={
                "agents_used": result.get("agents_used", []),
                "execution_trace": result.get("execution_trace", []),
            },
        )
