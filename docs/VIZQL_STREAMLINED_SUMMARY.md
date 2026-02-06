# VizQL Streamlined Agent - Executive Summary

## Overview
Streamlined variation of VizQL agent for performance comparison.

## Key Changes

### Removed Nodes
- ❌ **Router** - Takes too long, ineffective shortcut
- ❌ **Planner** - Adds LLM call overhead, planning merged into query building
- ❌ **Schema Fetch** - Inflexible, now optional via tools

### Enhanced Nodes
- ✅ **Build Query** - Now has tools and intelligence:
  - `get_datasource_schema` - Fetch only if needed
  - `get_datasource_metadata` - Get REST API info
  - `get_prior_query` - Reuse from conversation history
  - Makes smart decisions about what to fetch
  - Can reuse queries from prior messages

### Kept Nodes (Proven Effective)
- ✅ **Validator** - Fast, reliable local validation
- ✅ **Executor** - Works well as-is
- ✅ **Formatter** - Effective, now captured in reasoning steps
- ✅ **Error Handler** - Comprehensive error handling

## Architecture

### Before (Current Agent)
```
router → planner → schema_fetch → build_query → validator → executor → formatter
```

### After (Streamlined Agent)
```
build_query (with tools) → validator → executor → formatter
```

## Performance Targets

| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|
| P50 Latency | ~6s | < 4s | **-33%** |
| P95 Latency | ~12s | < 8s | **-33%** |
| Schema Fetch Rate | 100% | < 50% | **-50%** |
| Query Reuse | 0% | > 30% | **NEW** |
| Token Usage | Baseline | -20% | **-20%** |
| First-Try Success | ~80% | > 85% | **+5%** |

## Key Benefits

1. **Faster** - Fewer nodes, optional schema fetching
2. **Smarter** - Can reuse queries from conversation
3. **Flexible** - Tools let LLM make context-aware decisions
4. **Cheaper** - Fewer LLM calls = lower token usage
5. **Simpler** - 4 nodes instead of 7 = easier debugging

## Implementation Timeline

| Phase | Duration |
|-------|----------|
| Tool Implementation | 2 days |
| Enhanced Query Builder | 3 days |
| Node Integration | 2 days |
| Graph Construction | 1 day |
| Factory Integration | 0.5 days |
| Testing & Validation | 3 days |
| Monitoring & Metrics | 1 day |
| **Total Development** | **12.5 days (~2.5 weeks)** |
| Rollout (4 phases) | 4 weeks |
| **Total Project** | **~6.5 weeks** |

## Rollout Strategy

1. **Week 1:** Internal testing in dev
2. **Week 2:** Shadow mode (parallel run, no user exposure)
3. **Week 3:** A/B test with 10% traffic
4. **Week 4+:** Gradual increase to 100%

## Success Criteria

**Required:**
- Comparable accuracy (> 95% vs current)
- 20%+ latency improvement
- Query reuse works in conversations
- All tests pass

**Nice to Have:**
- 20%+ token reduction
- Higher first-try success
- Better error messages

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Tool usage increases latency | Tools optional, cached, parallel execution |
| LLM misuses tools | Clear prompts, examples, fallbacks |
| Query reuse produces wrong results | Conservative threshold, validation |
| Accuracy regression | Comparison testing, A/B rollout |

## Next Steps

1. ✅ Review and approve proposal
2. Answer open questions (caching, similarity threshold, message format)
3. Begin tool implementation
4. Set up comparison testing infrastructure

## File Structure

```
backend/app/services/agents/vizql_streamlined/
├── __init__.py
├── state.py                    # State schema
├── graph.py                    # Graph definition
├── tools/
│   ├── __init__.py
│   ├── schema_tool.py         # get_datasource_schema
│   ├── metadata_tool.py       # get_datasource_metadata
│   └── history_tool.py        # get_prior_query
└── nodes/
    ├── __init__.py
    ├── query_builder.py       # Enhanced with tools
    ├── validator.py           # Keep as-is
    ├── executor.py            # Keep as-is
    ├── formatter.py           # Add reasoning capture
    └── error_handler.py       # Keep as-is
```

---

**Status:** Ready for Implementation
**Full Proposal:** See `VIZQL_STREAMLINED_AGENT_PROPOSAL.md`
