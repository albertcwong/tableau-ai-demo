# Tool-Use Agent Debugging Guide

## Issue: "I wasn't able to retrieve the data needed to answer your question."

This error occurs when `raw_data` is `None` after the `get_data_node` completes.

## Debugging Steps

### 1. Check Logs

Look for these log messages in the backend logs:

```
Get data node: user_query='...'
Available functions: [...]
LLM response - has function_call: True/False, content: ...
Executing tool: ...
Tool ... returned result type: ..., keys: ...
Get data node complete: X tool calls made, raw_data is present/None
```

### 2. Common Issues

#### Issue A: LLM Not Calling Functions

**Symptoms:**
- Log shows `has function_call: False`
- No tool calls made
- LLM returns text response instead

**Possible Causes:**
1. Model doesn't support function calling (e.g., some older models)
2. Function definitions format incorrect
3. Gateway not configured for function calling

**Solutions:**
1. Use a model that supports function calling (gpt-4, gpt-3.5-turbo, claude-3-opus, etc.)
2. Check function definitions format matches OpenAI format
3. Verify gateway supports function calling

#### Issue B: Tool Execution Failing

**Symptoms:**
- Tool calls made but `raw_data` is None
- Log shows tool execution errors

**Check:**
- `datasource_id` is set correctly
- `site_id` is set correctly
- Tableau client is initialized
- Schema service can connect to Tableau

#### Issue C: Function Arguments Parsing Error

**Symptoms:**
- Log shows "Failed to parse function arguments"
- Tool calls made but with empty arguments

**Solution:**
- Check function parameter definitions match what LLM is sending
- Verify JSON parsing logic

### 3. Fallback Behavior

The agent now has a fallback that:
- Detects queries matching metadata patterns ("how many", "min/max", etc.)
- Automatically calls `get_datasource_metadata` if LLM doesn't call functions
- Logs fallback attempts

### 4. Manual Testing

Test with a simple query:
```bash
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "content": "how many customers do we have?",
    "agent_type": "vizql",
    "datasource_ids": ["your-datasource-id"],
    "model": "gpt-4"
  }'
```

### 5. Verify Configuration

Check `.env` or environment:
```bash
VIZQL_AGENT_TYPE=tool_use
TABLEAU_SITE_ID=your-site-id
```

### 6. Check Model Support

Not all models support function calling. Use:
- ✅ gpt-4, gpt-4-turbo, gpt-3.5-turbo
- ✅ claude-3-opus, claude-3-sonnet
- ✅ gemini-pro (if gateway supports)
- ❌ Some older models may not support

### 7. Enable Debug Logging

Set log level to DEBUG:
```python
import logging
logging.getLogger("app.services.agents.vizql_tool_use").setLevel(logging.DEBUG)
```

## Expected Flow

1. **Get Data Node:**
   - Receives user query
   - Calls LLM with function definitions
   - LLM decides which tool to call
   - Tool executes and returns data
   - `raw_data` is set

2. **Summarize Node:**
   - Receives `raw_data`
   - Formats into natural language
   - Returns `final_answer`

## Troubleshooting Checklist

- [ ] Model supports function calling
- [ ] `datasource_id` is set in state
- [ ] `site_id` is set in state
- [ ] Tableau client initialized correctly
- [ ] Function definitions format is correct
- [ ] Gateway supports function calling
- [ ] Logs show tool calls being made
- [ ] Tool execution succeeds (no errors)
- [ ] `raw_data` is set before summarize node

## Next Steps

If issue persists:
1. Check full error logs
2. Verify model supports function calling
3. Test with graph-based agent as comparison
4. Check gateway function calling support
5. Verify Tableau connection works
