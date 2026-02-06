## VizQL Agent Architecture Comparison

### Rule-Based Router Approach (Abandoned)
**Problem:** Brittle pattern matching, constant maintenance, limited flexibility

```
User Query → Rule-Based Router → [schema_query | reformat_previous | new_query]
                  ↓
            Pattern matching with regex
            Keyword detection
            Word boundary checks
```

**Issues:**
- Patterns break with novel query phrasing
- "distinct" triggers "in" keyword (substring matching bugs)
- Requires constant pattern updates
- Cannot handle ambiguous queries
- No multi-step reasoning

**Latency:** < 1ms (fast)
**Reliability:** Low (brittle patterns)
**Maintenance:** High (constant updates needed)

---

### Graph-Based Agent Approach (Current/Old)
**Problem:** Over-engineered with 8+ nodes and complex routing logic

```
Router → Planner → Schema Fetch → Query Builder → Validator → Refiner → Executor → Formatter
   ↓
Schema Handler
   ↓
Reformatter
```

**Nodes:**
1. Router - Classifies query type (LLM or rules)
2. Planner - Extracts intent (topN, filters, etc.)
3. Schema Fetch - Gets enriched schema
4. Query Builder - Constructs VizQL JSON
5. Validator - Checks query validity
6. Refiner - Fixes errors
7. Executor - Runs query
8. Formatter - Formats results
9. Schema Handler - Answers from metadata
10. Reformatter - Reformats previous results

**Issues:**
- Complex state management
- Fixed workflow (no flexibility)
- Multiple LLM calls required
- Difficult to debug
- Hard to add new capabilities
- Over-engineered for simple queries

**Latency:** ~3-5 seconds per query
**Reliability:** Medium (multiple points of failure)
**Maintenance:** Medium (complex graph logic)
**Code:** ~1000+ lines

---

### Tool-Use Agent Approach (New/Recommended)
**Solution:** Simple 2-step flow with LLM tool-calling

```
Step 1: Get Data (with tools) → Step 2: Summarize → Done
```

**Flow:**
1. **Get Data Node:**
   - LLM receives user query + tools
   - Decides which tools to use
   - Executes tools (get_metadata, build_query, query_datasource, etc.)
   - Returns raw data

2. **Summarize Node:**
   - Formats raw data
   - Returns natural language response

**Available Tools:**
1. `get_datasource_metadata` - Schema with statistics
2. `build_query` - Construct VizQL query
3. `validate_query` - Check query validity
4. `query_datasource` - Execute query
5. `get_previous_results` - Get conversation data

**Advantages:**
- **Simple:** 2 nodes vs 8+ nodes
- **Flexible:** LLM adapts to novel queries
- **Self-correcting:** Tool feedback guides LLM
- **Maintainable:** Add tools without changing graph
- **Debuggable:** Clear tool call sequence
- **Efficient:** Skip unnecessary steps

**Example Decision Making:**

```
Query: "how many customers?"
LLM thinks: "This is asking for count of distinct customers.
            I can answer this from metadata cardinality.
            I should use get_datasource_metadata tool."
Action: get_datasource_metadata(include_statistics=True)
Result: {cardinality: 1234}
Format: "We have 1,234 customers"
```

```
Query: "top 10 customers by revenue"
LLM thinks: "This needs TOP filter + data aggregation.
            I should build a query with topN."
Action 1: build_query(measures=["Revenue"], dimensions=["Customer"], topN={n:10})
Action 2: query_datasource(query)
Result: {columns: [...], data: [...]}
Format: [table with top 10]
```

```
Query: "put the results in a table"
LLM thinks: "User is referring to previous results.
            I should get previous data."
Action: get_previous_results()
Result: Previous query data
Format: [markdown table]
```

**Latency:** ~2-3 seconds per query
**Reliability:** High (LLM reasoning + tool validation)
**Maintenance:** Low (add/remove tools easily)
**Code:** ~300 lines (70% reduction)

---

## Decision Matrix

| Criteria | Rule-Based | Graph-Based | Tool-Use |
|----------|------------|-------------|----------|
| **Simplicity** | Medium | Low | **High** |
| **Flexibility** | Low | Medium | **High** |
| **Reliability** | Low | Medium | **High** |
| **Maintainability** | Low | Medium | **High** |
| **Performance** | **Fastest** | Slow | Fast |
| **Code Size** | 500 lines | 1000+ lines | **300 lines** |
| **Nodes** | 1 | 8+ | **2** |
| **LLM Calls** | 0 (rules) | 3-5 | **1-2** |
| **Novel Queries** | ❌ | ⚠️ | ✅ |
| **Multi-Step** | ❌ | ❌ | ✅ |
| **Debugging** | Hard | Hard | **Easy** |

**Legend:**
- ✅ Fully supported
- ⚠️ Partially supported
- ❌ Not supported

---

## Recommendation

**Use Tool-Use Agent** for:
- Maximum flexibility
- Easiest maintenance
- Best long-term scalability
- Novel query handling
- Multi-step reasoning

**Use Graph-Based Agent** for:
- Existing production systems (if stable)
- Specific workflow requirements
- Gradual migration path

**Avoid Rule-Based Router** for:
- Too brittle for production
- Pattern maintenance overhead
- Limited to known patterns

---

## Migration Strategy

### Phase 1: Parallel Deployment
- Deploy tool-use agent alongside graph-based
- Route 10% traffic to tool-use agent
- Monitor metrics: accuracy, latency, errors

### Phase 2: A/B Testing
- Increase to 50/50 split
- Compare user satisfaction
- Identify edge cases

### Phase 3: Full Migration
- Route 100% to tool-use agent
- Keep graph-based as fallback
- Monitor for issues

### Phase 4: Deprecation
- Remove graph-based agent code
- Archive rule-based router
- Document learnings

---

## Key Insights

### Why Tool-Use Wins

1. **Flexibility Over Speed**
   - Rule-based is fastest (< 1ms) but breaks often
   - Tool-use is slightly slower (~2s) but handles anything
   - User experience: Reliability > Latency

2. **Simplicity Over Complexity**
   - Graph-based tries to anticipate all paths
   - Tool-use lets LLM figure it out
   - Simpler code = fewer bugs

3. **Reasoning Over Rules**
   - Rules encode human logic (brittle)
   - Tools give LLM capabilities (flexible)
   - LLM reasoning > human pattern matching

4. **Modularity Over Monolith**
   - Graph nodes are tightly coupled
   - Tools are independent functions
   - Easy to add/remove/test tools

### When to Use What

**Use Rule-Based:**
- Never for production (too brittle)
- Maybe for simple prototypes

**Use Graph-Based:**
- When workflow is truly fixed
- When you need specific audit trail
- When LLM costs are prohibitive

**Use Tool-Use:**
- For any production system
- When flexibility matters
- When you want maintainable code
- **Default choice for new development**

---

## Summary

The tool-use architecture represents a paradigm shift from:
- **Fixed workflows** → **Flexible reasoning**
- **Pattern matching** → **Tool selection**
- **Complex graphs** → **Simple flows**
- **Brittle rules** → **LLM agency**

**Bottom line:** Give the LLM good tools and clear guidance, and let it figure out the best approach. This is simpler, more flexible, and easier to maintain than trying to anticipate all possible query patterns upfront.
