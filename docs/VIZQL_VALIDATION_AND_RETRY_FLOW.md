# VizQL Validation and Retry Flow

**Date:** February 5, 2026  
**Purpose:** Document how validation errors and suggestions are fed back to the LLM for query refinement

---

## Overview

The VizQL agent uses a **validation → refinement → retry** loop to improve query accuracy. When a query fails validation, errors and suggestions are fed back to the LLM to refine the query, with up to 3 retry attempts.

---

## Validation Flow

### 1. Query Validation (`validator` node)

**File:** `backend/app/services/agents/vizql/nodes/validator.py`

The validator performs two types of validation:

#### A. Basic Structure Validation
- Checks for required fields: `datasource.datasourceLuid`, `query.fields`
- Validates field names exist in schema (case-insensitive matching)
- Validates aggregation functions are valid (SUM, AVG, COUNT, etc.)
- Validates filter field names

#### B. Semantic Validation (if enriched schema available)
**File:** `backend/app/services/agents/vizql/constraint_validator.py`

Uses `VizQLConstraintValidator` to check:
- **MEASURE fields MUST have aggregation**: Fields with `fieldRole == "MEASURE"` require a `function` field
- **DIMENSION fields MUST NOT have aggregation**: Fields with `fieldRole == "DIMENSION"` should not have a `function` field
- **Aggregation compatibility**: Aggregation functions must be compatible with field data types
- **Field name matching**: Uses exact case-sensitive matching from enriched schema

### 2. Error and Suggestion Generation

The validator returns:
- `is_valid`: Boolean indicating if query passed validation
- `validation_errors`: List of error messages
- `validation_suggestions`: List of actionable suggestions

**Example errors:**
```
- "MEASURE field 'Sales' requires aggregation function"
- "Field 'Regoin' not found in schema"
- "DIMENSION field 'Region' should not have aggregation function"
```

**Example suggestions:**
```
- "Add aggregation to 'Sales': {\"fieldCaption\": \"Sales\", \"function\": \"SUM\"}"
- "Field 'Regoin' not found. Did you mean: Region, Revenue?"
- "Remove 'function' from 'Region': {\"fieldCaption\": \"Region\"}"
```

---

## Retry Mechanism

### Graph Flow

```
Planner → Schema Fetch → Query Builder → Validator
                                          ↓
                   ┌──────────────────────┴──────────────────────┐
                   ↓                                              ↓
           [is_valid = True]                            [is_valid = False]
                   ↓                                              ↓
             Executor                                    Refiner (max 3 attempts)
                   ↓                                              ↓
             Formatter                                   Validator (loop back)
                   ↓                                              
                 END
```

### Retry Logic

**File:** `backend/app/services/agents/vizql/graph.py`

The graph routes based on validation result:

```python
def route_after_validation(state: VizQLAgentState) -> str:
    if state.get("error"):
        return "error_handler"
    
    if state.get("is_valid", False):
        return "execute"  # Valid query → execute
    
    # Invalid query - check if we can refine
    # Allow up to 3 refinement attempts (query_version 1, 2, 3)
    # After 3 refinements, query_version will be 4, so stop
    query_version = state.get("query_version", 0)
    if query_version >= 4:
        return "error_handler"  # Max attempts reached
    
    return "refine"  # Try to refine
```

**Max Retries:** 3 refinement attempts
- Initial build: `query_version = 1`
- First refinement: `query_version = 2`
- Second refinement: `query_version = 3`
- Third refinement: `query_version = 4` (then stops)

---

## Query Refinement (`refiner` node)

**File:** `backend/app/services/agents/vizql/nodes/refiner.py`

When validation fails, the refiner node:

1. **Checks retry limit**: If `query_version >= 4`, returns error (allows 3 refinement attempts)
2. **Builds refinement prompt**: Uses `query_refinement.txt` template with:
   - Original user query
   - Failed query JSON
   - Validation errors (list)
   - Validation suggestions (formatted list)
   - Schema context (enriched schema if available)
3. **Calls LLM**: Sends prompt to LLM asking to fix the query
4. **Parses corrected query**: Extracts JSON from LLM response
5. **Updates state**: Sets `query_draft` to corrected query
6. **Loops back**: Routes directly to `validator` (not `query_builder`, to preserve the refined query)

### Refinement Prompt Template

**File:** `backend/app/prompts/agents/vizql/query_refinement.txt`

The prompt includes:
- Original user query (to maintain intent)
- Failed query JSON
- List of validation errors
- Formatted suggestions
- Schema reference
- VizQL rules (MEASURES need aggregation, DIMENSIONS don't)
- Common fixes guidance

**Example prompt variables:**
```
user_query: "show total sales by region"
original_query: { "query": { "fields": [{"fieldCaption": "Sales"}] } }
errors: ["MEASURE field 'Sales' requires aggregation function"]
suggestions: ["Add aggregation to 'Sales': {\"fieldCaption\": \"Sales\", \"function\": \"SUM\"}"]
schema: [enriched schema context]
```

---

## State Management

**File:** `backend/app/services/agents/vizql/state.py`

The state tracks:
- `query_version`: Current refinement attempt (0, 1, 2)
- `validation_errors`: List of error messages
- `validation_suggestions`: List of suggestion messages
- `is_valid`: Boolean validation result
- `query_draft`: Current query being validated/refined

**Note:** `query_version` is currently **not automatically incremented** in the refiner. This needs to be fixed.

---

## Query Version Tracking

**Implementation:** `query_version` tracks refinement attempts:

- **Initial build** (`query_builder`): Sets `query_version = 1` if it was 0
- **After refinement** (`refiner`): Increments `query_version` (1 → 2 → 3)
- **Max retries**: When `query_version >= 3`, no more refinements allowed

**Flow:**
1. Initial query: `query_version = 1` (set in query_builder)
2. First refinement: `query_version = 2` (incremented in refiner)
3. Second refinement: `query_version = 3` (incremented in refiner)
4. Third refinement: `query_version = 4` (incremented in refiner)
5. Fourth validation fails: Max attempts reached (`query_version >= 4`) → error_handler

---

## Example Flow

### Attempt 1 (query_version = 0)
1. **Query Builder** creates: `{"fields": [{"fieldCaption": "Sales"}]}`
2. **Validator** finds: `"MEASURE field 'Sales' requires aggregation function"`
3. **Suggestion**: `"Add aggregation to 'Sales': {\"fieldCaption\": \"Sales\", \"function\": \"SUM\"}"`
4. **Refiner** receives errors/suggestions → calls LLM → gets corrected query
5. **Query Builder** receives corrected query: `{"fields": [{"fieldCaption": "Sales", "function": "SUM"}]}`

### Attempt 2 (query_version = 1)
1. **Validator** validates corrected query
2. If still invalid → **Refiner** tries again with updated errors
3. If valid → **Executor** runs query

### Attempt 3 (query_version = 2)
1. Final attempt
2. If still invalid after 3 attempts → **Error Handler** returns error message

---

## Error Handler

**File:** `backend/app/services/agents/vizql/graph.py` (error_handler_node)

When max retries are reached or fatal errors occur, the error handler formats:
- Validation errors
- Validation suggestions
- Execution errors (if any)

This provides helpful feedback to the user even when the query fails.

---

## Validation Types

### 1. Basic Validation (always runs)
- Structure checks
- Field name existence
- Aggregation function validity

### 2. Semantic Validation (if enriched schema available)
- Field role checks (MEASURE vs DIMENSION)
- Aggregation compatibility
- Field combination warnings

### 3. Execution Validation (after execution)
- API errors
- Query execution errors
- Result validation

---

## Key Files

- **Validator**: `backend/app/services/agents/vizql/nodes/validator.py`
- **Refiner**: `backend/app/services/agents/vizql/nodes/refiner.py`
- **Constraint Validator**: `backend/app/services/agents/vizql/constraint_validator.py`
- **Graph**: `backend/app/services/agents/vizql/graph.py`
- **State**: `backend/app/services/agents/vizql/state.py`
- **Refinement Prompt**: `backend/app/prompts/agents/vizql/query_refinement.txt`

---

## Improvements Needed

1. **Fix query_version increment**: Ensure `query_version` is incremented in refiner
2. **Better error accumulation**: Track errors across retries to avoid repeating fixes
3. **Suggestion prioritization**: Rank suggestions by likelihood of fixing the issue
4. **Execution error feedback**: Feed execution errors back to refiner for additional retries
5. **Partial success handling**: If some fields are valid, preserve them during refinement

---

**Last Updated:** February 5, 2026
