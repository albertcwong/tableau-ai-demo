# VizQL Streamlined Agent - Implementation Checklist

## Pre-Development

- [ ] Review and approve full proposal
- [ ] Answer open questions:
  - [ ] Message history format (how many messages? full conversation?)
  - [ ] Caching strategy (in-memory? Redis? TTL?)
  - [ ] Similarity threshold for query reuse (0.8 proposed)
  - [ ] Tool call limits (max calls per query?)
  - [ ] Fallback behavior (retry with current agent on failure?)
- [ ] Set up comparison testing infrastructure
- [ ] Create feature flag in config
- [ ] Create development branch: `feature/vizql-streamlined`

## Phase 1: Tool Implementation (2 days)

### Tool 1: `get_datasource_schema`
- [ ] Create `backend/app/services/agents/vizql_streamlined/tools/schema_tool.py`
- [ ] Implement function to fetch schema via existing API
- [ ] Add caching layer (Redis/in-memory)
- [ ] Add error handling for network/auth failures
- [ ] Write unit tests:
  - [ ] Successful fetch
  - [ ] Cache hit
  - [ ] Network error
  - [ ] Invalid datasource ID
- [ ] Document function with docstring

### Tool 2: `get_datasource_metadata`
- [ ] Create `backend/app/services/agents/vizql_streamlined/tools/metadata_tool.py`
- [ ] Integrate with Tableau REST API client
- [ ] Add error handling
- [ ] Write unit tests:
  - [ ] Successful fetch
  - [ ] Auth error
  - [ ] Datasource not found
- [ ] Document function

### Tool 3: `get_prior_query`
- [ ] Create `backend/app/services/agents/vizql_streamlined/tools/history_tool.py`
- [ ] Implement message history search
- [ ] Add similarity scoring (embeddings or string match)
- [ ] Set up embedding model if using embeddings
- [ ] Write unit tests:
  - [ ] Exact match found
  - [ ] Similar match found (above threshold)
  - [ ] No match (below threshold)
  - [ ] Empty history
- [ ] Document function

### Tool Registry
- [ ] Create `backend/app/services/agents/vizql_streamlined/tools/__init__.py`
- [ ] Register all tools
- [ ] Create tool descriptions for LLM
- [ ] Test tool registration

## Phase 2: Enhanced Query Builder (3 days)

### Core Implementation
- [ ] Create `backend/app/services/agents/vizql_streamlined/nodes/query_builder.py`
- [ ] Integrate tool calling framework (LangChain tool binding)
- [ ] Implement decision logic:
  - [ ] Check message history first
  - [ ] Check for schema in state
  - [ ] Fall back to tool calls
- [ ] Add tool call parsing and execution
- [ ] Capture all reasoning including tool usage

### Prompt Engineering
- [ ] Create prompt template in `backend/app/prompts/agents/vizql_streamlined/query_builder.txt`
- [ ] Add clear instructions for tool usage
- [ ] Add few-shot examples:
  - [ ] Query with schema provided
  - [ ] Query without schema (fetch needed)
  - [ ] Query reuse scenario
  - [ ] Query with retry (validation errors)
- [ ] Test prompt with various scenarios

### Testing
- [ ] Write unit tests:
  - [ ] Schema provided in state (no fetch)
  - [ ] Schema not provided (fetch via tool)
  - [ ] Similar query in history (reuse)
  - [ ] No similar query (build new)
  - [ ] Retry with validation errors
  - [ ] Retry with execution errors
  - [ ] Tool call failure (fallback)
- [ ] Integration tests with mock tools
- [ ] Test reasoning capture

## Phase 3: Node Integration (2 days)

### Validator Node
- [ ] Copy from current vizql agent: `nodes/validator.py`
- [ ] Verify compatibility with new state schema
- [ ] Test with streamlined state
- [ ] No changes expected

### Executor Node
- [ ] Copy from current vizql agent: `nodes/executor.py`
- [ ] Verify compatibility with new state schema
- [ ] Test with streamlined state
- [ ] No changes expected

### Formatter Node
- [ ] Copy from current vizql agent: `nodes/formatter.py`
- [ ] Add reasoning capture logic:
  ```python
  reasoning_steps.append({
      "node": "format_results",
      "timestamp": datetime.utcnow().isoformat(),
      "thought": f"Formatted {row_count} rows",
      "action": "format",
      "output_length": len(final_answer)
  })
  ```
- [ ] Test reasoning capture
- [ ] Verify formatting still works

### Error Handler Node
- [ ] Copy from current vizql agent: `nodes/error_handler.py`
- [ ] Verify compatibility with new state schema
- [ ] Test error scenarios
- [ ] No changes expected

### Node Tests
- [ ] Integration tests for node chain:
  - [ ] build → validate → execute → format
  - [ ] build → validate (fail) → build (retry)
  - [ ] build → validate → execute (fail) → build (retry)
  - [ ] Max retries → error_handler

## Phase 4: Graph Construction (1 day)

### State Schema
- [ ] Create `backend/app/services/agents/vizql_streamlined/state.py`
- [ ] Define `StreamlinedVizQLState` TypedDict
- [ ] Add all required fields:
  - [ ] Input fields (user_query, datasource_id, etc.)
  - [ ] Optional fields (enriched_schema)
  - [ ] Tool output fields (schema, metadata)
  - [ ] Query fields (query_draft, reasoning)
  - [ ] Validation fields (is_valid, errors)
  - [ ] Execution fields (results, status)
  - [ ] Formatting fields (final_answer)
  - [ ] Control fields (attempt, current_thought)
  - [ ] NEW: reasoning_steps list
- [ ] Document all fields

### Graph Definition
- [ ] Create `backend/app/services/agents/vizql_streamlined/graph.py`
- [ ] Implement `create_streamlined_vizql_graph()` function
- [ ] Add all nodes to graph
- [ ] Set entry point to `build_query`
- [ ] Add edges:
  - [ ] build_query → validate_query
  - [ ] validate_query → [execute_query | build_query | error_handler]
  - [ ] execute_query → [format_results | build_query | error_handler]
  - [ ] format_results → END
  - [ ] error_handler → END

### Routing Functions
- [ ] Implement `route_after_validation`:
  - [ ] If valid → execute_query
  - [ ] If invalid and attempt < 3 → build_query
  - [ ] Else → error_handler
- [ ] Implement `route_after_execution`:
  - [ ] If success → format_results
  - [ ] If failed and attempt < 3 → build_query
  - [ ] Else → error_handler
- [ ] Test routing logic

### Memory/Checkpointing
- [ ] Add MemorySaver for checkpointing
- [ ] Test resume functionality
- [ ] Verify state persistence

### Graph Tests
- [ ] Test graph compilation
- [ ] Test full execution paths:
  - [ ] Happy path (success)
  - [ ] Validation retry path
  - [ ] Execution retry path
  - [ ] Error path
- [ ] Test state updates at each step

## Phase 5: Factory Integration (0.5 days)

### Graph Factory
- [ ] Update `backend/app/services/agents/graph_factory.py`
- [ ] Add `use_streamlined` parameter to `create_vizql_graph()`
- [ ] Import streamlined graph builder
- [ ] Add conditional logic:
  ```python
  if use_streamlined:
      from app.services.agents.vizql_streamlined.graph import create_streamlined_vizql_graph
      return create_streamlined_vizql_graph()
  ```
- [ ] Test factory with new flag

### Configuration
- [ ] Add feature flag to `backend/app/core/config.py`:
  ```python
  USE_STREAMLINED_VIZQL: bool = False
  ```
- [ ] Add environment variable `USE_STREAMLINED_VIZQL`
- [ ] Update `.env.example`

### API Integration
- [ ] Update API endpoint to support agent selection
- [ ] Add query parameter `?agent=streamlined` (optional)
- [ ] Update request validation
- [ ] Test API with both agents

## Phase 6: Testing & Validation (3 days)

### Unit Tests
- [ ] All tool tests passing
- [ ] All node tests passing
- [ ] All routing function tests passing
- [ ] State schema tests

### Integration Tests
- [ ] Full graph execution tests
- [ ] Error handling tests
- [ ] Retry logic tests
- [ ] Tool integration tests

### Comparison Tests
- [ ] Set up test suite: `tests/agents/test_agent_comparison.py`
- [ ] Create test query set (20+ diverse queries)
- [ ] Run queries on both agents
- [ ] Compare results:
  - [ ] Correctness (same answer)
  - [ ] Latency (time taken)
  - [ ] Token usage
  - [ ] Success rate
- [ ] Document differences
- [ ] Investigate failures

### Edge Case Tests
- [ ] Query with pre-provided enriched schema
- [ ] Query without schema (must fetch)
- [ ] Query similar to prior message (reuse)
- [ ] Complex query with multiple retries
- [ ] Invalid datasource ID
- [ ] Network timeout
- [ ] Auth failure
- [ ] Empty results
- [ ] Large results (10k+ rows)

### Performance Tests
- [ ] Measure P50, P95, P99 latency
- [ ] Measure token usage per query
- [ ] Measure schema fetch rate
- [ ] Measure query reuse rate
- [ ] Measure first-try success rate
- [ ] Compare against targets

### Regression Tests
- [ ] Ensure accuracy >= 95% vs current agent
- [ ] Ensure no critical functionality lost
- [ ] Test error messages are helpful

## Phase 7: Monitoring & Metrics (1 day)

### Logging
- [ ] Add structured logging to all nodes
- [ ] Log entry/exit timestamps
- [ ] Log tool calls and results
- [ ] Log reasoning at each step
- [ ] Log errors with context

### Metrics
- [ ] Add timing decorators to nodes
- [ ] Track per-node execution time
- [ ] Track tool call frequency
- [ ] Track query reuse rate
- [ ] Track retry rate
- [ ] Track success/failure rate

### Dashboards
- [ ] Create metrics dashboard
- [ ] Add latency charts (P50, P95, P99)
- [ ] Add success rate chart
- [ ] Add tool usage chart
- [ ] Add comparison chart (current vs streamlined)

### Alerts
- [ ] Set up alerts for high error rate
- [ ] Set up alerts for high latency
- [ ] Set up alerts for low success rate

## Rollout Preparation

### Documentation
- [ ] Update API documentation
- [ ] Write deployment guide
- [ ] Write troubleshooting guide
- [ ] Document differences from current agent
- [ ] Create runbook for common issues

### Deployment
- [ ] Create deployment plan
- [ ] Test in staging environment
- [ ] Create rollback plan
- [ ] Set up feature flag control

### Phase 1: Internal Testing (Week 1)
- [ ] Deploy to dev environment with feature flag
- [ ] Internal team testing (5+ team members)
- [ ] Collect feedback
- [ ] Fix critical bugs
- [ ] Document known issues

### Phase 2: Shadow Mode (Week 2)
- [ ] Deploy to staging
- [ ] Run both agents in parallel
- [ ] Don't expose streamlined to users
- [ ] Collect metrics:
  - [ ] Latency comparison
  - [ ] Accuracy comparison
  - [ ] Error rate comparison
- [ ] Analyze results
- [ ] Fix issues

### Phase 3: A/B Test (Week 3)
- [ ] Deploy to production with feature flag OFF
- [ ] Enable for 10% of traffic
- [ ] Monitor metrics closely:
  - [ ] Error rate
  - [ ] Latency
  - [ ] User complaints
- [ ] Collect user feedback
- [ ] Fix issues
- [ ] Decision point: continue or rollback?

### Phase 4: Gradual Rollout (Week 4+)
- [ ] Increase to 25% traffic
- [ ] Monitor for 2 days
- [ ] Increase to 50% traffic
- [ ] Monitor for 2 days
- [ ] Increase to 75% traffic
- [ ] Monitor for 2 days
- [ ] Increase to 100% traffic
- [ ] Monitor for 1 week
- [ ] Make streamlined default
- [ ] Keep current agent as fallback option

## Post-Launch

### Monitoring
- [ ] Daily metrics review (first week)
- [ ] Weekly metrics review (first month)
- [ ] Monthly metrics review (ongoing)

### Optimization
- [ ] Analyze slow queries
- [ ] Optimize tool performance
- [ ] Optimize prompts
- [ ] Tune similarity threshold
- [ ] Improve caching

### Documentation
- [ ] Document lessons learned
- [ ] Update architecture docs
- [ ] Update API docs
- [ ] Share results with team

### Cleanup
- [ ] Remove debug logging
- [ ] Archive comparison test data
- [ ] Update status page
- [ ] Celebrate! 🎉

---

## Quick Reference

### Key Files to Create
```
backend/app/services/agents/vizql_streamlined/
├── __init__.py
├── state.py
├── graph.py
├── tools/
│   ├── __init__.py
│   ├── schema_tool.py
│   ├── metadata_tool.py
│   └── history_tool.py
└── nodes/
    ├── __init__.py
    ├── query_builder.py
    ├── validator.py
    ├── executor.py
    ├── formatter.py
    └── error_handler.py

backend/app/prompts/agents/vizql_streamlined/
└── query_builder.txt

tests/agents/vizql_streamlined/
├── test_tools.py
├── test_nodes.py
├── test_graph.py
└── test_comparison.py
```

### Success Metrics
- [ ] Latency: P50 < 4s (target)
- [ ] Latency: P95 < 8s (target)
- [ ] Schema fetch rate: < 50% (target)
- [ ] Query reuse rate: > 30% (target)
- [ ] First-try success: > 85% (target)
- [ ] Token usage: -20% (target)
- [ ] Accuracy: >= 95% vs current (required)

### Decision Points
1. **After Phase 6 (Testing):** Continue to rollout or iterate?
2. **After Week 1 (Internal):** Ready for shadow mode?
3. **After Week 2 (Shadow):** Ready for A/B test?
4. **After Week 3 (10% A/B):** Increase or rollback?
5. **After Week 4 (50% rollout):** Make default?

---

**Total Estimated Time:** 12.5 days development + 4 weeks rollout
**Team Size:** 2-3 engineers recommended
**Priority:** High (performance comparison critical)
