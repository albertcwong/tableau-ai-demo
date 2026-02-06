# Context Extraction Solution for Follow-up Queries

## Problem

The VizQL agent was failing to use message history for follow-up queries. When a user asked:
1. "show me top 5 cities by profit" → Returns Houston, Philadelphia, Seattle, Dallas, Austin
2. "show me top 3 customers in each of those cities" → Agent didn't understand "those cities"

**Root cause**: We were asking the LLM to parse natural language responses to extract structured data (city names). This is unreliable even with extensive prompting.

## Solution Architecture

### 1. Structured Context Extraction (`context_extractor.py`)

Extract dimension values from query results and store them in a structured format:

```python
{
  "query_results": {
    "columns": ["City", "SUM(Profit)"],
    "row_count": 5,
    "dimension_values": {
      "City": ["Houston", "Philadelphia", "Seattle", "Dallas", "Austin"]
    }
  }
}
```

**Key function**: `extract_dimension_values()`
- Identifies dimension columns (non-aggregated fields)
- Extracts unique values for each dimension
- Limits to 50 values per dimension to prevent context overload
- Stores in `extra_metadata` when saving messages

### 2. Message History Enhancement (`chat.py`)

When saving messages:
- Extract dimension values from query results
- Store in `extra_metadata.query_results.dimension_values`
- Pass to agent state in structured format

When loading message history:
- Include dimension values in `data_metadata`
- Format them clearly for LLM consumption

### 3. LLM Context Formatting (`get_data.py`)

Append structured context to assistant messages:

```
Here are the top 5 cities by profit...
(natural language response)

[Context from previous query]
  - City: Houston, Philadelphia, Seattle, Dallas, Austin
```

This gives the LLM clear, structured data to reference.

### 4. Simplified Prompts

**Old approach** (unreliable):
- "Read the previous message and extract cities from the natural language"
- Required LLM to parse unstructured text
- Error-prone with different response formats

**New approach** (reliable):
- "Look for [Context from previous query] section"
- Use the exact values listed there
- Simple, clear, works every time

## Benefits

1. **Reliable** - No natural language parsing required
2. **Scalable** - Works for any dimension (cities, products, regions, dates, etc.)
3. **Clear** - LLM sees exactly what values to use
4. **Efficient** - Only stores up to 50 values per dimension
5. **General** - Not hard-coded for specific datasets

## Example Flow

### Query 1: "top 5 cities by profit"

1. Agent executes query, gets results:
   ```json
   {
     "columns": ["City", "SUM(Profit)"],
     "data": [
       ["Houston", 50000],
       ["Philadelphia", 45000],
       ["Seattle", 40000],
       ["Dallas", 35000],
       ["Austin", 30000]
     ]
   }
   ```

2. `extract_dimension_values()` extracts:
   ```json
   {
     "City": ["Houston", "Philadelphia", "Seattle", "Dallas", "Austin"]
   }
   ```

3. Saved in database as:
   ```json
   {
     "extra_metadata": {
       "query_results": {
         "columns": ["City", "SUM(Profit)"],
         "row_count": 5,
         "dimension_values": {
           "City": ["Houston", "Philadelphia", "Seattle", "Dallas", "Austin"]
         }
       }
     }
   }
   ```

4. Summarizer generates response:
   ```
   Here are the top 5 cities by profit:
   1. Houston: $50,000
   2. Philadelphia: $45,000
   ...
   
   [Context from previous query]
     - City: Houston, Philadelphia, Seattle, Dallas, Austin
   ```

### Query 2: "show me top 3 customers in each of those cities"

1. Agent sees message history with structured context
2. Extracts `["Houston", "Philadelphia", "Seattle", "Dallas", "Austin"]` from context
3. Builds query with filter:
   ```json
   {
     "filters": [
       {
         "field": "City",
         "type": "MATCH",
         "values": ["Houston", "Philadelphia", "Seattle", "Dallas", "Austin"]
       }
     ],
     "topN": {"n": 3, "by": "Sales", "direction": "top"}
   }
   ```
4. Executes query successfully

## Files Changed

1. **`backend/app/services/agents/vizql_tool_use/context_extractor.py`** (NEW)
   - Extract dimension values from query results
   - Format for LLM consumption

2. **`backend/app/api/chat.py`**
   - Call `extract_dimension_values()` when saving messages
   - Store dimension values in `extra_metadata`
   - Pass to message history

3. **`backend/app/services/agents/vizql_tool_use/nodes/get_data.py`**
   - Format dimension values when building LLM messages
   - Append structured context to assistant messages

4. **`backend/app/prompts/agents/vizql_tool_use/get_data.txt`**
   - Simplified instructions to use structured context
   - Removed complex extraction guidance

## Testing

Test with this flow:
1. Ask: "show me top 5 cities by profit"
2. Verify response includes `[Context from previous query]` section
3. Ask: "show me top 3 customers in each of those cities"
4. Verify agent uses only the 5 cities from context, not all 4,703 cities from dataset

## Future Enhancements

1. **Temporal context** - Track date ranges from queries
2. **Filter context** - Remember filters applied (e.g., "Region = West")
3. **Metric context** - Track which metrics were used
4. **Multi-turn context** - Reference queries from 2-3 turns ago
