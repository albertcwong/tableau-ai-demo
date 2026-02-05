# VizQL Query Accuracy - Implementation Checklist

**Sprint Goal:** Improve VizQL query success rate from 30% → 70%+  
**Timeline:** 2 weeks (10 working days)

---

## Phase 1: VizQL Rule Engine (Days 1-2)

### Day 1
- [ ] Create `backend/app/services/agents/vizql/semantic_rules.py`
  - [ ] Define `VIZQL_DATA_TYPES` constant
  - [ ] Define `VIZQL_FIELD_ROLES` dict
  - [ ] Define `VIZQL_AGGREGATIONS` dict with use cases
  - [ ] Implement `suggest_aggregation()` function
  - [ ] Implement `validate_aggregation_for_type()` function
  - [ ] Add unit tests for aggregation suggestions

- [ ] Create `backend/app/prompts/agents/vizql/semantic_rules.txt`
  - [ ] Document MEASURE vs DIMENSION rules
  - [ ] Add aggregation selection guide
  - [ ] Add field name matching rules

### Day 2
- [ ] Test semantic rules with sample fields
- [ ] Verify aggregation suggestions work correctly
- [ ] Code review for Phase 1
- [ ] Merge Phase 1 PR

**Acceptance Criteria:**
- ✅ `suggest_aggregation("Total Sales", "REAL")` returns "SUM"
- ✅ `suggest_aggregation("Customer ID", "STRING")` returns "COUNT"
- ✅ `validate_aggregation_for_type("AVG", "STRING")` returns False

---

## Phase 2: Schema Enrichment Service (Days 3-4)

### Day 3
- [ ] Add VizQL API methods to `backend/app/services/tableau/client.py`
  - [ ] `async def read_metadata(datasource_id: str)`
  - [ ] `async def list_supported_functions(datasource_id: str)`
  - [ ] Test with real Tableau instance

- [ ] Create `backend/app/services/agents/vizql/schema_enrichment.py`
  - [ ] Implement `SchemaEnrichmentService` class
  - [ ] Implement `enrich_datasource_schema()` method
  - [ ] Add Redis caching with 1hr TTL
  - [ ] Handle enrichment errors gracefully

### Day 4
- [ ] Create `backend/app/api/vizql.py`
  - [ ] POST `/api/vizql/datasources/{id}/enrich-schema` endpoint
  - [ ] Add force_refresh parameter
  - [ ] Return enrichment statistics

- [ ] Create `frontend/components/explorer/DatasourceEnrichButton.tsx`
  - [ ] Button with loading state
  - [ ] Call enrichment API
  - [ ] Display success message with stats
  - [ ] Handle errors

- [ ] Integrate button into datasource explorer UI
- [ ] Test end-to-end: UI → API → VizQL → Redis cache

**Acceptance Criteria:**
- ✅ Clicking "Enrich Schema" button calls API
- ✅ Enriched schema cached in Redis for 1 hour
- ✅ UI shows: "Enriched: 47 fields (23 measures, 24 dimensions)"
- ✅ Subsequent calls use cached data

---

## Phase 3: Compressed Context Builder (Day 5)

### Day 5
- [ ] Create `backend/app/services/agents/vizql/context_builder.py`
  - [ ] Implement `build_compressed_schema_context()`
  - [ ] Implement `build_semantic_hints()`
  - [ ] Test output format is token-efficient

- [ ] Update `backend/app/prompts/agents/vizql/query_construction.txt`
  - [ ] Replace `{{ schema }}` with `{{ compressed_schema }}`
  - [ ] Add `{{ semantic_hints }}` section
  - [ ] Add VizQL rules section (MEASURES REQUIRE AGGREGATION)
  - [ ] Emphasize EXACT fieldCaption matching

- [ ] Test compressed context with GPT-4
  - [ ] Verify token count reduction (target: 40% reduction)
  - [ ] Ensure LLM still understands schema

**Acceptance Criteria:**
- ✅ Compressed schema uses <2500 tokens for 50-field datasource
- ✅ Format: `Total Sales (REAL) [MEASURE] {default: SUM}`
- ✅ Includes measure/dimension categorization

---

## Phase 4: Semantic Constraint Validator (Days 6-7)

### Day 6
- [ ] Create `backend/app/services/agents/vizql/constraint_validator.py`
  - [ ] Implement `VizQLConstraintValidator` class
  - [ ] Implement `validate_query()` method
    - [ ] Check MEASURE fields have aggregation
    - [ ] Check DIMENSION fields don't have aggregation
    - [ ] Validate aggregation compatibility with data type
  - [ ] Implement `_find_close_matches()` for fuzzy matching
  - [ ] Add detailed suggestion messages

### Day 7
- [ ] Update `backend/app/services/agents/vizql/nodes/validator.py`
  - [ ] Import `VizQLConstraintValidator`
  - [ ] Add semantic validation after syntax validation
  - [ ] Append semantic errors to existing errors list
  - [ ] Append suggestions to existing suggestions list

- [ ] Test validator with intentionally broken queries
  - [ ] Missing aggregation on MEASURE
  - [ ] Aggregation on DIMENSION
  - [ ] Invalid aggregation for data type

**Acceptance Criteria:**
- ✅ Query with MEASURE missing aggregation fails validation
- ✅ Error message: "MEASURE field 'Sales' requires aggregation function"
- ✅ Suggestion: "Add: {\"fieldCaption\": \"Sales\", \"function\": \"SUM\"}"

---

## Phase 5: Integration (Days 8-9)

### Day 8
- [ ] Update `backend/app/services/agents/vizql/nodes/schema_fetch.py`
  - [ ] Import `SchemaEnrichmentService`
  - [ ] Call `enrich_datasource_schema()` instead of basic schema
  - [ ] Add `enriched_schema` to state
  - [ ] Fallback to basic schema if enrichment fails

- [ ] Update `backend/app/services/agents/vizql/nodes/query_builder.py`
  - [ ] Import context builder functions
  - [ ] Build compressed context from enriched schema
  - [ ] Pass compressed context to LLM prompt
  - [ ] Update prompt variables

### Day 9
- [ ] End-to-end testing
  - [ ] Test full flow: Enrich → Query → Validate → Execute
  - [ ] Test with 5 different datasources
  - [ ] Test cache hit/miss scenarios
  - [ ] Test error handling (VizQL API down, Redis down, etc.)

- [ ] Integration with existing VizQL graph
  - [ ] Ensure backward compatibility
  - [ ] Test with legacy schemas (no enrichment)

**Acceptance Criteria:**
- ✅ Full VizQL agent flow works with enriched schema
- ✅ Graceful fallback when enrichment unavailable
- ✅ Token usage reduced by 30-40%

---

## Phase 6: Validation & Documentation (Day 10)

### Day 10
- [ ] Run comprehensive test suite
  - [ ] Test 20+ real queries (see test plan in main doc)
  - [ ] Record success rates before/after
  - [ ] Measure token usage before/after
  - [ ] Document field hallucination rate

- [ ] Create results document
  - [ ] Success rate comparison table
  - [ ] Example queries with before/after results
  - [ ] Token cost savings analysis
  - [ ] Known limitations & edge cases

- [ ] Update team documentation
  - [ ] README with new enrichment feature
  - [ ] API documentation for new endpoint
  - [ ] Troubleshooting guide

- [ ] Demo to stakeholders
  - [ ] Show UI enrichment button
  - [ ] Demonstrate improved query accuracy
  - [ ] Present metrics

**Acceptance Criteria:**
- ✅ First-attempt success rate >60% (target: 70%)
- ✅ Field hallucination rate <10% (target: <5%)
- ✅ Team can replicate results
- ✅ Stakeholders approve for production

---

## Daily Standups (Check-ins)

### Daily Questions
1. What did I complete yesterday?
2. What am I working on today?
3. Any blockers?

### Key Blockers to Watch
- Redis not available in dev environment → Use in-memory cache fallback
- VizQL API auth issues → Verify X-Tableau-Auth token works
- Large datasource performance → Implement field truncation
- LLM still hallucinates → Review prompt wording, add more examples

---

## Testing Checklist

### Unit Tests
- [ ] `semantic_rules.py` - aggregation suggestion logic
- [ ] `context_builder.py` - compressed format generation
- [ ] `constraint_validator.py` - semantic validation rules

### Integration Tests
- [ ] Schema enrichment API endpoint
- [ ] Redis caching layer
- [ ] VizQL node updates (schema_fetch, query_builder, validator)

### End-to-End Tests
- [ ] UI button → API → Cache → VizQL → Success
- [ ] Query construction with enriched schema
- [ ] Validation catches semantic errors
- [ ] Error messages guide LLM to fix

### Manual Testing (20 Queries)
1. [ ] "show total sales by region"
2. [ ] "average price per product category"
3. [ ] "count of orders by month in 2024"
4. [ ] "top 10 customers by revenue"
5. [ ] "sum of profits for each state"
6. [ ] "distinct count of products sold"
7. [ ] "min and max order dates"
8. [ ] "median sales per transaction"
9. [ ] "total quantity by category and region"
10. [ ] "year over year revenue comparison"
11. [ ] "customers with more than 5 orders"
12. [ ] "products with zero sales"
13. [ ] "average days between orders"
14. [ ] "top selling product by state"
15. [ ] "monthly sales trend for 2023"
16. [ ] "percentage of total sales by region"
17. [ ] "products below average price"
18. [ ] "customers by lifetime value"
19. [ ] "sales by day of week"
20. [ ] "correlation between price and quantity"

**Success Criteria per Query:**
- ✅ First attempt generates valid query
- ✅ No field name hallucinations
- ✅ Correct aggregation functions
- ✅ Query executes successfully
- ✅ Results match user intent

---

## Rollout Plan

### Week 1: Development (Days 1-5)
- Build all components
- Local testing

### Week 2: Integration & Testing (Days 6-10)
- Wire components together
- Comprehensive testing
- Documentation

### Week 3: Soft Launch (Optional)
- Deploy to staging
- Beta testing with select users
- Monitor metrics

### Week 4: Production
- Production deployment
- Monitor success rates
- Gather user feedback

---

## Metrics to Track

### Before Implementation (Baseline)
- First-attempt success rate: **~30%**
- After 3 retries success rate: **~50%**
- Field hallucination rate: **~40%**
- Avg tokens per query: **~4000**

### After Implementation (Target)
- First-attempt success rate: **>70%**
- After 3 retries success rate: **>90%**
- Field hallucination rate: **<5%**
- Avg tokens per query: **~2500**

### How to Measure
1. Run 20 test queries before implementation → record results
2. Implement changes
3. Run same 20 queries after implementation → record results
4. Calculate improvement percentages
5. Document in results file

---

## Emergency Rollback Plan

If production issues occur:

1. **Disable enrichment feature**
   ```python
   # Feature flag in settings
   ENABLE_SCHEMA_ENRICHMENT = False
   ```

2. **Clear Redis cache**
   ```bash
   redis-cli FLUSHDB
   ```

3. **Revert to previous prompt**
   - Restore original `query_construction.txt`

4. **Monitor error rates**
   - Check logs for enrichment failures
   - Verify fallback to basic schema works

---

## Success Indicators

### Week 1 End
- ✅ All components built
- ✅ Unit tests passing
- ✅ UI button functional

### Week 2 End
- ✅ Integration complete
- ✅ Test suite passes
- ✅ Metrics show improvement

### Production
- ✅ Success rate >60%
- ✅ No increase in error rates
- ✅ User feedback positive

---

## Questions & Answers

**Q: What if Redis isn't available?**  
A: Implement in-memory cache fallback using `functools.lru_cache`

**Q: What if VizQL API is slow?**  
A: Aggressive caching (1hr TTL) + async processing

**Q: What if large datasource has 1000+ fields?**  
A: Truncate to top 200 most-used fields in context

**Q: What if LLM still hallucinates?**  
A: Enhanced validator catches errors + detailed correction hints

---

**Last Updated:** 2026-02-05  
**Owner:** Engineering Team  
**Status:** Ready to Start
