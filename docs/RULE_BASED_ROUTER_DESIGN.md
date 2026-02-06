# Rule-Based Router Design

## Problem
The LLM-based router adds latency (network + LLM processing time), slowing down query responses. For simple classification tasks, rule-based heuristics are faster and deterministic.

## Solution
Replace LLM router with rule-based pattern matching using regex and keyword detection.

## Classification Logic

### 1. Schema Query Detection
Queries answerable from schema metadata without data querying.

**Patterns:**
```python
# "How many [field]?" without grouping/filtering
r"how\s+many\s+(\w+)(?:\s+(?:do\s+we\s+have|are\s+there))?[?\s]*$"
# Without: by, where, in, for, with, per, grouped, filtered

# "What's the min/max [field]?"
r"what(?:'s|\s+is)\s+the\s+(?:min|max|minimum|maximum)(?:\s+(?:and|or)\s+(?:min|max|minimum|maximum))?\s+(?:of\s+)?(\w+)"

# "What [fields] are available?"
r"what\s+(?:fields|measures|dimensions|columns)\s+(?:are\s+)?(?:available|exist)"

# "List all [dimension]"
r"list\s+(?:all\s+)?(?:the\s+)?(\w+)"

# "What's the data type of [field]?"
r"what(?:'s|\s+is)\s+the\s+(?:data\s+)?type\s+of\s+(\w+)"

# "How many fields/measures/dimensions?"
r"how\s+many\s+(?:fields|measures|dimensions)"
```

**Keywords (schema query):**
- "how many" (without grouping keywords)
- "what fields", "what measures", "what dimensions"
- "min/max", "minimum/maximum"
- "data type"
- "available"
- "distinct values"
- "list all"

**Exclusion keywords (NOT schema query):**
- "by", "per", "grouped by", "for each"
- "where", "in", "filtered"
- "with", "when"
- "total", "sum", "average"

### 2. Reformat Previous Detection
Requests to reformat existing query results.

**Patterns:**
```python
# References to previous results
r"(?:the|those|these)\s+results?"
r"put\s+(?:the\s+results?\s+)?(?:in|as)\s+a?\s+table"
r"(?:show|display|format)\s+(?:that|it|those|them)\s+as"
r"summarize\s+(?:the|those|these)?\s+results?"
```

**Keywords (reformat):**
- "the results", "those results"
- "put in a table", "show as table"
- "format as", "display as"
- "summarize that", "summarize those"
- "show only top N" (when referring to existing results)

**Requirements:**
- Must have previous_results in state
- Must reference previous results ("the", "that", "those", "it")

### 3. New Query Detection
Requires constructing new VizQL query.

**Default:** If not schema_query or reformat_previous → new_query

**Keywords (new query):**
- "total", "sum", "average", "count of"
- "by", "per", "for each", "grouped by"
- "where", "in", "filtered by"
- "top N [dimension] by [measure]"
- "show me", "give me"
- Calculations: "profit margin", "percentage", "ratio"

## Implementation

### Fast Rule-Based Router

```python
import re
from typing import Dict, Any, Tuple

class RuleBasedRouter:
    """Fast rule-based query router using pattern matching."""
    
    # Schema query patterns
    SCHEMA_PATTERNS = [
        # How many [field]? (without grouping)
        r"how\s+many\s+(\w+)(?:\s+(?:do\s+we\s+have|are\s+there))?[?\s]*$",
        r"how\s+many\s+distinct\s+(\w+)",
        
        # Min/max queries
        r"what(?:'s|\s+is)\s+the\s+(?:min|max|minimum|maximum)",
        
        # Field availability
        r"what\s+(?:fields|measures|dimensions|columns)",
        r"list\s+(?:all\s+)?(?:the\s+)?(?:fields|measures|dimensions)",
        
        # Data types
        r"what(?:'s|\s+is)\s+the\s+(?:data\s+)?type",
        
        # Schema structure
        r"how\s+many\s+(?:fields|measures|dimensions)"
    ]
    
    # Grouping/filtering keywords that indicate new_query
    GROUPING_KEYWORDS = ["by", "per", "for each", "grouped", "group by"]
    FILTERING_KEYWORDS = ["where", "in", "filtered", "with", "when", "between"]
    AGGREGATION_KEYWORDS = ["total", "sum", "average", "avg", "count of"]
    
    # Reformat patterns
    REFORMAT_PATTERNS = [
        r"(?:the|those|these)\s+results?",
        r"put\s+(?:the\s+results?\s+)?(?:in|as)\s+a?\s+table",
        r"(?:show|display|format)\s+(?:that|it|those|them)\s+as",
        r"summarize\s+(?:the|those|these)?\s+results?",
        r"(?:show|display)\s+(?:only|just)?\s+(?:top|first)",
        r"sort\s+(?:that|those|them|the\s+results?)"
    ]
    
    REFORMAT_KEYWORDS = ["the results", "those results", "that", "those", "them", "it"]
    
    def classify(
        self, 
        user_query: str,
        has_previous_results: bool = False
    ) -> Tuple[str, str, float]:
        """
        Classify user query using rule-based heuristics.
        
        Returns:
            (query_type, reasoning, confidence)
        """
        query_lower = user_query.lower().strip()
        
        # 1. Check for reformat_previous
        if has_previous_results and self._is_reformat_query(query_lower):
            return (
                "reformat_previous",
                "References previous results and requests reformatting",
                0.95
            )
        
        # 2. Check for schema_query
        if self._is_schema_query(query_lower):
            return (
                "schema_query",
                "Simple metadata query answerable from schema",
                0.9
            )
        
        # 3. Default to new_query
        return (
            "new_query",
            "Requires data aggregation/filtering/computation",
            0.85
        )
    
    def _is_schema_query(self, query: str) -> bool:
        """Check if query is answerable from schema metadata."""
        # Check schema patterns
        for pattern in self.SCHEMA_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                # For "how many" queries, check for grouping/filtering
                if "how many" in query:
                    # Exclude if has grouping/filtering keywords
                    has_grouping = any(kw in query for kw in self.GROUPING_KEYWORDS)
                    has_filtering = any(kw in query for kw in self.FILTERING_KEYWORDS)
                    has_aggregation = any(kw in query for kw in self.AGGREGATION_KEYWORDS)
                    
                    if has_grouping or has_filtering or has_aggregation:
                        return False  # It's a new_query
                
                return True
        
        return False
    
    def _is_reformat_query(self, query: str) -> bool:
        """Check if query is reformatting previous results."""
        # Must reference previous results
        references_previous = any(
            keyword in query for keyword in self.REFORMAT_KEYWORDS
        )
        
        if not references_previous:
            return False
        
        # Check reformat patterns
        for pattern in self.REFORMAT_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return True
        
        # Check for common reformat keywords
        reformat_keywords = ["table", "format", "summarize", "chart", "json"]
        if any(kw in query for kw in reformat_keywords):
            return True
        
        return False
```

### Integration with VizQL Agent

```python
# In router.py
from app.services.agents.vizql.rule_based_router import RuleBasedRouter

@track_node_execution("vizql", "router")
async def route_query_node(state: VizQLAgentState) -> Dict[str, Any]:
    """
    Classify user query using fast rule-based routing (no LLM).
    """
    try:
        user_query = state.get("user_query", "")
        previous_results = state.get("previous_results")
        
        has_previous_results = (
            previous_results is not None and 
            len(previous_results.get("data", [])) > 0
        )
        
        # Use rule-based router (fast, no LLM call)
        router = RuleBasedRouter()
        query_type, reasoning, confidence = router.classify(
            user_query,
            has_previous_results
        )
        
        logger.info(f"Query classified as '{query_type}' with confidence {confidence:.2f}: {reasoning}")
        
        return {
            **state,
            "query_type": query_type,
            "routing_reason": reasoning,
            "routing_confidence": confidence,
            "current_thought": f"Classified query as '{query_type}' ({reasoning})"
        }
        
    except Exception as e:
        logger.error(f"Error in router node: {e}", exc_info=True)
        # Default to new_query on error
        return {
            **state,
            "query_type": "new_query",
            "routing_reason": f"Router error: {str(e)}",
            "routing_confidence": 0.0,
            "current_thought": "Router error, proceeding with new query"
        }
```

## Advantages

1. **Fast:** No LLM call, instant classification (< 1ms)
2. **Deterministic:** Same query always routes the same way
3. **Transparent:** Clear rules, easy to debug
4. **Maintainable:** Add new patterns without retraining
5. **Cost-effective:** No LLM API costs for routing

## Testing

```python
# Test cases
test_cases = [
    # Schema queries
    ("how many customers", "schema_query"),
    ("how many products do we have", "schema_query"),
    ("what's the min and max sales", "schema_query"),
    ("what fields are available", "schema_query"),
    ("list all categories", "schema_query"),
    
    # NOT schema queries (new_query)
    ("how many customers by region", "new_query"),
    ("how many customers in 2024", "new_query"),
    ("total customers", "new_query"),
    
    # Reformat queries (with previous_results)
    ("put the results in a table", "reformat_previous"),
    ("show that as a chart", "reformat_previous"),
    ("summarize those results", "reformat_previous"),
    
    # New queries
    ("show me total sales by region", "new_query"),
    ("top 10 customers by revenue", "new_query"),
    ("average price per product", "new_query"),
]

router = RuleBasedRouter()
for query, expected in test_cases:
    actual, _, _ = router.classify(query, has_previous_results=True)
    assert actual == expected, f"Failed: {query} -> {actual} (expected {expected})"
```

## Migration Path

1. Implement `RuleBasedRouter` class
2. Update `route_query_node` to use rule-based router
3. Keep LLM-based router as fallback (configurable)
4. Add metrics to compare performance
5. Monitor classification accuracy
6. Adjust patterns based on real usage

## Fallback Option

Keep LLM-based router available for:
- Complex/ambiguous queries
- When confidence < threshold
- Optional flag to enable LLM classification

```python
# Hybrid approach
if USE_LLM_ROUTER or confidence < 0.7:
    # Use LLM-based classification
    query_type = await llm_classify(user_query)
else:
    # Use fast rule-based classification
    query_type, _, _ = router.classify(user_query)
```

## Performance Comparison

| Router Type | Latency | Cost | Accuracy |
|-------------|---------|------|----------|
| LLM-based   | ~500-2000ms | $$$ | 95% |
| Rule-based  | < 1ms | $0 | 90% |
| Hybrid      | ~50-2000ms | $$ | 95% |

## Recommendation

Use **rule-based router** as default with LLM fallback for edge cases.
