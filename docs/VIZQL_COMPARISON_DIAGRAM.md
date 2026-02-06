# VizQL Agent Architecture Comparison

## Current Agent Flow (7 Nodes)

```
┌─────────────────────────────────────────────────────────────────┐
│                      Current VizQL Agent                         │
└─────────────────────────────────────────────────────────────────┘

    [START]
       ↓
    [ROUTER NODE] ─────────────────┐ Short circuits:
    (Classify query type)          │ - Schema queries
       ↓                           │ - Reformat requests
    (new_query)                    │
       ↓                           ↓
    [PLANNER NODE]            [SCHEMA HANDLER]
    (Create query plan)       [REFORMATTER]
       ↓                           ↓
    [SCHEMA FETCH NODE]          [END]
    (Always fetch schema)
       ↓
    [BUILD QUERY NODE]
    (Construct VizQL)
       ↓
    [VALIDATOR NODE] ─────┐
    (Local validation)    │ (invalid)
       ↓                  ↓
    (valid)          [REFINER NODE]
       ↓                  │ (retry)
    [EXECUTOR NODE]       │ (3 attempts max)
    (Execute query)       │
       ↓                  ↓
    [FORMATTER NODE]  [ERROR HANDLER]
    (Natural language)     ↓
       ↓                 [END]
    [END]

Issues:
❌ Router adds latency (500-1000ms)
❌ Planner adds LLM call (2-3s)
❌ Schema fetch always runs (1-2s)
❌ Cannot reuse queries from conversation
❌ Inflexible flow
```

## Streamlined Agent Flow (4 Nodes)

```
┌─────────────────────────────────────────────────────────────────┐
│                   Streamlined VizQL Agent                        │
└─────────────────────────────────────────────────────────────────┘

    [START]
       ↓
    [BUILD QUERY NODE WITH TOOLS] ←─────┐
    ┌──────────────────────────┐        │ (retry with errors)
    │ Tools Available:         │        │
    │ • get_datasource_schema  │ ←──────┤
    │ • get_datasource_metadata│        │
    │ • get_prior_query        │        │
    │                          │        │
    │ Decision Logic:          │        │
    │ 1. Check if similar to   │        │
    │    prior message → reuse │        │
    │ 2. Check if schema       │        │
    │    provided → use it     │        │
    │ 3. Otherwise fetch       │        │
    │    schema via tool       │        │
    └──────────────────────────┘        │
           ↓                            │
    [VALIDATOR NODE] ───────────────────┘
    (Local validation)          (invalid, retry)
           ↓
        (valid)
           ↓
    [EXECUTOR NODE] ────────────────────┘
    (Execute query)            (failed, retry)
           ↓
       (success)
           ↓
    [FORMATTER NODE]
    (Natural language + reasoning capture)
           ↓
        [END]

Benefits:
✅ No router overhead (save 500-1000ms)
✅ No separate planning (save 2-3s)
✅ Schema fetch only when needed (save 1-2s in 50% of cases)
✅ Can reuse queries (new capability)
✅ Intelligent tool usage
✅ Simpler debugging
```

## Side-by-Side Comparison

```
┌──────────────────────┬──────────────────────┬──────────────────────┐
│      Feature         │   Current Agent      │  Streamlined Agent   │
├──────────────────────┼──────────────────────┼──────────────────────┤
│ Entry Point          │ Router (classify)    │ Build Query (smart)  │
│ Query Planning       │ Separate node (LLM)  │ Integrated in build  │
│ Schema Fetching      │ Always fetched       │ Optional via tool    │
│ Query Reuse          │ No                   │ Yes (from history)   │
│ Node Count           │ 7 nodes              │ 4 nodes              │
│ LLM Calls (typical)  │ 3-4 calls            │ 2-3 calls            │
│ Validation           │ Local + semantic     │ Local + semantic     │
│ Execution            │ Standard             │ Standard             │
│ Formatting           │ Standard             │ + Reasoning capture  │
│ Error Handling       │ Centralized          │ Centralized          │
└──────────────────────┴──────────────────────┴──────────────────────┘
```

## Latency Breakdown

### Current Agent (Typical Query)
```
Router:          500ms  ████
Planner:        2500ms  ████████████████████████
Schema Fetch:   1500ms  ███████████████
Build Query:    3000ms  ██████████████████████████████
Validator:        50ms  ▌
Executor:       2000ms  ████████████████████
Formatter:      2500ms  ████████████████████████
─────────────────────────────────────────────────
TOTAL:         12050ms  (~12 seconds)
```

### Streamlined Agent (Schema Provided)
```
Build Query:    3000ms  ██████████████████████████████
Validator:        50ms  ▌
Executor:       2000ms  ████████████████████
Formatter:      2500ms  ████████████████████████
─────────────────────────────────────────────────
TOTAL:          7550ms  (~7.5 seconds)
Savings:        4500ms  (37% faster)
```

### Streamlined Agent (Query Reused)
```
Build Query:    2000ms  ████████████████████
  (retrieves from history, adapts)
Validator:        50ms  ▌
Executor:       2000ms  ████████████████████
Formatter:      2500ms  ████████████████████████
─────────────────────────────────────────────────
TOTAL:          6550ms  (~6.5 seconds)
Savings:        5500ms  (46% faster)
```

## Tool Usage Patterns

### Scenario 1: First Query (No Schema Provided)
```
User: "Show me top 10 cities by profit"

Build Query Node:
├─ Tool: get_datasource_schema()     [1500ms]
├─ LLM: Build query with schema      [2500ms]
└─ Output: New VizQL query

Total: 4000ms
```

### Scenario 2: Follow-up Query (Schema Cached)
```
User: "Now show me top 5 states by sales"

Build Query Node:
├─ Check: Schema in state ✓          [0ms]
├─ LLM: Build query with cached      [2500ms]
└─ Output: New VizQL query

Total: 2500ms (40% faster than Scenario 1)
```

### Scenario 3: Similar Query (Reuse)
```
User: "Show me top 10 cities by profit"
Assistant: [Returns results]

User: "Show me top 15 cities by profit instead"

Build Query Node:
├─ Tool: get_prior_query()           [200ms]
├─ LLM: Modify existing query        [1500ms]
│  (Change topN from 10 → 15)
└─ Output: Modified VizQL query

Total: 1700ms (58% faster than Scenario 1)
```

## Decision Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│            Build Query Node Decision Tree                │
└─────────────────────────────────────────────────────────┘

    Start Build Query
          ↓
    Check message history
          ↓
    ┌─────────────────┐
    │ Similar query   │
    │ in history?     │
    └─────────────────┘
       ↓           ↓
      YES          NO
       ↓           ↓
    Use tool:    Check state
    get_prior_   for schema
    query()        ↓
       ↓      ┌─────────────┐
       ↓      │ Schema in   │
       ↓      │ state?      │
       ↓      └─────────────┘
       ↓         ↓        ↓
       ↓        YES       NO
       ↓         ↓        ↓
       ↓      Use it    Use tool:
       ↓                get_datasource_
       ↓                schema()
       ↓                   ↓
       └────────┬──────────┘
                ↓
         Build/Modify Query
                ↓
         Return query_draft
```

## Token Usage Comparison

### Current Agent
```
Router Prompt:       500 tokens
Planner Prompt:     1500 tokens
Builder Prompt:     3000 tokens
Formatter Prompt:   2000 tokens
──────────────────────────────
TOTAL INPUT:        7000 tokens

Router Response:     100 tokens
Planner Response:    300 tokens
Builder Response:    500 tokens
Formatter Response:  800 tokens
──────────────────────────────
TOTAL OUTPUT:       1700 tokens

GRAND TOTAL:        8700 tokens
```

### Streamlined Agent (No Tools)
```
Builder Prompt:     3000 tokens
Formatter Prompt:   2000 tokens
──────────────────────────────
TOTAL INPUT:        5000 tokens

Builder Response:    500 tokens
Formatter Response:  800 tokens
──────────────────────────────
TOTAL OUTPUT:       1300 tokens

GRAND TOTAL:        6300 tokens
SAVINGS:            2400 tokens (28% reduction)
```

### Streamlined Agent (With Query Reuse)
```
Builder Prompt:     2500 tokens (shorter with history)
Formatter Prompt:   2000 tokens
──────────────────────────────
TOTAL INPUT:        4500 tokens

Builder Response:    300 tokens (just modifications)
Formatter Response:  800 tokens
──────────────────────────────
TOTAL OUTPUT:       1100 tokens

GRAND TOTAL:        5600 tokens
SAVINGS:            3100 tokens (36% reduction)
```

---

## Summary

The streamlined agent achieves performance gains through:

1. **Architectural simplification** - 4 nodes vs 7 nodes
2. **Smart tool usage** - Fetch only what's needed
3. **Query reuse** - Learn from conversation history
4. **Token efficiency** - Fewer LLM calls

Expected improvements:
- **Latency:** 20-37% faster (depending on scenario)
- **Cost:** 28-36% lower token usage
- **Capability:** Query reuse enables new use cases
- **Simplicity:** Easier to debug and maintain
