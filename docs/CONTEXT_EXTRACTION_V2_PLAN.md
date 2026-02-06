# Context Extraction V2: Post-Summarization Extraction

## Problem with V1

V1 extracted dimension values from `raw_data` (4,703 rows), but the summarizer only shows top 10.
Result: Context contains all 4,703 cities instead of the 10 actually shown to user.

**Root Cause**: Extraction happens BEFORE summarization, not after.

## V2 Solution: LLM-Assisted Context Extraction

Have the summarizer explicitly tell us which entities it included in the response.

### Architecture

```
User: "show me top cities by profit"
    ↓
get_data → Returns 4,703 rows (all cities)
    ↓
summarize → 
    Input: 4,703 rows
    Output: {
        "response": "Here are the top 10 cities...",
        "shown_entities": {
            "City": ["Houston", "Philadelphia", "Seattle", ...]  ← Only the 10 shown
        }
    }
    ↓
Extract dimension_values from shown_entities (not raw_data)
    ↓
Store: dimension_values = {"City": ["Houston", "Philadelphia", ...]}  ← Only 10
```

### Implementation Steps

**Step 1: Update Summarizer Prompt**

Add instruction to return structured JSON:

```
Format the data into a natural language response.

IMPORTANT: After your response, on a new line, output a JSON block with the dimension values you included:

```json
{
  "shown_entities": {
    "City": ["Houston", "Philadelphia", "Seattle"],
    "Region": ["West", "East"]
  }
}
```

Only include dimensions that appear in your response. If you showed top 10 cities, list those 10 cities only.
```

**Step 2: Parse LLM Response**

Update `summarize_node` to:
1. Parse the response to extract both natural language and JSON
2. Return `shown_entities` in state

**Step 3: Update Extraction Logic**

Update `chat.py` to:
1. Check if `last_state` has `shown_entities` → use those (highest priority)
2. Else fallback to extracting from `raw_data` only if small (<100 rows)
3. Else no structured context

### Why This Works

✅ **Accurate** - LLM knows exactly what it showed
✅ **Reliable** - No NLP parsing of natural language
✅ **Flexible** - Works for any query type (top N, filtered, etc.)
✅ **Simple** - Single source of truth

### Alternative: Structured Output API

For models that support it (GPT-4, Claude), use native structured output:

```python
response = await ai_client.chat(
    model=model,
    messages=messages,
    response_format={
        "type": "json_schema",
        "schema": {
            "response": "string",
            "shown_entities": "object"
        }
    }
)
```

### Fallback Strategy

If LLM doesn't provide `shown_entities`:
1. Check raw_data row count
2. If ≤ 100 rows → extract from raw_data (acceptable)
3. If > 100 rows → no structured context (too many values)

This prevents the 4,703 city problem while still supporting small result sets.

## Implementation Comparison

**V1 (Current - Broken)**:
- Extract from raw_data (4,703 rows) ❌
- User sees 10, context has 4,703 ❌

**V2 (Proposed - Fixed)**:
- Extract from summarizer's shown_entities (10 cities) ✅
- User sees 10, context has 10 ✅
- Fallback: Only extract from raw_data if <100 rows ✅

## Migration Path

1. Implement V2 alongside V1
2. Test with various query types
3. Once validated, remove V1 extraction from raw_data
4. Keep fallback for queries that skip summarizer
