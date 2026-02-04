"""Chat API endpoints."""
import logging
from typing import List, Optional, Dict
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel, Field, field_serializer, model_validator
from app.core.database import get_db
from app.models.chat import Conversation, Message, MessageRole, ChatContext
from app.services.ai.client import UnifiedAIClient, AIClientError
from app.services.ai.tools import get_tools, execute_tool, format_tool_result
from app.services.tableau.client import TableauClient
from app.core.config import settings
from app.services.memory import get_conversation_memory
from app.services.metrics import get_metrics
from app.services.debug import get_debugger
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
        return dt.isoformat()
    
    class Config:
        from_attributes = True


class MessageRequest(BaseModel):
    """Request model for sending a message."""
    conversation_id: int = Field(..., description="Conversation ID")
    content: str = Field(..., min_length=1, description="Message content")
    model: str = Field(default="gpt-4", description="AI model to use")
    agent_type: Optional[str] = Field(None, description="Agent type: 'summary', 'vizql', or 'general'")
    stream: bool = Field(default=False, description="Whether to stream the response")
    temperature: Optional[float] = Field(None, ge=0, le=2, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens to generate")


class MessageResponse(BaseModel):
    """Response model for a message."""
    id: int
    conversation_id: int
    role: str
    content: str
    model_used: Optional[str]
    tokens_used: Optional[int]
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


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(db: Session = Depends(get_db)):
    """Create a new conversation."""
    conversation = Conversation()
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    # Set message_count to 0 for new conversation
    conversation.message_count = 0
    
    logger.info(f"Created conversation {conversation.id}")
    return conversation


@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List all conversations with message counts."""
    conversations = db.query(Conversation).order_by(desc(Conversation.updated_at)).offset(skip).limit(limit).all()
    
    # Eager load messages to compute counts efficiently
    for conv in conversations:
        # Load messages count
        conv.message_count = db.query(Message).filter(Message.conversation_id == conv.id).count()
    
    return conversations


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Get a conversation by ID."""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
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
    db: Session = Depends(get_db)
):
    """Rename a conversation."""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conversation.name = request.name.strip()
    db.commit()
    db.refresh(conversation)
    
    # Compute message count
    conversation.message_count = db.query(Message).filter(Message.conversation_id == conversation_id).count()
    
    logger.info(f"Renamed conversation {conversation_id} to '{conversation.name}'")
    return conversation


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(conversation_id: int, db: Session = Depends(get_db)):
    """Get all messages for a conversation."""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at).all()
    # Return messages with uppercase roles (as stored in database)
    return [
        MessageResponse(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role.value if isinstance(msg.role, MessageRole) else str(msg.role).upper(),
            content=msg.content,
            model_used=msg.model_used,
            tokens_used=msg.tokens_used,
            created_at=msg.created_at
        )
        for msg in messages
    ]


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
    
    elif agent_type == 'general' or not agent_type:
        # General Agent: Include context but use general tools
        if datasource_ids or view_ids:
            system_prompt = "You are a General Agent helping users interact with Tableau. "
            system_prompt += "You have access to Tableau objects in context.\n\n"
            
            if datasource_ids:
                system_prompt += f"Context Datasources: {', '.join(datasource_ids)}\n"
            if view_ids:
                system_prompt += f"Context Views: {', '.join(view_ids)}\n"
            
            messages.insert(0, {
                "role": "system",
                "content": system_prompt
            })
    
    return messages


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: MessageRequest,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    """
    Send a message and get AI response.
    
    If stream=True, returns a streaming response.
    Supports agent routing via agent_type parameter.
    """
    # Verify conversation exists
    conversation = db.query(Conversation).filter(Conversation.id == request.conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Get context objects for this conversation
    context_objects = db.query(ChatContext).filter(
        ChatContext.conversation_id == request.conversation_id
    ).order_by(ChatContext.added_at).all()
    
    # Group by type
    datasource_ids = [ctx.object_id for ctx in context_objects if ctx.object_type == 'datasource']
    view_ids = [ctx.object_id for ctx in context_objects if ctx.object_type == 'view']
    
    # Save user message
    # Pass enum object directly - SQLAlchemy will use the enum value for storage
    user_message = Message(
        conversation_id=request.conversation_id,
        role=MessageRole.USER,
        content=request.content,
        model_used=request.model
    )
    db.add(user_message)
    
    # Auto-generate conversation name from first message if not set
    if not conversation.name:
        # Generate name from first message (truncate to 50 chars)
        name = request.content.strip()[:50]
        if len(request.content) > 50:
            # Try to break at word boundary
            truncated = name.rsplit(' ', 1)[0]
            name = truncated if len(truncated) > 30 else name
        conversation.name = name
    
    db.commit()
    
    # Get conversation history for context
    history_messages = db.query(Message).filter(
        Message.conversation_id == request.conversation_id
    ).order_by(Message.created_at).all()
    
    # Get conversation memory for context summarization
    conversation_memory = get_conversation_memory(request.conversation_id)
    context_summary = conversation_memory.get_context_summary()
    
    # Convert to OpenAI format (OpenAI expects lowercase)
    messages = [
        {"role": msg.role.value.lower() if isinstance(msg.role, MessageRole) else str(msg.role).lower(), "content": msg.content}
        for msg in history_messages
    ]
    
    # Add context summary if available and conversation is long
    if len(history_messages) > 10 and context_summary:
        # Insert context summary after system message (if any) or at the beginning
        messages.insert(0, {
            "role": "system",
            "content": f"Conversation context: {context_summary}"
        })
    
    # Extract API key from Authorization header if provided, otherwise use default from settings
    api_key = None
    if authorization and authorization.startswith("Bearer "):
        api_key = authorization[7:]
        logger.debug("Using API key from Authorization header")
    else:
        # Determine which API key to use based on model provider
        # This is a simple heuristic - in production, you might want to resolve the provider first
        model_lower = request.model.lower()
        if "gpt" in model_lower or "openai" in model_lower:
            api_key = settings.OPENAI_API_KEY
            logger.debug(f"Using OpenAI API key from settings (key present: {bool(api_key)})")
        elif "claude" in model_lower or "anthropic" in model_lower:
            api_key = settings.ANTHROPIC_API_KEY
            logger.debug(f"Using Anthropic API key from settings (key present: {bool(api_key)})")
        elif "endor" in model_lower or "apple" in model_lower:
            api_key = settings.APPLE_ENDOR_API_KEY
            logger.debug(f"Using Apple Endor API key from settings (key present: {bool(api_key)})")
        else:
            # Default to OpenAI API key if model is unknown
            api_key = settings.OPENAI_API_KEY
            logger.debug(f"Using default OpenAI API key from settings (key present: {bool(api_key)})")
        
        # Check if API key is configured
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail=f"API key not configured for model '{request.model}'. Please set the appropriate API key in settings or provide an Authorization header."
            )
    
    # Initialize Tableau client for context retrieval
    tableau_client = TableauClient()
    
    try:
        # Route to agent graphs if agent_type is specified and context is available
        agent_type = request.agent_type or 'general'
        
        # Route to VizQL agent graph
        if agent_type == 'vizql' and datasource_ids:
            from app.services.agents.graph_factory import AgentGraphFactory
            
            logger.info(f"Routing to VizQL agent graph with datasources: {datasource_ids}")
            
            # Track execution start time
            execution_start = time.time()
            execution_id = str(uuid.uuid4())
            metrics = get_metrics()
            conversation_memory = get_conversation_memory(request.conversation_id)
            debugger = get_debugger()
            node_states = []  # Track node states for debugging
            
            graph = AgentGraphFactory.create_vizql_graph()
            
            # Initialize state for VizQL agent
            initial_state = {
                "user_query": request.content,
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
                "api_key": api_key,
                "model": request.model,
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
                    try:
                        # Provide config with thread_id for checkpointer
                        config = {"configurable": {"thread_id": f"vizql-{request.conversation_id}"}}
                        async for state_update in graph.astream(initial_state, config=config):
                            # LangGraph astream returns updates keyed by node name
                            # Each update contains the state dictionary for that node
                            logger.debug(f"VizQL graph state update - node keys: {list(state_update.keys())}")
                            
                            # Iterate through all node updates in this state update
                            for node_name, node_state in state_update.items():
                                logger.debug(f"Processing node '{node_name}' - state keys: {list(node_state.keys()) if isinstance(node_state, dict) else 'not dict'}")
                                
                                # Keep track of the last state for final extraction
                                if isinstance(node_state, dict):
                                    last_state = node_state
                                
                                # Stream intermediate thoughts
                                if isinstance(node_state, dict) and "current_thought" in node_state and node_state.get("current_thought"):
                                    thought = node_state["current_thought"]
                                    # Only stream if it's different from what we've already sent
                                    if thought not in full_content:
                                        logger.debug(f"Streaming thought from {node_name}: {thought[:100]}")
                                        yield f"data: {thought}\n\n"
                                
                                # Stream final answer when available
                                if isinstance(node_state, dict) and "final_answer" in node_state and node_state.get("final_answer"):
                                    answer = node_state["final_answer"]
                                    logger.info(f"Found final_answer in {node_name}: {answer[:200]}")
                                    # Send the full answer if it's new or has changed
                                    if answer != last_final_answer:
                                        # If we haven't sent this answer yet, send it all
                                        if last_final_answer == "":
                                            logger.info(f"Streaming full final_answer from {node_name}: {len(answer)} chars")
                                            yield f"data: {answer}\n\n"
                                        else:
                                            # Send only the new part
                                            new_content = answer[len(last_final_answer):]
                                            if new_content:
                                                logger.info(f"Streaming new content from {node_name}: {len(new_content)} chars")
                                                yield f"data: {new_content}\n\n"
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
                                    yield f"data: {final_answer}\n\n"
                                    full_content = final_answer
                        
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
                                yield f"data: {full_content}\n\n"
                        
                        # Save assistant message after streaming completes
                        if full_content:
                            try:
                                assistant_message = Message(
                                    conversation_id=request.conversation_id,
                                    role=MessageRole.ASSISTANT,
                                    content=full_content,
                                    model_used=request.model
                                )
                                db.add(assistant_message)
                                conversation.updated_at = conversation.updated_at
                                db.commit()
                                logger.info(f"Saved assistant message with {len(full_content)} chars")
                            except Exception as e:
                                logger.error(f"Failed to save assistant message: {e}", exc_info=True)
                        else:
                            logger.error("No content to save after streaming completed!")
                        
                        yield "data: [DONE]\n\n"
                    except Exception as e:
                        logger.error(f"Error in VizQL graph streaming: {e}", exc_info=True)
                        import json
                        error_data = json.dumps({"error": str(e)})
                        yield f"data: {error_data}\n\n"
                        yield "data: [DONE]\n\n"
                
                return StreamingResponse(
                    stream_graph(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    }
                )
            else:
                # Non-streaming: execute graph and return result
                # Provide config with thread_id for checkpointer
                config = {"configurable": {"thread_id": f"vizql-{request.conversation_id}"}}
                
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
                except Exception as e:
                    execution_time = time.time() - execution_start
                    logger.error(f"Error executing VizQL graph: {e}", exc_info=True)
                    metrics.record_agent_execution("vizql", execution_time, success=False)
                    final_answer = f"Error executing query: {str(e)}"
                
                # Save assistant message
                assistant_message = Message(
                    conversation_id=request.conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=final_answer,
                    model_used=request.model
                )
                db.add(assistant_message)
                conversation.updated_at = conversation.updated_at
                db.commit()
                db.refresh(assistant_message)
                
                return ChatResponse(
                    message=MessageResponse(
                        id=assistant_message.id,
                        conversation_id=assistant_message.conversation_id,
                        role=assistant_message.role.value,
                        content=assistant_message.content,
                        model_used=assistant_message.model_used,
                        tokens_used=None,
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
            
            # Track execution start time
            execution_start = time.time()
            metrics = get_metrics()
            conversation_memory = get_conversation_memory(request.conversation_id)
            
            graph = AgentGraphFactory.create_summary_graph()
            
            # Initialize state for Summary agent
            initial_state = {
                "user_query": request.content,
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
                "api_key": api_key,
                "model": request.model,
            }
            
            if request.stream:
                # Stream graph execution
                async def stream_graph():
                    full_content = ""
                    try:
                        # Provide config with thread_id for checkpointer
                        config = {"configurable": {"thread_id": f"summary-{request.conversation_id}"}}
                        async for state in graph.astream(initial_state, config=config):
                            if "current_thought" in state and state.get("current_thought"):
                                thought = state["current_thought"]
                                yield f"data: {thought}\n\n"
                            
                            if "final_answer" in state and state.get("final_answer"):
                                answer = state["final_answer"]
                                if answer != full_content:
                                    new_content = answer[len(full_content):]
                                    if new_content:
                                        yield f"data: {new_content}\n\n"
                                        full_content = answer
                        
                        if full_content:
                            assistant_message = Message(
                                conversation_id=request.conversation_id,
                                role=MessageRole.ASSISTANT,
                                content=full_content,
                                model_used=request.model
                            )
                            db.add(assistant_message)
                            conversation.updated_at = conversation.updated_at
                            db.commit()
                        
                        yield "data: [DONE]\n\n"
                    except Exception as e:
                        logger.error(f"Error in Summary graph streaming: {e}", exc_info=True)
                        import json
                        error_data = json.dumps({"error": str(e)})
                        yield f"data: {error_data}\n\n"
                        yield "data: [DONE]\n\n"
                
                return StreamingResponse(
                    stream_graph(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    }
                )
            else:
                # Non-streaming: execute graph and return result
                # Provide config with thread_id for checkpointer
                config = {"configurable": {"thread_id": f"summary-{request.conversation_id}"}}
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
                
                assistant_message = Message(
                    conversation_id=request.conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=final_answer,
                    model_used=request.model
                )
                db.add(assistant_message)
                conversation.updated_at = conversation.updated_at
                db.commit()
                db.refresh(assistant_message)
                
                return ChatResponse(
                    message=MessageResponse(
                        id=assistant_message.id,
                        conversation_id=assistant_message.conversation_id,
                        role=assistant_message.role.value,
                        content=assistant_message.content,
                        model_used=assistant_message.model_used,
                        tokens_used=None,
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
            gateway_url=settings.GATEWAY_BASE_URL,
            api_key=api_key
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
                                messages=messages,
                                temperature=request.temperature,
                                max_tokens=request.max_tokens
                            ):
                                if chunk.content:
                                    chunk_count += 1
                                    full_content += chunk.content
                                    logger.debug(f"Streaming chunk {chunk_count}: {chunk.content[:50]}...")
                                    yield f"data: {chunk.content}\n\n"
                            
                            logger.info(f"Streaming completed: {chunk_count} chunks, {len(full_content)} total chars")
                        
                        # Save assistant message after streaming completes
                        if full_content:
                            assistant_message = Message(
                                conversation_id=request.conversation_id,
                                role=MessageRole.ASSISTANT,
                                content=full_content,
                                model_used=request.model
                            )
                            db.add(assistant_message)
                            conversation.updated_at = conversation.updated_at  # Trigger update
                            db.commit()
                        
                        yield "data: [DONE]\n\n"
                    except Exception as e:
                        logger.error(f"Error in streaming: {e}", exc_info=True)
                        import json
                        error_data = json.dumps({"error": str(e)})
                        yield f"data: {error_data}\n\n"
                        yield "data: [DONE]\n\n"
                
                return StreamingResponse(
                    generate_stream(),
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
                            messages=messages,
                            temperature=request.temperature,
                            max_tokens=request.max_tokens
                        )
                        total_tokens += final_response.tokens_used
                        
                        final_content = final_response.content
                    else:
                        # No function call, use original response
                        final_content = response.content
                
                # Save assistant message
                assistant_message = Message(
                    conversation_id=request.conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=final_content,
                    model_used=response.model,
                    tokens_used=total_tokens,
                    extra_metadata={
                        "function_call": response.function_call.__dict__ if response.function_call else None
                    }
                )
                db.add(assistant_message)
                conversation.updated_at = conversation.updated_at  # Trigger update
                db.commit()
                db.refresh(assistant_message)
                
                return ChatResponse(
                    message=MessageResponse(
                        id=assistant_message.id,
                        conversation_id=assistant_message.conversation_id,
                        role=assistant_message.role.value,
                        content=assistant_message.content,
                        model_used=assistant_message.model_used,
                        tokens_used=assistant_message.tokens_used,
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
        # Ensure tableau_client is closed even if AI client fails
        if tableau_client:
            await tableau_client.close()


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Delete a conversation and all its messages."""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db.delete(conversation)
    db.commit()
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
):
    """Add an object (datasource or view) to chat context."""
    # Verify conversation exists
    conversation = db.query(Conversation).filter(Conversation.id == request.conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
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
        db.commit()
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
    db.commit()
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
):
    """Remove an object from chat context."""
    # Verify conversation exists
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Find and delete context object
    context_obj = db.query(ChatContext).filter(
        ChatContext.conversation_id == conversation_id,
        ChatContext.object_id == object_id,
    ).first()
    
    if not context_obj:
        raise HTTPException(status_code=404, detail="Context object not found")
    
    db.delete(context_obj)
    db.commit()
    
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
