# VizQL Agent Improvements Summary

## Overview

This document summarizes two major improvements to the VizQL agent system:

1. **Enhanced Pattern Detection and Query Construction** - Improved agent's ability to construct correct VizQL queries for all filter types, calculations, bins, and sorting
2. **Intelligent Query Routing** - Added router to avoid unnecessary VizQL queries for schema-based questions and result reformatting

---

## Part 1: Enhanced Pattern Detection and Query Construction

### Problem
The agent wasn't correctly constructing VizQL queries for "top N" queries and other advanced patterns. It would use sorting instead of TOP filters, and didn't properly leverage other VizQL capabilities.

### Solution
Enhanced the entire agent pipeline to detect, extract, and use all VizQL pattern types.

### Changes Made

#### 1. Planning Stage (`planning.txt`)
- **Enhanced Output Schema**: Added structured extraction for:
  - `topN`: {enabled, howMany, direction, dimensionField, measureField}
  - `filters`: {filterType, params} for each filter
  - `sorting`: [{field, direction, priority}]
  - `calculations`: [{fieldCaption, formula}]
  - `bins`: [{fieldCaption, binSize}]

- **Added 10 Examples** covering:
  - Top N patterns (TOP filter)
  - Relative date filters (DATE filter)
  - MATCH filters
  - Quantitative filters
  - SET filters
  - Calculations
  - Bins

#### 2. State Management (`state.py`)
- Added state fields for all pattern types:
  ```python
  topN: Optional[dict[str, Any]]
  sorting: list[dict[str, Any]]
  calculations: list[dict[str, Any]]
  bins: list[dict[str, Any]]
  ```

#### 3. Planner Node (`nodes/planner.py`)
- Extracts all pattern types from intent parsing
- Stores in state with detailed pattern summary
- Builds thought message listing all detected patterns

#### 4. Context Builder (`context_builder.py`)
- Updated to accept all pattern types as parameters
- Generates explicit guidance for each detected pattern:
  - **TOP N**: Shows exact TOP filter structure with field names
  - **DATE filters**: Shows periodType, dateRangeType, rangeN
  - **MATCH filters**: Shows contains/startsWith/endsWith
  - **SET filters**: Shows values and exclude flag
  - **QUANTITATIVE filters**: Shows min/max parameters
  - **Calculations**: Shows formula examples
  - **Bins**: Shows binSize examples

#### 5. Query Construction Prompt (`query_construction.txt`)
- Added "CRITICAL: TOP N QUERIES" section at top
- Added comprehensive filter decision tree with 6 filter types
- Added filter construction examples for each type
- Added calculations, bins, and sorting guidance

#### 6. Semantic Rules (`semantic_rules.txt`)
- Expanded pattern library from 6 to 40+ patterns
- Added pattern priority rules (TOP filter > sorting)
- Added anti-patterns section with wrong vs correct examples

#### 7. Query Validation (`query_validation.txt`)
- Added filter-specific validation for all 6 filter types
- Added pattern-based validation (checks filter type matches intent)
- Validates required fields for each filter type

### Impact
- Agent now correctly uses TOP filters for "top N" queries
- All VizQL filter types, calculations, and bins are properly constructed
- Explicit guidance ensures LLM constructs correct query structures

---

## Part 2: Intelligent Query Routing

### Problem
The agent attempted to construct VizQL queries for ALL requests, even:
1. **Schema-based questions** answerable from metadata ("how many customers do we have?")
2. **Result reformatting** requests that just need to reformat previous results ("put the results in a table")

This caused:
- Unnecessary query construction attempts
- Failed queries for non-queryable requests
- Slower response times
- Wasted compute resources

### Solution
Added a **Router Node** that classifies queries and routes them appropriately, avoiding unnecessary VizQL queries.

### Architecture

```
User Query
    ↓
[Router/Classifier] ← Enriched Schema + Previous Results
    ↓
    ├─→ [Schema Query Handler] → Answer from Metadata → END
    ├─→ [Result Reformatter] → Reformat Results → END
    └─→ [Planner] → Query Builder → Execute → END (existing flow)
```

### Query Classification Types

#### 1. Schema Queries (`schema_query`)
Questions answerable from schema metadata:
- **Examples**: "How many customers?", "What's min/max sales?", "What regions are available?"
- **Uses**: cardinality, min/max, sample_values, null_percentage
- **No VizQL query needed**

#### 2. Result Reformatting (`reformat_previous`)
Requests to reformat previous results:
- **Examples**: "Put the results in a table", "Show as chart", "Summarize those results"
- **Requires**: Previous results stored in state
- **No VizQL query needed**

#### 3. New VizQL Query (`new_query`)
Requires constructing and executing new VizQL query:
- **Examples**: "Total sales by region", "Top 10 customers by revenue"
- **Requires**: Data aggregation, filtering, or computation
- **Uses existing flow**

### Components Implemented

#### 1. Router Node (`nodes/router.py`)
- Classifies user query into one of three types
- Uses LLM with routing prompt
- Returns classification with confidence score
- Falls back to `new_query` on error

#### 2. Routing Prompt (`routing.txt`)
- Describes all three query types with indicators and keywords
- Provides decision rules
- Includes context about available schema and previous results
- Returns structured JSON classification

#### 3. Schema Handler Node (`nodes/schema_handler.py`)
- Answers questions using enriched schema metadata only
- Formats schema (fields, cardinality, min/max, sample values)
- Generates natural language answer
- No VizQL query execution

#### 4. Schema Handler Prompt (`schema_query_handler.txt`)
- Guides LLM to answer using only metadata
- Provides examples of schema-based answers
- Emphasizes precision with numbers
- Handles missing metadata gracefully

#### 5. Reformatter Node (`nodes/reformatter.py`)
- Reformats previous query results per user request
- Supports: tables, summaries, top N, sorting, filtering, lists, JSON
- Preserves data accuracy
- No new query execution

#### 6. Reformatter Prompt (`result_reformatter.txt`)
- Describes common reformatting types
- Provides examples for each type
- Emphasizes following user's specific request
- Preserves data integrity

#### 7. State Updates
- Added routing fields:
  ```python
  query_type: Optional[str]  # Classification result
  routing_reason: Optional[str]  # Explanation
  routing_confidence: Optional[float]  # 0.0-1.0
  previous_results: Optional[dict]  # For reformatting
  schema_answer: Optional[str]  # Schema query answer
  ```

#### 8. Graph Updates
- Entry point changed from `planner` to `router`
- Router conditionally routes to:
  - `schema_handler` (schema queries)
  - `reformatter` (reformat requests)
  - `planner` (new queries - existing flow)
- Schema handler and reformatter terminate directly
- Formatter now stores `previous_results` for next query

### Benefits

1. **Faster Responses**: Schema queries don't require query construction/execution
2. **Better UX**: Reformatting requests don't fail with query errors
3. **Resource Efficiency**: Fewer unnecessary VizQL queries
4. **Clearer Intent**: Explicit classification of request types
5. **Persistent Results**: Previous results available for reformatting

### Example Flows

#### Schema Query Flow
```
User: "How many customers do we have?"
  ↓
Router: "schema_query" (checks Customer cardinality)
  ↓
Schema Handler: Look up Customer field → cardinality: 793
  ↓
Answer: "There are 793 customers in the dataset."
  ↓
END (no VizQL query)
```

#### Reformat Flow
```
User: "Top 3 cities by sales"
  ↓
Router: "new_query"
  ↓
Execute Query → Results: [{"City": "NYC", "Sales": 256000}, ...]
  ↓
Store previous_results
  ↓
User: "Put those results in a table"
  ↓
Router: "reformat_previous"
  ↓
Reformatter: Format as markdown table
  ↓
END (no new query)
```

#### New Query Flow
```
User: "Show me total sales by region"
  ↓
Router: "new_query" (requires aggregation)
  ↓
Planner → Query Builder → Execute → Format
  ↓
END
```

---

## Files Created/Modified

### New Files Created
1. `docs/VIZQL_ROUTER_IMPLEMENTATION_PLAN.md` - Detailed implementation plan
2. `backend/app/prompts/agents/vizql/routing.txt` - Router classification prompt
3. `backend/app/prompts/agents/vizql/schema_query_handler.txt` - Schema handler prompt
4. `backend/app/prompts/agents/vizql/result_reformatter.txt` - Reformatter prompt
5. `backend/app/services/agents/vizql/nodes/router.py` - Router node
6. `backend/app/services/agents/vizql/nodes/schema_handler.py` - Schema handler node
7. `backend/app/services/agents/vizql/nodes/reformatter.py` - Reformatter node

### Modified Files
1. `backend/app/prompts/agents/vizql/planning.txt` - Enhanced pattern detection
2. `backend/app/prompts/agents/vizql/query_construction.txt` - Filter decision tree + examples
3. `backend/app/prompts/agents/vizql/semantic_rules.txt` - Expanded patterns + anti-patterns
4. `backend/app/prompts/agents/vizql/query_validation.txt` - Filter-specific validation
5. `backend/app/prompts/agents/vizql/result_formatting.txt` - Added query context
6. `backend/app/services/agents/vizql/state.py` - Added routing + pattern fields
7. `backend/app/services/agents/vizql/nodes/planner.py` - Extract all patterns
8. `backend/app/services/agents/vizql/nodes/query_builder.py` - Pass all patterns to context
9. `backend/app/services/agents/vizql/nodes/formatter.py` - Store previous_results
10. `backend/app/services/agents/vizql/context_builder.py` - Generate pattern guidance
11. `backend/app/services/agents/vizql/graph.py` - Router-based flow

---

## Testing Recommendations

### Pattern Detection Testing
1. **Top N queries**: "top 10 customers by revenue", "bottom 5 products by sales"
2. **Date filters**: "sales in last 3 months", "this year", "between Jan and Mar"
3. **MATCH filters**: "products containing 'phone'", "customers starting with 'A'"
4. **Calculations**: "profit margin", "sales divided by quantity"
5. **Bins**: "create bins on sales with size 1000"

### Router Testing
1. **Schema queries**:
   - "How many customers are there?"
   - "What's the max order value?"
   - "List all categories"
   - "What fields are available?"

2. **Reformat queries** (after executing a query):
   - "Put the results in a table"
   - "Show only top 5"
   - "Summarize those results"
   - "What does this data mean?"

3. **Edge cases**:
   - Reformat without previous results → Should return error
   - Ambiguous query → Check router confidence score
   - Schema query for non-existent field → Should handle gracefully

---

## Performance Improvements

1. **Reduced Query Load**: Schema queries and reformats don't hit VizQL API
2. **Faster Response Time**: Metadata lookups are instant vs query execution
3. **Better Success Rate**: Proper filter construction reduces validation failures
4. **Context Preservation**: Previous results enable follow-up reformatting

---

## Future Enhancements

1. **Enhanced Schema Statistics**: Add more statistics (median, percentiles, histograms)
2. **Caching Previous Results**: Persist across sessions
3. **Multi-Query Reformatting**: "Compare those two queries"
4. **Interactive Filtering**: "Show only rows where sales > 1000" on previous results
5. **Chart Generation**: "Show that as a bar chart" → Generate visualization config

---

## Summary

These improvements make the VizQL agent:
- **Smarter**: Routes queries appropriately, avoiding unnecessary work
- **Faster**: Schema queries and reformats are instant
- **More Accurate**: Proper pattern detection ensures correct VizQL query construction
- **More Capable**: Handles all VizQL features (6 filter types, calculations, bins, sorting)
- **Better UX**: Clearer responses, no failed attempts for non-queryable requests
