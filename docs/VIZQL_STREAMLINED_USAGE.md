# How to Switch to the Streamlined VizQL Agent

## Quick Start

### Option 1: Environment Variable (Recommended)

Set the `VIZQL_AGENT_TYPE` environment variable in your `.env` file:

```bash
VIZQL_AGENT_TYPE=streamlined
```

Then restart your backend server:

```bash
# If using uvicorn directly
uvicorn app.main:app --reload --port 8000

# Or if using docker-compose
docker-compose restart backend
```

### Option 2: Update .env File

Edit `backend/.env` or `.env` in the project root:

```env
# Change this line:
VIZQL_AGENT_TYPE=graph_based

# To:
VIZQL_AGENT_TYPE=streamlined
```

## Available Agent Types

The `VIZQL_AGENT_TYPE` setting supports these values:

- **`streamlined`** - New streamlined agent (4 nodes, tool-enabled query builder)
- **`graph_based`** - Original graph-based agent (7+ nodes)
- **`tool_use`** - Tool-use agent (2-step)
- **`controlled`** - Controlled graph agent (7 nodes with explicit routing)

## Verification

After switching, you can verify the agent is being used by:

1. **Check logs** - Look for initialization messages:
   ```
   Initializing streamlined graph state with model: gpt-4
   ```

2. **Check API response** - The streamlined agent includes `reasoning_steps` in the response

3. **Monitor performance** - Streamlined agent should show:
   - Faster response times (20-30% improvement expected)
   - Lower token usage
   - Query reuse in multi-turn conversations

## Programmatic Usage

If you're calling the agent programmatically:

```python
from app.services.agents.graph_factory import AgentGraphFactory

# Create streamlined agent
graph = AgentGraphFactory.create_vizql_graph(use_streamlined=True)

# Use with state
state = {
    "user_query": "Show me top 10 cities by profit",
    "context_datasources": ["datasource_id"],
    "messages": [],  # Conversation history
    "api_key": "...",
    "model": "gpt-4",
    "attempt": 1,
    "query_version": 0,
    "reasoning_steps": [],
}

result = await graph.ainvoke(state)
```

## State Initialization

The streamlined agent expects this state structure:

```python
{
    # Base fields (from BaseAgentState)
    "user_query": str,
    "agent_type": "vizql",
    "context_datasources": List[str],
    "context_views": List[str],
    "messages": List[Dict],  # Conversation history
    "api_key": str,
    "model": str,
    
    # Streamlined-specific fields
    "attempt": int,  # Default: 1
    "query_version": int,  # Default: 0
    "reasoning_steps": List[Dict],  # Default: []
    "enriched_schema": Optional[Dict],  # Optional pre-fetched schema
    "schema": Optional[Dict],  # Will be fetched if needed
}
```

## Features Enabled

When using the streamlined agent, you get:

✅ **Query Reuse** - Reuses queries from conversation history when similar  
✅ **Smart Schema Fetching** - Only fetches schema when needed  
✅ **Tool-Enabled Query Builder** - Makes intelligent decisions  
✅ **Reasoning Capture** - All steps captured in `reasoning_steps`  
✅ **Simplified Flow** - 4 nodes instead of 7  

## Troubleshooting

### Agent Not Switching

1. **Check .env file location** - Make sure you're editing the correct `.env` file
2. **Restart server** - Changes require a server restart
3. **Check logs** - Look for errors during graph initialization

### State Errors

If you see state-related errors:

1. **Ensure all required fields** - Check that `context_datasources` is not empty
2. **Check message history format** - Should be list of dicts with `role` and `content`
3. **Verify API key** - Must be present in state

### Performance Issues

If performance doesn't improve:

1. **Check schema caching** - Schema should be cached after first fetch
2. **Monitor tool calls** - Check logs for tool usage patterns
3. **Compare metrics** - Use comparison tests to verify improvements

## Rollback

To switch back to the original agent:

```bash
VIZQL_AGENT_TYPE=graph_based
```

Or use any other supported agent type.
