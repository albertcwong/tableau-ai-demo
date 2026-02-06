# VizQL Agent Graph Redesign - Controlled Graph Architecture

## Overview

Shift from LLM-tool-chain approach to controlled graph for predictable, reliable query generation.

## Problem Statement

**Current Issue**: Tool-use chain gives LLM too much control, leading to:
- Unpredictable tool call sequences
- Difficulty debugging failures
- Inconsistent error handling
- No clear retry logic

**Solution**: Controlled graph with explicit nodes and edges for each operation.

## Graph Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     VizQL Query Graph                        │
└─────────────────────────────────────────────────────────────┘

    [start]
       ↓
    [get_schema] ←──────────────┐
       ↓                         │ (on schema error)
    [build_query] ←──────┐       │
       ↓                 │       │
    [validate_query]     │       │
       ↓         ↓       │       │
   (valid)   (invalid)  │       │
       ↓         ↓       │       │
       ↓    [retry?] ───┘       │
       ↓      ↓ (max attempts)   │
       ↓      └──> [error_handler]
       ↓
    [execute_query]
       ↓         ↓
   (success)  (failed)
       ↓         ↓
       ↓    [retry?] ───┘
       ↓      ↓ (max attempts)
       ↓      └──> [error_handler]
       ↓
    [summarize]
       ↓
    [end]
```

## Node Specifications

### 1. `start` Node

**Purpose**: Initialize workflow and notify client

**Inputs**:
- `user_query`: str
- `datasource_id`: str
- `site_id`: str
- `message_history`: list
- `api_key`: str
- `model`: str

**Outputs**:
- `current_thought`: "Starting query analysis..."
- All inputs passed through

**Duration**: < 10ms

---

### 2. `get_schema` Node

**Purpose**: Fetch and cache datasource metadata

**Operations**:
1. Check if schema already in state (from previous node)
2. If not, fetch from Tableau API
3. Enrich with pre-computed statistics
4. Cache for session

**Inputs**:
- `datasource_id`: str
- `site_id`: str

**Outputs**:
- `schema`: dict - Full datasource schema
- `metadata_stats`: dict - Pre-computed statistics
- `current_thought`: "Fetching datasource schema..."

**Error Handling**:
- If fetch fails → Set `schema_error` → Route to `error_handler`
- If timeout → Retry once, then error

**Duration**: 500-2000ms (with caching: < 50ms)

**State Structure**:
```python
{
    "schema": {
        "fields": [...],
        "measures": [...],
        "dimensions": [...]
    },
    "metadata_stats": {
        "City": {"cardinality": 542, "samples": [...]},
        ...
    }
}
```

---

### 3. `build_query` Node

**Purpose**: Use LLM to generate VizQL query from user question

**Inputs**:
- `user_query`: str
- `schema`: dict
- `metadata_stats`: dict
- `message_history`: list (for context)
- `validation_errors`: list (on retry)
- `execution_errors`: list (on retry)
- `attempt`: int (1, 2, or 3)

**Operations**:
1. Load prompt template
2. Format with schema, stats, user query, and error context (if retry)
3. Call LLM with structured output
4. Parse VizQL query JSON

**Outputs**:
- `query_draft`: dict - VizQL query JSON
- `reasoning`: str - LLM's explanation
- `current_thought`: "Building VizQL query..."

**LLM Instructions**:
```
You are a VizQL query builder. Generate a valid VizQL query.

Schema: {schema}
Statistics: {metadata_stats}
User Question: {user_query}

{if retry:}
Previous Attempt Failed:
- Validation Errors: {validation_errors}
- Execution Errors: {execution_errors}
Fix these issues in your next query.
{endif}

Output JSON:
{
  "query": {...},
  "reasoning": "..."
}
```

**Error Handling**:
- If LLM returns invalid JSON → Retry parse
- If parse fails twice → Set `build_error` → Route to `error_handler`

**Duration**: 2000-5000ms

---

### 4. `validate_query` Node

**Purpose**: Local syntax and semantic validation (no LLM)

**Inputs**:
- `query_draft`: dict

**Validation Checks**:

**A. Syntax Validation**:
1. Required fields present (datasourceLuid, query, options)
2. Field names match schema
3. Aggregation functions valid (SUM, AVG, COUNT, etc.)
4. Filter types valid (MATCH, RANGE, etc.)
5. Sorting directions valid (ASC, DESC)

**B. Semantic Validation**:
1. Measures used with aggregation functions
2. Dimensions not aggregated
3. Filters reference actual field names
4. TopN has valid measure for sorting
5. No duplicate field selections

**C. Safety Checks**:
1. Query not requesting > 10,000 rows without topN/limit
2. No nested aggregations
3. Calculated fields have valid syntax

**Outputs** (if valid):
- `validated_query`: dict - Same as query_draft
- `validation_status`: "valid"
- `current_thought`: "Validating query syntax..."

**Outputs** (if invalid):
- `validation_errors`: list[str] - Specific errors found
- `validation_status`: "invalid"
- `attempt`: int - Incremented

**Routing Logic**:
```python
if validation_status == "valid":
    return "execute_query"
elif attempt < 3:
    return "build_query"  # Retry with errors
else:
    return "error_handler"  # Max attempts reached
```

**Duration**: 10-50ms

---

### 5. `execute_query` Node

**Purpose**: Execute VizQL query against Tableau

**Inputs**:
- `validated_query`: dict
- `datasource_id`: str
- `site_id`: str

**Operations**:
1. Send query to Tableau VizQL Data Service
2. Parse response
3. Extract columns, data, row_count

**Outputs** (if successful):
- `raw_data`: dict - Query results
  ```python
  {
      "columns": ["City", "SUM(Profit)"],
      "data": [[...], ...],
      "row_count": 542
  }
  ```
- `execution_status`: "success"
- `current_thought`: "Executing query..."

**Outputs** (if failed):
- `execution_errors`: list[str] - Tableau error messages
- `execution_status`: "failed"
- `attempt`: int - Incremented

**Error Types**:
1. **Syntax Error** (Tableau rejected query) → Retry with error
2. **Timeout** (query took > 30s) → Set `timeout_error` → `error_handler`
3. **Auth Error** → Set `auth_error` → `error_handler`
4. **Resource Error** (datasource unavailable) → `error_handler`

**Routing Logic**:
```python
if execution_status == "success":
    return "summarize"
elif attempt < 3 and error_type == "syntax":
    return "build_query"  # Retry with error
else:
    return "error_handler"
```

**Duration**: 500-10000ms (depends on query complexity)

---

### 6. `summarize` Node

**Purpose**: Format results into natural language + extract context

**Inputs**:
- `user_query`: str
- `raw_data`: dict

**Operations**:
1. Call LLM to format data
2. Parse response for natural language + context
3. Extract `shown_entities` from LLM output

**LLM Instructions**:
```
Format this data into a clear response.

CRITICAL: After your response, include:
---CONTEXT---
{
  "shown_entities": {
    "City": ["Houston", "Philadelphia", ...]
  }
}
```

**Outputs**:
- `final_answer`: str - Natural language response
- `shown_entities`: dict - Dimension values shown
- `current_thought`: "Generating response..."

**Duration**: 2000-5000ms

---

### 7. `error_handler` Node

**Purpose**: Generate helpful error message after max retries

**Inputs**:
- `user_query`: str
- `attempt`: int
- `validation_errors`: list (if exists)
- `execution_errors`: list (if exists)
- `schema_error`: str (if exists)
- `query_draft`: dict (last attempt)

**Operations**:
1. Summarize what was tried
2. Explain what went wrong
3. Suggest next steps for user
4. Log full error context

**Outputs**:
- `final_answer`: str - Error explanation
- `error_summary`: dict - Structured error info

**Example Output**:
```
I tried 3 times to build a query for your question but encountered errors:

Attempt 1: Invalid field name "Saless" (should be "Sales")
Attempt 2: Aggregation SUM required for measure field
Attempt 3: Filter value type mismatch

The dataset has these fields:
- Measures: Sales, Profit, Quantity
- Dimensions: City, Region, Category

Could you rephrase your question or clarify which fields you'd like to query?
```

**Duration**: 1000-2000ms

---

## State Management

### State Schema

```python
class VizQLGraphState(TypedDict):
    # Input
    user_query: str
    datasource_id: str
    site_id: str
    message_history: list
    api_key: str
    model: str
    
    # Schema
    schema: Optional[dict]
    metadata_stats: Optional[dict]
    
    # Query Building
    query_draft: Optional[dict]
    reasoning: Optional[str]
    
    # Validation
    validated_query: Optional[dict]
    validation_errors: Optional[list]
    validation_status: Optional[str]
    
    # Execution
    raw_data: Optional[dict]
    execution_errors: Optional[list]
    execution_status: Optional[str]
    
    # Summarization
    final_answer: Optional[str]
    shown_entities: Optional[dict]
    
    # Control Flow
    attempt: int  # 1, 2, or 3
    current_thought: Optional[str]
    
    # Error Handling
    schema_error: Optional[str]
    error_summary: Optional[dict]
```

---

## Edge Definitions

```python
def create_graph():
    graph = StateGraph(VizQLGraphState)
    
    # Add nodes
    graph.add_node("start", start_node)
    graph.add_node("get_schema", get_schema_node)
    graph.add_node("build_query", build_query_node)
    graph.add_node("validate_query", validate_query_node)
    graph.add_node("execute_query", execute_query_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("error_handler", error_handler_node)
    
    # Linear flow
    graph.set_entry_point("start")
    graph.add_edge("start", "get_schema")
    
    # Conditional from get_schema
    graph.add_conditional_edges(
        "get_schema",
        route_after_schema,
        {
            "build_query": "build_query",
            "error": "error_handler"
        }
    )
    
    graph.add_edge("build_query", "validate_query")
    
    # Conditional from validate_query
    graph.add_conditional_edges(
        "validate_query",
        route_after_validation,
        {
            "execute": "execute_query",
            "retry": "build_query",
            "error": "error_handler"
        }
    )
    
    # Conditional from execute_query
    graph.add_conditional_edges(
        "execute_query",
        route_after_execution,
        {
            "summarize": "summarize",
            "retry": "build_query",
            "error": "error_handler"
        }
    )
    
    # Terminal nodes
    graph.add_edge("summarize", END)
    graph.add_edge("error_handler", END)
    
    return graph.compile()
```

---

## Routing Functions

```python
def route_after_schema(state: VizQLGraphState) -> str:
    """Route after schema fetch."""
    if state.get("schema_error"):
        return "error"
    return "build_query"

def route_after_validation(state: VizQLGraphState) -> str:
    """Route after query validation."""
    if state["validation_status"] == "valid":
        return "execute"
    elif state["attempt"] < 3:
        return "retry"
    return "error"

def route_after_execution(state: VizQLGraphState) -> str:
    """Route after query execution."""
    if state["execution_status"] == "success":
        return "summarize"
    elif state["attempt"] < 3:
        return "retry"
    return "error"
```

---

## Migration Strategy

### Phase 1: Create New Graph (Parallel)
- Implement new node structure
- Keep existing tool-use agent running
- Add feature flag to switch between agents

### Phase 2: Testing & Validation
- Test new graph with existing queries
- Compare results with tool-use agent
- Validate retry logic works
- Ensure context extraction integrated

### Phase 3: Gradual Rollout
- Enable for internal testing
- Monitor error rates, latency
- Collect feedback
- Fix issues

### Phase 4: Full Migration
- Make new graph default
- Deprecate tool-use agent
- Remove old code

---

## Key Improvements Over Tool-Use Chain

| Aspect | Tool-Use Chain | Controlled Graph |
|--------|---------------|------------------|
| **Predictability** | LLM decides flow | Fixed flow with conditions |
| **Debugging** | Hard to trace | Clear node execution logs |
| **Retry Logic** | Ad-hoc | Explicit retry edges |
| **Validation** | LLM-based | Local, fast, reliable |
| **Error Handling** | Inconsistent | Centralized error_handler |
| **Performance** | Variable | Optimized node execution |
| **Monitoring** | Difficult | Per-node metrics |
| **Testing** | Complex | Test each node independently |

---

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| **P50 Latency** | < 4s | Simple queries |
| **P95 Latency** | < 8s | Complex queries |
| **P99 Latency** | < 12s | Retry scenarios |
| **Success Rate** | > 95% | Valid queries |
| **First-Try Success** | > 80% | No retries needed |
| **Schema Cache Hit** | > 90% | Repeated queries |

---

## Observability

### Logging

Each node logs:
- Entry timestamp
- Exit timestamp
- Duration
- Input state keys
- Output state keys
- Errors (if any)

### Metrics

Track:
- Node execution times
- Retry rates per node
- Error types and frequencies
- Success rates
- Cache hit rates

### Tracing

- Assign execution_id to each graph run
- Link all node executions to execution_id
- Enable distributed tracing

---

## Open Questions

1. **Schema Caching**: In-memory vs Redis vs database?
2. **Concurrent Queries**: How to handle multiple queries for same datasource?
3. **Query Optimization**: Should we add a query optimization node?
4. **Partial Results**: Return partial results if query timeout?
5. **Query History**: Store successful queries for re-use?

---

## Next Steps

1. Review and approve this design
2. Create feature flag for graph selection
3. Implement core graph structure (1-2 days)
4. Implement individual nodes (3-5 days)
5. Integration testing (2-3 days)
6. Performance testing (1-2 days)
7. Gradual rollout (1 week)

Total estimate: **2-3 weeks** for full migration
