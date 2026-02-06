# VizQL Streamlined Agent - Engineering Proposal

## Executive Summary

This proposal outlines a streamlined variation of the VizQL agent designed for performance comparison against the current implementation. The streamlined agent removes routing/planning overhead and gives the query builder node enhanced capabilities through tool integration, enabling it to make intelligent decisions about query reuse and schema fetching.

**Key Changes:**
- **Remove:** Router node (shortcut ineffective)
- **Remove:** Planning node (merge planning into query building)
- **Remove:** Schema fetch node (make optional via tool)
- **Enhance:** Build query node with tools and prior message awareness
- **Keep:** Validator, executor, formatter nodes (proven effective)
- **Fix:** Ensure formatter is captured in reasoning steps

---

## Motivation

### Performance Analysis of Current Agent

Current VizQL agent flow:
```
router → planner → schema_fetch → build_query → validator → executor → formatter
```

**Issues Identified:**
1. **Router overhead:** Takes too long; intended to shortcut but adds latency instead
2. **Planning overhead:** Separate planning step adds LLM call without value
3. **Schema fetch always runs:** Even when schema was provided or query can be reused
4. **Inflexible:** Can't reuse queries from prior messages in conversation

**Hypothesis:** Giving build_query node intelligence + tools will be faster and more flexible than explicit routing/planning stages.

---

## Architecture Design

### Simplified Flow

```
┌──────────────────────────────────────────────────┐
│          Streamlined VizQL Agent Flow             │
└──────────────────────────────────────────────────┘

    [start]
       ↓
    [build_query] ←────────┐
    (with tools)           │ (retry with errors)
       ↓                   │
    [validate_query]       │
       ↓         ↓         │
   (valid)   (invalid)    │
       ↓         ↓         │
       ↓    [max retries?]─┘
       ↓         ↓
       ↓    [error_handler]
       ↓
    [execute_query]
       ↓         ↓
   (success)  (failed)
       ↓         ↓
       ↓    [max retries?]─┘
       ↓         ↓
       ↓    [error_handler]
       ↓
    [format_results]
       ↓
    [end]
```

### Key Innovation: Smart Query Builder with Tools

The `build_query` node now has access to tools and can:
1. **Check conversation history** for reusable queries
2. **Fetch schema only if needed** (not provided or context insufficient)
3. **Fetch datasource metadata** (REST API info)
4. **Make intelligent decisions** about what information it needs

---

## Node Specifications

### 1. `build_query` Node (Enhanced)

**Purpose:** Intelligently construct VizQL query, fetching only needed information

**Available Tools:**
```python
tools = [
    get_datasource_schema,      # Fetch full schema if needed
    get_datasource_metadata,    # Fetch datasource info (REST API)
    get_prior_query,            # Extract query from message history
]
```

**Decision Logic:**
```
IF user query is similar to prior message AND prior query exists:
    → Retrieve prior query using get_prior_query tool
    → Modify if needed for new request
    → Return modified query

ELSE IF enriched_schema is provided in state:
    → Use provided schema
    → Build new query

ELSE:
    → Call get_datasource_schema tool
    → Build new query with fetched schema
```

**Inputs:**
- `user_query`: str
- `datasource_id`: str
- `site_id`: str
- `message_history`: list[dict] - Conversation context
- `enriched_schema`: dict (optional) - Pre-fetched schema
- `api_key`: str
- `model`: str
- `validation_errors`: list (on retry)
- `execution_errors`: list (on retry)
- `attempt`: int (1, 2, or 3)

**Outputs:**
- `query_draft`: dict - VizQL query JSON
- `reasoning`: str - LLM's reasoning (includes tool decisions)
- `schema`: dict (if fetched via tool)
- `datasource_metadata`: dict (if fetched via tool)
- `query_reused`: bool - True if query from prior message
- `current_thought`: str

**Prompt Structure:**
```
You are a VizQL query builder with access to tools.

Tools Available:
- get_datasource_schema: Fetch schema if not provided
- get_datasource_metadata: Get datasource info via REST API
- get_prior_query: Extract query from conversation history

User Query: {user_query}
Message History: {message_history}
Enriched Schema (if provided): {enriched_schema}

Instructions:
1. Analyze user query and message history
2. If this query is similar to a prior message, use get_prior_query
3. If schema not provided and needed, use get_datasource_schema
4. If datasource info needed, use get_datasource_metadata
5. Build or adapt the query
6. Return JSON with reasoning

{if retry:}
Previous Attempt Failed:
- Validation Errors: {validation_errors}
- Execution Errors: {execution_errors}
Use tools to get additional context if needed to fix errors.
{endif}
```

**Duration:** 2000-6000ms (depending on tool calls)

**Benefits:**
- **Flexibility:** Can reuse queries from conversation
- **Efficiency:** Only fetches schema when truly needed
- **Intelligence:** Makes context-aware decisions
- **Transparency:** Tool usage captured in reasoning

---

### 2. `validate_query` Node

**Status:** Keep as-is (proven effective)

**Purpose:** Local syntax and semantic validation

**Inputs:**
- `query_draft`: dict
- `schema`: dict (from state or fetched by build_query)
- `enriched_schema`: dict (optional)

**Outputs:**
- `is_valid`: bool
- `validation_errors`: list[str]
- `validation_suggestions`: list[str]
- `current_thought`: str

**Routing:**
```python
if is_valid:
    return "execute_query"
elif attempt < 3:
    state["attempt"] += 1
    return "build_query"  # Retry with errors
else:
    return "error_handler"
```

**Duration:** 10-50ms

**No changes needed** - current implementation is fast and reliable.

---

### 3. `execute_query` Node

**Status:** Keep as-is (proven effective)

**Purpose:** Execute VizQL query against Tableau

**Inputs:**
- `query_draft`: dict (validated)
- `datasource_id`: str
- `site_id`: str

**Outputs:**
- `query_results`: dict
  ```python
  {
      "columns": ["City", "SUM(Profit)"],
      "data": [[...], ...],
      "row_count": 542
  }
  ```
- `execution_status`: "success" | "failed"
- `execution_errors`: list[str] (if failed)
- `current_thought`: str

**Routing:**
```python
if execution_status == "success":
    return "format_results"
elif attempt < 3:
    state["attempt"] += 1
    return "build_query"  # Retry with errors
else:
    return "error_handler"
```

**Duration:** 500-10000ms (query dependent)

**No changes needed** - current implementation works well.

---

### 4. `format_results` Node

**Status:** Keep with modification (capture in reasoning)

**Purpose:** Format results into natural language

**Inputs:**
- `user_query`: str
- `query_results`: dict
- `query_draft`: dict (for context)

**Outputs:**
- `final_answer`: str - Natural language response
- `formatted_response`: str (same as final_answer)
- `previous_results`: dict (for potential reformatting)
- `reasoning_steps`: list - **NEW: Capture formatting as reasoning step**
- `current_thought`: None (clear as done)

**Modification:**
```python
# At end of format_results_node:
reasoning_steps = state.get("reasoning_steps", [])
reasoning_steps.append({
    "node": "format_results",
    "timestamp": datetime.utcnow().isoformat(),
    "thought": f"Formatted {row_count} rows into natural language",
    "action": "format",
    "output_length": len(final_answer)
})

return {
    **state,
    "final_answer": final_answer,
    "reasoning_steps": reasoning_steps,  # Include in state
    "current_thought": None
}
```

**Duration:** 2000-5000ms

---

### 5. `error_handler` Node

**Status:** Keep as-is

**Purpose:** Generate helpful error message after max retries

**Inputs:**
- `user_query`: str
- `attempt`: int
- `validation_errors`: list
- `execution_errors`: list
- `query_draft`: dict

**Outputs:**
- `final_answer`: str - Error explanation
- `error_summary`: dict

**Duration:** 1000-2000ms

**No changes needed.**

---

## State Schema

```python
from typing import TypedDict, Optional, List, Dict, Any

class StreamlinedVizQLState(TypedDict, total=False):
    """
    State for streamlined VizQL agent.
    """
    # Input
    user_query: str
    datasource_id: str
    site_id: str
    message_history: List[Dict[str, Any]]  # Conversation context
    api_key: str
    model: str
    
    # Optional pre-fetched data (can be provided to skip fetching)
    enriched_schema: Optional[Dict[str, Any]]
    
    # Schema (fetched by build_query if needed)
    schema: Optional[Dict[str, Any]]
    datasource_metadata: Optional[Dict[str, Any]]
    
    # Query Building
    query_draft: Optional[Dict[str, Any]]
    reasoning: Optional[str]  # LLM reasoning + tool usage
    query_reused: Optional[bool]  # True if from prior message
    
    # Validation
    is_valid: Optional[bool]
    validation_errors: Optional[List[str]]
    validation_suggestions: Optional[List[str]]
    
    # Execution
    query_results: Optional[Dict[str, Any]]
    execution_status: Optional[str]  # "success" | "failed"
    execution_errors: Optional[List[str]]
    
    # Formatting
    final_answer: Optional[str]
    formatted_response: Optional[str]
    previous_results: Optional[Dict[str, Any]]
    
    # Control Flow
    attempt: int  # 1, 2, or 3
    current_thought: Optional[str]
    
    # Reasoning Capture (NEW)
    reasoning_steps: List[Dict[str, Any]]  # Capture all reasoning including format
    
    # Error Handling
    error: Optional[str]
    error_summary: Optional[Dict[str, Any]]
```

---

## Tool Definitions

### Tool 1: `get_datasource_schema`

**Purpose:** Fetch full datasource schema

**Function Signature:**
```python
async def get_datasource_schema(
    datasource_id: str,
    site_id: str
) -> Dict[str, Any]:
    """
    Fetch schema for datasource.
    
    Returns:
        {
            "columns": [...],
            "measures": [...],
            "dimensions": [...]
        }
    """
```

**When to Use:**
- Schema not provided in state
- Need field information to build query

---

### Tool 2: `get_datasource_metadata`

**Purpose:** Fetch datasource info via REST API

**Function Signature:**
```python
async def get_datasource_metadata(
    datasource_id: str,
    site_id: str
) -> Dict[str, Any]:
    """
    Fetch datasource metadata via Tableau REST API.
    
    Returns:
        {
            "name": "Superstore",
            "project": {...},
            "certificationNote": "...",
            "tags": [...]
        }
    """
```

**When to Use:**
- Need datasource name or description
- Need to understand data source context

---

### Tool 3: `get_prior_query`

**Purpose:** Extract query from prior message in conversation

**Function Signature:**
```python
def get_prior_query(
    message_history: List[Dict[str, Any]],
    similarity_threshold: float = 0.8
) -> Optional[Dict[str, Any]]:
    """
    Search message history for similar queries.
    
    Args:
        message_history: Conversation history
        similarity_threshold: How similar queries must be
        
    Returns:
        {
            "query": {...},  # Prior VizQL query
            "message": "...",  # Original user message
            "timestamp": "...",
            "similarity_score": 0.92
        }
    """
```

**When to Use:**
- User query similar to prior message
- Want to modify existing query instead of building from scratch

**Implementation:**
- Use embedding similarity to compare queries
- Return None if no similar queries found
- LLM can then modify the returned query

---

## Implementation Plan

### Phase 1: Tool Implementation (2 days)

**Tasks:**
1. Implement `get_datasource_schema` tool
   - Wrapper around existing schema fetcher
   - Add caching layer
2. Implement `get_datasource_metadata` tool
   - REST API client integration
   - Error handling
3. Implement `get_prior_query` tool
   - Message history search
   - Similarity scoring using embeddings
4. Write unit tests for each tool

**Files to Create:**
```
backend/app/services/agents/vizql_streamlined/
├── tools/
│   ├── __init__.py
│   ├── schema_tool.py
│   ├── metadata_tool.py
│   └── history_tool.py
```

---

### Phase 2: Enhanced Query Builder Node (3 days)

**Tasks:**
1. Create new `build_query_node` with tool integration
2. Implement prompt that instructs LLM on tool usage
3. Add tool call parsing and execution
4. Add decision logic for query reuse
5. Capture all reasoning including tool calls
6. Write unit tests

**Files to Create:**
```
backend/app/services/agents/vizql_streamlined/
├── nodes/
│   ├── __init__.py
│   ├── query_builder.py  # Enhanced with tools
```

**Prompt Engineering:**
- Write clear instructions on when to use each tool
- Include examples of tool usage
- Test with various scenarios:
  - Query with schema provided
  - Query without schema (must fetch)
  - Query similar to prior message (reuse)
  - Query needing datasource metadata

---

### Phase 3: Node Integration (2 days)

**Tasks:**
1. Copy and adapt validator node (minimal changes)
2. Copy and adapt executor node (no changes)
3. Modify formatter node to capture reasoning
4. Copy error handler (no changes)
5. Write integration tests

**Files to Create:**
```
backend/app/services/agents/vizql_streamlined/
├── nodes/
│   ├── validator.py
│   ├── executor.py
│   ├── formatter.py  # Modified to capture reasoning
│   └── error_handler.py
```

---

### Phase 4: Graph Construction (1 day)

**Tasks:**
1. Create state schema
2. Implement graph with conditional edges
3. Add routing functions
4. Add memory/checkpointing
5. Write graph tests

**Files to Create:**
```
backend/app/services/agents/vizql_streamlined/
├── __init__.py
├── state.py
├── graph.py
```

**Graph Structure:**
```python
def create_streamlined_vizql_graph() -> StateGraph:
    workflow = StateGraph(StreamlinedVizQLState)
    
    # Add nodes
    workflow.add_node("build_query", build_query_node)
    workflow.add_node("validate_query", validate_query_node)
    workflow.add_node("execute_query", execute_query_node)
    workflow.add_node("format_results", format_results_node)
    workflow.add_node("error_handler", error_handler_node)
    
    # Entry point
    workflow.set_entry_point("build_query")
    
    # Edges
    workflow.add_edge("build_query", "validate_query")
    
    workflow.add_conditional_edges(
        "validate_query",
        route_after_validation,
        {
            "execute": "execute_query",
            "retry": "build_query",
            "error": "error_handler"
        }
    )
    
    workflow.add_conditional_edges(
        "execute_query",
        route_after_execution,
        {
            "format": "format_results",
            "retry": "build_query",
            "error": "error_handler"
        }
    )
    
    workflow.add_edge("format_results", END)
    workflow.add_edge("error_handler", END)
    
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
```

---

### Phase 5: Factory Integration (0.5 days)

**Tasks:**
1. Update `AgentGraphFactory` to support streamlined agent
2. Add configuration flag
3. Update API endpoint to accept agent variation

**Modifications:**
```python
# In graph_factory.py
@staticmethod
def create_vizql_graph(
    use_tool_use: bool = False,
    use_controlled: bool = False,
    use_streamlined: bool = False  # NEW
) -> StateGraph:
    if use_streamlined:
        from app.services.agents.vizql_streamlined.graph import create_streamlined_vizql_graph
        return create_streamlined_vizql_graph()
    # ... existing code
```

---

### Phase 6: Testing & Validation (3 days)

**Test Categories:**

**1. Unit Tests**
- Test each tool individually
- Test each node individually
- Test routing functions

**2. Integration Tests**
- Test full graph execution
- Test retry logic
- Test error handling

**3. Comparison Tests**
- Run same queries on both agents
- Compare results for correctness
- Compare latency
- Compare token usage

**4. Edge Case Tests**
- Query with pre-provided schema
- Query without schema (must fetch)
- Query similar to prior message
- Complex query requiring multiple retries
- Invalid datasource ID
- Network errors

**Test Files:**
```
tests/agents/vizql_streamlined/
├── test_tools.py
├── test_nodes.py
├── test_graph.py
└── test_comparison.py
```

---

### Phase 7: Monitoring & Metrics (1 day)

**Metrics to Track:**
1. **Latency:**
   - Overall graph execution time
   - Per-node execution time
   - Tool call latency
2. **Efficiency:**
   - Schema fetch rate (should be lower)
   - Query reuse rate (new metric)
   - Retry rate
3. **Success:**
   - First-try success rate
   - Overall success rate
   - Error types
4. **Cost:**
   - Token usage per query
   - LLM call count

**Implementation:**
- Add timing decorators to nodes
- Log tool usage
- Track query reuse
- Compare with baseline (current agent)

---

## Performance Targets

| Metric | Current Agent | Streamlined Agent Target | Notes |
|--------|---------------|-------------------------|-------|
| **P50 Latency** | ~6s | **< 4s** | Simple queries, schema provided |
| **P95 Latency** | ~12s | **< 8s** | Complex queries |
| **Schema Fetch Rate** | 100% | **< 50%** | When schema provided |
| **Query Reuse Rate** | 0% | **> 30%** | In multi-turn conversations |
| **First-Try Success** | ~80% | **> 85%** | Better with tools |
| **Token Usage** | Baseline | **-20%** | Fewer nodes = fewer prompts |

---

## Success Criteria

### Required for Launch:
1. ✅ All unit tests pass
2. ✅ Integration tests pass
3. ✅ Achieves comparable accuracy to current agent (> 95%)
4. ✅ Latency improvement of at least 20% (P50)
5. ✅ Query reuse works in conversation scenarios

### Nice to Have:
1. Token usage reduction of 20%+
2. Higher first-try success rate
3. Better error messages via tool context

---

## Risks & Mitigations

### Risk 1: Tool Usage Increases Latency
**Mitigation:**
- Tools are optional and used only when needed
- Parallel tool execution where possible
- Caching for schema and metadata

### Risk 2: LLM Doesn't Use Tools Correctly
**Mitigation:**
- Clear prompt instructions with examples
- Extensive testing of tool calling
- Fallback to fetching schema if tool call fails

### Risk 3: Query Reuse Produces Wrong Results
**Mitigation:**
- Conservative similarity threshold (0.8)
- LLM validates reused query against new request
- Validation node catches mismatches

### Risk 4: Regression in Accuracy
**Mitigation:**
- Comparison testing with current agent
- Same validation logic as current agent
- Gradual rollout with A/B testing

---

## Rollout Strategy

### Phase 1: Internal Testing (Week 1)
- Deploy to dev environment
- Internal team testing
- Fix critical issues

### Phase 2: Shadow Mode (Week 2)
- Run both agents in parallel
- Compare results
- Don't expose streamlined to users yet
- Gather metrics

### Phase 3: A/B Test (Week 3)
- 10% traffic to streamlined agent
- Monitor metrics closely
- Collect user feedback
- Iterate on issues

### Phase 4: Gradual Increase (Week 4+)
- Increase to 25%, 50%, 75%
- Continue monitoring
- Make streamlined default if successful
- Keep current agent as fallback

---

## Open Questions

1. **Message History Format:**
   - What format should message_history use?
   - Should we store just user queries or full conversations?
   - How many prior messages to include?

2. **Caching Strategy:**
   - Where to cache schemas? (In-memory, Redis, DB?)
   - Cache TTL?
   - Cache invalidation strategy?

3. **Similarity Threshold:**
   - What threshold for query reuse? (0.8 proposed)
   - How to compute similarity? (Embeddings? String match?)

4. **Tool Call Limits:**
   - Should we limit number of tool calls per query?
   - What if LLM calls tools repeatedly?

5. **Fallback Behavior:**
   - If streamlined agent fails, automatically retry with current agent?
   - Or return error?

---

## Timeline Summary

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 1. Tool Implementation | 2 days | Working tools with tests |
| 2. Enhanced Query Builder | 3 days | Smart query builder node |
| 3. Node Integration | 2 days | All nodes adapted |
| 4. Graph Construction | 1 day | Working graph |
| 5. Factory Integration | 0.5 days | API integration |
| 6. Testing & Validation | 3 days | Test suite + comparison |
| 7. Monitoring & Metrics | 1 day | Metrics dashboard |
| **Total Development** | **12.5 days** | **~2.5 weeks** |
| 8. Rollout (4 phases) | 4 weeks | Production deployment |
| **Total Project** | **~6.5 weeks** | **Full migration** |

---

## Conclusion

The streamlined VizQL agent represents a focused optimization of the current architecture:

**Removed:**
- Router node (latency overhead)
- Planner node (unnecessary abstraction)
- Schema fetch node (inflexible)

**Enhanced:**
- Query builder with tools (intelligent, flexible)
- Reasoning capture (includes formatting step)

**Kept:**
- Validator (fast, reliable)
- Executor (works well)
- Formatter (effective)
- Error handler (comprehensive)

**Expected Benefits:**
- 20-30% latency reduction
- Query reuse in conversations (new capability)
- Lower token usage
- Simpler debugging (fewer nodes)
- More flexible (tools > rigid flow)

This variation enables direct performance comparison while maintaining the proven components of the current agent. The tool-based approach gives the LLM agency while the controlled graph ensures predictable flow.

**Next Steps:**
1. Review and approve this proposal
2. Answer open questions
3. Begin Phase 1 implementation
4. Set up comparison testing infrastructure

---

**Document Status:** Ready for Engineering Review
**Author:** AI Agent
**Date:** 2026-02-06
**Version:** 1.0
