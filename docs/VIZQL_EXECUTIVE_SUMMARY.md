# VizQL Query Accuracy Improvement - Executive Summary

**Date:** February 5, 2026  
**Priority:** Critical (Fix Now)  
**Timeline:** 2 weeks  
**Status:** Ready for Implementation

---

## Problem Statement

Our VizQL AI agent currently has a **30% first-attempt success rate** when translating natural language queries to VizQL Data Service queries. This results in:

- **Poor user experience** - Users wait 15-20 seconds for retries
- **High API costs** - Multiple LLM calls per query (3-5x cost)
- **Low adoption** - Users revert to manual query building
- **Wasted compute** - 70% of queries require expensive retry loops

**Root Cause:** The AI agent lacks semantic understanding of:
- Which database fields are measures vs dimensions
- When to apply which aggregation functions (SUM vs AVG vs COUNT)
- Exact field names in the datasource
- Valid field combinations and constraints

---

## Proposed Solution: Hybrid Semantic Query Framework

### High-Level Approach
1. **Enrich datasource metadata** with semantic information (field roles, aggregations, descriptions)
2. **Cache enriched schemas** in Redis for fast access (1-hour TTL)
3. **Provide semantic rules** to the AI (measures require aggregation, exact field names, etc.)
4. **Validate queries semantically** before and after AI generation
5. **Compress context** to reduce token costs by 40%

### User Experience Change
**Before:**
- User asks: "show total sales by region"
- AI guesses field names, often wrong
- Query fails, retries 2-3 times
- Total time: 15-20 seconds

**After:**
- User clicks "Enrich Schema for AI" button (one-time, 3 seconds)
- User asks: "show total sales by region"
- AI uses exact field names and correct aggregations
- Query succeeds immediately
- Total time: 2-3 seconds

---

## Expected Business Impact

### Quantitative Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **First-attempt success rate** | 30% | 70%+ | +133% |
| **Overall success rate** | 50% | 90%+ | +80% |
| **Field hallucination rate** | 40% | <5% | -87.5% |
| **Average query time** | 15-20s | 2-3s | -75% |
| **LLM token cost per query** | 4000 tokens | 2500 tokens | -37.5% |
| **API retry calls** | 2-3x | <1.5x | -50% |

### Qualitative Benefits
- ✅ **Better user trust** - Queries work consistently
- ✅ **Faster iteration** - Users can refine queries quickly
- ✅ **Lower support burden** - Fewer "why didn't this work?" tickets
- ✅ **Increased adoption** - Users prefer AI over manual query building
- ✅ **Scalable foundation** - Applies to all datasources automatically

---

## Cost-Benefit Analysis

### Implementation Cost
- **Engineering time:** 2 weeks (1 engineer)
- **Infrastructure:** Redis caching (already available)
- **Risk:** Low (graceful fallback to existing behavior)

### Annual Savings (Estimated)
Assumptions:
- 10,000 queries per month
- Current retry rate: 70% (7,000 extra LLM calls)
- LLM cost: $0.01 per 1K tokens

**Current monthly cost:**
- Primary queries: 10,000 × 4,000 tokens × $0.01/1K = $400
- Retry queries: 7,000 × 4,000 tokens × $0.01/1K = $280
- **Total: $680/month = $8,160/year**

**New monthly cost:**
- Primary queries: 10,000 × 2,500 tokens × $0.01/1K = $250
- Retry queries: 1,500 × 2,500 tokens × $0.01/1K = $37.50
- **Total: $287.50/month = $3,450/year**

**Annual Savings: $4,710** (58% cost reduction)

Plus:
- Reduced support tickets (~20 hours/month saved)
- Improved user productivity (faster queries)
- Higher feature adoption

**ROI: >500%** (2 weeks implementation for ongoing savings)

---

## Technical Architecture (Simplified)

```
┌──────────────────────────────────────────────────────┐
│ User clicks "Enrich Schema" button (one-time)        │
│   ↓                                                  │
│ Fetch metadata from Tableau VizQL API               │
│   ↓                                                  │
│ Cache enriched schema in Redis (1 hour)             │
└──────────────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────┐
│ User asks natural language query                     │
│   ↓                                                  │
│ Load enriched schema from cache                      │
│   ↓                                                  │
│ AI generates query with semantic guidance           │
│   ↓                                                  │
│ Validate query semantically (catch errors early)    │
│   ↓                                                  │
│ Execute query (or retry with detailed hints)        │
└──────────────────────────────────────────────────────┘
```

**Key Innovation:** Separate build-time rules (static VizQL semantics) from runtime data (datasource-specific metadata) for optimal accuracy and performance.

---

## Implementation Plan

### Week 1: Core Development
- **Days 1-2:** Build VizQL semantic rules engine
- **Days 3-4:** Implement schema enrichment service + UI button
- **Day 5:** Create compressed context builder

### Week 2: Integration & Validation
- **Days 6-7:** Build semantic constraint validator
- **Days 8-9:** Wire components together, end-to-end testing
- **Day 10:** Comprehensive testing, documentation, demo

### Rollout Strategy
- **Week 3:** Staging deployment + beta testing (optional)
- **Week 4:** Production deployment with monitoring
- **Ongoing:** Monitor success rates, gather feedback

---

## Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| VizQL API rate limits | Low | Medium | Aggressive caching (1hr), manual trigger |
| Redis unavailable | Low | Low | In-memory cache fallback |
| Large datasources (1000+ fields) | Medium | Medium | Truncate to top 200 fields |
| LLM still hallucinates | Low | Medium | Enhanced validator catches errors |

### Business Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| User adoption of "Enrich" button | Medium | Medium | Auto-suggest after first failed query |
| Success rate doesn't improve | Low | High | Comprehensive testing before rollout |
| Increased infrastructure cost | Low | Low | Caching reduces API calls |

**Overall Risk Level: LOW**

---

## Success Criteria

### Must Have (Go/No-Go)
- ✅ First-attempt success rate ≥60%
- ✅ Overall success rate ≥80%
- ✅ No increase in error rates
- ✅ Token cost reduction ≥30%

### Nice to Have (Future Enhancements)
- Automatic enrichment on datasource publish
- Query pattern learning (improve examples over time)
- Field relationship recommendations

---

## Dependencies & Requirements

### Technical Dependencies
- ✅ Tableau VizQL API access (already available)
- ✅ Redis instance (already in infrastructure)
- ✅ LangChain framework (already integrated)
- ✅ React/TypeScript frontend (already built)

### Team Dependencies
- **1 Backend Engineer** (Python/FastAPI)
- **0.5 Frontend Engineer** (React UI button)
- **QA/Testing** (Manual test execution)
- **DevOps** (Redis setup, monitoring)

**No external dependencies or blockers identified.**

---

## Alternatives Considered

### Alternative 1: Fine-tune LLM on VizQL queries
- **Pros:** Could improve accuracy
- **Cons:** Expensive ($10K-50K), requires 1000+ labeled queries, weeks of training, hard to maintain
- **Verdict:** Not feasible for current timeline

### Alternative 2: Use OpenAI function calling with full schema
- **Pros:** Structured output
- **Cons:** Still lacks semantic context, token limits for large datasources
- **Verdict:** Doesn't solve core problem

### Alternative 3: Rule-based query builder (no LLM)
- **Pros:** Deterministic, fast
- **Cons:** Can't handle natural language, brittle, requires constant maintenance
- **Verdict:** Defeats purpose of AI agent

**Conclusion:** The proposed Hybrid Semantic Framework is the optimal solution balancing cost, timeline, and effectiveness.

---

## Key Stakeholders

### Engineering
- **Implementation:** Backend team (Python)
- **Review:** AI/ML team lead
- **Testing:** QA team

### Product
- **Approval:** Product Manager
- **UX Review:** Design team (UI button)
- **User Testing:** Beta users

### Operations
- **Infrastructure:** DevOps (Redis monitoring)
- **Support:** Customer success (documentation)

---

## Next Steps

1. ✅ **Approve this plan** - Engineering lead sign-off
2. ✅ **Assign team members** - 1 backend engineer, 0.5 frontend engineer
3. ✅ **Kickoff meeting** - Review detailed implementation plan
4. ✅ **Begin Week 1** - Start development (Days 1-5)
5. ✅ **Weekly check-ins** - Monitor progress, address blockers

**Target Start Date:** Immediate  
**Target Completion Date:** 2 weeks from start

---

## Questions & Answers

**Q: Will this work for all datasources?**  
A: Yes, the approach is generic and works with any Tableau datasource that supports VizQL API.

**Q: What if enrichment fails?**  
A: Graceful fallback to current behavior (basic schema without enrichment).

**Q: Do we need new infrastructure?**  
A: No, Redis is already in our stack. We're adding a new API endpoint and cache keys.

**Q: How do we measure success?**  
A: Track query success rates before/after deployment. Test suite with 20+ queries provides baseline.

**Q: What about international/non-English queries?**  
A: LLM handles multilingual queries. Field names are language-agnostic (from datasource).

**Q: Can we automate enrichment instead of manual button?**  
A: Yes, but deferred to future sprint. Manual trigger ensures we don't overwhelm VizQL API.

---

## Recommendation

**Proceed with implementation immediately.** This is a high-ROI, low-risk improvement that directly addresses our #1 AI agent pain point.

**Expected Outcome:**
- 2.3x improvement in success rate
- 75% reduction in query time
- 58% reduction in LLM costs
- Significantly better user experience

**Investment:** 2 weeks engineering time  
**Return:** Ongoing cost savings + improved adoption

---

## Approval

**Prepared by:** AI Engineering Architect  
**Reviewed by:** ___________________________  
**Approved by:** ___________________________  
**Date:** ___________________________

---

## Appendix: Reference Documents

- **Detailed Plan:** `/docs/VIZQL_QUERY_ACCURACY_IMPROVEMENT_PLAN.md`
- **Implementation Checklist:** `/docs/VIZQL_IMPLEMENTATION_CHECKLIST.md`
- **Architecture Diagram:** `/docs/VIZQL_ARCHITECTURE_DIAGRAM.md`
- **OpenAPI Spec:** `/VizQLDataServiceOpenAPISchema.json`
