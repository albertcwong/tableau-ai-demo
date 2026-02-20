"""Chat API endpoints."""
import logging
from typing import List, Optional, Dict
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel, Field, field_serializer, model_validator
from app.core.database import get_db, safe_commit
from app.models.chat import Conversation, Message, MessageRole, ChatContext
from app.api.auth import get_current_user
from app.models.user import User
from app.services.ai.client import UnifiedAIClient, AIClientError
from app.services.ai.tools import get_tools, execute_tool, format_tool_result
from app.services.tableau.client import TableauClient
from app.api.tableau import get_tableau_client
from app.core.config import settings
from fastapi import Request
from app.services.memory import get_conversation_memory
from app.services.metrics import get_metrics
from app.api.chat_helpers import prepare_chat_context
from app.api.chat_agent_integration import (
    build_agent_request,
    build_adapters,
    invoke_agent,
    invoke_agent_stream,
    parse_stream_chunk,
)
from app.services.debug import get_debugger
from app.api.models import AgentMessageChunk, AgentMessageContent
import time
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# Request/Response Models
class ConversationCreate(BaseModel):
    """Request model for creating a conversation."""
    pass


class ConversationResponse(BaseModel):
    """Response model for conversation."""
    id: int
    name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    
    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, dt: datetime, _info):
        if dt is None:
            return None
        return dt.isoformat()
    
    class Config:
        from_attributes = True


class MessageRequest(BaseModel):
    """Request model for sending a message."""
    conversation_id: int = Field(..., description="Conversation ID")
    content: str = Field(..., min_length=1, description="Message content")
    model: str = Field(default="gpt-4", description="AI model to use")
    provider: str = Field(..., description="Provider name (e.g., 'openai', 'apple', 'vertex')")
    agent_type: Optional[str] = Field(None, description="Agent type: 'summary', 'vizql', or 'multi_agent'")
    agent_version: Optional[str] = Field(None, description="Agent version (e.g., 'v1', 'v2', 'v3' for vizql). Defaults to DB default.")
    stream: bool = Field(default=False, description="Whether to stream the response")
    temperature: Optional[float] = Field(None, ge=0, le=2, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens to generate")
    embedded_state: Optional[dict] = Field(None, description="Per-view embedded dashboard state (filters, summary_data, sheets_data) from client capture")
    summary_mode: Optional[str] = Field(None, description="'brief', 'full', or 'custom'. Only used when agent_type is 'summary'")
    invalidate_cache: Optional[bool] = Field(None, description="If true, invalidate cached view data for this conversation before processing. Used when view data may have changed (e.g., filters applied).")
    tableau_auth_type: Optional[str] = Field(None, description="Tableau auth: connected_app, connected_app_oauth, pat, standard. Used for summary agent data retrieval path.")


class MessageResponse(BaseModel):
    """Response model for a message."""
    id: int
    conversation_id: int
    role: str
    content: str
    model_used: Optional[str]
    tokens_used: Optional[int]
    feedback: Optional[str] = None
    feedback_text: Optional[str] = None
    total_time_ms: Optional[float] = None
    vizql_query: Optional[dict] = None  # VizQL query used to generate the answer (for vizql agent)
    extra_metadata: Optional[dict] = None  # Additional metadata (e.g., is_greeting flag)
    created_at: datetime
    
    @model_validator(mode='before')
    @classmethod
    def normalize_role(cls, data):
        """Normalize role to uppercase string before validation (accept uppercase for now)."""
        if isinstance(data, dict) and 'role' in data:
            role = data['role']
            if isinstance(role, MessageRole):
                data['role'] = role.value  # Now returns uppercase
            elif isinstance(role, str):
                data['role'] = role.upper()  # Convert to uppercase
            else:
                data['role'] = str(role).upper()
        return data
    
    @field_serializer('created_at')
    def serialize_datetime(self, dt: datetime, _info):
        return dt.isoformat()
    
    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    """Response model for chat completion."""
    message: MessageResponse
    conversation_id: int
    model: str
    tokens_used: int


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None."""
    try:
        return get_current_user(request, db)
    except HTTPException:
        # Authentication failed or user not found - return None
        return None
    except Exception as e:
        # Log unexpected errors but still return None to allow unauthenticated access
        logger.warning(f"Unexpected error in get_current_user_optional: {e}", exc_info=True)
        return None


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: Request,
    agent_type: Optional[str] = Query(None, description="Agent type for personalized greeting: 'vizql' or 'summary'"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Create a new conversation with personalized greeting based on agent type."""
    conversation = Conversation(user_id=current_user.id if current_user else None)
    db.add(conversation)
    safe_commit(db)
    db.refresh(conversation)
    
    # Personalized greetings per agent type
    greeting_messages = {
        'general': "Hello! I'm your General Agent assistant. I can help you explore Tableau objects, answer questions about your data, and assist with general queries. What would you like to know?",
        'vizql': "Hello! I'm your VizQL Agent. I specialize in constructing and executing VizQL queries to interact with Tableau datasources. I can help you build queries, filter data, and explore your datasets. What would you like to query?",
        'summary': "I'm your Summary Agent. Add views to your context, then click one of the buttons above to choose your summary type: Brief, Full, or Custom instructions.",
    }
    
    # Default greeting if agent_type is not provided or invalid
    agent_type_normalized = agent_type.lower() if agent_type else 'vizql'
    greeting_content = greeting_messages.get(agent_type_normalized, greeting_messages['vizql'])
    
    # Create initial greeting message from assistant
    extra_meta = {"is_greeting": True, "agent_type": agent_type_normalized}
    if agent_type_normalized == "summary":
        extra_meta["summary_buttons"] = True
    greeting_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=greeting_content,
        created_at=datetime.now(),
        extra_metadata=extra_meta
    )
    db.add(greeting_message)
    safe_commit(db)
    db.refresh(conversation)
    
    # Compute message count (should be 1 after adding greeting)
    conversation.message_count = db.query(Message).filter(Message.conversation_id == conversation.id).count()
    
    logger.info(f"Created conversation {conversation.id} with initial greeting for agent type: {agent_type_normalized}")
    return conversation


@router.post("/conversations/{conversation_id}/greeting", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_greeting_message(
    conversation_id: int,
    agent_type: str = Query(..., description="Agent type for personalized greeting: 'vizql' or 'summary'"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Create a greeting message for an existing conversation when agent type changes."""
    # Verify conversation exists
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Personalized greetings per agent type
    greeting_messages = {
        'vizql': "Hello! I'm your VizQL Agent. I specialize in constructing and executing VizQL queries to interact with Tableau datasources. I can help you build queries, filter data, and explore your datasets. What would you like to query?",
        'summary': "I'm your Summary Agent. Add views to your context, then click one of the buttons above to choose your summary type: Brief, Full, or Custom instructions.",
    }
    
    # Normalize agent type (default to vizql)
    agent_type_normalized = agent_type.lower() if agent_type else 'vizql'
    greeting_content = greeting_messages.get(agent_type_normalized, greeting_messages['vizql'])
    
    # Create greeting message
    extra_meta = {"is_greeting": True, "agent_type": agent_type_normalized}
    if agent_type_normalized == "summary":
        extra_meta["summary_buttons"] = True
    greeting_message = Message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=greeting_content,
        created_at=datetime.now(),
        extra_metadata=extra_meta
    )
    db.add(greeting_message)
    safe_commit(db)
    db.refresh(greeting_message)
    
    logger.info(f"Created greeting message {greeting_message.id} for conversation {conversation_id} with agent type: {agent_type_normalized}")
    
    # Convert to response model
    return MessageResponse(
        id=greeting_message.id,
        conversation_id=greeting_message.conversation_id,
        role=greeting_message.role.value,
        content=greeting_message.content,
        model_used=greeting_message.model_used,
        tokens_used=greeting_message.tokens_used,
        feedback=greeting_message.feedback,
        feedback_text=greeting_message.feedback_text,
        total_time_ms=greeting_message.total_time_ms,
        vizql_query=None,
        extra_metadata=greeting_message.extra_metadata,
        created_at=greeting_message.created_at
    )


@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """List conversations for the current user (or unauthenticated sessions)."""
    try:
        q = db.query(Conversation).order_by(desc(Conversation.updated_at))
        if current_user:
            q = q.filter(Conversation.user_id == current_user.id)
        else:
            q = q.filter(Conversation.user_id.is_(None))
        conversations = q.offset(skip).limit(limit).all()
        
        # Eager load messages to compute counts efficiently
        for conv in conversations:
            try:
                # Load messages count
                conv.message_count = db.query(Message).filter(Message.conversation_id == conv.id).count()
            except Exception as e:
                logger.error(f"Error computing message count for conversation {conv.id}: {e}")
                conv.message_count = 0
        
        return conversations
    except Exception as e:
        logger.error(f"Error listing conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list conversations: {str(e)}")


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get a conversation by ID."""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Validate ownership: user must own the conversation (or conversation must be unauthenticated if user is None)
    if current_user:
        if conversation.user_id is not None and conversation.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You don't have permission to access this conversation")
    else:
        # Unauthenticated users can only access conversations with user_id=None
        if conversation.user_id is not None:
            raise HTTPException(status_code=403, detail="Authentication required to access this conversation")
    
    # Compute message count
    conversation.message_count = db.query(Message).filter(Message.conversation_id == conversation_id).count()
    
    return conversation


class ConversationRenameRequest(BaseModel):
    """Request model for renaming a conversation."""
    name: str = Field(..., min_length=1, max_length=255, description="New conversation name")


@router.patch("/conversations/{conversation_id}/rename", response_model=ConversationResponse)
async def rename_conversation(
    conversation_id: int,
    request: ConversationRenameRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Rename a conversation."""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Validate ownership
    if current_user:
        if conversation.user_id is not None and conversation.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You don't have permission to rename this conversation")
    else:
        if conversation.user_id is not None:
            raise HTTPException(status_code=403, detail="Authentication required to rename this conversation")
    
    conversation.name = request.name.strip()
    safe_commit(db)
    db.refresh(conversation)
    
    # Compute message count
    conversation.message_count = db.query(Message).filter(Message.conversation_id == conversation_id).count()
    
    logger.info(f"Renamed conversation {conversation_id} to '{conversation.name}'")
    return conversation


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get all messages for a conversation."""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Validate ownership
    if current_user:
        if conversation.user_id is not None and conversation.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You don't have permission to access this conversation")
    else:
        if conversation.user_id is not None:
            raise HTTPException(status_code=403, detail="Authentication required to access this conversation")
    
    messages = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at).all()
    # Return messages with uppercase roles (as stored in database)
    result = []
    for msg in messages:
        # Extract vizql_query from extra_metadata if available
        vizql_query = None
        if msg.extra_metadata and isinstance(msg.extra_metadata, dict):
            vizql_query = msg.extra_metadata.get('vizql_query')
        
        result.append(MessageResponse(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role.value if isinstance(msg.role, MessageRole) else str(msg.role).upper(),
            content=msg.content,
            model_used=msg.model_used,
            tokens_used=msg.tokens_used,
            feedback=msg.feedback,
            feedback_text=msg.feedback_text,
            total_time_ms=msg.total_time_ms,
            vizql_query=vizql_query,
            extra_metadata=msg.extra_metadata,
            created_at=msg.created_at
        ))
    return result


async def build_agent_messages(
    agent_type: str,
    conversation_messages: List[Dict],
    datasource_ids: List[str],
    view_ids: List[str],
    tableau_client: TableauClient
) -> List[Dict]:
    """Build messages with context based on agent type."""
    messages = conversation_messages.copy()
    
    if agent_type == 'summary':
        # Summary Agent: Include view data
        if view_ids:
            system_prompt = "You are a Summary Agent specialized in analyzing Tableau views. "
            system_prompt += "You have access to view data and can summarize insights, trends, and key findings.\n\n"
            system_prompt += "Context Views:\n"
            
            for view_id in view_ids:
                try:
                    if not tableau_client:
                        raise ValueError("Tableau client not available")
                    # Get view data using Tableau Data API
                    view_data = await tableau_client.get_view_data(view_id, max_rows=100)
                    system_prompt += f"\nView {view_id}:\n"
                    system_prompt += f"Columns: {', '.join(view_data.get('columns', []))}\n"
                    # Include sample data (first 10 rows)
                    sample_data = view_data.get('data', [])[:10]
                    if sample_data:
                        system_prompt += f"Sample Data (first 10 rows):\n"
                        for row in sample_data:
                            system_prompt += f"  {', '.join(str(v) for v in row)}\n"
                except Exception as e:
                    logger.warning(f"Failed to fetch view data for {view_id}: {e}")
                    system_prompt += f"\nView {view_id}: (data unavailable - {str(e)})\n"
            
            # Insert system message at the beginning
            messages.insert(0, {
                "role": "system",
                "content": system_prompt
            })
    
    elif agent_type == 'vizql':
        # VizQL Agent: Include datasource schema
        if datasource_ids:
            system_prompt = "You are a VizQL Agent specialized in constructing VizQL queries. "
            system_prompt += "You have access to datasource schemas and can help users query data.\n\n"
            system_prompt += "Context Datasources:\n"
            
            for datasource_id in datasource_ids:
                try:
                    if not tableau_client:
                        raise ValueError("Tableau client not available")
                    schema = await tableau_client.get_datasource_schema(datasource_id)
                    system_prompt += f"\nDatasource {datasource_id}:\n"
                    columns = schema.get('columns', [])
                    if columns:
                        system_prompt += "Columns:\n"
                        for col in columns:
                            col_name = col.get('name', 'Unknown')
                            col_type = col.get('data_type', 'Unknown')
                            is_measure = col.get('is_measure', False)
                            is_dimension = col.get('is_dimension', False)
                            col_type_str = "measure" if is_measure else ("dimension" if is_dimension else "unknown")
                            system_prompt += f"  - {col_name} ({col_type}, {col_type_str})\n"
                except Exception as e:
                    logger.warning(f"Failed to fetch schema for {datasource_id}: {e}")
                    system_prompt += f"\nDatasource {datasource_id}: (schema unavailable - {str(e)})\n"
            
            messages.insert(0, {
                "role": "system",
                "content": system_prompt
            })
    
    # Note: General agent removed - default to vizql if no agent_type specified
    return messages


async def get_tableau_client_optional(
    request: Request,
    x_tableau_config_id: Optional[str] = Header(None, alias="X-Tableau-Config-Id"),
    x_tableau_auth_type: Optional[str] = Header(None, alias="X-Tableau-Auth-Type"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> Optional[TableauClient]:
    """Optional Tableau client - returns None if no config provided or user not authenticated.
    Propagates HTTPException (401/400) for Tableau auth failures so frontend can handle gracefully."""
    if not x_tableau_config_id or not current_user:
        return None
    # Let HTTPException propagate (session expired, PAT not configured, etc.)
    return await get_tableau_client(
        x_tableau_config_id=x_tableau_config_id,
        x_tableau_auth_type=x_tableau_auth_type,
        db=db,
        current_user=current_user
    )


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: MessageRequest,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_tableau_auth_type: Optional[str] = Header(None, alias="X-Tableau-Auth-Type"),
    current_user: User = Depends(get_current_user),
    tableau_client: Optional[TableauClient] = Depends(get_tableau_client_optional)
):
    """
    Send a message and get AI response.
    
    If stream=True, returns a streaming response.
    Supports agent routing via agent_type parameter.
    """
    conversation = db.query(Conversation).filter(Conversation.id == request.conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user_message = Message(
        conversation_id=request.conversation_id,
        role=MessageRole.USER,
        content=request.content,
        model_used=request.model,
    )
    db.add(user_message)
    if not conversation.name:
        name = request.content.strip()[:50]
        if len(request.content) > 50:
            truncated = name.rsplit(" ", 1)[0]
            name = truncated if len(truncated) > 30 else name
        conversation.name = name
    safe_commit(db)

    ctx = prepare_chat_context(db, request.conversation_id)
    conversation = ctx["conversation"]
    datasource_ids = ctx["datasource_ids"]
    view_ids = ctx["view_ids"]
    history_messages = ctx["history_messages"]
    messages = ctx["messages"]
    
    # Provider is required and validated by MessageRequest. Gateway resolves credentials from ProviderConfig.
    provider = request.provider.strip()
    provider_for_state = provider
    
    # Tableau client is provided via dependency (uses user's selected config from X-Tableau-Config-Id header)
    # Require connection for Tableau-dependent agents
    resolved_agent_type = request.agent_type or 'vizql'  # Default to vizql instead of general
    if resolved_agent_type in ('vizql', 'summary', 'multi_agent') and (datasource_ids or view_ids):
        if not tableau_client:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please connect to Tableau first using the Connect button.",
                headers={"X-Error-Code": "TABLEAU_NOT_CONNECTED"},
            )
    
    # Initialize feedback manager for query refinement
    from app.services.agents.feedback import FeedbackManager
    feedback_manager = FeedbackManager(db=db, model=request.model, provider=provider)
    
    defer_tableau_close = False  # True when returning stream; stream wrapper closes client

    async def _stream_with_tableau_cleanup(agen):
        """Wrap stream to close tableau_client when done (avoids closing before stream consumes)."""
        try:
            async for chunk in agen:
                yield chunk
        finally:
            if tableau_client:
                await tableau_client.close()

    try:
        # Route to agent graphs if agent_type is specified and context is available
        agent_type = request.agent_type or 'vizql'  # Default to vizql instead of general
        
        # Check if multi-agent is needed (either explicitly requested or detected)
        use_multi_agent = False
        if agent_type == 'multi_agent':
            use_multi_agent = True
        elif not agent_type or agent_type == 'vizql':
            # Use meta-agent to determine if multi-agent is needed (when no explicit agent_type)
            from app.services.agents.meta_agent import MetaAgentSelector
            meta_selector = MetaAgentSelector(model=request.model, provider=provider)
            selection = await meta_selector.select_agent(
                user_query=request.content,
                context={
                    "datasources": datasource_ids,
                    "views": view_ids,
                    "conversation_history": history_messages[-5:] if history_messages else []
                },
                available_agents=["vizql", "summary", "multi_agent"]  # Remove general from available agents
            )
            if selection.get("requires_multi_agent") or selection.get("selected_agent") == "multi_agent":
                use_multi_agent = True
                agent_type = "multi_agent"
                logger.info(f"Meta-agent detected multi-agent workflow needed: {selection.get('reasoning')}")
        
        # Route to Multi-Agent Orchestrator (via Agent Service)
        if use_multi_agent:
            logger.info("Routing to Multi-Agent orchestrator via Agent Service")

            refined_query_result = await feedback_manager.apply_feedback_to_query(
                query=request.content,
                conversation_id=request.conversation_id,
                agent_type="multi_agent"
            )
            refined_query = refined_query_result.get("refined_query", request.content)
            if refined_query != request.content:
                logger.info(f"Query refined based on feedback: {refined_query_result.get('changes')}")

            execution_start = time.time()
            execution_id = str(uuid.uuid4())
            metrics = get_metrics()
            agent_req = build_agent_request(
                agent_type="multi_agent",
                user_query=refined_query,
                datasource_ids=datasource_ids,
                view_ids=view_ids,
                message_history=history_messages,
                model=request.model,
                provider=provider_for_state,
                conversation_id=request.conversation_id,
                embedded_state=request.embedded_state,
                summary_mode=request.summary_mode if request.summary_mode in ("brief", "full", "custom") else "full",
                tableau_auth_type=(request.tableau_auth_type or x_tableau_auth_type or "connected_app").lower(),
                site_id=(tableau_client.site_id or "") if tableau_client else settings.TABLEAU_SITE_ID,
                stream=request.stream,
            )
            adapters = build_adapters(tableau_client)

            if request.stream:
                async def generate_multi_agent_stream():
                    full_content = ""
                    try:
                        async for chunk in invoke_agent_stream(agent_req, adapters):
                            yield chunk
                            if chunk.startswith("data: ") and "final_answer" in chunk and "[DONE]" not in chunk:
                                try:
                                    import json
                                    j = json.loads(chunk[6:].split("\n")[0])
                                    if j.get("message_type") == "final_answer":
                                        c = j.get("content", {})
                                        full_content += str(c.get("data", "")) if isinstance(c, dict) else ""
                                except Exception:
                                    pass
                        if full_content:
                            assistant_message = Message(
                                conversation_id=request.conversation_id,
                                role=MessageRole.ASSISTANT,
                                content=full_content,
                                model_used=request.model,
                                extra_metadata={
                                    "execution_id": execution_id,
                                    "agent_type": "multi_agent",
                                    "agents_used": [],
                                    "execution_trace": [],
                                },
                            )
                            db.add(assistant_message)
                            conversation.updated_at = conversation.updated_at
                            safe_commit(db)
                    except Exception as e:
                        logger.error(f"Error in multi-agent workflow: {e}", exc_info=True)
                        yield f"data: {{\"message_type\":\"error\",\"content\":{{\"type\":\"text\",\"data\":\"{str(e)}\"}}}}\n\n"
                        yield "data: [DONE]\n\n"

                defer_tableau_close = True
                return StreamingResponse(
                    _stream_with_tableau_cleanup(generate_multi_agent_stream()),
                    media_type="text/event-stream",
                )
            else:
                result = await invoke_agent(agent_req, adapters)
                final_answer = result.content or result.error or "Workflow completed"
                execution_time = time.time() - execution_start
                metrics.record_agent_execution(agent_type="multi_agent", execution_time=execution_time, success=True)
                assistant_message = Message(
                    conversation_id=request.conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=final_answer,
                    model_used=request.model,
                    extra_metadata={
                        "execution_id": execution_id,
                        "agent_type": "multi_agent",
                        "agents_used": result.metadata.get("agents_used", []),
                        "execution_trace": result.metadata.get("execution_trace", []),
                        "execution_time": execution_time,
                    },
                )
                db.add(assistant_message)
                conversation.updated_at = conversation.updated_at
                safe_commit(db)
                db.refresh(assistant_message)
                return ChatResponse(
                    message=MessageResponse(
                        id=assistant_message.id,
                        conversation_id=assistant_message.conversation_id,
                        role=assistant_message.role.value,
                        content=assistant_message.content,
                        model_used=assistant_message.model_used,
                        tokens_used=None,
                        feedback=assistant_message.feedback,
                        total_time_ms=assistant_message.total_time_ms,
                        vizql_query=None,
                        created_at=assistant_message.created_at,
                    ),
                    conversation_id=request.conversation_id,
                    model=request.model,
                    tokens_used=0,
                )
        
        # Route to VizQL agent graph
        elif agent_type == 'vizql' and datasource_ids:
            from app.services.agents.graph_factory import AgentGraphFactory
            
            logger.info(f"Routing to VizQL agent graph with datasources: {datasource_ids}")
            
            # Apply feedback-based refinement to query
            from app.services.agents.feedback import FeedbackManager
            feedback_manager = FeedbackManager(db=db, model=request.model, provider=provider)
            refined_query_result = await feedback_manager.apply_feedback_to_query(
                query=request.content,
                conversation_id=request.conversation_id,
                agent_type="vizql"
            )
            refined_query = refined_query_result.get("refined_query", request.content)
            
            if refined_query != request.content:
                logger.info(f"Query refined based on feedback: {refined_query_result.get('changes')}")
            
            # Track execution start time
            execution_start = time.time()
            execution_id = str(uuid.uuid4())
            metrics = get_metrics()
            conversation_memory = get_conversation_memory(request.conversation_id)
            debugger = get_debugger()
            node_states = []  # Track node states for debugging
            
            # Get agent version and retry settings from DB config
            from app.services.agent_config_service import AgentConfigService
            agent_config_service = AgentConfigService(db)
            
            # Get version (use request param or DB default)
            agent_version = request.agent_version
            if not agent_version:
                agent_version = agent_config_service.get_default_version('vizql') or 'v3'
            
            # Validate version is enabled
            if not agent_config_service.is_version_enabled('vizql', agent_version):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"VizQL version '{agent_version}' is not enabled. Available versions: {', '.join(agent_config_service.get_enabled_versions('vizql'))}"
                )
            
            # Get retry settings from DB (with fallback to env vars)
            retry_settings = agent_config_service.get_agent_settings('vizql')
            max_build_retries = retry_settings.get('max_build_retries')
            max_execution_retries = retry_settings.get('max_execution_retries')
            
            agent_req = build_agent_request(
                agent_type="vizql",
                user_query=refined_query,
                datasource_ids=datasource_ids,
                view_ids=view_ids,
                message_history=history_messages,
                model=request.model,
                provider=provider_for_state,
                conversation_id=request.conversation_id,
                agent_version=agent_version,
                max_build_retries=max_build_retries,
                max_execution_retries=max_execution_retries,
                site_id=(tableau_client.site_id or "") if tableau_client else settings.TABLEAU_SITE_ID,
                stream=request.stream,
            )
            adapters = build_adapters(tableau_client)

            if request.stream:
                async def stream_graph():
                    full_content = ""
                    stored_vizql_query = None
                    stored_query_results = None
                    stream_start_time = time.time()
                    try:
                        async for chunk in invoke_agent_stream(agent_req, adapters):
                            yield chunk
                            mt, data, meta = parse_stream_chunk(chunk)
                            if mt == "final_answer" and data:
                                full_content += str(data)
                            elif mt == "metadata" and meta:
                                if meta.get("vizql_query"):
                                    stored_vizql_query = meta["vizql_query"]

                        if full_content:
                            try:
                                total_time_ms = (time.time() - stream_start_time) * 1000
                                assistant_message = Message(
                                    conversation_id=request.conversation_id,
                                    role=MessageRole.ASSISTANT,
                                    content=full_content,
                                    model_used=request.model,
                                    total_time_ms=total_time_ms,
                                    extra_metadata={
                                        "agent_type": "vizql",
                                        "vizql_query": stored_vizql_query,
                                        "query_results": stored_query_results
                                    }
                                )
                                db.add(assistant_message)
                                conversation.updated_at = conversation.updated_at
                                safe_commit(db)
                                logger.info(f"Saved assistant message with {len(full_content)} chars, total_time_ms: {total_time_ms:.2f}")
                            except Exception as e:
                                logger.error(f"Failed to save assistant message: {e}", exc_info=True)
                        else:
                            logger.error("No content to save after streaming completed!")
                        
                        # Send completion marker
                        done_chunk = AgentMessageChunk(
                            message_type="progress",
                            content=AgentMessageContent(type="text", data="[DONE]"),
                            timestamp=time.time()
                        )
                        yield done_chunk.to_sse_format()
                    except Exception as e:
                        logger.error(f"Error in VizQL graph streaming: {e}", exc_info=True)
                        error_chunk = AgentMessageChunk(
                            message_type="error",
                            content=AgentMessageContent(type="text", data=str(e)),
                            timestamp=time.time()
                        )
                        yield error_chunk.to_sse_format()
                        done_chunk = AgentMessageChunk(
                            message_type="progress",
                            content=AgentMessageContent(type="text", data="[DONE]"),
                            timestamp=time.time()
                        )
                        yield done_chunk.to_sse_format()
                
                defer_tableau_close = True
                return StreamingResponse(
                    _stream_with_tableau_cleanup(stream_graph()),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    }
                )
            else:
                try:
                    result = await invoke_agent(agent_req, adapters)
                    execution_time = time.time() - execution_start
                    final_answer = result.content or result.error or "Query execution completed."
                    vizql_query = result.metadata.get("vizql_query")
                    query_results = result.metadata.get("query_results")
                    success = result.error is None
                    metrics.record_agent_execution("vizql", execution_time, success=success)
                    conversation_memory.add_message(
                        query_id=f"vizql-{request.conversation_id}-{int(time.time())}",
                        user_query=request.content,
                        agent_type="vizql",
                        response=final_answer,
                        datasource_ids=datasource_ids,
                        view_ids=view_ids,
                    )
                except Exception as e:
                    execution_time = time.time() - execution_start
                    logger.error(f"Error executing VizQL: {e}", exc_info=True)
                    metrics.record_agent_execution("vizql", execution_time, success=False)
                    final_answer = f"Error executing query: {str(e)}"
                    vizql_query = None
                    query_results = None

                assistant_message = Message(
                    conversation_id=request.conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=final_answer,
                    model_used=request.model,
                    extra_metadata={
                        "agent_type": "vizql",
                        "vizql_query": vizql_query,
                        "query_results": query_results
                    }
                )
                db.add(assistant_message)
                conversation.updated_at = conversation.updated_at
                safe_commit(db)
                db.refresh(assistant_message)
                
                return ChatResponse(
                    message=MessageResponse(
                        id=assistant_message.id,
                        conversation_id=assistant_message.conversation_id,
                        role=assistant_message.role.value,
                        content=assistant_message.content,
                        model_used=assistant_message.model_used,
                        tokens_used=None,
                        feedback=assistant_message.feedback,
                        total_time_ms=assistant_message.total_time_ms,
                        vizql_query=vizql_query,
                        created_at=assistant_message.created_at
                    ),
                    conversation_id=request.conversation_id,
                    model=request.model,
                    tokens_used=0
                )
        
        # Route to Summary agent (via Agent Service)
        elif agent_type == 'summary' and view_ids:
            logger.info(f"Routing to Summary agent via Agent Service with views: {view_ids}")
            refined_query_result = await feedback_manager.apply_feedback_to_query(
                query=request.content,
                conversation_id=request.conversation_id,
                agent_type="summary"
            )
            refined_query = refined_query_result.get("refined_query", request.content)
            if refined_query != request.content:
                logger.info(f"Query refined based on feedback: {refined_query_result.get('changes')}")
            execution_start = time.time()
            metrics = get_metrics()
            conversation_memory = get_conversation_memory(request.conversation_id)
            summary_mode = request.summary_mode if request.summary_mode in ("brief", "full", "custom") else "full"
            tableau_auth_type = (request.tableau_auth_type or x_tableau_auth_type or "connected_app").lower()
            agent_req = build_agent_request(
                agent_type="summary",
                user_query=refined_query,
                datasource_ids=datasource_ids,
                view_ids=view_ids,
                message_history=history_messages,
                model=request.model,
                provider=provider_for_state,
                conversation_id=request.conversation_id,
                embedded_state=request.embedded_state,
                summary_mode=summary_mode,
                tableau_auth_type=tableau_auth_type,
                site_id=(tableau_client.site_id or "") if tableau_client else settings.TABLEAU_SITE_ID,
                stream=request.stream,
            )
            adapters = build_adapters(tableau_client)

            if request.stream:
                async def stream_graph():
                    full_content = ""
                    stream_start_time = time.time()
                    try:
                        async for chunk in invoke_agent_stream(agent_req, adapters):
                            yield chunk
                            mt, data, _ = parse_stream_chunk(chunk)
                            if mt == "final_answer" and data:
                                full_content += str(data)

                        # Save assistant message after streaming completes
                        if full_content:
                            try:
                                # Calculate total time (from when user message was created to now)
                                stream_end_time = time.time()
                                total_time_ms = (stream_end_time - stream_start_time) * 1000  # Convert to milliseconds
                                
                                assistant_message = Message(
                                    conversation_id=request.conversation_id,
                                    role=MessageRole.ASSISTANT,
                                    content=full_content,
                                    model_used=request.model,
                                    total_time_ms=total_time_ms,
                                    extra_metadata={"agent_type": "summary"}
                                )
                                db.add(assistant_message)
                                conversation.updated_at = conversation.updated_at
                                safe_commit(db)
                                logger.info(f"Saved assistant message with {len(full_content)} chars, total_time_ms: {total_time_ms:.2f}")
                            except Exception as e:
                                logger.error(f"Failed to save assistant message: {e}", exc_info=True)
                        else:
                            logger.error("No content to save after streaming completed!")
                        
                        # Send completion marker
                        done_chunk = AgentMessageChunk(
                            message_type="progress",
                            content=AgentMessageContent(type="text", data="[DONE]"),
                            timestamp=time.time()
                        )
                        yield done_chunk.to_sse_format()
                    except Exception as e:
                        logger.error(f"Error in Summary graph streaming: {e}", exc_info=True)
                        error_chunk = AgentMessageChunk(
                            message_type="error",
                            content=AgentMessageContent(type="text", data=str(e)),
                            timestamp=time.time()
                        )
                        yield error_chunk.to_sse_format()
                        
                        # Send completion marker
                        done_chunk = AgentMessageChunk(
                            message_type="progress",
                            content=AgentMessageContent(type="text", data="[DONE]"),
                            timestamp=time.time()
                        )
                        yield done_chunk.to_sse_format()
                
                defer_tableau_close = True
                return StreamingResponse(
                    _stream_with_tableau_cleanup(stream_graph()),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    }
                )
            else:
                result = await invoke_agent(agent_req, adapters)
                execution_time = time.time() - execution_start
                final_answer = result.content or result.error or "Summary generation completed."
                success = result.error is None
                metrics.record_agent_execution("summary", execution_time, success=success)
                conversation_memory.add_message(
                    query_id=f"summary-{request.conversation_id}-{int(time.time())}",
                    user_query=request.content,
                    agent_type="summary",
                    response=final_answer,
                    datasource_ids=datasource_ids,
                    view_ids=view_ids,
                )
                
                # Calculate total time for non-streaming summary agent
                total_time_ms = (time.time() - execution_start) * 1000
                
                assistant_message = Message(
                    conversation_id=request.conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=final_answer,
                    model_used=request.model,
                    total_time_ms=total_time_ms,
                    extra_metadata={"agent_type": "summary"}
                )
                db.add(assistant_message)
                conversation.updated_at = conversation.updated_at
                safe_commit(db)
                db.refresh(assistant_message)
                
                return ChatResponse(
                    message=MessageResponse(
                        id=assistant_message.id,
                        conversation_id=assistant_message.conversation_id,
                        role=assistant_message.role.value,
                        content=assistant_message.content,
                        model_used=assistant_message.model_used,
                        tokens_used=None,
                        feedback=assistant_message.feedback,
                        total_time_ms=assistant_message.total_time_ms,
                        vizql_query=None,  # Not available for multi-agent
                        created_at=assistant_message.created_at
                    ),
                    conversation_id=request.conversation_id,
                    model=request.model,
                    tokens_used=0
                )
        
        # Fallback to context-aware messages for general agent or when context is missing
        # Build context-aware messages based on agent_type
        messages = await build_agent_messages(
            agent_type=agent_type,
            conversation_messages=messages,
            datasource_ids=datasource_ids,
            view_ids=view_ids,
            tableau_client=tableau_client
        )
        
        # Initialize AI client
        ai_client = UnifiedAIClient(
            gateway_url=settings.BACKEND_API_URL
        )
        
        try:
            if request.stream:
                # Streaming response
                async def generate_stream():
                    full_content = ""
                    logger.info(f"Starting stream for conversation {request.conversation_id}, model: {request.model}")
                    try:
                        async with ai_client:
                            chunk_count = 0
                            async for chunk in ai_client.stream_chat(
                                model=request.model,
                                provider=provider_for_state,
                                messages=messages,
                                temperature=request.temperature,
                                max_tokens=request.max_tokens
                            ):
                                if chunk.content:
                                    chunk_count += 1
                                    full_content += chunk.content
                                    logger.debug(f"Streaming chunk {chunk_count}: {chunk.content[:50]}...")
                                    # Send as structured final_answer chunk
                                    answer_chunk = AgentMessageChunk(
                                        message_type="final_answer",
                                        content=AgentMessageContent(type="text", data=chunk.content),
                                        timestamp=time.time()
                                    )
                                    yield answer_chunk.to_sse_format()
                            
                            logger.info(f"Streaming completed: {chunk_count} chunks, {len(full_content)} total chars")
                        
                        # Save assistant message after streaming completes
                        if full_content:
                            assistant_message = Message(
                                conversation_id=request.conversation_id,
                                role=MessageRole.ASSISTANT,
                                content=full_content,
                                model_used=request.model,
                                extra_metadata={"agent_type": agent_type or "general"}
                            )
                            db.add(assistant_message)
                            conversation.updated_at = conversation.updated_at  # Trigger update
                            safe_commit(db)
                        
                        # Send completion marker
                        done_chunk = AgentMessageChunk(
                            message_type="progress",
                            content=AgentMessageContent(type="text", data="[DONE]"),
                            timestamp=time.time()
                        )
                        yield done_chunk.to_sse_format()
                    except Exception as e:
                        logger.error(f"Error in streaming: {e}", exc_info=True)
                        error_chunk = AgentMessageChunk(
                            message_type="error",
                            content=AgentMessageContent(type="text", data=str(e)),
                            timestamp=time.time()
                        )
                        yield error_chunk.to_sse_format()
                        done_chunk = AgentMessageChunk(
                            message_type="progress",
                            content=AgentMessageContent(type="text", data="[DONE]"),
                            timestamp=time.time()
                        )
                        yield done_chunk.to_sse_format()
                
                defer_tableau_close = True
                return StreamingResponse(
                    _stream_with_tableau_cleanup(generate_stream()),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    }
                )
            else:
                # Non-streaming response with function calling support
                tools = get_tools()
                # Reuse tableau_client created earlier for context retrieval
                total_tokens = 0
                
                async with ai_client:
                    # First call: let LLM decide which tools to use
                    response = await ai_client.chat(
                        model=request.model,
                        provider=provider_for_state,
                        messages=messages,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        functions=[tool["function"] for tool in tools],
                        function_call="auto"
                    )
                    total_tokens += response.tokens_used
                    
                    # Handle function calls
                    if response.function_call:
                        function_name = response.function_call.name
                        import json
                        try:
                            arguments = json.loads(response.function_call.arguments)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse function arguments: {response.function_call.arguments}")
                            arguments = {}
                        
                        # Execute tool
                        tool_result = await execute_tool(
                            tool_name=function_name,
                            arguments=arguments,
                            tableau_client=tableau_client
                        )
                        
                        # Format result
                        formatted_result = format_tool_result(tool_result)
                        
                        # Add tool call and result to conversation
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "function_call": {
                                "name": function_name,
                                "arguments": response.function_call.arguments
                            }
                        })
                        messages.append({
                            "role": "function",
                            "name": function_name,
                            "content": formatted_result
                        })
                        
                        # Second call: let LLM generate final response with tool results
                        final_response = await ai_client.chat(
                            model=request.model,
                            provider=provider_for_state,
                            messages=messages,
                            temperature=request.temperature,
                            max_tokens=request.max_tokens
                        )
                        total_tokens += final_response.tokens_used
                        
                        final_content = final_response.content
                    else:
                        # No function call, use original response
                        final_content = response.content
                
                # Calculate total time for non-streaming general agent
                # Note: execution_start is defined earlier in the function for general agent
                total_time_ms = None
                try:
                    if 'execution_start' in locals():
                        total_time_ms = (time.time() - execution_start) * 1000
                except (NameError, TypeError) as e:
                    # Expected if execution_start not defined or invalid - continue silently
                    logger.debug(f"Could not calculate execution time: {e}")
                    pass
                except Exception as e:
                    # Log unexpected errors but continue
                    logger.warning(f"Unexpected error calculating execution time: {e}", exc_info=True)
                    pass
                
                # Save assistant message
                extra_metadata = {
                    "function_call": response.function_call.__dict__ if response.function_call else None,
                    "agent_type": agent_type or "general"
                }
                assistant_message = Message(
                    conversation_id=request.conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=final_content,
                    model_used=response.model,
                    tokens_used=total_tokens,
                    total_time_ms=total_time_ms,
                    extra_metadata=extra_metadata
                )
                db.add(assistant_message)
                conversation.updated_at = conversation.updated_at  # Trigger update
                safe_commit(db)
                db.refresh(assistant_message)
                
                return ChatResponse(
                    message=MessageResponse(
                        id=assistant_message.id,
                        conversation_id=assistant_message.conversation_id,
                        role=assistant_message.role.value,
                        content=assistant_message.content,
                        model_used=assistant_message.model_used,
                        tokens_used=assistant_message.tokens_used,
                        feedback=assistant_message.feedback,
                        total_time_ms=assistant_message.total_time_ms,
                        vizql_query=None,  # Not available for multi-agent
                        created_at=assistant_message.created_at
                    ),
                    conversation_id=request.conversation_id,
                    model=response.model,
                    tokens_used=total_tokens
                )
        except AIClientError as e:
            logger.error(f"AI client error: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"AI service error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error in chat: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error: {str(e)}"
            )
    finally:
        # Close tableau_client only for non-streaming; streaming paths close in _stream_with_tableau_cleanup
        if not defer_tableau_close and tableau_client:
            await tableau_client.close()


class MessageFeedbackRequest(BaseModel):
    """Request model for message feedback."""
    feedback: Optional[str] = Field(None, description="Feedback: 'thumbs_up', 'thumbs_down', or null to clear")
    feedback_text: Optional[str] = Field(None, max_length=1000, description="Optional feedback text")


@router.put("/messages/{message_id}/feedback", response_model=MessageResponse)
async def update_message_feedback(
    message_id: int,
    request: MessageFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Update feedback for a message."""
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Validate ownership via conversation
    conversation = db.query(Conversation).filter(Conversation.id == message.conversation_id).first()
    if conversation:
        if current_user:
            if conversation.user_id is not None and conversation.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="You don't have permission to modify this message")
        else:
            if conversation.user_id is not None:
                raise HTTPException(status_code=403, detail="Authentication required to modify this message")
    
    # Validate feedback value if provided
    if request.feedback is not None and request.feedback not in ['thumbs_up', 'thumbs_down']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feedback must be 'thumbs_up', 'thumbs_down', or null"
        )
    
    message.feedback = request.feedback
    message.feedback_text = request.feedback_text
    safe_commit(db)
    db.refresh(message)
    
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role.value,
        content=message.content,
        model_used=message.model_used,
        tokens_used=message.tokens_used,
        feedback=message.feedback,
        feedback_text=message.feedback_text,
        total_time_ms=message.total_time_ms,
        vizql_query=None,  # Not stored in DB
        created_at=message.created_at
    )


@router.delete("/conversations/{conversation_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    conversation_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Delete a single message from a conversation."""
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.conversation_id == conversation_id
    ).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conversation:
        if current_user and conversation.user_id is not None and conversation.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You don't have permission to delete this message")
        if conversation.user_id is not None and not current_user:
            raise HTTPException(status_code=403, detail="Authentication required to delete this message")
    db.delete(message)
    safe_commit(db)
    logger.info(f"Deleted message {message_id} from conversation {conversation_id}")


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Delete a conversation and all its messages."""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Validate ownership
    if current_user:
        if conversation.user_id is not None and conversation.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You don't have permission to delete this conversation")
    else:
        if conversation.user_id is not None:
            raise HTTPException(status_code=403, detail="Authentication required to delete this conversation")
    
    db.delete(conversation)
    safe_commit(db)
    logger.info(f"Deleted conversation {conversation_id}")


class DeleteAllConversationsResponse(BaseModel):
    """Response model for deleting all conversations."""
    deleted_count: int
    message: str


@router.delete("/conversations", status_code=status.HTTP_200_OK, response_model=DeleteAllConversationsResponse)
async def delete_all_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete all conversations and their messages for the current user."""
    # Find all conversations for this user
    conversations = db.query(Conversation).filter(Conversation.user_id == current_user.id).all()
    
    deleted_count = len(conversations)
    
    if deleted_count == 0:
        return DeleteAllConversationsResponse(
            deleted_count=0,
            message="No conversations found to delete"
        )
    
    # Delete all conversations (cascade will handle messages and chat_contexts)
    for conversation in conversations:
        db.delete(conversation)
    
    safe_commit(db)
    logger.info(f"User {current_user.id} deleted {deleted_count} conversation(s)")
    
    return DeleteAllConversationsResponse(
        deleted_count=deleted_count,
        message=f"Successfully deleted {deleted_count} conversation(s) and all associated messages"
    )


# Phase 5B: Chat Context Management
from app.api.models import (
    AddContextRequest,
    RemoveContextRequest,
    ChatContextObject,
    ChatContextResponse,
)


@router.post("/context/add", response_model=ChatContextObject, status_code=status.HTTP_201_CREATED)
async def add_context_object(
    request: AddContextRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Add an object (datasource or view) to chat context."""
    # Verify conversation exists
    conversation = db.query(Conversation).filter(Conversation.id == request.conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Validate ownership
    if current_user:
        if conversation.user_id is not None and conversation.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You don't have permission to modify this conversation")
    else:
        if conversation.user_id is not None:
            raise HTTPException(status_code=403, detail="Authentication required to modify this conversation")
    
    # Validate object type
    if request.object_type not in ["datasource", "view"]:
        raise HTTPException(status_code=400, detail="object_type must be 'datasource' or 'view'")
    
    # Check if object already in context
    existing = db.query(ChatContext).filter(
        ChatContext.conversation_id == request.conversation_id,
        ChatContext.object_id == request.object_id,
        ChatContext.object_type == request.object_type,
    ).first()
    
    if existing:
        # Update existing context object
        if request.object_name:
            existing.object_name = request.object_name
        safe_commit(db)
        db.refresh(existing)
        logger.info(f"Updated context object {request.object_id} for conversation {request.conversation_id}")
        return ChatContextObject(
            object_id=existing.object_id,
            object_type=existing.object_type,
            object_name=existing.object_name,
            added_at=existing.added_at.isoformat(),
        )
    
    # Create new context object
    context_obj = ChatContext(
        conversation_id=request.conversation_id,
        object_id=request.object_id,
        object_type=request.object_type,
        object_name=request.object_name,
    )
    db.add(context_obj)
    safe_commit(db)
    db.refresh(context_obj)
    
    logger.info(f"Added context object {request.object_id} ({request.object_type}) to conversation {request.conversation_id}")
    
    return ChatContextObject(
        object_id=context_obj.object_id,
        object_type=context_obj.object_type,
        object_name=context_obj.object_name,
        added_at=context_obj.added_at.isoformat(),
    )


@router.delete("/context/remove", status_code=status.HTTP_204_NO_CONTENT)
async def remove_context_object(
    conversation_id: int = Query(..., description="Conversation ID"),
    object_id: str = Query(..., description="Object ID to remove"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Remove an object from chat context."""
    # Verify conversation exists
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Validate ownership
    if current_user:
        if conversation.user_id is not None and conversation.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You don't have permission to modify this conversation")
    else:
        if conversation.user_id is not None:
            raise HTTPException(status_code=403, detail="Authentication required to modify this conversation")
    
    # Find and delete context object
    context_obj = db.query(ChatContext).filter(
        ChatContext.conversation_id == conversation_id,
        ChatContext.object_id == object_id,
    ).first()
    
    if not context_obj:
        raise HTTPException(status_code=404, detail="Context object not found")
    
    db.delete(context_obj)
    safe_commit(db)
    
    logger.info(f"Removed context object {object_id} from conversation {conversation_id}")


@router.get("/context/{conversation_id}", response_model=ChatContextResponse)
async def get_context(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    """Get chat context for a conversation."""
    # Verify conversation exists
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Get all context objects for this conversation
    context_objects = db.query(ChatContext).filter(
        ChatContext.conversation_id == conversation_id
    ).order_by(ChatContext.added_at).all()
    
    return ChatContextResponse(
        conversation_id=conversation_id,
        objects=[
            ChatContextObject(
                object_id=obj.object_id,
                object_type=obj.object_type,
                object_name=obj.object_name,
                added_at=obj.added_at.isoformat(),
            )
            for obj in context_objects
        ],
    )
