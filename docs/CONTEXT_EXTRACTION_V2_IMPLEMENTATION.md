# Context Extraction V2 - Implementation Complete

## Problem Solved

**V1 Issue**: Extracted dimension values from raw query results (4,703 rows), but summarizer only showed top 10. Follow-up queries failed because context contained all 4,703 cities instead of the 10 shown.

**V2 Solution**: Extract dimension values from what the summarizer actually shows, not from raw data.

## How It Works

### Flow Diagram

```
User: "show me top cities by profit"
    ↓
get_data → Returns 4,703 rows (all cities)
    ↓
summarize → 
    Formats to show top 10
    Outputs response with ---CONTEXT--- marker:
    
    "Here are the top 10 cities...
    
    ---CONTEXT---
    {
      "shown_entities": {
        "City": ["Houston", "Philadelphia", "Seattle", ...]  ← Only 10
      }
    }"
    ↓
Parse response → Extract shown_entities
    ↓
Store dimension_values = {"City": ["Houston", ...]}  ← Only the 10 shown
    ↓
User: "show me customers in those cities"
    ↓
Agent sees structured context with 10 cities (not 4,703)
    ↓
Success! ✅
```

### Priority Order

The extraction logic follows this priority:

1. **PRIORITY 1**: Use `shown_entities` from summarizer (most accurate)
   - Summarizer knows exactly what it showed
   - Handles top N, filtered results, samples correctly
   
2. **PRIORITY 2**: Extract from `raw_data` only if < 100 rows
   - Fallback for queries that skip summarizer
   - Safe threshold prevents 4,703 city problem
   
3. **PRIORITY 3**: No structured context
   - If dataset is large (≥ 100 rows) and no summarizer
   - Prevents storing massive dimension lists

## Files Changed

### 1. Summarizer Prompt (`summarize.txt`)
**Added**: Instructions to output structured context

```
After your natural language response:

---CONTEXT---
{
  "shown_entities": {
    "City": ["Houston", "Philadelphia", ...]
  }
}
```

### 2. Summarizer Node (`summarize.py`)
**Added**: Parse response to extract `shown_entities`

```python
if "---CONTEXT---" in full_response:
    parts = full_response.split("---CONTEXT---")
    final_answer = parts[0].strip()
    # Parse JSON to get shown_entities
    shown_entities = context_json.get("shown_entities", {})

return {
    "final_answer": final_answer,
    "shown_entities": shown_entities  # Add to state
}
```

### 3. Chat API (`chat.py`)
**Modified**: 4 locations (streaming + non-streaming paths)

- Check for `shown_entities` in state first
- Fallback to extracting from raw_data only if < 100 rows
- Store dimension_values in `extra_metadata`

## Testing

### Test Case 1: Top N Query
```
1. Ask: "show me top 10 cities by profit"
2. Check logs: Should show "Using shown_entities from summarizer: 1 dimensions"
3. Verify: dimension_values should have exactly 10 cities
4. Ask: "show me customers in those cities"  
5. Verify: Query filters by only those 10 cities
```

### Test Case 2: Large Dataset
```
1. Query returns 4,703 rows
2. Summarizer shows top 10
3. Check logs: "Using shown_entities from summarizer"
4. Verify: Context has 10 cities, not 4,703
```

### Test Case 3: Small Dataset
```
1. Query returns 5 rows
2. No summarizer (direct data)
3. Check logs: "Fallback: Extracted from raw_data (small dataset): 5 rows"
4. Verify: Context has all 5 values
```

### Test Case 4: Metadata Query
```
1. Query: "how many customers?"
2. Response: "1,234 customers"
3. No dimensions shown
4. Verify: shown_entities = {}
```

## Benefits

✅ **Accurate** - Uses what was actually shown, not raw data
✅ **Reliable** - LLM explicitly tells us what it showed
✅ **Safe** - 100-row threshold prevents large dataset problems
✅ **Flexible** - Works for top N, filtered, sampled results
✅ **Backward Compatible** - Fallback handles queries without summarizer

## Migration Notes

- V1 code removed from raw_data extraction paths
- All extraction now follows priority order
- Logs clearly indicate which extraction method was used
- No breaking changes to API or database schema

## Monitoring

Watch for these log messages:

**Success cases**:
- `"Using shown_entities from summarizer: N dimensions"` ← Best case
- `"Fallback: Extracted from raw_data (small dataset): N rows"` ← Acceptable

**Warning cases**:
- `"Skipping extraction: dataset too large (N rows)"` ← Expected for large datasets
- `"Failed to parse shown_entities context"` ← LLM didn't follow format

## Future Enhancements

1. **Validate shown_entities** - Cross-check with raw_data to ensure accuracy
2. **Structured output API** - Use native JSON mode for guaranteed format
3. **Multi-level context** - Track nested dimensions (Region > City > Store)
4. **Temporal context** - Remember date ranges across queries
