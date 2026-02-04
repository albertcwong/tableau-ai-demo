# Agent Implementation - Architecture & Implementation Plan

## Executive Summary

This document outlines the implementation strategy for AI agents in the Tableau AI Demo. The current implementation lacks:
1. **State management framework** for multi-step reasoning
2. **ReAct pattern** (Reason-Act-Observe) for iterative problem solving
3. **Centralized prompt architecture** for agent behaviors
4. **Query validation and refinement loops**
5. **Tool orchestration and error recovery**

**Recommended Architecture**: LangGraph-based ReAct agents with externalized prompts, state persistence, and validation loops.

## Current State

### What's Working
- ✅ Agent selector UI (Summary, VizQL, General)
- ✅ Context management (add/remove datasources and views to conversation context)
- ✅ Chat API endpoint (`/api/v1/chat/message`)
- ✅ Agent service implementations exist:
  - `SummaryAgent` (`backend/app/services/agents/summary_agent.py`)
  - `VDSAgent` (`backend/app/services/agents/vds_agent.py`)
  - `AgentRouter` (`backend/app/services/agents/router.py`)
- ✅ Agent API endpoints exist (`/api/v1/agents/*`)

### What's Missing
- ❌ Chat endpoint doesn't accept `agent_type` parameter
- ❌ Chat endpoint doesn't retrieve context objects from database
- ❌ Chat endpoint doesn't include context information in AI messages
- ❌ Chat endpoint doesn't route to specialized agents based on agent_type
- ❌ Frontend doesn't pass agent_type to chat API

## Critical Gaps & Architectural Issues

### 1. No State Management Framework
**Current Issue**: Each message is processed independently with no persistent state.

**Problems**:
- Cannot track multi-step operations (e.g., build query → validate → refine → execute)
- No memory of previous tool calls or intermediate results
- Cannot implement retry logic or error recovery
- No way to handle complex workflows requiring multiple iterations

**Solution**: Implement LangGraph for state management with:
- Graph-based workflow orchestration
- State persistence across steps
- Checkpoint/resume capabilities
- Built-in error handling and retries

### 2. Missing ReAct Pattern
**Current Issue**: Agents process requests in a single shot without iterative reasoning.

**Problems**:
- VizQL queries constructed without validation
- No refinement loop for improving queries based on results
- Cannot decompose complex queries into subtasks
- No "thought → action → observation → reflection" cycle

**Solution**: Implement ReAct (Reason-Act-Observe) pattern:
```
Thought: "User wants sales by region, need to find sales measure and region dimension"
Action: get_datasource_schema(datasource_id)
Observation: Found "Total Sales" (measure) and "Sales Region" (dimension)
Thought: "Should aggregate sales using SUM function"
Action: construct_vds_query(fields=[{field: "Total Sales", function: "SUM"}, {field: "Sales Region"}])
Observation: Query constructed successfully
Action: validate_query(query)
Observation: Query is valid
Action: execute_vds_query(query)
Observation: Results returned, 5 regions found
Thought: "Results look good, format for user"
Final Answer: [formatted results]
```

### 3. Inline System Prompts (Anti-Pattern)
**Current Issue**: System prompts are hardcoded inline in the chat API.

**Problems**:
- Cannot version or A/B test prompts
- Difficult to maintain and update
- No prompt engineering workflow
- Cannot share prompts across agents or contexts
- No prompt templates or composition

**Solution**: Centralized prompt management system:
- Separate prompt files per agent type
- Template system for dynamic content injection
- Version control for prompts
- Prompt registry with metadata
- Support for few-shot examples and chain-of-thought prompts

### 4. No Query Validation/Refinement Loop
**Current Issue**: VizQL queries are constructed once and executed without validation.

**Problems**:
- Invalid queries fail at execution time
- No opportunity to fix column name mismatches
- Cannot refine queries based on user feedback
- No handling of ambiguous requests

**Solution**: Multi-stage query workflow:
```
1. Construct initial query from natural language
2. Validate query structure (syntax, field names, functions)
3. If invalid → refine with AI assistance
4. Preview query (dry run or EXPLAIN)
5. If results unexpected → allow user refinement
6. Execute final query
7. Format and present results
```

### 5. No Tool Orchestration Framework
**Current Issue**: Tool calls are ad-hoc without coordination or dependency management.

**Problems**:
- Cannot chain tool calls with dependencies
- No parallel tool execution for independent operations
- Missing error handling and fallback strategies
- No tool call validation or rate limiting

**Solution**: LangGraph tool nodes with:
- Explicit tool dependencies in graph edges
- Conditional routing based on tool results
- Error handling nodes for retry/fallback
- Tool result caching to avoid duplicate calls

### 6. Missing Agent Memory & Context
**Current Issue**: No persistent memory of agent actions across conversation turns.

**Problems**:
- Agent repeats tool calls unnecessarily
- Cannot reference previous query results
- No learning from user corrections
- Cannot build on previous insights

**Solution**: Agent memory layers:
- **Short-term**: Current conversation context (messages, tool results)
- **Session**: Current user session (datasources in context, recent queries)
- **Long-term**: Cross-session patterns (common queries, user preferences)

### 7. No Error Recovery Strategy
**Current Issue**: Failures result in error messages without recovery attempts.

**Problems**:
- Authentication failures aren't retried
- Invalid queries don't trigger refinement
- API timeouts don't fall back to cached data
- No graceful degradation

**Solution**: Layered error recovery:
```python
try:
    result = execute_query(query)
except InvalidFieldError as e:
    # Attempt 1: AI-assisted field name correction
    corrected_query = await refine_query_with_ai(query, error=e)
    result = execute_query(corrected_query)
except TimeoutError:
    # Attempt 2: Use cached results if available
    result = get_cached_results(query)
    if not result:
        # Attempt 3: Simplify query and retry
        simplified = simplify_query(query)
        result = execute_query(simplified)
```

## Problem

When a user:
1. Selects "Summary Agent"
2. Adds a view to context
3. Sends "summarize this view"

The AI responds: *"I'm sorry, but as a text-based AI, I can't view or summarize any images or visual content."*

**Root Cause:** The chat endpoint (`/api/v1/chat/message`) doesn't:
- Know which agent was selected
- Retrieve context objects (views/datasources) from the database
- Include view data or datasource schema in the messages sent to the AI
- Use the specialized agent services

## Recommended Architecture: LangGraph-Based Agents

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Chat API Layer                          │
│  - Receives messages with agent_type                            │
│  - Retrieves context (datasources, views)                       │
│  - Routes to appropriate agent graph                            │
└────────────────────┬────────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
┌──────────────┬──────────────┬──────────────┐
│  Summary     │  VizQL       │  General     │
│  Agent Graph │  Agent Graph │  Agent Graph │
└──────────────┴──────────────┴──────────────┘
        │            │            │
        └────────────┼────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌──────────────┐         ┌──────────────┐
│  Prompt      │         │  Tool        │
│  Registry    │         │  Registry    │
│              │         │              │
│ - System     │         │ - Tableau    │
│   prompts    │         │   API tools  │
│ - Few-shot   │         │ - VizQL      │
│   examples   │         │   tools      │
│ - Templates  │         │ - Validation │
└──────────────┘         └──────────────┘
```

### LangGraph State Management

Each agent is implemented as a LangGraph with nodes representing steps in the ReAct cycle:

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """Shared state across all agent nodes."""
    # Input
    user_query: str
    agent_type: str
    context_datasources: list[str]
    context_views: list[str]
    
    # Intermediate state
    messages: Annotated[Sequence[BaseMessage], "conversation messages"]
    current_thought: str
    tool_calls: list[dict]
    tool_results: list[dict]
    
    # Query construction (VizQL agent)
    query_draft: dict | None
    query_validated: bool
    query_errors: list[str]
    
    # Summary generation (Summary agent)
    view_data: dict | None
    analysis: dict | None
    
    # Output
    final_answer: str
    confidence: float

# VizQL Agent Graph
def create_vizql_agent_graph():
    workflow = StateGraph(AgentState)
    
    # Nodes
    workflow.add_node("planner", plan_query_node)           # Reason: Understand intent
    workflow.add_node("schema_fetch", fetch_schema_node)    # Act: Get datasource schema
    workflow.add_node("query_builder", build_query_node)    # Act: Construct VizQL query
    workflow.add_node("validator", validate_query_node)     # Observe: Validate query
    workflow.add_node("refiner", refine_query_node)         # Reason: Fix errors
    workflow.add_node("executor", execute_query_node)       # Act: Run query
    workflow.add_node("formatter", format_results_node)     # Act: Format for user
    
    # Edges (workflow control)
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "schema_fetch")
    workflow.add_edge("schema_fetch", "query_builder")
    workflow.add_edge("query_builder", "validator")
    
    # Conditional routing based on validation
    workflow.add_conditional_edges(
        "validator",
        lambda state: "execute" if state["query_validated"] else "refine",
        {
            "execute": "executor",
            "refine": "refiner"
        }
    )
    
    # Refiner loops back to query_builder (max 3 attempts)
    workflow.add_conditional_edges(
        "refiner",
        lambda state: "build" if len(state["tool_calls"]) < 5 else "fail",
        {
            "build": "query_builder",
            "fail": END
        }
    )
    
    workflow.add_edge("executor", "formatter")
    workflow.add_edge("formatter", END)
    
    return workflow.compile()
```

### Prompt Architecture

Prompts are externalized into a dedicated prompt registry:

```
backend/app/prompts/
├── __init__.py
├── registry.py          # Prompt registry and loading
├── base.py              # Base prompt templates
├── agents/
│   ├── summary/
│   │   ├── system.txt       # System prompt
│   │   ├── examples.yaml    # Few-shot examples
│   │   └── templates.py     # Dynamic templates
│   ├── vizql/
│   │   ├── system.txt
│   │   ├── query_construction.txt
│   │   ├── query_validation.txt
│   │   ├── query_refinement.txt
│   │   └── examples.yaml
│   └── general/
│       ├── system.txt
│       └── examples.yaml
└── tools/
    ├── schema_analysis.txt
    ├── data_summary.txt
    └── error_recovery.txt
```

**Example: VizQL System Prompt** (`backend/app/prompts/agents/vizql/system.txt`):
```
You are a VizQL expert specializing in Tableau Data Service queries.

## Your Capabilities
- Analyze datasource schemas to understand available fields
- Translate natural language queries into VizQL Data Service JSON format
- Validate query structure and field references
- Suggest query optimizations

## VizQL Data Service Query Format
Queries must follow this JSON structure:
{
  "datasource": {"datasourceLuid": "<LUID>"},
  "query": {
    "fields": [
      {"fieldCaption": "<name>", "function": "<AGG>"}  // measures
      {"fieldCaption": "<name>"}                       // dimensions
    ],
    "filters": [
      {"fieldCaption": "<name>", "values": ["value"]}
    ]
  },
  "options": {
    "returnFormat": "OBJECTS",
    "disaggregate": false
  }
}

## Query Construction Process
1. **Understand Intent**: Parse user request for measures, dimensions, filters
2. **Map to Schema**: Match user terms to actual field names (fuzzy matching OK)
3. **Build Query**: Construct valid VizQL Data Service JSON
4. **Validate**: Check field names exist, functions are appropriate
5. **Refine**: Fix any errors or ambiguities

## Available Aggregation Functions
- SUM, AVG, MIN, MAX, COUNT, COUNTD
- MEDIAN, STDEV, VAR
- ATTR (attribute, for dimensions used as measures)

## Common Patterns
- "Total sales by region" → SUM(Sales) grouped by Region
- "Average price per product" → AVG(Price) grouped by Product
- "Top 10 customers" → Use limit in options, sort by measure DESC

## Context
{{context_description}}

Available Datasources:
{{datasources}}
```

**Example: Query Validation Prompt** (`backend/app/prompts/agents/vizql/query_validation.txt`):
```
Validate this VizQL Data Service query against the schema:

Schema:
{{schema}}

Query:
{{query}}

Check for:
1. ✓ All fieldCaption values exist in schema
2. ✓ Aggregation functions are appropriate for field types
3. ✓ Filters reference valid fields and values
4. ✓ Required fields (datasource.datasourceLuid, query.fields) are present
5. ✓ No syntax errors in JSON structure

If errors found, provide:
- Specific error descriptions
- Suggested corrections
- Corrected query JSON

Format response as:
{
  "valid": true/false,
  "errors": ["error1", "error2"],
  "suggestions": ["suggestion1", "suggestion2"],
  "corrected_query": { ... }
}
```

### Prompt Registry Implementation

```python
# backend/app/prompts/registry.py
from pathlib import Path
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader
import yaml

class PromptRegistry:
    """Centralized prompt management with templates."""
    
    def __init__(self, prompts_dir: Path = None):
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent
        self.prompts_dir = prompts_dir
        self.env = Environment(loader=FileSystemLoader(str(prompts_dir)))
        self._cache: Dict[str, str] = {}
    
    def get_prompt(
        self,
        prompt_path: str,
        variables: Dict[str, Any] = None
    ) -> str:
        """
        Get a prompt with optional variable substitution.
        
        Args:
            prompt_path: Path relative to prompts dir (e.g., "agents/vizql/system.txt")
            variables: Dictionary of variables for template rendering
            
        Returns:
            Rendered prompt string
        """
        # Check cache
        cache_key = f"{prompt_path}:{hash(frozenset(variables.items()) if variables else 0)}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Load template
        template = self.env.get_template(prompt_path)
        
        # Render with variables
        rendered = template.render(**(variables or {}))
        
        # Cache
        self._cache[cache_key] = rendered
        
        return rendered
    
    def get_examples(self, examples_path: str) -> list[dict]:
        """Load few-shot examples from YAML file."""
        full_path = self.prompts_dir / examples_path
        with open(full_path, 'r') as f:
            return yaml.safe_load(f)
    
    def build_few_shot_prompt(
        self,
        system_prompt: str,
        examples: list[dict],
        user_query: str
    ) -> list[dict]:
        """Build messages array with few-shot examples."""
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add examples
        for ex in examples:
            messages.append({"role": "user", "content": ex["user"]})
            messages.append({"role": "assistant", "content": ex["assistant"]})
        
        # Add actual user query
        messages.append({"role": "user", "content": user_query})
        
        return messages

# Global registry instance
prompt_registry = PromptRegistry()
```

## Implementation Plan

### Phase 0: Foundation - LangGraph & Prompt Infrastructure

#### 0.1 Install Dependencies
```bash
pip install langgraph langchain-core langchain-openai jinja2
```

#### 0.2 Create Prompt Registry Structure
```bash
mkdir -p backend/app/prompts/agents/{summary,vizql,general}
mkdir -p backend/app/prompts/tools
```

#### 0.3 Implement Prompt Registry
**File:** `backend/app/prompts/registry.py`
- Implement `PromptRegistry` class (see above)
- Add template loading and caching
- Add few-shot example support

#### 0.4 Create Base Agent State
**File:** `backend/app/services/agents/base_state.py`
```python
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage

class BaseAgentState(TypedDict):
    """Base state for all agents."""
    user_query: str
    agent_type: str
    context_datasources: list[str]
    context_views: list[str]
    messages: Annotated[Sequence[BaseMessage], "conversation history"]
    final_answer: str
    error: str | None
```

#### 0.5 Create Agent Graph Factory
**File:** `backend/app/services/agents/graph_factory.py`
```python
from langgraph.graph import StateGraph
from typing import Callable

class AgentGraphFactory:
    """Factory for creating agent graphs."""
    
    @staticmethod
    def create_vizql_graph() -> StateGraph:
        # Implementation for VizQL agent graph
        pass
    
    @staticmethod
    def create_summary_graph() -> StateGraph:
        # Implementation for Summary agent graph
        pass
    
    @staticmethod
    def create_general_graph() -> StateGraph:
        # Implementation for General agent graph
        pass
```

### Phase 1: Add Agent Type and Context to Chat API

#### 1.1 Update MessageRequest Model
**File:** `backend/app/api/chat.py`

Add `agent_type` field to `MessageRequest`:
```python
class MessageRequest(BaseModel):
    conversation_id: int
    content: str
    model: str = "gpt-4"
    agent_type: Optional[str] = Field(None, description="Agent type: 'summary', 'vizql', or 'general'")
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
```

#### 1.2 Retrieve Context Objects
**File:** `backend/app/api/chat.py`

In `send_message` endpoint, after retrieving conversation:
```python
# Get context objects for this conversation
context_objects = db.query(ChatContext).filter(
    ChatContext.conversation_id == request.conversation_id
).order_by(ChatContext.added_at).all()

# Group by type
datasource_ids = [ctx.object_id for ctx in context_objects if ctx.object_type == 'datasource']
view_ids = [ctx.object_id for ctx in context_objects if ctx.object_type == 'view']
```

#### 1.3 Build Context-Aware Messages
**File:** `backend/app/api/chat.py`

Create a helper function to build context-aware messages based on agent_type:

```python
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
                    view_data = await tableau_client.get_view_data(view_id)
                    system_prompt += f"\nView {view_id}:\n"
                    system_prompt += f"Columns: {', '.join(view_data.get('columns', []))}\n"
                    system_prompt += f"Sample Data (first 10 rows):\n{json.dumps(view_data.get('data', [])[:10], indent=2)}\n"
                except Exception as e:
                    logger.warning(f"Failed to fetch view data for {view_id}: {e}")
            
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
                    system_prompt += f"Columns:\n{json.dumps([{'name': c.name, 'type': c.data_type, 'is_measure': c.is_measure, 'is_dimension': c.is_dimension} for c in schema.get('columns', [])], indent=2)}\n"
                except Exception as e:
                    logger.warning(f"Failed to fetch schema for {datasource_id}: {e}")
            
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
```

#### 1.4 Update send_message Endpoint
**File:** `backend/app/api/chat.py`

Modify `send_message` to:
1. Extract `agent_type` from request
2. Retrieve context objects
3. Build context-aware messages
4. Optionally route to specialized agents

```python
@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: MessageRequest,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    # ... existing code ...
    
    # Get context objects
    context_objects = db.query(ChatContext).filter(
        ChatContext.conversation_id == request.conversation_id
    ).order_by(ChatContext.added_at).all()
    
    datasource_ids = [ctx.object_id for ctx in context_objects if ctx.object_type == 'datasource']
    view_ids = [ctx.object_id for ctx in context_objects if ctx.object_type == 'view']
    
    # Build context-aware messages
    messages = await build_agent_messages(
        agent_type=request.agent_type or 'general',
        conversation_messages=messages,
        datasource_ids=datasource_ids,
        view_ids=view_ids,
        tableau_client=tableau_client
    )
    
    # ... rest of existing code ...
```

### Phase 2: Frontend Updates

#### 2.1 Pass Agent Type to Chat API
**File:** `frontend/components/agent-panel/AgentPanel.tsx`

Pass `agentType` to `ChatInterface`:
```typescript
<ChatInterface
  conversationId={activeThreadId}
  defaultModel={model}
  hideModelSelector={true}
  agentType={agentType}  // Add this
/>
```

#### 2.2 Update ChatInterface Props
**File:** `frontend/components/chat/ChatInterface.tsx`

Add `agentType` prop and pass to API:
```typescript
export interface ChatInterfaceProps {
  conversationId?: number;
  className?: string;
  defaultModel?: string;
  hideModelSelector?: boolean;
  agentType?: 'summary' | 'vizql' | 'general';  // Add this
}

// In handleSendMessage:
await chatApi.sendMessageStream(
  {
    conversation_id: conversationId,
    content,
    model: selectedModel,
    stream: true,
    agent_type: agentType,  // Add this
  },
  // ...
);
```

#### 2.3 Update API Client
**File:** `frontend/lib/api.ts`

Add `agent_type` to `sendMessage` and `sendMessageStream`:
```typescript
export interface SendMessageRequest {
  conversation_id: number;
  content: string;
  model?: string;
  stream?: boolean;
  agent_type?: 'summary' | 'vizql' | 'general';  // Add this
  temperature?: number;
  max_tokens?: number;
}
```

### Phase 3: Implement View Data Retrieval

#### 3.1 Add get_view_data Method
**File:** `backend/app/services/tableau/client.py`

Add method to retrieve view data using Tableau Data API:
```python
async def get_view_data(
    self,
    view_id: str,
    max_rows: int = 1000
) -> Dict[str, Any]:
    """
    Get data from a view using Tableau Data API.
    
    Uses: GET /api/api-version/sites/site-id/views/view-id/data
    
    Args:
        view_id: View ID
        max_rows: Maximum number of rows to return
        
    Returns:
        Dictionary with columns and data
    """
    await self._ensure_authenticated()
    site_id = self.site_id or ""
    
    if not site_id:
        raise ValueError("Site ID not available.")
    
    endpoint = f"sites/{site_id}/views/{view_id}/data"
    params = {"maxAge": 0}  # Get fresh data
    
    response = await self._request("GET", endpoint, params=params)
    
    # Parse CSV response
    # Tableau returns CSV format: "Column1,Column2\nValue1,Value2\n..."
    csv_data = response if isinstance(response, str) else response.get("data", "")
    
    lines = csv_data.strip().split('\n')
    if len(lines) < 2:
        return {"columns": [], "data": []}
    
    columns = [col.strip() for col in lines[0].split(',')]
    data_rows = []
    
    for line in lines[1:max_rows+1]:
        values = [val.strip() for val in line.split(',')]
        data_rows.append(values)
    
    return {
        "columns": columns,
        "data": data_rows,
        "row_count": len(data_rows)
    }
```

### Phase 4: Enhanced Agent Routing (Optional)

For more sophisticated routing, integrate with `AgentRouter`:

```python
# In send_message endpoint
if request.agent_type == 'summary' and view_ids:
    # Use SummaryAgent for specialized handling
    from app.services.agents.summary_agent import SummaryAgent
    agent = SummaryAgent(tableau_client=tableau_client)
    
    # Generate summary using agent
    result = await agent.generate_report(
        view_ids=view_ids,
        format='text',
        include_visualizations=False
    )
    
    # Return agent-generated response
    return ChatResponse(...)

elif request.agent_type == 'vizql' and datasource_ids:
    # Use VDSAgent for query construction
    from app.services.agents.vds_agent import VDSAgent
    agent = VDSAgent(tableau_client=tableau_client)
    # ... handle VizQL queries ...
```

## Summary Agent: LangGraph Implementation

### Overview
The Summary Agent analyzes Tableau view data and generates natural language insights using a multi-stage analysis pipeline.

### Agent Graph Architecture

```
                    START
                      │
                      ▼
              ┌──────────────┐
              │ DATA_FETCHER │  Act: Retrieve view data
              │              │  Tool: get_view_data(view_id)
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │   ANALYZER   │  Reason: Identify patterns, trends, outliers
              │              │  Uses: Statistical analysis + AI interpretation
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ INSIGHT_GEN  │  Reason: Generate key insights
              │              │  Produces: Top findings, trends, recommendations
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ SUMMARIZER   │  Act: Generate natural language summary
              │              │  Output: Executive summary + detailed breakdown
              └──────┬───────┘
                     │
                     ▼
                   END
```

### State Definition

```python
# backend/app/services/agents/summary/state.py
class SummaryAgentState(BaseAgentState):
    """State for Summary agent graph."""
    
    # View data
    view_data: dict | None
    view_metadata: dict | None
    
    # Analysis
    column_stats: dict | None      # Mean, median, std dev for numeric columns
    trends: list[dict]              # Detected trends
    outliers: list[dict]            # Outlier detection results
    correlations: dict | None       # Column correlations
    
    # Insights
    key_insights: list[str]
    recommendations: list[str]
    
    # Output
    executive_summary: str
    detailed_analysis: str
```

### Node Implementations

#### 1. Data Fetcher Node
```python
async def fetch_data_node(state: SummaryAgentState) -> SummaryAgentState:
    """Fetch view data from Tableau."""
    view_id = state["context_views"][0]
    
    try:
        # Fetch view data (up to 1000 rows for analysis)
        view_data = await tableau_client.get_view_data(view_id, max_rows=1000)
        
        # Fetch view metadata
        view_metadata = await tableau_client.get_view(view_id)
        
        return {
            **state,
            "view_data": view_data,
            "view_metadata": view_metadata,
            "tool_calls": state.get("tool_calls", []) + [{
                "tool": "get_view_data",
                "args": {"view_id": view_id},
                "result": f"success - {view_data['row_count']} rows"
            }]
        }
    except Exception as e:
        return {
            **state,
            "error": f"Failed to fetch view data: {str(e)}"
        }
```

#### 2. Analyzer Node
```python
async def analyze_data_node(state: SummaryAgentState) -> SummaryAgentState:
    """Perform statistical analysis on view data."""
    view_data = state["view_data"]
    
    # Convert to pandas DataFrame for analysis
    df = pd.DataFrame(view_data["data"], columns=view_data["columns"])
    
    # Calculate statistics for numeric columns
    column_stats = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    
    for col in numeric_cols:
        column_stats[col] = {
            "mean": df[col].mean(),
            "median": df[col].median(),
            "std": df[col].std(),
            "min": df[col].min(),
            "max": df[col].max(),
            "missing": df[col].isna().sum()
        }
    
    # Detect trends (simple: check if sorted column shows trend)
    trends = []
    for col in numeric_cols:
        # Check for monotonic increase/decrease
        if df[col].is_monotonic_increasing:
            trends.append({"column": col, "trend": "increasing"})
        elif df[col].is_monotonic_decreasing:
            trends.append({"column": col, "trend": "decreasing"})
    
    # Detect outliers using IQR method
    outliers = []
    for col in numeric_cols:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        outlier_mask = (df[col] < (Q1 - 1.5 * IQR)) | (df[col] > (Q3 + 1.5 * IQR))
        if outlier_mask.any():
            outliers.append({
                "column": col,
                "count": outlier_mask.sum(),
                "values": df[df[col][outlier_mask]].tolist()
            })
    
    # Calculate correlations
    correlations = df[numeric_cols].corr().to_dict() if len(numeric_cols) > 1 else {}
    
    return {
        **state,
        "column_stats": column_stats,
        "trends": trends,
        "outliers": outliers,
        "correlations": correlations
    }
```

#### 3. Insight Generation Node
```python
async def generate_insights_node(state: SummaryAgentState) -> SummaryAgentState:
    """Use AI to generate key insights from analysis."""
    
    # Build prompt with analysis results
    system_prompt = prompt_registry.get_prompt(
        "agents/summary/insight_generation.txt",
        variables={
            "view_name": state["view_metadata"]["name"],
            "column_stats": json.dumps(state["column_stats"], indent=2),
            "trends": state["trends"],
            "outliers": state["outliers"],
            "correlations": state["correlations"]
        }
    )
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Generate insights for: {state['user_query']}")
    ]
    
    response = await llm.ainvoke(messages)
    
    # Parse insights (expects JSON with insights and recommendations)
    result = json.loads(response.content)
    
    return {
        **state,
        "key_insights": result.get("insights", []),
        "recommendations": result.get("recommendations", [])
    }
```

#### 4. Summarizer Node
```python
async def summarize_node(state: SummaryAgentState) -> SummaryAgentState:
    """Generate final natural language summary."""
    
    # Build comprehensive summary prompt
    system_prompt = prompt_registry.get_prompt(
        "agents/summary/final_summary.txt",
        variables={
            "view_name": state["view_metadata"]["name"],
            "row_count": state["view_data"]["row_count"],
            "insights": state["key_insights"],
            "recommendations": state["recommendations"],
            "user_query": state["user_query"]
        }
    )
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Generate executive summary and detailed analysis.")
    ]
    
    response = await llm.ainvoke(messages)
    
    return {
        **state,
        "executive_summary": response.content,
        "final_answer": response.content
    }
```

### Requirements
1. **View Data Access**: Retrieve actual data from views (not just metadata)
2. **Data Analysis**: Analyze trends, patterns, and insights
3. **Natural Language Summary**: Generate human-readable summaries
4. **Statistical Analysis**: Compute descriptive statistics, detect outliers, find correlations

## VizQL Agent: LangGraph Implementation

### Overview
The VizQL Agent uses a ReAct pattern with validation loops to construct, validate, refine, and execute VizQL Data Service queries.

### Agent Graph Architecture

```
                    START
                      │
                      ▼
              ┌──────────────┐
              │   PLANNER    │  Reason: Parse intent, identify requirements
              │              │  Output: required_measures, required_dimensions, filters
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ SCHEMA_FETCH │  Act: Retrieve datasource schema
              │              │  Tool: get_datasource_schema(datasource_id)
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │QUERY_BUILDER │  Act: Construct VizQL query JSON
              │              │  Uses: Schema + Intent → VizQL JSON
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │  VALIDATOR   │  Observe: Check query validity
              │              │  Checks: field names, functions, syntax
              └──────┬───────┘
                     │
           ┌─────────┴─────────┐
           │                   │
       VALID?              INVALID?
           │                   │
           ▼                   ▼
    ┌──────────────┐    ┌──────────────┐
    │  EXECUTOR    │    │   REFINER    │  Reason: Fix errors
    │              │    │              │  Uses: AI to correct field names, etc.
    └──────┬───────┘    └──────┬───────┘
           │                   │
           │                   └─────► Back to QUERY_BUILDER (max 3 loops)
           │
           ▼
    ┌──────────────┐
    │  FORMATTER   │  Act: Format results for user
    │              │  Output: Natural language + data table
    └──────┬───────┘
           │
           ▼
         END
```

### State Definition

```python
# backend/app/services/agents/vizql/state.py
from typing import TypedDict, Optional
from backend.app.services.agents.base_state import BaseAgentState

class VizQLAgentState(BaseAgentState):
    """State for VizQL agent graph."""
    
    # Schema info
    schema: dict | None
    
    # Intent parsing
    required_measures: list[str]
    required_dimensions: list[str]
    required_filters: dict[str, Any]
    
    # Query construction
    query_draft: dict | None
    query_version: int  # Track refinement iterations
    
    # Validation
    is_valid: bool
    validation_errors: list[str]
    validation_suggestions: list[str]
    
    # Execution
    query_results: dict | None
    execution_error: str | None
    
    # Output
    formatted_response: str
```

### Node Implementations

#### 1. Planner Node
**File:** `backend/app/services/agents/vizql/nodes/planner.py`

```python
from langchain_core.messages import SystemMessage, HumanMessage
from backend.app.prompts.registry import prompt_registry

async def plan_query_node(state: VizQLAgentState) -> VizQLAgentState:
    """
    Parse user intent to identify required measures, dimensions, and filters.
    
    This is the "Reason" step in ReAct.
    """
    # Get planning prompt
    system_prompt = prompt_registry.get_prompt(
        "agents/vizql/planning.txt",
        variables={
            "datasources": state["context_datasources"],
            "user_query": state["user_query"]
        }
    )
    
    # Call LLM to parse intent
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["user_query"])
    ]
    
    response = await llm.ainvoke(messages)
    
    # Parse response (expects JSON with measures, dimensions, filters)
    intent = json.loads(response.content)
    
    return {
        **state,
        "required_measures": intent.get("measures", []),
        "required_dimensions": intent.get("dimensions", []),
        "required_filters": intent.get("filters", {}),
        "messages": state["messages"] + [
            HumanMessage(content=state["user_query"]),
            response
        ]
    }
```

#### 2. Schema Fetch Node
**File:** `backend/app/services/agents/vizql/nodes/schema_fetch.py`

```python
async def fetch_schema_node(state: VizQLAgentState) -> VizQLAgentState:
    """
    Fetch datasource schema using Tableau API.
    
    This is an "Act" step in ReAct.
    """
    datasource_id = state["context_datasources"][0]  # Use first datasource
    
    try:
        schema = await tableau_client.get_datasource_schema(datasource_id)
        
        return {
            **state,
            "schema": schema,
            "tool_calls": state.get("tool_calls", []) + [{
                "tool": "get_datasource_schema",
                "args": {"datasource_id": datasource_id},
                "result": "success"
            }]
        }
    except Exception as e:
        return {
            **state,
            "error": f"Failed to fetch schema: {str(e)}"
        }
```

#### 3. Query Builder Node
**File:** `backend/app/services/agents/vizql/nodes/query_builder.py`

```python
async def build_query_node(state: VizQLAgentState) -> VizQLAgentState:
    """
    Construct VizQL Data Service query from intent and schema.
    
    This is an "Act" step in ReAct.
    """
    # Get query construction prompt with examples
    system_prompt = prompt_registry.get_prompt(
        "agents/vizql/query_construction.txt",
        variables={
            "schema": json.dumps(state["schema"], indent=2),
            "measures": state["required_measures"],
            "dimensions": state["required_dimensions"],
            "filters": state["required_filters"],
            "datasource_id": state["context_datasources"][0]
        }
    )
    
    # Include few-shot examples
    examples = prompt_registry.get_examples("agents/vizql/examples.yaml")
    messages = prompt_registry.build_few_shot_prompt(
        system_prompt,
        examples,
        f"Build query for: {state['user_query']}"
    )
    
    response = await llm.ainvoke(messages)
    
    # Parse query JSON
    query_draft = json.loads(response.content)
    
    return {
        **state,
        "query_draft": query_draft,
        "query_version": state.get("query_version", 0) + 1
    }
```

#### 4. Validator Node
**File:** `backend/app/services/agents/vizql/nodes/validator.py`

```python
async def validate_query_node(state: VizQLAgentState) -> VizQLAgentState:
    """
    Validate VizQL query against schema.
    
    This is an "Observe" step in ReAct.
    """
    query = state["query_draft"]
    schema = state["schema"]
    
    errors = []
    suggestions = []
    
    # Validation checks
    if not query.get("datasource", {}).get("datasourceLuid"):
        errors.append("Missing datasource.datasourceLuid")
    
    if not query.get("query", {}).get("fields"):
        errors.append("Missing query.fields")
    
    # Validate field names
    schema_fields = {col["name"] for col in schema.get("columns", [])}
    for field in query.get("query", {}).get("fields", []):
        field_name = field.get("fieldCaption")
        if field_name not in schema_fields:
            errors.append(f"Field '{field_name}' not found in schema")
            # Fuzzy match suggestion
            close_matches = difflib.get_close_matches(field_name, schema_fields, n=1)
            if close_matches:
                suggestions.append(f"Did you mean '{close_matches[0]}'?")
    
    # Validate aggregation functions
    valid_aggs = {"SUM", "AVG", "MIN", "MAX", "COUNT", "COUNTD", "MEDIAN", "STDEV", "VAR", "ATTR"}
    for field in query.get("query", {}).get("fields", []):
        if "function" in field:
            func = field["function"].upper()
            if func not in valid_aggs:
                errors.append(f"Invalid aggregation function: {func}")
    
    is_valid = len(errors) == 0
    
    return {
        **state,
        "is_valid": is_valid,
        "validation_errors": errors,
        "validation_suggestions": suggestions
    }
```

#### 5. Refiner Node
**File:** `backend/app/services/agents/vizql/nodes/refiner.py`

```python
async def refine_query_node(state: VizQLAgentState) -> VizQLAgentState:
    """
    Refine query based on validation errors.
    
    This is a "Reason" step in ReAct - reflect on errors and fix.
    """
    # Check max refinement attempts
    if state.get("query_version", 0) >= 3:
        return {
            **state,
            "error": f"Max refinement attempts reached. Errors: {state['validation_errors']}"
        }
    
    # Get refinement prompt
    system_prompt = prompt_registry.get_prompt(
        "agents/vizql/query_refinement.txt",
        variables={
            "original_query": json.dumps(state["query_draft"], indent=2),
            "errors": state["validation_errors"],
            "suggestions": state["validation_suggestions"],
            "schema": json.dumps(state["schema"], indent=2)
        }
    )
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Fix the query based on validation errors.")
    ]
    
    response = await llm.ainvoke(messages)
    
    # This node updates state to trigger re-building
    return {
        **state,
        "current_thought": f"Refining query due to errors: {state['validation_errors']}"
    }
```

#### 6. Executor Node
**File:** `backend/app/services/agents/vizql/nodes/executor.py`

```python
async def execute_query_node(state: VizQLAgentState) -> VizQLAgentState:
    """
    Execute validated VizQL query.
    
    This is an "Act" step in ReAct.
    """
    query = state["query_draft"]
    
    try:
        # Execute using VizQL Data Service API
        results = await tableau_client.execute_vds_query(query)
        
        return {
            **state,
            "query_results": results,
            "tool_calls": state.get("tool_calls", []) + [{
                "tool": "execute_vds_query",
                "args": {"query": query},
                "result": "success",
                "row_count": results.get("row_count", 0)
            }]
        }
    except Exception as e:
        return {
            **state,
            "execution_error": str(e),
            "error": f"Query execution failed: {str(e)}"
        }
```

#### 7. Formatter Node
**File:** `backend/app/services/agents/vizql/nodes/formatter.py`

```python
async def format_results_node(state: VizQLAgentState) -> VizQLAgentState:
    """
    Format query results for user presentation.
    
    This is a final "Act" step in ReAct.
    """
    results = state["query_results"]
    
    # Build natural language response
    response = f"Query executed successfully. Found {results['row_count']} rows.\n\n"
    
    # Add data table (first 10 rows)
    if results.get("data"):
        response += "Results:\n"
        response += format_as_table(results["columns"], results["data"][:10])
        
        if results["row_count"] > 10:
            response += f"\n\n(Showing first 10 of {results['row_count']} rows)"
    
    # Add query details
    response += f"\n\nQuery used:\n```json\n{json.dumps(state['query_draft'], indent=2)}\n```"
    
    return {
        **state,
        "formatted_response": response,
        "final_answer": response
    }
```

### Requirements
1. **Datasource Schema Access**: Full column metadata (name, type, measure/dimension)
2. **Query Construction**: Build VizQL Data Service queries from natural language
3. **Query Validation**: Validate queries before execution
4. **Query Execution**: Execute queries using VizQL Data Service API

### Current Issues

The `VDSAgent` has several gaps:

1. **`analyze_datasource()` uses wrong API**: Currently uses REST API (`/sites/{site_id}/datasources/{id}`) which doesn't return full schema. Should use `get_datasource_schema()` which uses VizQL Data Service API.

2. **`construct_query()` returns wrong format**: Returns SQL-like strings, but VizQL Data Service API expects JSON objects with structure:
   ```json
   {
     "datasource": {"datasourceLuid": "..."},
     "query": {
       "fields": [...],
       "filters": [...],
       "parameters": [...]
     },
     "options": {
       "returnFormat": "OBJECTS",
       "disaggregate": false
     }
   }
   ```

3. **Missing execution method**: No method to execute VizQL Data Service queries directly.

4. **No AI-assisted query construction**: Has `ai_client` but doesn't use it for better query understanding.

### Missing Methods

#### 1. `construct_vds_query()` - Build VizQL Data Service Query Object
**Purpose**: Convert natural language to proper VizQL Data Service JSON format

```python
async def construct_vds_query(
    self,
    user_query: str,
    datasource_id: str,
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Construct VizQL Data Service query object from natural language.
    
    Args:
        user_query: Natural language query (e.g., "show sales by region")
        datasource_id: Datasource LUID
        limit: Optional row limit
        
    Returns:
        Dictionary with VizQL Data Service query structure:
        {
            "datasource": {"datasourceLuid": "..."},
            "query": {
                "fields": [
                    {"fieldCaption": "Sales", "function": "SUM"},
                    {"fieldCaption": "Region"}
                ],
                "filters": [...],
                "parameters": [...]
            },
            "options": {
                "returnFormat": "OBJECTS",
                "disaggregate": False
            }
        }
    """
    # Get schema using VizQL Data Service API
    schema = await self.tableau_client.get_datasource_schema(datasource_id)
    
    # Extract intent using AI or rule-based approach
    measures = self._extract_measures(user_query, schema)
    dimensions = self._extract_dimensions(user_query, schema)
    filters = self._extract_filters(user_query, schema)
    
    # Build field objects
    fields = []
    for measure in measures:
        field_obj = {"fieldCaption": measure}
        # Add aggregation function
        agg = self._get_aggregation(user_query, measure)
        if agg:
            field_obj["function"] = agg
        fields.append(field_obj)
    
    for dimension in dimensions:
        fields.append({"fieldCaption": dimension})
    
    # Build query object
    query_obj = {
        "datasource": {
            "datasourceLuid": datasource_id
        },
        "query": {
            "fields": fields
        },
        "options": {
            "returnFormat": "OBJECTS",
            "disaggregate": False
        }
    }
    
    # Add filters if any
    if filters:
        query_obj["query"]["filters"] = self._build_filter_objects(filters, schema)
    
    return query_obj
```

#### 2. `execute_vds_query()` - Execute VizQL Data Service Query
**Purpose**: Execute a VizQL Data Service query and return results

```python
async def execute_vds_query(
    self,
    query_obj: Dict[str, Any],
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Execute a VizQL Data Service query.
    
    Args:
        query_obj: VizQL Data Service query object
        limit: Optional row limit
        
    Returns:
        Dictionary with columns, data, and row_count
    """
    if not self.tableau_client:
        from app.services.tableau.client import TableauClient
        self.tableau_client = TableauClient()
    
    # Use existing get_datasource_sample pattern but with custom query
    datasource_id = query_obj["datasource"]["datasourceLuid"]
    
    # Construct VDS API URL
    from urllib.parse import urljoin
    vds_url = urljoin(self.tableau_client.server_url, '/api/v1/vizql-data-service/query-datasource')
    
    # Add limit to options if provided
    if limit:
        query_obj["options"]["limit"] = limit
    
    # Execute query
    headers = self.tableau_client._get_auth_headers()
    response = await self.tableau_client._client.post(
        vds_url,
        headers=headers,
        json=query_obj,
        timeout=self.tableau_client.timeout,
    )
    response.raise_for_status()
    response_data = response.json()
    
    # Parse response (similar to get_datasource_sample)
    # ... parse logic ...
    
    return {
        "columns": column_names,
        "data": data_rows,
        "row_count": len(data_rows)
    }
```

#### 3. `construct_query_with_ai()` - AI-Assisted Query Construction
**Purpose**: Use AI to better understand natural language and construct queries

```python
async def construct_query_with_ai(
    self,
    user_query: str,
    datasource_id: str
) -> Dict[str, Any]:
    """
    Use AI to construct VizQL query from natural language.
    
    Args:
        user_query: Natural language query
        datasource_id: Datasource LUID
        
    Returns:
        VizQL Data Service query object
    """
    if not self.ai_client:
        # Fallback to rule-based construction
        return await self.construct_vds_query(user_query, datasource_id)
    
    # Get schema
    schema = await self.tableau_client.get_datasource_schema(datasource_id)
    
    # Build prompt for AI
    prompt = f"""
    You are a VizQL expert. Given this datasource schema and user query, construct a VizQL Data Service query.
    
    Datasource Schema:
    {json.dumps(schema, indent=2)}
    
    User Query: {user_query}
    
    Return a JSON object with this structure:
    {{
        "fields": [
            {{"fieldCaption": "FieldName", "function": "SUM"}}  // for measures
            {{"fieldCaption": "FieldName"}}  // for dimensions
        ],
        "filters": [
            {{"fieldCaption": "FieldName", "values": ["value1", "value2"]}}
        ]
    }}
    """
    
    # Call AI
    response = await self.ai_client.chat(
        model=self.model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Parse AI response and build query object
    # ... implementation ...
```

#### 4. `_build_filter_objects()` - Build Filter Objects
**Purpose**: Convert extracted filters to VizQL Data Service filter format

```python
def _build_filter_objects(
    self,
    filters: Dict[str, Any],
    schema: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Build VizQL Data Service filter objects.
    
    Args:
        filters: Dictionary of field_name -> value mappings
        schema: Datasource schema
        
    Returns:
        List of filter objects for VizQL Data Service
    """
    filter_objects = []
    
    for field_name, value in filters.items():
        # Find field in schema
        field_info = next(
            (col for col in schema.get("columns", []) if col.get("name") == field_name),
            None
        )
        
        if not field_info:
            continue
        
        filter_obj = {
            "fieldCaption": field_name
        }
        
        # Handle different filter types
        if isinstance(value, list):
            filter_obj["values"] = value
        elif isinstance(value, dict):
            # Range filter: {"min": 100, "max": 200}
            if "min" in value or "max" in value:
                filter_obj["range"] = value
        else:
            filter_obj["values"] = [value]
        
        filter_objects.append(filter_obj)
    
    return filter_objects
```

#### 5. Update `analyze_datasource()` to use VizQL Data Service API
**Purpose**: Use proper schema retrieval method

```python
async def analyze_datasource(self, datasource_id: str) -> Dict[str, Any]:
    """Analyze datasource schema using VizQL Data Service API."""
    if not self.tableau_client:
        from app.services.tableau.client import TableauClient
        self.tableau_client = TableauClient()
    
    # Use VizQL Data Service API instead of REST API
    schema_response = await self.tableau_client.get_datasource_schema(datasource_id)
    
    # Transform to expected format
    columns = schema_response.get("columns", [])
    
    return {
        "datasource_id": datasource_id,
        "columns": columns,
        "measures": [col for col in columns if col.get("is_measure")],
        "dimensions": [col for col in columns if col.get("is_dimension")],
        "calculated_fields": [col for col in columns if col.get("formula")]
    }
```

### Implementation Steps

1. **Update `analyze_datasource()`**: Use `get_datasource_schema()` instead of REST API
2. **Add `construct_vds_query()`**: Build proper VizQL Data Service JSON format
3. **Add `execute_vds_query()`**: Execute queries using VizQL Data Service API
4. **Add `construct_query_with_ai()`**: Use AI for better query understanding (optional)
5. **Add `_build_filter_objects()`**: Helper for filter construction
6. **Update `construct_query()`**: Deprecate or update to call `construct_vds_query()`

### Enhanced VizQL Agent Prompt

```
You are a VizQL Agent specialized in constructing VizQL Data Service queries.
You have access to datasource schemas and can help users query data.

When constructing queries:
1. Understand user intent from natural language
2. Map user requests to datasource columns (using fieldCaption)
3. Construct valid VizQL Data Service query objects (JSON format)
4. Apply appropriate aggregations for measures
5. Build filters for date ranges, categories, etc.
6. Explain the query structure

VizQL Data Service Query Format:
{
  "datasource": {"datasourceLuid": "..."},
  "query": {
    "fields": [
      {"fieldCaption": "Sales", "function": "SUM"},  // Measures with aggregation
      {"fieldCaption": "Region"}  // Dimensions
    ],
    "filters": [
      {"fieldCaption": "Year", "values": ["2024"]}
    ]
  },
  "options": {
    "returnFormat": "OBJECTS",
    "disaggregate": false
  }
}
```

## General Agent Implementation

### Requirements
1. **Context Awareness**: Know what objects are in context
2. **Tool Access**: Use available Tableau tools (list, query, etc.)
3. **Flexible Responses**: Handle various types of queries

### Implementation Steps

1. **Include Context Summary**:
   - List datasources and views in context
   - Provide object names and IDs
   - Allow agent to use tools to fetch more details as needed

2. **Use Existing Tools**:
   - The agent already has access to `get_tools()` which includes Tableau operations
   - Tools can be called via function calling

## Integration with Chat API

### Updated Chat Flow

```python
# backend/app/api/chat.py

from app.services.agents.graph_factory import AgentGraphFactory

@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: MessageRequest,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    # ... existing validation code ...
    
    # Get context objects
    context_objects = db.query(ChatContext).filter(
        ChatContext.conversation_id == request.conversation_id
    ).order_by(ChatContext.added_at).all()
    
    datasource_ids = [ctx.object_id for ctx in context_objects if ctx.object_type == 'datasource']
    view_ids = [ctx.object_id for ctx in context_objects if ctx.object_type == 'view']
    
    # Route to agent graph based on agent_type
    agent_type = request.agent_type or 'general'
    
    if agent_type == 'vizql' and datasource_ids:
        # Use VizQL agent graph
        graph = AgentGraphFactory.create_vizql_graph()
        
        initial_state = {
            "user_query": request.content,
            "agent_type": "vizql",
            "context_datasources": datasource_ids,
            "context_views": view_ids,
            "messages": [],
            "query_version": 0
        }
        
        # Execute graph
        final_state = await graph.ainvoke(initial_state)
        
        # Handle streaming if requested
        if request.stream:
            # Stream intermediate steps
            async def stream_graph():
                async for state in graph.astream(initial_state):
                    if "current_thought" in state:
                        yield f"data: {json.dumps({'type': 'thought', 'content': state['current_thought']})}\n\n"
                    if "final_answer" in state:
                        yield f"data: {json.dumps({'type': 'answer', 'content': state['final_answer']})}\n\n"
            
            return StreamingResponse(stream_graph(), media_type="text/event-stream")
        
        # Save response to database
        # ... save message ...
        
        return ChatResponse(
            message_id=db_message.id,
            content=final_state["final_answer"],
            # ... other fields ...
        )
    
    elif agent_type == 'summary' and view_ids:
        # Use Summary agent graph
        graph = AgentGraphFactory.create_summary_graph()
        
        initial_state = {
            "user_query": request.content,
            "agent_type": "summary",
            "context_datasources": datasource_ids,
            "context_views": view_ids,
            "messages": []
        }
        
        final_state = await graph.ainvoke(initial_state)
        
        # ... save and return ...
    
    else:
        # Use General agent or fallback to basic chat
        # ... existing chat logic ...
```

## Testing Strategy

### Unit Tests

#### 1. Prompt Registry Tests
```python
# tests/unit/test_prompt_registry.py

def test_prompt_loading():
    registry = PromptRegistry()
    prompt = registry.get_prompt("agents/vizql/system.txt")
    assert "VizQL" in prompt
    assert "datasource" in prompt.lower()

def test_prompt_template_rendering():
    registry = PromptRegistry()
    prompt = registry.get_prompt(
        "agents/vizql/system.txt",
        variables={"datasources": ["ds1", "ds2"]}
    )
    assert "ds1" in prompt

def test_few_shot_examples():
    registry = PromptRegistry()
    examples = registry.get_examples("agents/vizql/examples.yaml")
    assert len(examples) > 0
    assert "user" in examples[0]
    assert "assistant" in examples[0]
```

#### 2. Agent Node Tests
```python
# tests/unit/agents/vizql/test_nodes.py

@pytest.mark.asyncio
async def test_planner_node():
    state = {
        "user_query": "show sales by region",
        "context_datasources": ["ds-123"],
        "messages": []
    }
    
    result = await plan_query_node(state)
    
    assert "required_measures" in result
    assert "required_dimensions" in result
    assert len(result["required_measures"]) > 0

@pytest.mark.asyncio
async def test_validator_node():
    state = {
        "query_draft": {
            "datasource": {"datasourceLuid": "ds-123"},
            "query": {
                "fields": [
                    {"fieldCaption": "Sales", "function": "SUM"}
                ]
            }
        },
        "schema": {
            "columns": [
                {"name": "Sales", "data_type": "number", "is_measure": True}
            ]
        }
    }
    
    result = await validate_query_node(state)
    
    assert result["is_valid"] == True
    assert len(result["validation_errors"]) == 0
```

#### 3. Graph Execution Tests
```python
# tests/integration/test_vizql_graph.py

@pytest.mark.asyncio
async def test_vizql_graph_end_to_end():
    graph = AgentGraphFactory.create_vizql_graph()
    
    initial_state = {
        "user_query": "show total sales by region",
        "agent_type": "vizql",
        "context_datasources": ["test-datasource-id"],
        "context_views": [],
        "messages": []
    }
    
    final_state = await graph.ainvoke(initial_state)
    
    assert "final_answer" in final_state
    assert final_state.get("error") is None
    assert final_state.get("query_results") is not None

@pytest.mark.asyncio
async def test_vizql_graph_handles_invalid_fields():
    """Test that graph refines query when fields don't match schema."""
    graph = AgentGraphFactory.create_vizql_graph()
    
    initial_state = {
        "user_query": "show revenue by country",  # "revenue" might not exist
        "agent_type": "vizql",
        "context_datasources": ["test-datasource-id"],
        "context_views": [],
        "messages": []
    }
    
    final_state = await graph.ainvoke(initial_state)
    
    # Should either succeed with corrected field or fail gracefully
    if final_state.get("error"):
        assert "validation" in final_state["error"].lower()
    else:
        assert final_state["query_results"] is not None
```

### Integration Tests

#### 1. Chat API with Agents
```python
# tests/integration/test_chat_api.py

@pytest.mark.asyncio
async def test_chat_with_vizql_agent(client, db_session):
    # Setup: Create datasource in context
    conversation = create_test_conversation(db_session)
    datasource = create_test_datasource_context(db_session, conversation.id)
    
    # Send message with vizql agent
    response = client.post("/api/v1/chat/message", json={
        "conversation_id": conversation.id,
        "content": "show sales by region",
        "agent_type": "vizql",
        "model": "gpt-4",
        "stream": False
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "query" in data["content"].lower()
    assert data["agent_type"] == "vizql"

@pytest.mark.asyncio
async def test_chat_with_summary_agent(client, db_session):
    # Setup: Create view in context
    conversation = create_test_conversation(db_session)
    view = create_test_view_context(db_session, conversation.id)
    
    # Send message with summary agent
    response = client.post("/api/v1/chat/message", json={
        "conversation_id": conversation.id,
        "content": "summarize this view",
        "agent_type": "summary",
        "model": "gpt-4",
        "stream": False
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data["content"].lower() or "insight" in data["content"].lower()
```

### Manual Testing Checklist

- [ ] **VizQL Agent - Happy Path**
  - Add datasource to context
  - Query: "show total sales by region"
  - Expected: Valid VizQL query constructed and executed, results returned
  
- [ ] **VizQL Agent - Field Name Mismatch**
  - Add datasource to context
  - Query: "show revenue by country" (where "revenue" doesn't exist but "sales" does)
  - Expected: Agent refines query, suggests correct field name, executes corrected query
  
- [ ] **VizQL Agent - Complex Query**
  - Add datasource to context
  - Query: "show top 10 products by sales, filtered to 2024, grouped by category"
  - Expected: Multi-field query with filters, sorting, and grouping
  
- [ ] **Summary Agent - Basic Summary**
  - Add view to context
  - Query: "summarize this view"
  - Expected: Statistical summary with key insights, trends, and recommendations
  
- [ ] **Summary Agent - Specific Question**
  - Add view to context
  - Query: "what are the top 5 regions by sales?"
  - Expected: Targeted analysis answering specific question
  
- [ ] **General Agent - Multiple Contexts**
  - Add 2 datasources and 1 view to context
  - Query: "what's in my context?"
  - Expected: Lists all context objects with details
  
- [ ] **Error Handling - No Context**
  - Don't add any context objects
  - Query with VizQL agent: "show sales"
  - Expected: Graceful error message asking user to add datasource
  
- [ ] **Error Handling - API Failure**
  - Add datasource to context (but disconnect from Tableau)
  - Query: "show sales"
  - Expected: Error message with retry option
  
- [ ] **Streaming - Thought Process**
  - Enable streaming
  - Query with VizQL agent
  - Expected: See intermediate thoughts ("Fetching schema...", "Building query...", "Validating...")
  
- [ ] **Performance - Large View**
  - Add view with 10,000+ rows
  - Query: "summarize this view"
  - Expected: Completes within 30 seconds, samples data appropriately

## Implementation Roadmap

### Sprint 1: Foundation (3-5 days)
**Goal**: Set up LangGraph infrastructure and prompt management

#### Tasks
1. **Install Dependencies** (30 min)
   - Add `langgraph`, `langchain-core`, `langchain-openai`, `jinja2` to requirements
   - Run `pip install`
   
2. **Create Prompt Infrastructure** (1-2 days)
   - [ ] Create `backend/app/prompts/` directory structure
   - [ ] Implement `PromptRegistry` class
   - [ ] Write VizQL system prompts
   - [ ] Write Summary system prompts
   - [ ] Create few-shot examples for each agent
   - [ ] Add prompt templates for validation, refinement, etc.
   
3. **Create Base Agent State** (2-3 hours)
   - [ ] Implement `BaseAgentState` TypedDict
   - [ ] Implement `VizQLAgentState` TypedDict
   - [ ] Implement `SummaryAgentState` TypedDict
   
4. **Create Agent Graph Factory** (2-3 hours)
   - [ ] Implement `AgentGraphFactory` class
   - [ ] Add graph creation methods (stubs for now)
   
5. **Testing** (1 day)
   - [ ] Unit tests for PromptRegistry
   - [ ] Integration test for basic graph creation

**Dependencies**: None
**Deliverable**: Prompt system ready, basic graph structure in place

---

### Sprint 2: VizQL Agent Implementation (5-7 days)
**Goal**: Complete VizQL agent with ReAct pattern and validation loops

#### Tasks
1. **Implement VizQL Agent Nodes** (3-4 days)
   - [ ] Planner node (intent parsing)
   - [ ] Schema fetch node
   - [ ] Query builder node (with AI assistance)
   - [ ] Validator node (comprehensive validation)
   - [ ] Refiner node (error correction)
   - [ ] Executor node
   - [ ] Formatter node
   
2. **Build VizQL Agent Graph** (1 day)
   - [ ] Wire nodes together in StateGraph
   - [ ] Add conditional edges for validation loop
   - [ ] Add error handling and max retry logic
   - [ ] Implement checkpointing for resume capability
   
3. **Enhance Tableau Client** (1 day)
   - [ ] Add `execute_vds_query()` method (if not exists)
   - [ ] Add retry logic for API failures
   - [ ] Add query result caching
   
4. **Testing** (2 days)
   - [ ] Unit tests for each node
   - [ ] Integration tests for full graph
   - [ ] Test validation and refinement loops
   - [ ] Test error recovery

**Dependencies**: Sprint 1 complete
**Deliverable**: Working VizQL agent that can construct, validate, and execute queries

---

### Sprint 3: Summary Agent Implementation (4-5 days)
**Goal**: Complete Summary agent with statistical analysis

#### Tasks
1. **Implement Summary Agent Nodes** (2-3 days)
   - [ ] Data fetcher node
   - [ ] Analyzer node (statistical analysis)
   - [ ] Insight generation node
   - [ ] Summarizer node
   
2. **Build Summary Agent Graph** (1 day)
   - [ ] Wire nodes together in StateGraph
   - [ ] Add error handling
   
3. **Add Statistical Analysis** (1 day)
   - [ ] Install `pandas`, `numpy`, `scipy` if needed
   - [ ] Implement trend detection
   - [ ] Implement outlier detection
   - [ ] Implement correlation analysis
   
4. **Testing** (1 day)
   - [ ] Unit tests for analyzer node
   - [ ] Integration tests for full graph
   - [ ] Test with various view types

**Dependencies**: Sprint 1 complete, Sprint 2 optional
**Deliverable**: Working Summary agent that analyzes views and generates insights

---

### Sprint 4: Chat API Integration (3-4 days)
**Goal**: Integrate agents into chat API with agent routing

#### Tasks
1. **Update Chat API** (2 days)
   - [ ] Add `agent_type` to `MessageRequest` model
   - [ ] Retrieve context objects (datasources/views)
   - [ ] Implement agent routing logic
   - [ ] Handle streaming with graph state updates
   - [ ] Add error handling and fallbacks
   
2. **Update Frontend** (1 day)
   - [ ] Pass `agentType` from AgentPanel to ChatInterface
   - [ ] Update ChatInterface to send `agent_type` to API
   - [ ] Update API client types
   
3. **Testing** (1 day)
   - [ ] Integration tests for chat API with agents
   - [ ] Test all agent types
   - [ ] Test context handling
   - [ ] Test streaming

**Dependencies**: Sprints 1, 2, 3 complete
**Deliverable**: Agents fully integrated into chat UI

---

### Sprint 5: Enhanced Features (3-5 days)
**Goal**: Add advanced features like memory, caching, and observability

#### Tasks
1. **Agent Memory** (2 days)
   - [ ] Implement session memory (recent queries, results)
   - [ ] Cache expensive operations (schema fetches, view data)
   - [ ] Add conversation context summarization
   
2. **Observability** (1 day)
   - [ ] Add logging for each graph node
   - [ ] Track agent performance metrics (latency, success rate)
   - [ ] Add debug mode for viewing graph execution
   
3. **Error Recovery** (1 day)
   - [ ] Implement retry strategies with exponential backoff
   - [ ] Add fallback to cached results
   - [ ] Graceful degradation for API failures
   
4. **Query Optimization** (1 day)
   - [ ] Query result caching
   - [ ] Query simplification for large datasets
   - [ ] Parallel tool execution where possible

**Dependencies**: Sprint 4 complete
**Deliverable**: Production-ready agents with robust error handling and monitoring

---

### Sprint 6: Advanced Agent Features (Optional, 5-7 days)
**Goal**: Multi-agent collaboration and advanced reasoning

#### Tasks
1. **Multi-Agent Orchestration** (3 days)
   - [ ] Agent-to-agent communication
   - [ ] Handoff between agents (e.g., VizQL → Summary)
   - [ ] Parallel agent execution for complex queries
   
2. **Advanced Reasoning** (2 days)
   - [ ] Chain-of-thought prompting
   - [ ] Self-reflection and critique
   - [ ] Meta-agent for agent selection
   
3. **User Feedback Loop** (2 days)
   - [ ] Accept user corrections to queries
   - [ ] Learn from user preferences
   - [ ] Query refinement based on feedback

**Dependencies**: Sprint 5 complete
**Deliverable**: Advanced multi-agent system with sophisticated reasoning

---

## Files to Create/Modify

### New Files to Create

#### Prompts
- `backend/app/prompts/registry.py` - Prompt registry implementation
- `backend/app/prompts/base.py` - Base prompt templates
- `backend/app/prompts/agents/vizql/system.txt` - VizQL system prompt
- `backend/app/prompts/agents/vizql/planning.txt` - Intent parsing prompt
- `backend/app/prompts/agents/vizql/query_construction.txt` - Query building prompt
- `backend/app/prompts/agents/vizql/query_validation.txt` - Validation prompt
- `backend/app/prompts/agents/vizql/query_refinement.txt` - Refinement prompt
- `backend/app/prompts/agents/vizql/examples.yaml` - Few-shot examples
- `backend/app/prompts/agents/summary/system.txt` - Summary system prompt
- `backend/app/prompts/agents/summary/insight_generation.txt` - Insight prompt
- `backend/app/prompts/agents/summary/final_summary.txt` - Summary prompt
- `backend/app/prompts/agents/summary/examples.yaml` - Few-shot examples

#### Agent Infrastructure
- `backend/app/services/agents/base_state.py` - Base state definitions
- `backend/app/services/agents/graph_factory.py` - Graph creation factory
- `backend/app/services/agents/vizql/state.py` - VizQL agent state
- `backend/app/services/agents/vizql/nodes/planner.py` - Planner node
- `backend/app/services/agents/vizql/nodes/schema_fetch.py` - Schema fetch node
- `backend/app/services/agents/vizql/nodes/query_builder.py` - Query builder node
- `backend/app/services/agents/vizql/nodes/validator.py` - Validator node
- `backend/app/services/agents/vizql/nodes/refiner.py` - Refiner node
- `backend/app/services/agents/vizql/nodes/executor.py` - Executor node
- `backend/app/services/agents/vizql/nodes/formatter.py` - Formatter node
- `backend/app/services/agents/summary/state.py` - Summary agent state
- `backend/app/services/agents/summary/nodes/data_fetcher.py` - Data fetcher node
- `backend/app/services/agents/summary/nodes/analyzer.py` - Analyzer node
- `backend/app/services/agents/summary/nodes/insight_gen.py` - Insight generation node
- `backend/app/services/agents/summary/nodes/summarizer.py` - Summarizer node

#### Tests
- `tests/unit/test_prompt_registry.py`
- `tests/unit/agents/vizql/test_nodes.py`
- `tests/unit/agents/summary/test_nodes.py`
- `tests/integration/test_vizql_graph.py`
- `tests/integration/test_summary_graph.py`
- `tests/integration/test_chat_api_agents.py`

### Files to Modify

#### Backend
- `backend/app/api/chat.py` - Add agent routing and graph execution
- `backend/app/api/models.py` - Add `agent_type` to `MessageRequest`
- `backend/app/services/tableau/client.py` - Add missing methods if needed
- `backend/requirements.txt` - Add LangGraph and dependencies

#### Frontend
- `frontend/components/agent-panel/AgentPanel.tsx` - Pass agentType prop
- `frontend/components/chat/ChatInterface.tsx` - Accept and use agentType
- `frontend/lib/api.ts` - Add agent_type to SendMessageRequest
- `frontend/types/index.ts` - Add agent_type types

---

## Estimated Effort Summary

| Sprint | Duration | Complexity | Priority |
|--------|----------|------------|----------|
| Sprint 1: Foundation | 3-5 days | Medium | **Critical** |
| Sprint 2: VizQL Agent | 5-7 days | High | **Critical** |
| Sprint 3: Summary Agent | 4-5 days | Medium | **Critical** |
| Sprint 4: Chat Integration | 3-4 days | Medium | **Critical** |
| Sprint 5: Enhanced Features | 3-5 days | Medium | High |
| Sprint 6: Advanced Features | 5-7 days | High | Optional |

**Total (Critical Path)**: 15-21 days
**Total (With Enhancements)**: 18-26 days
**Total (All Features)**: 23-33 days

---

## Key Architectural Decisions

### 1. Why LangGraph?
- **State Management**: Built-in state persistence across multi-step workflows
- **ReAct Pattern**: Natural fit for Reason-Act-Observe cycles
- **Conditional Routing**: Easy to implement validation loops and error recovery
- **Checkpointing**: Can resume long-running operations
- **Observability**: Built-in logging and debugging support
- **Community**: Strong ecosystem and integrations

### 2. Why Externalized Prompts?
- **Version Control**: Track prompt changes over time
- **A/B Testing**: Easy to test different prompts
- **Maintenance**: Update prompts without code changes
- **Collaboration**: Non-engineers can contribute to prompt engineering
- **Reusability**: Share prompts across agents and contexts

### 3. Why Multi-Node Graphs vs Single Shot?
- **Debuggability**: Each step is isolated and testable
- **Flexibility**: Easy to add/remove steps or reorder them
- **Error Recovery**: Can retry individual steps without restarting
- **Observability**: Clear visibility into where agent is in the process
- **Validation**: Built-in checkpoints ensure quality

### 4. Why Separate State Types?
- **Type Safety**: Each agent has appropriate state fields
- **Clarity**: Explicit about what data each agent needs/produces
- **Evolution**: Easy to add new fields without breaking other agents

---

## Migration Strategy

For teams with existing agent implementations:

1. **Parallel Development**: Build new LangGraph agents alongside existing code
2. **Feature Flag**: Use feature flag to switch between old and new implementations
3. **Gradual Rollout**: Start with one agent type (e.g., VizQL), validate, then migrate others
4. **Deprecation Period**: Keep old code for 2-3 sprints as fallback
5. **Monitoring**: Compare performance and success rates between old and new

**Do NOT** try to refactor existing agents in place - build new and migrate gradually.

---

## Potential Pitfalls & Best Practices

### 1. State Mutation Anti-Patterns

❌ **DON'T: Mutate state directly**
```python
def bad_node(state: AgentState) -> AgentState:
    state["query_draft"]["fields"].append(new_field)  # Mutation!
    return state
```

✅ **DO: Return new state**
```python
def good_node(state: AgentState) -> AgentState:
    return {
        **state,
        "query_draft": {
            **state["query_draft"],
            "fields": state["query_draft"]["fields"] + [new_field]
        }
    }
```

### 2. Infinite Loop Prevention

❌ **DON'T: Forget to limit retry loops**
```python
workflow.add_conditional_edges(
    "validator",
    lambda state: "refine" if not state["is_valid"] else "execute",
    {"refine": "refiner", "execute": "executor"}
)
# Refiner always goes back to query_builder - infinite loop!
```

✅ **DO: Add loop counter and exit condition**
```python
workflow.add_conditional_edges(
    "refiner",
    lambda state: "build" if state["query_version"] < 3 else "fail",
    {"build": "query_builder", "fail": END}
)
```

### 3. Prompt Token Management

❌ **DON'T: Include entire dataset in prompts**
```python
system_prompt += f"Data:\n{json.dumps(view_data)}\n"  # Could be 100k+ tokens!
```

✅ **DO: Sample and summarize data**
```python
sample_data = view_data["data"][:20]  # First 20 rows only
system_prompt += f"Sample Data (showing 20 of {len(view_data['data'])} rows):\n"
system_prompt += f"{json.dumps(sample_data, indent=2)}\n"
```

### 4. Error Handling in Nodes

❌ **DON'T: Let exceptions propagate**
```python
async def fetch_schema_node(state):
    schema = await tableau_client.get_datasource_schema(datasource_id)
    return {**state, "schema": schema}
```

✅ **DO: Catch and add to state**
```python
async def fetch_schema_node(state):
    try:
        schema = await tableau_client.get_datasource_schema(datasource_id)
        return {**state, "schema": schema, "error": None}
    except Exception as e:
        logger.error(f"Schema fetch failed: {e}")
        return {**state, "schema": None, "error": f"Schema fetch failed: {str(e)}"}
```

### 5. Streaming User Experience

❌ **DON'T: Stream only final answer**
```python
async def stream_graph():
    final_state = await graph.ainvoke(initial_state)
    yield final_state["final_answer"]
```

✅ **DO: Stream intermediate steps for transparency**
```python
async def stream_graph():
    async for state in graph.astream(initial_state):
        if "current_thought" in state:
            yield f"💭 {state['current_thought']}\n"
        if "tool_calls" in state and state["tool_calls"]:
            last_call = state["tool_calls"][-1]
            yield f"🔧 {last_call['tool']}...\n"
        if "final_answer" in state:
            yield f"\n{state['final_answer']}\n"
```

### 6. Prompt Cache Invalidation

❌ **DON'T: Cache prompts indefinitely**
```python
class PromptRegistry:
    def __init__(self):
        self._cache = {}  # Never cleared!
```

✅ **DO: Add TTL or version-based invalidation**
```python
class PromptRegistry:
    def __init__(self):
        self._cache = {}
        self._cache_ttl = {}
        self.ttl_seconds = 3600  # 1 hour
    
    def get_prompt(self, path, variables=None):
        cache_key = f"{path}:{hash(frozenset(variables.items()) if variables else 0)}"
        
        # Check cache with TTL
        if cache_key in self._cache:
            if time.time() - self._cache_ttl[cache_key] < self.ttl_seconds:
                return self._cache[cache_key]
        
        # Load and cache
        prompt = self._load_prompt(path, variables)
        self._cache[cache_key] = prompt
        self._cache_ttl[cache_key] = time.time()
        
        return prompt
```

### 7. Schema Field Matching

❌ **DON'T: Use exact string matching only**
```python
def find_field(field_name: str, schema: dict) -> dict | None:
    for col in schema["columns"]:
        if col["name"] == field_name:  # Miss "Sales" vs "Total Sales"
            return col
    return None
```

✅ **DO: Use fuzzy matching with similarity threshold**
```python
import difflib

def find_field(field_name: str, schema: dict, threshold: float = 0.8) -> dict | None:
    schema_fields = {col["name"]: col for col in schema["columns"]}
    
    # Try exact match first
    if field_name in schema_fields:
        return schema_fields[field_name]
    
    # Fuzzy match
    matches = difflib.get_close_matches(
        field_name, 
        schema_fields.keys(), 
        n=1, 
        cutoff=threshold
    )
    
    if matches:
        return schema_fields[matches[0]]
    
    return None
```

### 8. Query Result Size Management

❌ **DON'T: Return unlimited results**
```python
results = await execute_vds_query(query)
return results  # Could be 1 million rows!
```

✅ **DO: Paginate and limit by default**
```python
async def execute_vds_query(query, limit=100, offset=0):
    # Add limit to query options
    query["options"]["limit"] = limit
    query["options"]["offset"] = offset
    
    results = await _execute_query(query)
    
    return {
        **results,
        "limit": limit,
        "offset": offset,
        "has_more": results["row_count"] > (offset + limit)
    }
```

### 9. Prompt Testing

❌ **DON'T: Only test with happy path**
```python
def test_query_construction():
    prompt = build_query_prompt("show sales by region")
    assert "sales" in prompt.lower()
```

✅ **DO: Test edge cases and failure modes**
```python
@pytest.mark.parametrize("user_query,expected_measures,expected_dimensions", [
    ("show sales by region", ["sales"], ["region"]),
    ("total revenue and profit by year", ["revenue", "profit"], ["year"]),
    ("average price", ["price"], []),  # No dimensions
    ("list all categories", [], ["category"]),  # No measures
    ("show me everything", [], []),  # Ambiguous
])
def test_query_construction(user_query, expected_measures, expected_dimensions):
    result = parse_intent(user_query)
    assert set(result["measures"]) == set(expected_measures)
    assert set(result["dimensions"]) == set(expected_dimensions)
```

### 10. Agent Timeout Handling

❌ **DON'T: Let graphs run indefinitely**
```python
final_state = await graph.ainvoke(initial_state)
```

✅ **DO: Set timeouts and handle gracefully**
```python
import asyncio

try:
    final_state = await asyncio.wait_for(
        graph.ainvoke(initial_state),
        timeout=30.0  # 30 seconds
    )
except asyncio.TimeoutError:
    return {
        "error": "Query took too long. Try simplifying your request.",
        "partial_results": graph.get_state()  # Return partial state if available
    }
```

---

## Performance Optimization Strategies

### 1. Parallel Tool Calls
When tools don't depend on each other, execute in parallel:

```python
async def fetch_context_data_node(state: AgentState) -> AgentState:
    """Fetch schema and view data in parallel."""
    
    tasks = []
    
    if state["context_datasources"]:
        tasks.append(tableau_client.get_datasource_schema(state["context_datasources"][0]))
    
    if state["context_views"]:
        tasks.append(tableau_client.get_view_data(state["context_views"][0]))
    
    # Execute in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    schema = results[0] if len(results) > 0 and not isinstance(results[0], Exception) else None
    view_data = results[1] if len(results) > 1 and not isinstance(results[1], Exception) else None
    
    return {
        **state,
        "schema": schema,
        "view_data": view_data
    }
```

### 2. Result Caching
Cache expensive operations with time-based invalidation:

```python
from functools import wraps
import time

def cache_with_ttl(ttl_seconds=300):
    """Cache decorator with TTL."""
    cache = {}
    cache_times = {}
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from args
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            
            # Check cache
            if cache_key in cache:
                if time.time() - cache_times[cache_key] < ttl_seconds:
                    return cache[cache_key]
            
            # Execute and cache
            result = await func(*args, **kwargs)
            cache[cache_key] = result
            cache_times[cache_key] = time.time()
            
            return result
        
        return wrapper
    return decorator

@cache_with_ttl(ttl_seconds=300)  # Cache for 5 minutes
async def get_datasource_schema(datasource_id: str):
    return await tableau_client.get_datasource_schema(datasource_id)
```

### 3. Batch Operations
When operating on multiple objects, batch API calls:

```python
async def fetch_multiple_schemas(datasource_ids: list[str]) -> dict[str, dict]:
    """Fetch multiple schemas in parallel with batching."""
    
    # Batch into groups of 5 to avoid rate limiting
    batch_size = 5
    batches = [datasource_ids[i:i+batch_size] for i in range(0, len(datasource_ids), batch_size)]
    
    all_schemas = {}
    
    for batch in batches:
        tasks = [tableau_client.get_datasource_schema(ds_id) for ds_id in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for ds_id, result in zip(batch, results):
            if not isinstance(result, Exception):
                all_schemas[ds_id] = result
    
    return all_schemas
```

### 4. Streaming for Long Operations
For operations that take >5 seconds, stream progress:

```python
async def long_running_analysis(state: AgentState):
    """Analysis with progress updates."""
    
    # Yield initial state update
    yield {**state, "current_thought": "Starting analysis..."}
    
    # Step 1: Fetch data
    view_data = await get_view_data(state["context_views"][0])
    yield {**state, "current_thought": "Data fetched, computing statistics..."}
    
    # Step 2: Compute stats
    stats = compute_statistics(view_data)
    yield {**state, "current_thought": "Statistics computed, detecting patterns..."}
    
    # Step 3: Pattern detection
    patterns = detect_patterns(view_data, stats)
    yield {**state, "current_thought": "Patterns detected, generating insights..."}
    
    # Step 4: Generate insights
    insights = await generate_insights(patterns)
    
    # Final state
    yield {
        **state,
        "statistics": stats,
        "patterns": patterns,
        "insights": insights,
        "current_thought": None
    }
```

---

## Monitoring & Observability

### Key Metrics to Track

1. **Agent Performance**
   - Response latency (p50, p95, p99)
   - Success rate by agent type
   - Validation loop iterations (avg, max)
   - Query execution time

2. **Tool Usage**
   - Tool call frequency by type
   - Tool failure rate
   - Tool latency by operation

3. **User Experience**
   - Time to first token (streaming)
   - Total conversation time
   - User refinement rate (how often users ask for corrections)
   - Context objects per conversation

4. **AI Model**
   - Token usage per request
   - Model latency
   - Prompt cache hit rate

### Implementation Example

```python
from prometheus_client import Counter, Histogram
import time

# Metrics
agent_requests = Counter('agent_requests_total', 'Total agent requests', ['agent_type', 'status'])
agent_latency = Histogram('agent_latency_seconds', 'Agent latency', ['agent_type'])
validation_loops = Histogram('validation_loops_count', 'Validation loop iterations', ['agent_type'])

async def execute_agent_with_metrics(agent_type: str, initial_state: dict):
    """Execute agent with metrics tracking."""
    start_time = time.time()
    
    try:
        graph = AgentGraphFactory.create_graph(agent_type)
        final_state = await graph.ainvoke(initial_state)
        
        # Record success metrics
        latency = time.time() - start_time
        agent_latency.labels(agent_type=agent_type).observe(latency)
        agent_requests.labels(agent_type=agent_type, status='success').inc()
        
        # Record validation loops (for VizQL)
        if agent_type == 'vizql' and 'query_version' in final_state:
            validation_loops.labels(agent_type=agent_type).observe(final_state['query_version'])
        
        return final_state
        
    except Exception as e:
        agent_requests.labels(agent_type=agent_type, status='error').inc()
        logger.error(f"Agent {agent_type} failed: {e}")
        raise
```

---

## Quick Wins: Incremental Improvements

If full LangGraph implementation seems too large, consider these incremental improvements:

### Quick Win 1: Externalize Prompts (1-2 days)
**Benefit**: Easier prompt iteration without code changes
**Effort**: Low
**Implementation**:
1. Create `backend/app/prompts/` directory
2. Move system prompts to `.txt` files
3. Create simple loader function
4. Update agents to load from files

**Impact**: 🟢 High (enables faster prompt engineering)

### Quick Win 2: Add Query Validation (2-3 days)
**Benefit**: Reduce invalid query failures
**Effort**: Medium
**Implementation**:
1. Create `validate_vizql_query()` function
2. Check field names against schema
3. Check aggregation function validity
4. Add validation before execution

**Impact**: 🟢 High (better user experience, fewer errors)

### Quick Win 3: Simple Retry Logic (1 day)
**Benefit**: Handle transient API failures
**Effort**: Low
**Implementation**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def execute_vds_query_with_retry(query):
    return await tableau_client.execute_vds_query(query)
```

**Impact**: 🟡 Medium (reduces user frustration from transient errors)

### Quick Win 4: Add Context Summary to Prompts (1-2 days)
**Benefit**: Better agent awareness of available data
**Effort**: Low
**Implementation**:
1. Fetch context objects in chat API
2. Add context summary to system prompt
3. Include datasource/view names and IDs

**Impact**: 🟢 High (agents immediately more useful)

### Quick Win 5: Streaming Thoughts (1 day)
**Benefit**: User sees agent progress
**Effort**: Low
**Implementation**:
1. Stream intermediate status messages
2. Show "Fetching schema...", "Building query...", etc.
3. Update UI to display thoughts

**Impact**: 🟡 Medium (better perceived performance)

---

## Decision Matrix: Implementation Approaches

| Approach | Complexity | Time | Flexibility | Debuggability | Scalability | Recommended For |
|----------|------------|------|-------------|---------------|-------------|-----------------|
| **Current (inline prompts, single-shot)** | Low | 0 days | Low | Low | Low | ❌ Not recommended |
| **Quick Wins Only** | Low | 5-7 days | Medium | Medium | Low | ✅ MVP, tight deadlines |
| **LangGraph (Sprints 1-4)** | Medium-High | 15-21 days | High | High | High | ✅✅ Production systems |
| **Full Implementation (All Sprints)** | High | 23-33 days | Very High | Very High | Very High | ✅ Long-term, complex use cases |

### When to Choose Each Approach

#### Quick Wins Only
**Choose if:**
- Need to demo in < 2 weeks
- Limited engineering resources
- Exploring feasibility
- Simple use cases only

**Limitations:**
- Still mostly single-shot processing
- Limited error recovery
- Hard to add new agent capabilities
- Prompts still somewhat coupled to code

#### LangGraph (Sprints 1-4)
**Choose if:**
- Building production system
- Need validation loops and error recovery
- Want to iterate on agent behavior
- Have 3-4 weeks for implementation

**Benefits:**
- Clean separation of concerns
- Easy to debug and test
- Extensible for future features
- Professional-grade architecture

#### Full Implementation
**Choose if:**
- Building complex multi-agent system
- Need advanced reasoning capabilities
- Want agent-to-agent collaboration
- Have 5-7 weeks for development

**Benefits:**
- All the benefits of LangGraph approach
- Advanced features for power users
- Production-ready with monitoring
- Handles edge cases gracefully

---

## Recommended Path Forward

### For Most Teams: LangGraph (Sprints 1-4) + Selected Quick Wins

**Week 1**: Sprint 1 (Foundation) + Quick Win 4 (Context Summary)
- Set up LangGraph infrastructure
- Create prompt registry
- Add context awareness to existing chat

**Week 2-3**: Sprint 2 (VizQL Agent) + Quick Win 2 (Validation)
- Implement VizQL agent with ReAct pattern
- Add comprehensive validation
- Test with real datasources

**Week 3-4**: Sprint 3 (Summary Agent)
- Implement Summary agent
- Add statistical analysis
- Test with real views

**Week 4**: Sprint 4 (Integration) + Quick Win 5 (Streaming)
- Integrate agents into chat API
- Update frontend
- Add streaming for better UX
- End-to-end testing

**Result**: Production-ready agent system with solid architecture that can be extended later.

### Success Criteria

Before considering the implementation complete, validate:

1. ✅ **VizQL Agent Success Rate**: >80% of valid queries execute successfully
2. ✅ **Validation Loop**: Invalid queries are corrected within 3 iterations >90% of the time
3. ✅ **Summary Agent Quality**: Users find summaries helpful in >75% of cases (survey)
4. ✅ **Response Time**: p95 latency < 15 seconds for queries, < 10 seconds for summaries
5. ✅ **Error Recovery**: Transient failures retry successfully >95% of the time
6. ✅ **Code Quality**: >80% test coverage for agent nodes and graphs
7. ✅ **Observability**: All critical paths have logging and metrics

---

## Appendix: LangGraph vs Alternatives

### Why Not Plain LangChain?
- ❌ No built-in state management for multi-step workflows
- ❌ Harder to implement validation loops
- ❌ Less structured error handling
- ✅ LangGraph is built on LangChain, uses same primitives

### Why Not Custom State Machine?
- ❌ More boilerplate code
- ❌ Need to implement checkpointing yourself
- ❌ Less standardized, harder for new team members
- ✅ LangGraph is essentially a well-designed state machine framework

### Why Not OpenAI Assistants API?
- ❌ Vendor lock-in
- ❌ Less control over execution flow
- ❌ Harder to customize validation logic
- ❌ Cannot easily integrate with Tableau-specific tools

### Why Not CrewAI or AutoGen?
- ❌ More focused on multi-agent collaboration (overkill for this use case)
- ❌ Less control over individual agent logic
- ❌ Higher abstraction might hide important details
- ✅ Could be useful for Sprint 6 (advanced multi-agent features)

**Verdict**: LangGraph provides the right balance of structure and flexibility for this use case.

---

## Getting Started: First Steps

1. **Review this document with team** (1 hour)
   - Discuss approach: Quick Wins vs LangGraph vs Full
   - Align on priorities and timeline
   - Assign sprint owners

2. **Set up development environment** (2 hours)
   - Install LangGraph and dependencies
   - Create prompts directory structure
   - Set up testing framework

3. **Spike: Build minimal VizQL graph** (4-8 hours)
   - Implement just 3 nodes: planner, schema_fetch, query_builder
   - Wire them together in a simple graph
   - Test with one example query
   - **Goal**: Validate approach and identify gotchas

4. **Review spike results** (1 hour)
   - What worked well?
   - What was harder than expected?
   - Adjust estimates and plan

5. **Proceed with Sprint 1** 🚀

---

## Questions & Answers

**Q: Can we mix old and new agent implementations?**
A: Yes! Use feature flags to route to different implementations. Start with one agent type (e.g., VizQL), validate, then migrate others.

**Q: What if LangGraph adds too much latency?**
A: The graph structure adds minimal overhead (<100ms). Most latency comes from LLM calls and Tableau API calls. You can optimize by:
- Caching schemas and view data
- Running independent tool calls in parallel
- Using faster models for simple nodes (e.g., validation)

**Q: How do we handle breaking changes in prompts?**
A: Version your prompts using subdirectories:
```
prompts/agents/vizql/
  v1/
    system.txt
  v2/
    system.txt
```
Then specify version when loading: `get_prompt("agents/vizql/v2/system.txt")`

**Q: Can we use this architecture with other LLM providers (e.g., Claude, Gemini)?**
A: Yes! LangGraph is provider-agnostic. Just swap the LLM client in your nodes. The graph structure remains the same.

**Q: What about rate limiting from Tableau APIs?**
A: Implement rate limiting in the Tableau client:
```python
from aiolimiter import AsyncLimiter

rate_limiter = AsyncLimiter(max_rate=10, time_period=1)  # 10 req/sec

async def _request(self, method, endpoint, **kwargs):
    async with rate_limiter:
        return await self._make_request(method, endpoint, **kwargs)
```

**Q: How do we handle very large schemas (1000+ columns)?**
A: Three strategies:
1. Summarize schema in prompt (show only relevant columns based on user query)
2. Use vector search to find relevant columns (embed column names + descriptions)
3. Let user specify which columns to include in context

---

## Conclusion

The current agent implementation lacks the sophisticated state management, validation loops, and error recovery needed for production use. By adopting a LangGraph-based architecture with externalized prompts and ReAct patterns, we can build agents that:

- ✅ Validate and refine queries before execution
- ✅ Recover gracefully from errors
- ✅ Provide transparent reasoning to users
- ✅ Scale to handle complex multi-step workflows
- ✅ Maintain high code quality and testability

The recommended path is a 4-week implementation of Sprints 1-4, which delivers a production-ready foundation that can be extended with advanced features as needed.

**Next Step**: Review with team and decide on approach → Set up development environment → Start Sprint 1 or Quick Wins 🚀
