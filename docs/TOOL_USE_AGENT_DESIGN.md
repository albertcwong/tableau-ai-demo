# Tool-Use Agent Architecture

## Problem with Current Approach

1. **Brittle Routing:** Rule-based patterns require constant maintenance
2. **Complex Graph:** Multiple nodes with conditional routing logic
3. **Limited Flexibility:** Agent can't adapt to novel query patterns
4. **Over-Engineering:** Separate nodes for planning, validation, refinement, etc.

## Proposed Architecture

### Simple 2-Step Flow

```
User Query → [Step 1: Get Data] → [Step 2: Summarize Data] → Response
```

**Step 1: Get Data**
- LLM has access to tools
- Decides which tools to use based on query and context
- Can use schema metadata, build queries, or reference message history
- Returns raw data

**Step 2: Summarize Data**
- Takes data from Step 1
- Formats it into natural language response
- Handles presentation logic

## Tool Design

### Available Tools for Step 1

#### 1. `get_datasource_metadata`
Retrieve enriched schema with statistics.

**When to use:**
- Query asks "how many [field]?" (check cardinality)
- Query asks "min/max [field]?" (check statistics)
- Query asks "what fields are available?"
- Need to understand available data before building query

**Returns:**
```python
{
    "fields": [...],
    "measures": [...],
    "dimensions": [...],
    "statistics": {
        "field_name": {
            "cardinality": 123,
            "min": 0,
            "max": 1000,
            "sample_values": [...]
        }
    }
}
```

**Example use cases:**
- "how many customers?" → Use cardinality from metadata
- "what's the min sales?" → Use min from metadata
- "what fields can I query?" → List fields from metadata

#### 2. `build_query`
Construct a VizQL query JSON.

**When to use:**
- Need to aggregate data (sum, average, count)
- Need to group by dimensions
- Need to filter or apply Top N
- Need calculations or bins

**Parameters:**
```python
{
    "measures": ["field_name"],
    "dimensions": ["field_name"],
    "filters": [...],
    "topN": {...},
    "calculations": [...],
    "bins": [...]
}
```

**Returns:**
```python
{
    "query": {...},  # VizQL JSON
    "is_valid": True
}
```

**Example use cases:**
- "total sales by region" → Build query with SUM(Sales) grouped by Region
- "top 10 customers by revenue" → Build query with TOP filter
- "average price per category" → Build query with AVG aggregation

#### 3. `validate_query`
Validate a VizQL query before execution.

**When to use:**
- After building a query
- To check for errors before execution

**Parameters:**
```python
{
    "query": {...}  # VizQL JSON
}
```

**Returns:**
```python
{
    "is_valid": True,
    "errors": [],
    "warnings": []
}
```

#### 4. `query_datasource`
Execute a VizQL query and return results.

**When to use:**
- After building and validating a query
- When data aggregation/filtering is needed

**Parameters:**
```python
{
    "query": {...}  # VizQL JSON
}
```

**Returns:**
```python
{
    "columns": ["Region", "SUM(Sales)"],
    "data": [
        ["East", 12345],
        ["West", 23456],
        ...
    ],
    "row_count": 10
}
```

#### 5. `get_previous_results`
Retrieve results from previous query in conversation.

**When to use:**
- User asks to reformat previous results
- User references "the results", "that data", etc.

**Returns:**
```python
{
    "columns": [...],
    "data": [...],
    "original_query": "..."
}
```

**Example use cases:**
- "put the results in a table" → Get previous results and reformat
- "show only top 5 from that" → Get previous results and filter

## Implementation

### Step 1: Get Data Agent

```python
class GetDataAgent:
    """
    Agent that uses tools to retrieve data based on user query.
    """
    
    tools = [
        get_datasource_metadata,
        build_query,
        validate_query,
        query_datasource,
        get_previous_results
    ]
    
    system_prompt = """
You are a data retrieval agent. Your job is to get the data needed to answer the user's question.

You have access to these tools:
1. get_datasource_metadata - Get schema with statistics (cardinality, min/max, sample values)
2. build_query - Construct a VizQL query for aggregation/filtering
3. validate_query - Check if a query is valid
4. query_datasource - Execute a query and get results
5. get_previous_results - Get data from previous query in conversation

IMPORTANT DECISION RULES:

1. Simple metadata questions → Use get_datasource_metadata ONLY
   - "how many customers?" → Check cardinality in metadata
   - "what's the min/max sales?" → Check statistics in metadata
   - "what fields are available?" → List fields from metadata

2. Data aggregation/filtering → Build and execute query
   - "total sales by region" → build_query + validate_query + query_datasource
   - "top 10 customers" → build_query (with TOP filter) + query_datasource
   - "average price per category" → build_query + query_datasource

3. Reformatting previous results → Get previous data
   - "put the results in a table" → get_previous_results
   - "show that as a chart" → get_previous_results
   - "summarize those results" → get_previous_results

WORKFLOW:
1. Analyze user query and message history
2. Decide which approach to use (metadata, query, or previous results)
3. Use appropriate tools to get data
4. Return data in structured format

Your output should be the raw data needed to answer the question.
DO NOT format or summarize the data - that happens in the next step.
"""
    
    async def run(self, user_query: str, message_history: List[Dict]) -> Dict[str, Any]:
        """
        Use tools to get data for user query.
        
        Returns:
            {
                "data_type": "metadata" | "query_results" | "previous_results",
                "data": {...},
                "source": "tool or reasoning used"
            }
        """
        # Call LLM with tools
        response = await call_llm_with_tools(
            system_prompt=self.system_prompt,
            user_query=user_query,
            message_history=message_history,
            tools=self.tools
        )
        
        return response
```

### Step 2: Summarize Data Agent

```python
class SummarizeDataAgent:
    """
    Agent that formats data into natural language response.
    """
    
    system_prompt = """
You are a data presentation agent. Your job is to take raw data and present it in a clear, natural language format.

The data you receive may be:
1. Metadata (field information, statistics)
2. Query results (rows and columns)
3. Previous results being reformatted

Your task:
1. Analyze the data structure
2. Format it appropriately for the user's question
3. Provide clear, concise summary

Guidelines:
- Use tables for structured data
- Use bullet points for lists
- Highlight key insights
- Answer the specific question asked
- Be concise but complete
"""
    
    async def run(self, user_query: str, data: Dict[str, Any]) -> str:
        """
        Format data into natural language response.
        
        Returns:
            Natural language response string
        """
        response = await call_llm(
            system_prompt=self.system_prompt,
            user_query=user_query,
            data=data
        )
        
        return response
```

### Main Agent Graph

```python
from langgraph.graph import StateGraph, END

class VizQLAgentState(TypedDict):
    user_query: str
    message_history: List[Dict]
    raw_data: Optional[Dict[str, Any]]
    final_answer: Optional[str]
    error: Optional[str]

def create_vizql_agent():
    """Create simplified 2-step agent."""
    
    workflow = StateGraph(VizQLAgentState)
    
    # Step 1: Get data using tools
    workflow.add_node("get_data", get_data_node)
    
    # Step 2: Summarize data
    workflow.add_node("summarize", summarize_node)
    
    # Linear flow
    workflow.set_entry_point("get_data")
    workflow.add_edge("get_data", "summarize")
    workflow.add_edge("summarize", END)
    
    return workflow.compile()

async def get_data_node(state: VizQLAgentState) -> Dict[str, Any]:
    """Use tools to get data."""
    agent = GetDataAgent()
    data = await agent.run(
        user_query=state["user_query"],
        message_history=state["message_history"]
    )
    
    return {
        **state,
        "raw_data": data
    }

async def summarize_node(state: VizQLAgentState) -> Dict[str, Any]:
    """Format data into response."""
    agent = SummarizeDataAgent()
    answer = await agent.run(
        user_query=state["user_query"],
        data=state["raw_data"]
    )
    
    return {
        **state,
        "final_answer": answer
    }
```

## Tool Function Implementations

### get_datasource_metadata Tool

```python
async def get_datasource_metadata_tool(
    include_statistics: bool = True
) -> Dict[str, Any]:
    """
    Get datasource schema with optional statistics.
    
    Args:
        include_statistics: Whether to include cardinality, min/max, sample values
    
    Returns:
        Enriched schema dictionary
    """
    # Use existing schema enrichment service
    from app.services.schema_enrichment import get_enriched_schema
    
    schema = await get_enriched_schema(
        include_statistics=include_statistics
    )
    
    return schema
```

### build_query Tool

```python
async def build_query_tool(
    measures: List[str],
    dimensions: List[str] = None,
    filters: List[Dict] = None,
    topN: Dict = None,
    calculations: List[Dict] = None,
    bins: List[Dict] = None
) -> Dict[str, Any]:
    """
    Build a VizQL query JSON.
    
    Uses existing query construction logic with semantic rules.
    """
    from app.services.agents.vizql.query_builder import build_vizql_query
    
    query = await build_vizql_query(
        measures=measures,
        dimensions=dimensions,
        filters=filters,
        topN=topN,
        calculations=calculations,
        bins=bins
    )
    
    return {
        "query": query,
        "is_valid": True  # Basic validation
    }
```

### validate_query Tool

```python
async def validate_query_tool(query: Dict) -> Dict[str, Any]:
    """
    Validate a VizQL query.
    """
    from app.services.agents.vizql.validator import validate_query
    
    validation_result = await validate_query(query)
    
    return validation_result
```

### query_datasource Tool

```python
async def query_datasource_tool(query: Dict) -> Dict[str, Any]:
    """
    Execute VizQL query and return results.
    """
    from app.services.vizql.client import execute_query
    
    results = await execute_query(query)
    
    return {
        "columns": results.get("columns", []),
        "data": results.get("data", []),
        "row_count": len(results.get("data", []))
    }
```

### get_previous_results Tool

```python
async def get_previous_results_tool(
    message_history: List[Dict]
) -> Optional[Dict[str, Any]]:
    """
    Get results from previous query in conversation.
    """
    # Find last assistant message with query results
    for msg in reversed(message_history):
        if msg.get("role") == "assistant" and "data" in msg:
            return {
                "columns": msg["data"].get("columns", []),
                "data": msg["data"].get("data", []),
                "original_query": msg.get("query", "")
            }
    
    return None
```

## Advantages

### 1. Simplicity
- 2 nodes instead of 8+ nodes
- Linear flow instead of complex conditional routing
- Clear separation of concerns

### 2. Flexibility
- LLM decides how to get data
- Can adapt to novel query patterns
- No pattern maintenance required

### 3. Maintainability
- Tool functions are modular
- Easy to add new tools
- Clear tool documentation

### 4. Reliability
- LLM reasoning instead of brittle rules
- Can handle ambiguous queries
- Self-correcting via tool use

### 5. Performance
- Can skip unnecessary steps (no forced validation if not needed)
- Parallel tool calls possible
- Caching at tool level

## Migration Strategy

1. **Phase 1:** Implement new tool-use agent alongside existing agent
2. **Phase 2:** A/B test both approaches
3. **Phase 3:** Migrate all traffic to tool-use agent
4. **Phase 4:** Deprecate old graph-based agent

## Example Flows

### Example 1: Metadata Query
```
User: "how many customers do we have?"

Step 1 (Get Data):
  - LLM decides: This is answerable from metadata
  - Calls: get_datasource_metadata(include_statistics=True)
  - Returns: {"statistics": {"Customer Name": {"cardinality": 1234}}}

Step 2 (Summarize):
  - LLM formats: "We have 1,234 customers in the dataset."
```

### Example 2: Aggregation Query
```
User: "show me total sales by region"

Step 1 (Get Data):
  - LLM decides: Needs data aggregation
  - Calls: build_query(measures=["Sales"], dimensions=["Region"])
  - Calls: validate_query(query)
  - Calls: query_datasource(query)
  - Returns: {"columns": ["Region", "SUM(Sales)"], "data": [...]}

Step 2 (Summarize):
  - LLM formats: "Here are the total sales by region: [table]"
```

### Example 3: Reformat Previous
```
User: "put the results in a table"

Step 1 (Get Data):
  - LLM decides: Referring to previous results
  - Calls: get_previous_results(message_history)
  - Returns: Previous query results

Step 2 (Summarize):
  - LLM formats: Data in markdown table format
```

### Example 4: Complex Multi-Tool Query
```
User: "what's the average sales for customers in the top 3 regions?"

Step 1 (Get Data):
  - LLM decides: Need to first find top 3 regions, then calculate average
  - Calls: build_query(measures=["Sales"], dimensions=["Region"], topN={"n": 3})
  - Calls: query_datasource(query1) → Get top 3 regions
  - Calls: build_query(measures=["Sales"], filters=[regions from query1], aggregation="AVG")
  - Calls: query_datasource(query2)
  - Returns: Average sales value

Step 2 (Summarize):
  - LLM formats: "The average sales for customers in the top 3 regions is $X"
```

## Configuration

```python
# config.py
VIZQL_AGENT_TYPE = "tool_use"  # or "graph_based" for old approach

TOOL_USE_CONFIG = {
    "max_tool_calls": 10,  # Prevent infinite loops
    "timeout_seconds": 30,
    "enable_parallel_tools": True,
    "cache_metadata": True,
    "cache_ttl_seconds": 300
}
```

## Monitoring

Track metrics:
- Tool usage frequency
- Tool call sequences
- Success/failure rates
- Latency per tool
- Total query time

```python
# Example metrics
{
    "query_id": "...",
    "tool_calls": [
        {"tool": "get_datasource_metadata", "duration_ms": 50, "success": True},
        {"tool": "build_query", "duration_ms": 200, "success": True},
        {"tool": "query_datasource", "duration_ms": 1500, "success": True}
    ],
    "total_duration_ms": 1750,
    "final_status": "success"
}
```
