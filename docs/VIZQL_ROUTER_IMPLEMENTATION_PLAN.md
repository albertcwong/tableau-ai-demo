# VizQL Agent Router Implementation Plan

## Problem Statement

The VizQL agent currently attempts to construct and execute VizQL queries for ALL user requests, even when:
1. **Schema-based questions** can be answered from enriched schema metadata (e.g., "how many customers do we have?")
2. **Result reformatting requests** only need to reformat previous results (e.g., "put the results in a table")

This leads to:
- Unnecessary VizQL query construction attempts
- Failed queries for non-queryable requests
- Slower response times
- Wasted compute resources

## Solution Overview

Add a **Router Node** at the beginning of the agent graph that classifies user requests and routes them appropriately:

```
User Query
    ↓
[Router/Classifier] ← Enriched Schema + Previous Results
    ↓
    ├─→ [Schema Query Handler] → Format Answer → END
    ├─→ [Result Reformatter] → Format Results → END
    └─→ [Planner] → Query Builder → ... (existing flow)
```

## Query Classification Types

### 1. Schema Queries (`schema_query`)
Questions answerable from schema metadata alone:

**Examples:**
- "How many customers do we have?" → Check Customer field cardinality
- "What's the min/max sales value?" → Check Sales field min/max
- "What regions are available?" → Check Region field sample_values
- "How many fields are in this dataset?" → Count schema fields
- "What measures are available?" → List measures from schema
- "What's the data type of the Price field?" → Check field dataType

**Schema Metadata Available:**
- `cardinality`: Distinct count of values
- `min/max`: Min and max values for numeric fields
- `sample_values`: Sample values for dimensions
- `null_percentage`: Percentage of null values
- `dataType`: Field data type
- `fieldRole`: MEASURE or DIMENSION
- `description`: Field description

### 2. Result Reformatting (`reformat_previous`)
Requests to reformat/reorganize previous query results:

**Examples:**
- "Put the results in a table"
- "Show that as a chart"
- "Format the output as JSON"
- "Summarize those results"
- "Show only the top 5"
- "Sort by sales descending"

**Requirements:**
- Previous query results must exist in state
- User is referring to "the results", "that", "those", etc.

### 3. New VizQL Query (`new_query`)
Requires constructing and executing a new VizQL query:

**Examples:**
- "Show me total sales by region"
- "Top 10 customers by revenue"
- "Average price per product"
- Any question requiring data aggregation or filtering

## Implementation Plan

### Phase 1: Create Router Node

**File:** `backend/app/services/agents/vizql/nodes/router.py`

```python
async def route_query_node(state: VizQLAgentState) -> Dict[str, Any]:
    """
    Classify user query and determine routing path.
    
    Returns state with:
    - query_type: "schema_query" | "reformat_previous" | "new_query"
    - routing_reason: Explanation for classification
    """
```

**Router Prompt:** `backend/app/prompts/agents/vizql/routing.txt`

```
## Task
Classify the user query into one of three types:

1. **schema_query**: Question answerable from schema metadata
   - Asks about field cardinality, min/max, data types, available fields
   - Keywords: "how many", "what fields", "what's the min/max", "what values"
   
2. **reformat_previous**: Request to reformat previous results
   - References previous results: "the results", "that", "those"
   - Asks for reformatting: "put in a table", "show as chart", "format as"
   - Only applies if previous results exist
   
3. **new_query**: Requires new VizQL query
   - Asks for data aggregation, filtering, grouping
   - Requires computing new values

## Available Context
- Enriched Schema: {{ schema_summary }}
- Previous Results Available: {{ has_previous_results }}

## Output Format
{
  "query_type": "schema_query|reformat_previous|new_query",
  "confidence": 0.0-1.0,
  "reasoning": "explanation",
  "schema_fields_referenced": ["field1", "field2"]  // if applicable
}
```

### Phase 2: Create Schema Query Handler Node

**File:** `backend/app/services/agents/vizql/nodes/schema_handler.py`

```python
async def handle_schema_query_node(state: VizQLAgentState) -> Dict[str, Any]:
    """
    Answer questions using enriched schema metadata.
    
    Looks up field statistics (cardinality, min/max, sample_values) 
    and generates natural language answer.
    """
```

**Schema Handler Prompt:** `backend/app/prompts/agents/vizql/schema_query_handler.txt`

```
## Task
Answer the user's question using ONLY the enriched schema metadata provided.

## User Question
{{ user_query }}

## Enriched Schema
{{ enriched_schema }}

## Examples

Q: "How many customers do we have?"
A: "Based on the schema, the Customer Name field has 793 distinct values, meaning there are 793 customers in the dataset."

Q: "What's the min and max sales value?"
A: "The Sales field has a minimum value of $0.44 and a maximum value of $22,638.48."

Q: "What regions are available?"
A: "The Region field has 4 distinct values: Central, East, South, and West."

## Guidelines
- Reference specific field statistics (cardinality, min/max, sample_values)
- Be precise with numbers
- Explain what the metadata means
- If metadata is unavailable, say so
```

### Phase 3: Create Result Reformatter Node

**File:** `backend/app/services/agents/vizql/nodes/reformatter.py`

```python
async def reformat_results_node(state: VizQLAgentState) -> Dict[str, Any]:
    """
    Reformat previous query results based on user request.
    
    Takes query_results from state and reformats according to user's request
    (table, chart, JSON, summary, filtered, sorted, etc.)
    """
```

**Reformatter Prompt:** `backend/app/prompts/agents/vizql/result_reformatter.txt`

```
## Task
Reformat the previous query results according to the user's request.

## User Request
{{ user_query }}

## Previous Query Results
{{ previous_results }}

## Available Formats
- **Table**: Formatted text table
- **Summary**: Key insights and highlights
- **List**: Numbered or bulleted list
- **Top N**: Show only top N results
- **Sorted**: Re-sort by specified field

## Examples

User: "Put the results in a table"
→ Format as markdown table with aligned columns

User: "Show only the top 5"
→ Take first 5 rows from results

User: "Summarize those results"
→ Generate natural language summary with key insights
```

### Phase 4: Update State

**File:** `backend/app/services/agents/vizql/state.py`

```python
class VizQLAgentState(BaseAgentState):
    # ... existing fields ...
    
    # Routing
    query_type: Optional[str]  # "schema_query" | "reformat_previous" | "new_query"
    routing_reason: Optional[str]  # Explanation for routing decision
    
    # Schema query handling
    schema_answer: Optional[str]  # Answer from schema metadata
    
    # Result reformatting
    previous_results: Optional[dict]  # Store previous query results for reformatting
```

### Phase 5: Update Graph Flow

**File:** `backend/app/services/agents/vizql/graph.py`

```python
def create_vizql_graph() -> StateGraph:
    workflow = StateGraph(VizQLAgentState)
    
    # Add nodes
    workflow.add_node("router", route_query_node)  # NEW
    workflow.add_node("schema_handler", handle_schema_query_node)  # NEW
    workflow.add_node("reformatter", reformat_results_node)  # NEW
    workflow.add_node("planner", plan_query_node)
    # ... rest of existing nodes ...
    
    # Set entry point to router
    workflow.set_entry_point("router")  # CHANGED
    
    # Conditional routing from router
    def route_from_router(state: VizQLAgentState) -> str:
        query_type = state.get("query_type")
        if query_type == "schema_query":
            return "schema_handler"
        elif query_type == "reformat_previous":
            return "reformatter"
        else:
            return "planner"
    
    workflow.add_conditional_edges(
        "router",
        route_from_router,
        {
            "schema_handler": "schema_handler",
            "reformatter": "reformatter",
            "planner": "planner"
        }
    )
    
    # Schema handler and reformatter go directly to END
    workflow.add_edge("schema_handler", END)
    workflow.add_edge("reformatter", END)
    
    # Existing flow: planner -> schema_fetch -> ...
    workflow.add_edge("planner", "schema_fetch")
    # ... rest of existing edges ...
```

### Phase 6: Persist Previous Results

Currently, when a query completes successfully, we need to store the results in state so they can be accessed for reformatting.

**Update:** `backend/app/services/agents/vizql/nodes/formatter.py`

```python
async def format_results_node(state: VizQLAgentState) -> Dict[str, Any]:
    # ... existing formatting logic ...
    
    return {
        **state,
        "formatted_response": final_answer,
        "final_answer": final_answer,
        "previous_results": results,  # NEW: Store for potential reformatting
        "current_thought": None
    }
```

## Benefits

1. **Faster responses** for schema queries (no VizQL query construction/execution)
2. **Better UX** for reformatting requests (no failed query attempts)
3. **Resource efficiency** (fewer unnecessary VizQL queries)
4. **Clearer intent handling** (explicit classification of request types)

## Example Flows

### Schema Query Flow
```
User: "How many customers do we have?"
  ↓
Router: "schema_query" (references Customer field cardinality)
  ↓
Schema Handler: Look up Customer field → cardinality: 793
  ↓
Format Answer: "There are 793 customers in the dataset."
  ↓
END
```

### Reformat Flow
```
User: "Top 3 cities by sales"
  ↓
Router: "new_query"
  ↓
Planner → Query Builder → Execute → Format
  ↓
Results: [{"City": "New York", "Sales": 256000}, ...]
  ↓
Store previous_results
  ↓
END

User: "Put those results in a table"
  ↓
Router: "reformat_previous" (references "those results")
  ↓
Reformatter: Take previous_results, format as table
  ↓
Output markdown table
  ↓
END
```

### New Query Flow
```
User: "Show me total sales by region"
  ↓
Router: "new_query" (requires aggregation)
  ↓
Planner → Query Builder → Execute → Format (existing flow)
  ↓
END
```

## Testing Strategy

1. **Schema queries**:
   - "How many products are there?"
   - "What's the max order value?"
   - "List all categories"

2. **Reformat queries**:
   - Execute query → "Put the results in a table"
   - Execute query → "Show only top 5"
   - Execute query → "Summarize those results"

3. **Edge cases**:
   - Reformat without previous results → Should fall back to error
   - Ambiguous query → Router confidence score

## Implementation Order

1. Create router prompt and node
2. Create schema handler prompt and node
3. Create reformatter prompt and node
4. Update state definition
5. Update graph flow
6. Add tests
7. Update documentation
