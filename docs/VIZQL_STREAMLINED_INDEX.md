# VizQL Streamlined Agent - Documentation Index

## Overview

This directory contains the complete engineering documentation for the **VizQL Streamlined Agent** - a performance-optimized variation of the current VizQL agent designed for direct comparison.

**Project Goal:** Create a streamlined agent that removes routing/planning overhead and adds intelligent query building with tools, targeting 20-30% latency improvement.

---

## 📚 Documentation Files

### 1. [Executive Summary](./VIZQL_STREAMLINED_SUMMARY.md)
**Start here!** Quick 2-page overview of the project.

**Contents:**
- Key changes (what's removed, enhanced, kept)
- Architecture before/after
- Performance targets
- Benefits
- Timeline
- Success criteria

**Read this if:** You need a quick understanding or executive briefing.

---

### 2. [Full Engineering Proposal](./VIZQL_STREAMLINED_AGENT_PROPOSAL.md)
**Most comprehensive.** Complete 20+ page engineering specification.

**Contents:**
- Detailed motivation and analysis
- Node-by-node specifications
- Tool definitions
- State schema
- Implementation plan (7 phases)
- Testing strategy
- Monitoring & metrics
- Risk mitigation
- Rollout strategy
- Open questions

**Read this if:** You're implementing the system or need full technical details.

---

### 3. [Architecture Comparison](./VIZQL_COMPARISON_DIAGRAM.md)
**Visual diagrams.** Side-by-side comparison of current vs streamlined.

**Contents:**
- Flow diagrams (current vs streamlined)
- Side-by-side feature comparison
- Latency breakdown analysis
- Token usage comparison
- Tool usage patterns
- Decision flow diagrams
- Performance projections

**Read this if:** You want visual understanding or need to present to stakeholders.

---

### 4. [Implementation Checklist](./VIZQL_STREAMLINED_CHECKLIST.md)
**Actionable tasks.** Complete checkbox-based implementation plan.

**Contents:**
- Pre-development tasks
- Phase 1-7 task breakdowns
- Testing checklist
- Deployment checklist
- Rollout phases
- Success metrics
- Decision points

**Use this if:** You're actively implementing and need task tracking.

---

## 🎯 Quick Navigation

### By Role

**Executive/Product Manager:**
→ Start with [Executive Summary](./VIZQL_STREAMLINED_SUMMARY.md)
→ Review [Architecture Comparison](./VIZQL_COMPARISON_DIAGRAM.md) for performance projections

**Engineering Manager:**
→ Read [Executive Summary](./VIZQL_STREAMLINED_SUMMARY.md)
→ Review [Full Proposal](./VIZQL_STREAMLINED_AGENT_PROPOSAL.md) for timeline and resources
→ Use [Implementation Checklist](./VIZQL_STREAMLINED_CHECKLIST.md) for planning

**Software Engineer:**
→ Skim [Executive Summary](./VIZQL_STREAMLINED_SUMMARY.md)
→ Deep-dive [Full Proposal](./VIZQL_STREAMLINED_AGENT_PROPOSAL.md) sections relevant to your work
→ Use [Implementation Checklist](./VIZQL_STREAMLINED_CHECKLIST.md) for daily tasks

**Architect/Tech Lead:**
→ Read [Full Proposal](./VIZQL_STREAMLINED_AGENT_PROPOSAL.md) completely
→ Study [Architecture Comparison](./VIZQL_COMPARISON_DIAGRAM.md) for design decisions

**QA/Testing:**
→ Review [Full Proposal](./VIZQL_STREAMLINED_AGENT_PROPOSAL.md) Phase 6 (Testing)
→ Use [Implementation Checklist](./VIZQL_STREAMLINED_CHECKLIST.md) Phase 6 for test planning

### By Phase

**Pre-Development / Planning:**
→ [Executive Summary](./VIZQL_STREAMLINED_SUMMARY.md)
→ [Full Proposal](./VIZQL_STREAMLINED_AGENT_PROPOSAL.md)
→ [Architecture Comparison](./VIZQL_COMPARISON_DIAGRAM.md)

**During Implementation:**
→ [Implementation Checklist](./VIZQL_STREAMLINED_CHECKLIST.md)
→ [Full Proposal](./VIZQL_STREAMLINED_AGENT_PROPOSAL.md) (reference)

**Testing & Validation:**
→ [Implementation Checklist](./VIZQL_STREAMLINED_CHECKLIST.md) Phase 6
→ [Full Proposal](./VIZQL_STREAMLINED_AGENT_PROPOSAL.md) Phase 6

**Deployment & Rollout:**
→ [Implementation Checklist](./VIZQL_STREAMLINED_CHECKLIST.md) Rollout section
→ [Full Proposal](./VIZQL_STREAMLINED_AGENT_PROPOSAL.md) Rollout Strategy

---

## 🔑 Key Concepts

### What's Being Changed?

**Removed:**
- Router node (ineffective shortcut, adds latency)
- Planner node (unnecessary LLM call)
- Schema fetch node (inflexible, now optional via tool)

**Enhanced:**
- Build query node now has tools and can:
  - Fetch schema only if needed
  - Reuse queries from conversation history
  - Get datasource metadata
  - Make intelligent decisions

**Kept:**
- Validator (fast, reliable)
- Executor (works well)
- Formatter (effective, now captures reasoning)
- Error handler (comprehensive)

### Why These Changes?

**Problem:** Current agent has 7 nodes with routing/planning overhead taking 3-4 seconds before query building even starts.

**Solution:** Streamlined agent with 4 nodes where build_query node is smart enough to make its own decisions via tools.

**Result:** 20-30% faster latency, 20%+ lower token usage, plus new capability (query reuse).

### Key Performance Targets

| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|
| P50 Latency | ~6s | < 4s | **-33%** |
| P95 Latency | ~12s | < 8s | **-33%** |
| Token Usage | Baseline | -20% | **-20%** |
| Query Reuse | 0% | > 30% | **NEW** |

---

## 📋 Implementation Summary

### Timeline
- **Development:** 12.5 days (~2.5 weeks)
- **Rollout:** 4 weeks (phased)
- **Total:** ~6.5 weeks

### Phases
1. Tool Implementation (2 days)
2. Enhanced Query Builder (3 days)
3. Node Integration (2 days)
4. Graph Construction (1 day)
5. Factory Integration (0.5 days)
6. Testing & Validation (3 days)
7. Monitoring & Metrics (1 day)

### Team
- 2-3 engineers recommended
- 1 QA engineer for testing
- 1 DevOps for deployment

---

## ❓ Open Questions

Before starting implementation, resolve:

1. **Message History Format**
   - How many prior messages to include?
   - Full conversation or just user queries?
   - Storage format?

2. **Caching Strategy**
   - In-memory cache? Redis?
   - TTL for schema cache?
   - Invalidation strategy?

3. **Similarity Threshold**
   - What threshold for query reuse? (0.8 proposed)
   - Use embeddings or string matching?
   - Which embedding model?

4. **Tool Call Limits**
   - Max tool calls per query?
   - Timeout for tool calls?
   - Parallel or sequential?

5. **Fallback Behavior**
   - If streamlined fails, retry with current agent?
   - Or return error?

**Action:** Schedule meeting to resolve these questions.

---

## 📊 Success Criteria

### Required (Must Meet All)
- [ ] Achieves comparable accuracy (> 95% vs current agent)
- [ ] 20%+ latency improvement (P50)
- [ ] Query reuse works in conversation scenarios
- [ ] All unit and integration tests pass
- [ ] No critical bugs in production

### Nice to Have
- [ ] 20%+ token usage reduction
- [ ] Higher first-try success rate (> 85%)
- [ ] Better error messages via tool context
- [ ] Positive user feedback

---

## 🚀 Next Steps

1. **Review Phase** (1-2 days)
   - [ ] Review all documentation
   - [ ] Get stakeholder approval
   - [ ] Resolve open questions
   - [ ] Assign team members

2. **Setup Phase** (1 day)
   - [ ] Create feature branch
   - [ ] Set up development environment
   - [ ] Create project board
   - [ ] Schedule kickoff meeting

3. **Development Phase** (2.5 weeks)
   - [ ] Follow [Implementation Checklist](./VIZQL_STREAMLINED_CHECKLIST.md)
   - [ ] Daily standups
   - [ ] Weekly demos

4. **Rollout Phase** (4 weeks)
   - [ ] Internal testing (Week 1)
   - [ ] Shadow mode (Week 2)
   - [ ] A/B test at 10% (Week 3)
   - [ ] Gradual increase to 100% (Week 4+)

---

## 📞 Contact & Support

**Project Lead:** [Assign]
**Engineering Lead:** [Assign]
**Product Owner:** [Assign]

**Slack Channel:** #vizql-streamlined (create)
**JIRA Project:** [Create]
**GitHub Branch:** `feature/vizql-streamlined`

---

## 📝 Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-06 | AI Agent | Initial proposal created |

---

## 🔗 Related Documentation

- [GRAPH_REDESIGN_PLAN.md](./GRAPH_REDESIGN_PLAN.md) - Original controlled graph design
- [FIELD_ROLE_DETERMINATION_LOGIC.md](./FIELD_ROLE_DETERMINATION_LOGIC.md) - Field role logic
- Current VizQL agent: `backend/app/services/agents/vizql/`

---

**Status:** ✅ Ready for Review
**Priority:** High
**Risk:** Medium (new architecture, needs thorough testing)
**Impact:** High (performance improvement + new capabilities)
