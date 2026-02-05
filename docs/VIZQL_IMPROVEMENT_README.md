# VizQL Query Accuracy Improvement - Documentation Index

**Project Goal:** Improve VizQL AI agent success rate from 30% to 70%+  
**Timeline:** 2 weeks  
**Status:** Ready for Implementation

---

## Document Guide

### 👥 For Stakeholders & Leadership
**Start here:** [`VIZQL_EXECUTIVE_SUMMARY.md`](./VIZQL_EXECUTIVE_SUMMARY.md)
- Business impact and ROI
- Cost-benefit analysis
- Risk assessment
- 5-minute read

### 🏗️ For Engineering Team
**Start here:** [`VIZQL_IMPLEMENTATION_CHECKLIST.md`](./VIZQL_IMPLEMENTATION_CHECKLIST.md)
- Day-by-day task breakdown
- Acceptance criteria for each phase
- Testing checklist
- Daily standup guide

**Then read:** [`VIZQL_QUERY_ACCURACY_IMPROVEMENT_PLAN.md`](./VIZQL_QUERY_ACCURACY_IMPROVEMENT_PLAN.md)
- Detailed implementation plan
- Code examples and file structure
- API specifications
- Complete technical design

### 🎨 For Architects & Tech Leads
**Start here:** [`VIZQL_ARCHITECTURE_DIAGRAM.md`](./VIZQL_ARCHITECTURE_DIAGRAM.md)
- Visual architecture diagrams
- Before/after comparison
- Data flow
- Component descriptions

---

## Quick Summary

### Problem
VizQL agent has low success rate because it:
- Hallucinates field names (invents "sales" instead of "Total Sales")
- Doesn't know when to use aggregations (SUM vs AVG vs COUNT)
- Lacks understanding of measure vs dimension behavior

### Solution
Hybrid Semantic Query Framework with 5 layers:
1. **VizQL Rule Engine** - Static semantic rules (build-time)
2. **Schema Enrichment** - On-demand metadata via UI button (runtime)
3. **Compressed Context** - Token-efficient schema format (-40% tokens)
4. **Semantic Validator** - Pre/post LLM validation with detailed errors
5. **Enhanced Prompts** - Guide LLM with exact field names and rules

### User Flow
```
[One-time] User clicks "Enrich Schema for AI" button
           ↓
           Enriched metadata cached in Redis (1 hour)

[Each Query] User asks: "show total sales by region"
             ↓
             AI uses enriched schema + semantic rules
             ↓
             Query succeeds on first attempt (70%+ success rate)
```

### Key Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| First-attempt success | 30% | 70%+ | +133% |
| Query time | 15-20s | 2-3s | -75% |
| Token cost | 4000 | 2500 | -37.5% |
| Field hallucinations | 40% | <5% | -87.5% |

---

## Implementation Timeline

### Week 1: Build Components
- **Days 1-2:** VizQL semantic rules engine
- **Days 3-4:** Schema enrichment service + UI button
- **Day 5:** Compressed context builder

### Week 2: Integration & Testing
- **Days 6-7:** Semantic constraint validator
- **Days 8-9:** Wire everything together
- **Day 10:** Testing, documentation, demo

---

## File Structure

```
docs/
├── VIZQL_IMPROVEMENT_README.md           # This file (start here)
├── VIZQL_EXECUTIVE_SUMMARY.md            # For stakeholders
├── VIZQL_IMPLEMENTATION_CHECKLIST.md     # For engineers (daily tasks)
├── VIZQL_QUERY_ACCURACY_IMPROVEMENT_PLAN.md  # Detailed tech plan
└── VIZQL_ARCHITECTURE_DIAGRAM.md         # Visual architecture

backend/app/services/agents/vizql/
├── semantic_rules.py                     # NEW: VizQL rules
├── schema_enrichment.py                  # NEW: Enrichment service
├── context_builder.py                    # NEW: Compressed context
├── constraint_validator.py               # NEW: Semantic validator
└── nodes/
    ├── schema_fetch.py                   # UPDATED
    ├── query_builder.py                  # UPDATED
    └── validator.py                      # UPDATED

backend/app/api/
└── vizql.py                              # NEW: Enrichment endpoint

frontend/components/explorer/
└── DatasourceEnrichButton.tsx            # NEW: UI button

VizQLDataServiceOpenAPISchema.json        # Reference (Tableau API spec)
```

---

## Getting Started

### For Engineering Team

1. **Read the checklist**
   ```bash
   open docs/VIZQL_IMPLEMENTATION_CHECKLIST.md
   ```

2. **Set up development environment**
   ```bash
   # Ensure Redis is running
   redis-cli ping  # Should return PONG
   
   # Install dependencies (if needed)
   pip install redis langchain-core
   ```

3. **Review VizQL API spec**
   ```bash
   open VizQLDataServiceOpenAPISchema.json
   # Key endpoints: /read-metadata, /list-supported-functions
   ```

4. **Start with Phase 1**
   - Create `semantic_rules.py`
   - Implement aggregation suggestion logic
   - Write unit tests

### For Stakeholders

1. **Read executive summary**
   ```bash
   open docs/VIZQL_EXECUTIVE_SUMMARY.md
   ```

2. **Review cost-benefit analysis**
   - ROI: >500%
   - Annual savings: $4,710 + support hours
   - 2-week implementation

3. **Approve and assign resources**
   - 1 backend engineer
   - 0.5 frontend engineer
   - QA support

---

## Key Design Decisions

### Why Manual Enrichment Button?
- **Scalability:** Prevents overwhelming VizQL API with automatic requests
- **User Control:** Users decide when to enrich (not forced)
- **Testing Friendly:** Easy to test enrichment separately
- **Future-Proof:** Can add automation later without changing architecture

### Why Redis Caching?
- **Performance:** <50ms cache lookups vs 2-5s API calls
- **Cost Efficiency:** Reduces VizQL API calls by 95%+
- **TTL:** 1-hour expiry balances freshness and caching benefits
- **Fallback:** Graceful degradation to basic schema if cache misses

### Why Compressed Context?
- **Token Cost:** 40% reduction (4000→2500 tokens)
- **Latency:** Faster LLM responses with smaller context
- **Clarity:** Compact format easier for LLM to parse
- **Scalability:** Works with large datasources (1000+ fields)

### Why Semantic Validator?
- **Proactive:** Catches errors before execution
- **Guided Retry:** Provides specific correction hints
- **Domain Knowledge:** Encodes VizQL-specific rules
- **Maintainable:** Centralized validation logic

---

## Success Metrics (How to Measure)

### Before Implementation
1. Run 20 test queries on current system
2. Record:
   - Success/fail on first attempt
   - Total attempts needed
   - Field hallucinations
   - Token usage
   - Time to completion

### After Implementation
1. Enrich test datasources via UI button
2. Run same 20 queries on new system
3. Record same metrics
4. Calculate improvement percentages

### Target Metrics
- ✅ First-attempt success ≥60% (stretch: 70%)
- ✅ Field hallucination <10% (stretch: <5%)
- ✅ Token usage <3000 (stretch: <2500)
- ✅ Query time <5s (stretch: <3s)

---

## FAQ

**Q: Do we need to change the database?**  
A: No, only adding Redis cache keys. No schema changes.

**Q: Will existing queries break?**  
A: No, graceful fallback to current behavior if enrichment unavailable.

**Q: How do we handle schema changes in Tableau?**  
A: 1-hour cache TTL auto-refreshes. Manual refresh button for immediate updates.

**Q: What if VizQL API is down?**  
A: Fallback to basic schema (current behavior). Enrichment is optional enhancement.

**Q: Do all users need to click "Enrich"?**  
A: No, enrichment is per-datasource, not per-user. Any user's enrichment benefits all users.

---

## Dependencies

### Infrastructure
- ✅ Redis (already deployed)
- ✅ Tableau Server with VizQL API
- ✅ Python 3.10+
- ✅ FastAPI backend

### External APIs
- ✅ Tableau VizQL Data Service API
  - `/read-metadata` endpoint
  - `/list-supported-functions` endpoint
  - `X-Tableau-Auth` authentication

### Libraries
- ✅ `redis>=4.0.0`
- ✅ `langchain-core`
- ✅ `pydantic`
- ✅ `fastapi`

---

## Rollout Plan

### Phase 0: Approval & Kickoff (Day 0)
- [ ] Stakeholder approval
- [ ] Assign team members
- [ ] Set up project tracking

### Phase 1: Development (Week 1)
- [ ] Build core components
- [ ] Unit tests passing
- [ ] Code review completed

### Phase 2: Integration (Week 2)
- [ ] Wire components together
- [ ] Integration tests passing
- [ ] Manual testing completed

### Phase 3: Deployment (Week 3, optional staging)
- [ ] Deploy to staging
- [ ] Beta user testing
- [ ] Monitor metrics

### Phase 4: Production (Week 3-4)
- [ ] Production deployment
- [ ] Monitor success rates
- [ ] Gather user feedback

---

## Support & Contact

**Project Lead:** TBD  
**Engineering Lead:** TBD  
**Product Manager:** TBD  

**Slack Channel:** #vizql-improvement  
**Jira Epic:** TBD  
**GitHub Branch:** `feature/vizql-semantic-framework`

---

## References

### Internal Documentation
- VizQL Agent Implementation Guide
- Tableau Integration Documentation
- Redis Setup Guide

### External Resources
- [Tableau VizQL Data Service API Docs](https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_concepts_data_api.htm)
- [LangChain Documentation](https://python.langchain.com/docs/get_started/introduction)
- [Redis Caching Best Practices](https://redis.io/docs/manual/patterns/cache/)

---

## Changelog

**2026-02-05:** Initial documentation created
- Executive summary
- Implementation plan
- Checklist
- Architecture diagrams

---

**Ready to Start? → Open [`VIZQL_IMPLEMENTATION_CHECKLIST.md`](./VIZQL_IMPLEMENTATION_CHECKLIST.md) and begin Day 1 tasks!**
