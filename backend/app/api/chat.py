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
        'summary': "Hello! I'm your Summary Agent. I excel at exporting and summarizing multiple Tableau views. I can help you combine insights from different visualizations and create comprehensive summaries. What views would you like me to summarize?",
    }
    
    # Default greeting if agent_type is not provided or invalid
    agent_type_normalized = agent_type.lower() if agent_type else 'vizql'
    greeting_content = greeting_messages.get(agent_type_normalized, greeting_messages['vizql'])
    
    # Create initial greeting message from assistant
    greeting_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=greeting_content,
        created_at=datetime.now(),
        extra_metadata={"is_greeting": True, "agent_type": agent_type_normalized}  # Mark as greeting message
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
        'summary': "Hello! I'm your Summary Agent. I excel at exporting and summarizing multiple Tableau views. I can help you combine insights from different visualizations and create comprehensive summaries. What views would you like me to summarize?",
    }
    
    # Normalize agent type (default to vizql)
    agent_type_normalized = agent_type.lower() if agent_type else 'vizql'
    greeting_content = greeting_messages.get(agent_type_normalized, greeting_messages['vizql'])
    
    # Create greeting message
    greeting_message = Message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=greeting_content,
        created_at=datetime.now(),
        extra_metadata={"is_greeting": True, "agent_type": agent_type_normalized}
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
    db: Session = Depends(get_db)
):
    """List all conversations with message counts."""
    try:
        conversations = db.query(Conversation).order_by(desc(Conversation.updated_at)).offset(skip).limit(limit).all()
        
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
        
        # Route to Multi-Agent Orchestrator
        if use_multi_agent:
            from app.services.agents.multi_agent import MultiAgentOrchestrator
            
            logger.info(f"Routing to Multi-Agent orchestrator")
            
            # Apply feedback-based refinement to query
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
            conversation_memory = get_conversation_memory(request.conversation_id)
            debugger = get_debugger()
            
            orchestrator = MultiAgentOrchestrator(
                model=request.model,
                provider=provider_for_state
            )
            
            if request.stream:
                # For streaming, we'll execute and stream the final answer
                # Multi-agent workflows are complex, so we stream the final combined result
                async def generate_multi_agent_stream():
                    try:
                        result = await orchestrator.execute_workflow(
                            user_query=refined_query,
                            context={
                                "datasources": datasource_ids,
                                "views": view_ids
                            },
                            tableau_client=tableau_client
                        )
                        
                        # Stream the final answer
                        final_answer = result.get("final_answer", "Workflow completed")
                        execution_trace = result.get("execution_trace", [])
                        
                        # Stream execution trace updates
                        for step in execution_trace:
                            if step.get("parallel"):
                                yield f"data: [PARALLEL] {step.get('agent_type')}: {step.get('action')}\n\n"
                            else:
                                yield f"data: [{step.get('agent_type')}] {step.get('action')}\n\n"
                        
                        # Stream final answer in chunks
                        words = final_answer.split()
                        for word in words:
                            yield f"data: {word} \n\n"
                        
                        yield "data: [DONE]\n\n"
                        
                        # Save final message
                        assistant_message = Message(
                            conversation_id=request.conversation_id,
                            role=MessageRole.ASSISTANT,
                            content=final_answer,
                            model_used=request.model,
                            extra_metadata={
                                "execution_id": execution_id,
                                "agent_type": "multi_agent",
                                "agents_used": result.get("agents_used", []),
                                "execution_trace": execution_trace
                            }
                        )
                        db.add(assistant_message)
                        conversation.updated_at = conversation.updated_at
                        safe_commit(db)
                        
                    except Exception as e:
                        logger.error(f"Error in multi-agent workflow: {e}", exc_info=True)
                        yield f"data: Error: {str(e)}\n\n"
                        yield "data: [DONE]\n\n"
                
                defer_tableau_close = True
                return StreamingResponse(
                    _stream_with_tableau_cleanup(generate_multi_agent_stream()),
                    media_type="text/event-stream"
                )
            else:
                # Non-streaming execution
                result = await orchestrator.execute_workflow(
                    user_query=refined_query,
                    context={
                        "datasources": datasource_ids,
                        "views": view_ids
                    },
                    tableau_client=tableau_client
                )
                
                final_answer = result.get("final_answer", "Workflow completed")
                execution_time = time.time() - execution_start
                
                # Track metrics
                metrics.record_agent_execution(
                    agent_type="multi_agent",
                    execution_time=execution_time,
                    success=True
                )
                
                # Save assistant message
                assistant_message = Message(
                    conversation_id=request.conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=final_answer,
                    model_used=request.model,
                    extra_metadata={
                        "execution_id": execution_id,
                        "agent_type": "multi_agent",
                        "agents_used": result.get("agents_used", []),
                        "execution_trace": result.get("execution_trace", []),
                        "execution_time": execution_time
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
                        vizql_query=None,  # Not available for multi-agent
                        created_at=assistant_message.created_at
                    ),
                    conversation_id=request.conversation_id,
                    model=request.model,
                    tokens_used=0
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
            
            # Create graph with version and retry settings
            graph = AgentGraphFactory.create_vizql_graph(
                version=agent_version,
                max_build_retries=max_build_retries,
                max_execution_retries=max_execution_retries
            )
            
            # Initialize state for VizQL agent based on version
            if agent_version == "v3":
                # Streamlined agent state (v3)
                message_history = []
                for msg in history_messages:
                    msg_dict = {
                        "role": msg.role.value.lower() if isinstance(msg.role, MessageRole) else str(msg.role).lower(),
                        "content": msg.content
                    }
                    # Add query_draft and query_results for prior query reuse
                    if msg.role == MessageRole.ASSISTANT and msg.extra_metadata:
                        if isinstance(msg.extra_metadata, dict):
                            msg_dict["query_draft"] = msg.extra_metadata.get('vizql_query')
                            msg_dict["query_results"] = msg.extra_metadata.get('query_results')
                    message_history.append(msg_dict)
                
                logger.info(f"Initializing streamlined graph state (v3) with model: {request.model}")
                initial_state = {
                    "user_query": refined_query,
                    "agent_type": "vizql",
                    "context_datasources": datasource_ids,
                    "context_views": view_ids,
                    "messages": message_history,
                    "tool_calls": [],
                    "tool_results": [],
                    "current_thought": None,
                    "final_answer": None,
                    "error": None,
                    "confidence": None,
                    "processing_time": None,
                    "model": request.model,
                    "provider": provider_for_state,
                    "site_id": (tableau_client.site_id or "") if tableau_client else settings.TABLEAU_SITE_ID,
                    "build_attempt": 1,
                    "execution_attempt": 1,
                    "query_version": 0,
                    "reasoning_steps": [],
                    "build_errors": None,
                    "execution_errors": None,
                    "enriched_schema": None,  # Optional - can be pre-fetched
                    "schema": None,  # Will be fetched if needed
                }
            elif agent_version == "v2":
                # Tool-use agent state (v2)
                tool_use_message_history = []
                for msg in history_messages:
                    msg_dict = {
                        "role": msg.role.value.lower() if isinstance(msg.role, MessageRole) else str(msg.role).lower(),
                        "content": msg.content
                    }
                    # Add metadata and dimension values for assistant messages with query results
                    if msg.role == MessageRole.ASSISTANT and msg.extra_metadata:
                        if isinstance(msg.extra_metadata, dict):
                            vizql_query = msg.extra_metadata.get('vizql_query')
                            query_results = msg.extra_metadata.get('query_results')
                            if query_results:
                                row_count = query_results.get('row_count', len(query_results.get('data', [])))
                                columns = query_results.get('columns', [])
                                dimension_values = query_results.get('dimension_values', {})
                                
                                msg_dict["data_metadata"] = {
                                    "row_count": row_count,
                                    "columns": columns,
                                    "dimension_values": dimension_values
                                }
                            if vizql_query:
                                msg_dict["original_query"] = str(vizql_query)
                    tool_use_message_history.append(msg_dict)
                
                logger.info(f"Initializing tool-use agent state (v2) with model: {request.model}")
                initial_state = {
                    "user_query": refined_query,
                    "message_history": tool_use_message_history,
                    "site_id": (tableau_client.site_id or "") if tableau_client else settings.TABLEAU_SITE_ID,
                    "datasource_id": datasource_ids[0] if datasource_ids else None,
                    "tableau_client": tableau_client,
                    "raw_data": None,
                    "tool_calls": [],
                    "final_answer": None,
                    "error": None,
                    "model": request.model,
                    "provider": provider_for_state,
                }
            else:  # v1
                # Graph-based agent state (v1 - original)
                initial_state = {
                    "user_query": refined_query,
                    "agent_type": "vizql",
                    "context_datasources": datasource_ids,
                    "context_views": view_ids,
                    "messages": [],
                    "tool_calls": [],
                    "tool_results": [],
                    "current_thought": None,
                    "final_answer": None,
                    "error": None,
                    "confidence": None,
                    "processing_time": None,
                    # AI client configuration
                    "model": request.model,
                    "provider": provider_for_state,
                    # VizQL-specific fields
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
            
            if request.stream:
                # Stream graph execution
                async def stream_graph():
                    full_content = ""
                    last_final_answer = ""
                    last_state = None
                    reasoningStepIndex = 0  # Track reasoning step index
                    stream_start_time = time.time()  # Track when streaming starts
                    stream_graph._query_sent = False  # Track if query has been sent
                    stream_graph._streamed_node_thoughts = set()  # Track which node thoughts we've already streamed
                    try:
                        # Log timing before graph execution starts
                        pre_graph_time = time.time()
                        logger.info(f"About to start graph execution. Time since stream_start: {(pre_graph_time - stream_start_time) * 1000:.2f}ms")
                        
                        # Provide config with thread_id + tableau_client (not in state - not serializable)
                        config = {"configurable": {"thread_id": f"vizql-{request.conversation_id}", "tableau_client": tableau_client}}
                        
                        # Log timing right before astream
                        pre_astream_time = time.time()
                        logger.info(f"About to call graph.astream(). Time since stream_start: {(pre_astream_time - stream_start_time) * 1000:.2f}ms")
                        
                        async for state_update in graph.astream(initial_state, config=config):
                            # Log timing when first state update arrives
                            first_update_time = time.time()
                            if not hasattr(stream_graph, '_first_update_logged'):
                                logger.info(f"First state update received. Time since stream_start: {(first_update_time - stream_start_time) * 1000:.2f}ms, since pre_astream: {(first_update_time - pre_astream_time) * 1000:.2f}ms")
                                stream_graph._first_update_logged = True
                            # LangGraph astream returns updates keyed by node name
                            # Each update contains the state dictionary for that node
                            logger.debug(f"VizQL graph state update - node keys: {list(state_update.keys())}")
                            
                            # Iterate through all node updates in this state update
                            for node_name, node_state in state_update.items():
                                logger.debug(f"Processing node '{node_name}' - state keys: {list(node_state.keys()) if isinstance(node_state, dict) else 'not dict'}")
                                
                                # Keep track of the last state for final extraction
                                if isinstance(node_state, dict):
                                    last_state = node_state
                                
                                # Stream intermediate thoughts as reasoning steps
                                # Only stream one step per node (from current_thought), not individual tool calls
                                if isinstance(node_state, dict) and "current_thought" in node_state and node_state.get("current_thought"):
                                    thought = node_state["current_thought"]
                                    
                                    # For build_query node, use build_attempt to create unique key (allow multiple builds)
                                    # For other nodes, use node name to prevent duplicates
                                    if node_name == "build_query":
                                        build_attempt = node_state.get("build_attempt", 1)
                                        node_thought_key = f"{node_name}_thought_attempt_{build_attempt}"
                                    else:
                                        node_thought_key = f"{node_name}_thought"
                                    
                                    if node_thought_key not in stream_graph._streamed_node_thoughts:
                                        logger.info(f"Streaming reasoning step from {node_name}: {thought[:100]}")
                                        
                                        # Extract step metadata if available (tool calls, tokens, query_draft)
                                        step_metadata = dict(node_state.get("step_metadata") or {})
                                        # Only include query_draft for build_query and pre_validation
                                        if node_name == "build_query":
                                            if "query_draft" in node_state:
                                                step_metadata["query_draft"] = node_state.get("query_draft")
                                            step_metadata["build_attempt"] = node_state.get("build_attempt", 1)
                                        elif node_name in ("validate_query", "execute_query"):
                                            step_metadata.pop("query_draft", None)
                                        elif node_name == "pre_validation":
                                            if "query_draft" in node_state:
                                                step_metadata["query_draft"] = node_state.get("query_draft")
                                        
                                        reasoning_chunk = AgentMessageChunk(
                                            message_type="reasoning",
                                            content=AgentMessageContent(type="text", data=thought),
                                            step_name=node_name,
                                            timestamp=time.time(),  # Unix timestamp in seconds
                                            step_index=reasoningStepIndex,
                                            metadata=step_metadata if step_metadata else None
                                        )
                                        reasoningStepIndex += 1
                                        yield reasoning_chunk.to_sse_format()
                                        stream_graph._streamed_node_thoughts.add(node_thought_key)
                                        full_content += " " + thought  # Track to avoid duplicates
                                
                                # Stream final answer when available
                                if isinstance(node_state, dict) and "final_answer" in node_state and node_state.get("final_answer"):
                                    answer = node_state["final_answer"]
                                    logger.info(f"Found final_answer in {node_name}: {answer[:200]}")
                                    # Send the full answer if it's new or has changed
                                    if answer != last_final_answer:
                                        # If we haven't sent this answer yet, send it all
                                        if last_final_answer == "":
                                            logger.info(f"Streaming full final_answer from {node_name}: {len(answer)} chars")
                                            answer_chunk = AgentMessageChunk(
                                                message_type="final_answer",
                                                content=AgentMessageContent(type="text", data=answer),
                                                timestamp=time.time()
                                            )
                                            yield answer_chunk.to_sse_format()
                                        else:
                                            # Send only the new part
                                            new_content = answer[len(last_final_answer):]
                                            if new_content:
                                                logger.info(f"Streaming new content from {node_name}: {len(new_content)} chars")
                                                answer_chunk = AgentMessageChunk(
                                                    message_type="final_answer",
                                                    content=AgentMessageContent(type="text", data=new_content),
                                                    timestamp=time.time()
                                                )
                                                yield answer_chunk.to_sse_format()
                                        last_final_answer = answer
                                        full_content = answer
                        
                        # After streaming completes, check last state for final_answer if we didn't get it
                        if not full_content:
                            logger.warning(f"Streaming completed but no full_content received. Last state: {type(last_state)}")
                            
                            # last_state should be a dict from the last node update
                            if last_state and isinstance(last_state, dict):
                                logger.info(f"Checking last_state for final_answer - keys: {list(last_state.keys())}")
                                final_answer = last_state.get("final_answer")
                                if not final_answer:
                                    # Try to extract error or other info
                                    error = last_state.get("error")
                                    execution_error = last_state.get("execution_error")
                                    validation_errors = last_state.get("validation_errors", [])
                                    
                                    logger.info(f"Extracting from last_state - error: {error}, execution_error: {execution_error}, validation_errors: {validation_errors}")
                                    
                                    if error:
                                        final_answer = f"Error: {error}"
                                    elif execution_error:
                                        final_answer = f"Execution error: {execution_error}"
                                    elif validation_errors:
                                        final_answer = f"Validation errors: {', '.join(validation_errors)}"
                                    else:
                                        # Check if we have query_results but no formatted answer
                                        query_results = last_state.get("query_results")
                                        if query_results:
                                            row_count = query_results.get("row_count", 0)
                                            final_answer = f"Query executed successfully! Retrieved {row_count} row(s)."
                                        else:
                                            final_answer = "Query execution completed but no response was generated."
                                
                                if final_answer and final_answer != last_final_answer:
                                    logger.info(f"Sending final_answer after stream: {final_answer[:200]}")
                                    # Send as structured final_answer chunk
                                    answer_chunk = AgentMessageChunk(
                                        message_type="final_answer",
                                        content=AgentMessageContent(type="text", data=final_answer),
                                        timestamp=time.time()
                                    )
                                    yield answer_chunk.to_sse_format()
                                    full_content = final_answer
                        
                        # Extract VizQL query from last_state for saving and streaming
                        # Always try to get query_draft, even if there were errors
                        vizql_query = None
                        if last_state:
                            logger.info(f"Extracting VizQL query from last_state. Keys: {list(last_state.keys())}")
                            
                            # Try multiple keys where query might be stored
                            for key in ["query_draft", "query", "validated_query"]:
                                if key in last_state and last_state.get(key):
                                    vizql_query = last_state.get(key)
                                    logger.info(f"Found VizQL query in key '{key}'")
                                    break
                            
                            # For tool-use agent, also check tool_calls for query
                            if not vizql_query and "tool_calls" in last_state:
                                tool_calls = last_state.get("tool_calls", [])
                                logger.info(f"Checking {len(tool_calls)} tool_calls for VizQL query")
                                for tool_call in tool_calls:
                                    if tool_call.get("tool") in ["build_query", "query_datasource"]:
                                        result = tool_call.get("result", {})
                                        if isinstance(result, dict):
                                            vizql_query = result.get("query") or result.get("query_draft")
                                            if vizql_query:
                                                logger.info(f"Extracted VizQL query from tool_call: {tool_call.get('tool')}")
                                                break
                        
                        # Send vizql_query as metadata chunk if available and not already sent
                        if vizql_query and not getattr(stream_graph, '_query_sent', False):
                            logger.info(f"Sending VizQL query as metadata chunk: {str(vizql_query)[:200]}")
                            metadata_chunk = AgentMessageChunk(
                                message_type="metadata",
                                content=AgentMessageContent(type="json", data={"vizql_query": vizql_query}),
                                timestamp=time.time()
                            )
                            yield metadata_chunk.to_sse_format()
                            stream_graph._query_sent = True
                        elif not vizql_query:
                            logger.warning("No VizQL query found to send as metadata")
                        
                        # Ensure we have content to save - if not, try to get it from last_state one more time
                        if not full_content and last_state:
                            logger.warning("No content after streaming, attempting to extract from last_state")
                            # Check all possible sources
                            full_content = (
                                last_state.get("final_answer") or
                                last_state.get("formatted_response") or
                                (f"Error: {last_state.get('error')}" if last_state.get("error") else None) or
                                (f"Execution error: {last_state.get('execution_error')}" if last_state.get("execution_error") else None) or
                                "Query execution completed. Please check the conversation messages."
                            )
                            if full_content and full_content != "Query execution completed. Please check the conversation messages.":
                                logger.info(f"Extracted content from last_state: {full_content[:200]}")
                                # Send as structured final_answer chunk
                                answer_chunk = AgentMessageChunk(
                                    message_type="final_answer",
                                    content=AgentMessageContent(type="text", data=full_content),
                                    timestamp=time.time()
                                )
                                yield answer_chunk.to_sse_format()
                        
                        # Save assistant message after streaming completes
                        if full_content:
                            try:
                                # Calculate total time (from when user message was created to now)
                                stream_end_time = time.time()
                                total_time_ms = (stream_end_time - stream_start_time) * 1000  # Convert to milliseconds
                                
                                # Extract VizQL query and query results from last_state for storage
                                stored_vizql_query = None
                                stored_query_results = None
                                
                                if last_state:
                                    # Extract query
                                    for key in ["query_draft", "query", "validated_query"]:
                                        if key in last_state and last_state.get(key):
                                            stored_vizql_query = last_state.get(key)
                                            break
                                    
                                    # For tool-use agent, check tool_calls for query
                                    if not stored_vizql_query and "tool_calls" in last_state:
                                        tool_calls = last_state.get("tool_calls", [])
                                        for tool_call in tool_calls:
                                            if tool_call.get("tool") in ["build_query", "query_datasource"]:
                                                result = tool_call.get("result", {})
                                                if isinstance(result, dict):
                                                    stored_vizql_query = result.get("query") or result.get("query_draft")
                                                    if stored_vizql_query:
                                                        break
                                    
                                    # Extract query results METADATA and DIMENSION VALUES
                                    # Priority: Use shown_entities from summarizer (most accurate)
                                    # Fallback: Extract from raw_data only if small dataset
                                    
                                    dimension_values = {}
                                    
                                    # PRIORITY 1: Check if summarizer provided shown_entities (most accurate)
                                    shown_entities = last_state.get("shown_entities")
                                    if shown_entities and isinstance(shown_entities, dict):
                                        dimension_values = shown_entities
                                        logger.info(f"Using shown_entities from summarizer: {len(dimension_values)} dimensions")
                                    
                                    # PRIORITY 2: Fallback to extracting from raw_data only if small dataset
                                    elif not dimension_values:
                                        raw_data = last_state.get("raw_data")
                                        if raw_data and isinstance(raw_data, dict):
                                            if "columns" in raw_data and "data" in raw_data:
                                                row_count = raw_data.get("row_count", len(raw_data.get("data", [])))
                                                # Only extract if dataset is small (< 100 rows) to avoid 4,703 city problem
                                                if row_count < 100:
                                                    from app.services.agents.vizql_tool_use.context_extractor import extract_dimension_values
                                                    dimension_values = extract_dimension_values(raw_data, max_values_per_dimension=50)
                                                    logger.info(f"Fallback: Extracted from raw_data (small dataset): {row_count} rows, {len(dimension_values)} dimensions")
                                                else:
                                                    logger.info(f"Skipping extraction from raw_data: dataset too large ({row_count} rows)")
                                    
                                    raw_data = last_state.get("raw_data")
                                    if raw_data and isinstance(raw_data, dict):
                                        # Check if raw_data has the query results format
                                        if "columns" in raw_data and "data" in raw_data:
                                            stored_query_results = {
                                                "columns": raw_data.get("columns"),
                                                "row_count": raw_data.get("row_count", len(raw_data.get("data", []))),
                                                "dimension_values": dimension_values  # Store dimension values (from summarizer or extracted)
                                                # NOTE: NOT storing full "data" array - only metadata + dimension values
                                            }
                                            logger.info(f"Stored query_results metadata: {stored_query_results.get('row_count', 0)} rows, {len(dimension_values)} dimensions (data array excluded)")
                                        elif "tool_calls" in last_state:
                                            # Extract from query_datasource tool call result
                                            tool_calls = last_state.get("tool_calls", [])
                                            for tool_call in tool_calls:
                                                if tool_call.get("tool") == "query_datasource":
                                                    result = tool_call.get("result", {})
                                                    if isinstance(result, dict) and "data" in result:
                                                        # Extract dimension values for context
                                                        # Only extract if small dataset to avoid 4,703 city problem
                                                        dimension_values = {}
                                                        row_count = result.get("row_count", len(result.get("data", [])))
                                                        
                                                        if row_count < 100:
                                                            from app.services.agents.vizql_tool_use.context_extractor import extract_dimension_values
                                                            dimension_values = extract_dimension_values(result, max_values_per_dimension=50)
                                                            logger.info(f"Extracted from query_datasource tool (small dataset): {row_count} rows, {len(dimension_values)} dimensions")
                                                        else:
                                                            logger.info(f"Skipping extraction from query_datasource tool: dataset too large ({row_count} rows)")
                                                        
                                                        stored_query_results = {
                                                            "columns": result.get("columns", []),
                                                            "row_count": row_count,
                                                            "dimension_values": dimension_values  # Store dimension values (only if small dataset)
                                                            # NOTE: NOT storing full "data" array - only metadata + dimension values
                                                        }
                                                        logger.info(f"Stored query_results metadata from tool call: {row_count} rows, {len(dimension_values)} dimensions (data array excluded)")
                                                        break
                                
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
                        # Try to extract query_draft even on error if last_state is available
                        error_vizql_query = None
                        try:
                            if 'last_state' in locals() and last_state:
                                error_vizql_query = last_state.get("query_draft")
                                # Also check alternative keys
                                if not error_vizql_query:
                                    for key in ["query", "validated_query"]:
                                        if key in last_state:
                                            error_vizql_query = last_state.get(key)
                                            break
                                
                                # For tool-use agent, also check tool_calls
                                if not error_vizql_query and "tool_calls" in last_state:
                                    tool_calls = last_state.get("tool_calls", [])
                                    for tool_call in tool_calls:
                                        if tool_call.get("tool") in ["build_query", "query_datasource"]:
                                            result = tool_call.get("result", {})
                                            if isinstance(result, dict):
                                                error_vizql_query = result.get("query") or result.get("query_draft")
                                                if error_vizql_query:
                                                    break
                        except (KeyError, AttributeError, TypeError) as e:
                            # Expected errors when extracting query from result - continue silently
                            logger.debug(f"Could not extract query from result: {e}")
                            pass
                        except Exception as e:
                            # Log unexpected errors but continue
                            logger.warning(f"Unexpected error extracting query from result: {e}", exc_info=True)
                            pass
                        
                        # Send query as metadata even on error if available and not already sent
                        if error_vizql_query and not getattr(stream_graph, '_query_sent', False):
                            metadata_chunk = AgentMessageChunk(
                                message_type="metadata",
                                content=AgentMessageContent(type="json", data={"vizql_query": error_vizql_query}),
                                timestamp=time.time()
                            )
                            yield metadata_chunk.to_sse_format()
                            stream_graph._query_sent = True
                        
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
                # Non-streaming: execute graph and return result
                # Provide config with thread_id + tableau_client (not in state - not serializable)
                config = {"configurable": {"thread_id": f"vizql-{request.conversation_id}", "tableau_client": tableau_client}}
                
                try:
                    logger.info(f"Executing VizQL graph for conversation {request.conversation_id} (execution_id: {execution_id})")
                    
                    # Track node states during execution for debugging
                    if request.stream:
                        # For streaming, we'll track states from astream
                        async def track_states():
                            async for state in graph.astream(initial_state, config=config):
                                node_states.append({
                                    "timestamp": time.time(),
                                    "state_keys": list(state.keys()),
                                    "has_error": "error" in state,
                                    "has_final_answer": "final_answer" in state
                                })
                                yield state
                        
                        # This won't work directly - need to handle differently
                        # For now, just execute normally
                        final_state = await graph.ainvoke(initial_state, config=config)
                    else:
                        final_state = await graph.ainvoke(initial_state, config=config)
                    
                    execution_time = time.time() - execution_start
                    logger.info(f"VizQL graph completed in {execution_time:.3f}s. Final state keys: {list(final_state.keys())}")
                    
                    # Track metrics
                    success = final_state.get("error") is None and final_state.get("execution_error") is None
                    metrics.record_agent_execution("vizql", execution_time, success=success)
                    
                    # Track in debugger
                    debugger.record_execution(
                        execution_id=execution_id,
                        agent_type="vizql",
                        initial_state=initial_state,
                        final_state=final_state,
                        execution_time=execution_time,
                        node_states=node_states
                    )
                    
                    # Track in memory
                    query_id = f"vizql-{request.conversation_id}-{int(time.time())}"
                    conversation_memory.add_message(
                        query_id=query_id,
                        user_query=request.content,
                        agent_type="vizql",
                        response=final_state.get("final_answer", ""),
                        datasource_ids=datasource_ids,
                        view_ids=view_ids
                    )
                    
                    # Get final answer or error
                    final_answer = final_state.get("final_answer")
                    if not final_answer:
                        error = final_state.get("error")
                        execution_error = final_state.get("execution_error")
                        validation_errors = final_state.get("validation_errors", [])
                        
                        if error:
                            final_answer = f"Error: {error}"
                        elif execution_error:
                            final_answer = f"Execution error: {execution_error}"
                        elif validation_errors:
                            final_answer = f"Validation errors: {', '.join(validation_errors)}"
                        else:
                            final_answer = "Query execution completed but no response was generated. Please check the logs."
                            logger.warning(f"No final_answer or error in final state: {final_state}")
                    
                    # Extract VizQL query and query results from final state - always include it, even on errors
                    vizql_query = None
                    query_results = None
                    
                    if final_state:
                        # Try multiple keys where query might be stored
                        for key in ["query_draft", "query", "validated_query"]:
                            if key in final_state and final_state.get(key):
                                vizql_query = final_state.get(key)
                                break
                        
                        # Extract query results METADATA and DIMENSION VALUES
                        # Priority: Use shown_entities from summarizer, fallback to raw_data if small
                        
                        dimension_values = {}
                        
                        # PRIORITY 1: Check if summarizer provided shown_entities
                        shown_entities = final_state.get("shown_entities")
                        if shown_entities and isinstance(shown_entities, dict):
                            dimension_values = shown_entities
                            logger.info(f"Non-streaming: Using shown_entities from summarizer: {len(dimension_values)} dimensions")
                        
                        # PRIORITY 2: Fallback to extracting from raw_data only if small dataset
                        elif not dimension_values:
                            raw_data = final_state.get("raw_data")
                            if raw_data and isinstance(raw_data, dict):
                                if "columns" in raw_data and "data" in raw_data:
                                    row_count = raw_data.get("row_count", len(raw_data.get("data", [])))
                                    if row_count < 100:
                                        from app.services.agents.vizql_tool_use.context_extractor import extract_dimension_values
                                        dimension_values = extract_dimension_values(raw_data, max_values_per_dimension=50)
                                        logger.info(f"Non-streaming: Fallback extraction from raw_data (small dataset): {row_count} rows, {len(dimension_values)} dimensions")
                                    else:
                                        logger.info(f"Non-streaming: Skipping extraction from raw_data: dataset too large ({row_count} rows)")
                        
                        raw_data = final_state.get("raw_data")
                        if raw_data and isinstance(raw_data, dict):
                            if "columns" in raw_data and "data" in raw_data:
                                query_results = {
                                    "columns": raw_data.get("columns"),
                                    "row_count": raw_data.get("row_count", len(raw_data.get("data", []))),
                                    "dimension_values": dimension_values  # Store dimension values (from summarizer or extracted)
                                    # NOTE: NOT storing full "data" array - only metadata + dimension values
                                }
                                logger.info(f"Non-streaming: Stored query_results metadata: {query_results.get('row_count', 0)} rows, {len(dimension_values)} dimensions (data array excluded)")
                        
                        # For tool-use agent, also check tool_calls
                        if not vizql_query and "tool_calls" in final_state:
                            tool_calls = final_state.get("tool_calls", [])
                            for tool_call in tool_calls:
                                if tool_call.get("tool") in ["build_query", "query_datasource"]:
                                    result = tool_call.get("result", {})
                                    if isinstance(result, dict):
                                        vizql_query = result.get("query") or result.get("query_draft")
                                        if vizql_query:
                                            break
                        
                        # Extract query results METADATA ONLY from query_datasource tool call if not already found
                        if not query_results and "tool_calls" in final_state:
                            tool_calls = final_state.get("tool_calls", [])
                            for tool_call in tool_calls:
                                if tool_call.get("tool") == "query_datasource":
                                    result = tool_call.get("result", {})
                                    if isinstance(result, dict) and "data" in result:
                                        # Extract dimension values only if small dataset
                                        dimension_values = {}
                                        row_count = result.get("row_count", len(result.get("data", [])))
                                        
                                        if row_count < 100:
                                            from app.services.agents.vizql_tool_use.context_extractor import extract_dimension_values
                                            dimension_values = extract_dimension_values(result, max_values_per_dimension=50)
                                            logger.info(f"Non-streaming: Extracted from query_datasource tool (small dataset): {row_count} rows, {len(dimension_values)} dimensions")
                                        else:
                                            logger.info(f"Non-streaming: Skipping extraction from query_datasource tool: dataset too large ({row_count} rows)")
                                        
                                        query_results = {
                                            "columns": result.get("columns", []),
                                            "row_count": row_count,
                                            "dimension_values": dimension_values  # Store dimension values (only if small dataset)
                                            # NOTE: NOT storing full "data" array - only metadata + dimension values
                                        }
                                        logger.info(f"Non-streaming: Stored query_results metadata from tool call: {row_count} rows, {len(dimension_values)} dimensions (data array excluded)")
                                        break
                except Exception as e:
                    execution_time = time.time() - execution_start
                    logger.error(f"Error executing VizQL graph: {e}", exc_info=True)
                    metrics.record_agent_execution("vizql", execution_time, success=False)
                    final_answer = f"Error executing query: {str(e)}"
                    # Try to extract query_draft even on exception if we have partial state
                    vizql_query = None
                    try:
                        # Try to get final_state from exception context if available
                        if 'final_state' in locals() and final_state:
                            for key in ["query_draft", "query", "validated_query"]:
                                if key in final_state and final_state.get(key):
                                    vizql_query = final_state.get(key)
                                    break
                    except (KeyError, AttributeError, TypeError) as e:
                        # Expected errors when extracting query from state - continue silently
                        logger.debug(f"Could not extract query from final_state: {e}")
                        pass
                    except Exception as e:
                        # Log unexpected errors but continue
                        logger.warning(f"Unexpected error extracting query from final_state: {e}", exc_info=True)
                        pass
                
                # Save assistant message
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
        
        # Route to Summary agent graph
        elif agent_type == 'summary' and view_ids:
            from app.services.agents.graph_factory import AgentGraphFactory
            
            logger.info(f"Routing to Summary agent graph with views: {view_ids}")
            
            # Apply feedback-based refinement to query
            from app.services.agents.feedback import FeedbackManager
            feedback_manager = FeedbackManager(db=db, model=request.model, provider=provider)
            refined_query_result = await feedback_manager.apply_feedback_to_query(
                query=request.content,
                conversation_id=request.conversation_id,
                agent_type="summary"
            )
            refined_query = refined_query_result.get("refined_query", request.content)
            
            if refined_query != request.content:
                logger.info(f"Query refined based on feedback: {refined_query_result.get('changes')}")
            
            # Track execution start time
            execution_start = time.time()
            metrics = get_metrics()
            conversation_memory = get_conversation_memory(request.conversation_id)
            
            graph = AgentGraphFactory.create_summary_graph()
            
            # Initialize state for Summary agent
            initial_state = {
                "user_query": refined_query,
                "agent_type": "summary",
                "context_datasources": datasource_ids,
                "context_views": view_ids,
                "messages": [],
                "tool_calls": [],
                "tool_results": [],
                "current_thought": None,
                "final_answer": None,
                "error": None,
                "confidence": None,
                "processing_time": None,
                # AI client configuration
                "model": request.model,
                "provider": provider_for_state,
                "embedded_state": request.embedded_state or None,
            }
            
            if request.stream:
                # Stream graph execution
                async def stream_graph():
                    full_content = ""
                    last_final_answer = ""
                    last_state = None
                    reasoningStepIndex = 0
                    stream_start_time = time.time()  # Track when streaming starts
                    stream_graph._streamed_node_thoughts = set()  # Track which node thoughts we've already streamed
                    try:
                        # Provide config with thread_id + tableau_client (not in state - not msgpack serializable)
                        config = {"configurable": {"thread_id": f"summary-{request.conversation_id}", "tableau_client": tableau_client}}
                        async for state_update in graph.astream(initial_state, config=config):
                            # LangGraph astream returns updates keyed by node name
                            # Each update contains the state dictionary for that node
                            logger.debug(f"Summary graph state update - node keys: {list(state_update.keys())}")
                            
                            # Iterate through all node updates in this state update
                            for node_name, node_state in state_update.items():
                                logger.debug(f"Processing node '{node_name}' - state keys: {list(node_state.keys()) if isinstance(node_state, dict) else 'not dict'}")
                                
                                # Keep track of the last state for final extraction
                                if isinstance(node_state, dict):
                                    last_state = node_state
                                
                                # Stream intermediate thoughts as reasoning steps
                                # Only stream one step per node (from current_thought), not individual tool calls
                                if isinstance(node_state, dict) and "current_thought" in node_state and node_state.get("current_thought"):
                                    thought = node_state["current_thought"]
                                    
                                    # For build_query node, use build_attempt to create unique key (allow multiple builds)
                                    # For other nodes, use node name to prevent duplicates
                                    if node_name == "build_query":
                                        build_attempt = node_state.get("build_attempt", 1)
                                        node_thought_key = f"{node_name}_thought_attempt_{build_attempt}"
                                    else:
                                        node_thought_key = f"{node_name}_thought"
                                    
                                    if node_thought_key not in stream_graph._streamed_node_thoughts:
                                        logger.info(f"Streaming reasoning step from {node_name}: {thought[:100]}")
                                        
                                        # Extract step metadata if available (tool calls, tokens, query_draft)
                                        step_metadata = dict(node_state.get("step_metadata") or {})
                                        # Only include query_draft for build_query and pre_validation
                                        if node_name == "build_query":
                                            if "query_draft" in node_state:
                                                step_metadata["query_draft"] = node_state.get("query_draft")
                                            step_metadata["build_attempt"] = node_state.get("build_attempt", 1)
                                        elif node_name in ("validate_query", "execute_query"):
                                            step_metadata.pop("query_draft", None)
                                        elif node_name == "pre_validation":
                                            if "query_draft" in node_state:
                                                step_metadata["query_draft"] = node_state.get("query_draft")
                                        
                                        reasoning_chunk = AgentMessageChunk(
                                            message_type="reasoning",
                                            content=AgentMessageContent(type="text", data=thought),
                                            step_name=node_name,
                                            timestamp=time.time(),  # Unix timestamp in seconds
                                            step_index=reasoningStepIndex,
                                            metadata=step_metadata if step_metadata else None
                                        )
                                        reasoningStepIndex += 1
                                        yield reasoning_chunk.to_sse_format()
                                        stream_graph._streamed_node_thoughts.add(node_thought_key)
                                        full_content += " " + thought  # Track to avoid duplicates
                                
                                # Stream final answer when available
                                if isinstance(node_state, dict) and "final_answer" in node_state and node_state.get("final_answer"):
                                    answer = node_state["final_answer"]
                                    logger.info(f"Found final_answer in {node_name}: {answer[:200]}")
                                    # Send the full answer if it's new or has changed
                                    if answer != last_final_answer:
                                        # If we haven't sent this answer yet, send it all
                                        if last_final_answer == "":
                                            logger.info(f"Streaming full final_answer from {node_name}: {len(answer)} chars")
                                            answer_chunk = AgentMessageChunk(
                                                message_type="final_answer",
                                                content=AgentMessageContent(type="text", data=answer),
                                                timestamp=time.time()
                                            )
                                            yield answer_chunk.to_sse_format()
                                        else:
                                            # Send only the new part
                                            new_content = answer[len(last_final_answer):]
                                            if new_content:
                                                logger.info(f"Streaming new content from {node_name}: {len(new_content)} chars")
                                                answer_chunk = AgentMessageChunk(
                                                    message_type="final_answer",
                                                    content=AgentMessageContent(type="text", data=new_content),
                                                    timestamp=time.time()
                                                )
                                                yield answer_chunk.to_sse_format()
                                        last_final_answer = answer
                                        full_content = answer
                        
                        # After streaming completes, check last state for final_answer if we didn't get it
                        if not full_content:
                            logger.warning(f"Streaming completed but no full_content received. Last state: {type(last_state)}")
                            
                            # last_state should be a dict from the last node update
                            if last_state and isinstance(last_state, dict):
                                logger.info(f"Checking last_state for final_answer - keys: {list(last_state.keys())}")
                                final_answer = last_state.get("final_answer")
                                if not final_answer:
                                    # Try to extract error or other info
                                    error = last_state.get("error")
                                    executive_summary = last_state.get("executive_summary")
                                    detailed_analysis = last_state.get("detailed_analysis")
                                    
                                    logger.info(f"Extracting from last_state - error: {error}, executive_summary: {executive_summary}, detailed_analysis: {detailed_analysis}")
                                    
                                    if error:
                                        final_answer = f"Error: {error}"
                                    elif executive_summary:
                                        final_answer = executive_summary
                                    elif detailed_analysis:
                                        final_answer = detailed_analysis
                                    else:
                                        final_answer = "Summary generation completed but no response was generated."
                                
                                if final_answer and final_answer != last_final_answer:
                                    logger.info(f"Sending final_answer after stream: {final_answer[:200]}")
                                    # Send as structured final_answer chunk
                                    answer_chunk = AgentMessageChunk(
                                        message_type="final_answer",
                                        content=AgentMessageContent(type="text", data=final_answer),
                                        timestamp=time.time()
                                    )
                                    yield answer_chunk.to_sse_format()
                                    full_content = final_answer
                        
                        # Ensure we have content to save - if not, try to get it from last_state one more time
                        if not full_content and last_state:
                            logger.warning("No content after streaming, attempting to extract from last_state")
                            # Check all possible sources
                            full_content = (
                                last_state.get("final_answer") or
                                last_state.get("executive_summary") or
                                last_state.get("detailed_analysis") or
                                (f"Error: {last_state.get('error')}" if last_state.get("error") else None) or
                                "Summary generation completed. Please check the conversation messages."
                            )
                            if full_content and full_content != "Summary generation completed. Please check the conversation messages.":
                                logger.info(f"Extracted content from last_state: {full_content[:200]}")
                                # Send as structured final_answer chunk
                                answer_chunk = AgentMessageChunk(
                                    message_type="final_answer",
                                    content=AgentMessageContent(type="text", data=full_content),
                                    timestamp=time.time()
                                )
                                yield answer_chunk.to_sse_format()
                        
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
                        # Try to extract query from last_state even on error if available
                        error_vizql_query = None
                        try:
                            if 'last_state' in locals() and last_state:
                                for key in ["query_draft", "query", "validated_query"]:
                                    if key in last_state and last_state.get(key):
                                        error_vizql_query = last_state.get(key)
                                        break
                        except (KeyError, AttributeError, TypeError) as e:
                            # Expected errors when extracting query from state - continue silently
                            logger.debug(f"Could not extract query from last_state: {e}")
                            pass
                        except Exception as e:
                            # Log unexpected errors but continue
                            logger.warning(f"Unexpected error extracting query from last_state: {e}", exc_info=True)
                            pass
                        
                        # Send error chunk
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
                # Non-streaming: execute graph and return result
                # Provide config with thread_id + tableau_client (not in state - not msgpack serializable)
                config = {"configurable": {"thread_id": f"summary-{request.conversation_id}", "tableau_client": tableau_client}}
                final_state = await graph.ainvoke(initial_state, config=config)
                execution_time = time.time() - execution_start
                
                # Track metrics
                success = final_state.get("error") is None
                metrics.record_agent_execution("summary", execution_time, success=success)
                
                # Track in memory
                query_id = f"summary-{request.conversation_id}-{int(time.time())}"
                conversation_memory.add_message(
                    query_id=query_id,
                    user_query=request.content,
                    agent_type="summary",
                    response=final_state.get("final_answer", ""),
                    datasource_ids=datasource_ids,
                    view_ids=view_ids
                )
                
                final_answer = final_state.get("final_answer") or final_state.get("error", "Summary generation completed.")
                
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
