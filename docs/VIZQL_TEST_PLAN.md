# VizQL Query Accuracy Test Plan

**Date:** February 5, 2026  
**Purpose:** Validate Phase 1-4 improvements  
**Target:** >70% first-attempt success rate

---

## Test Environment Setup

### Prerequisites
- ✅ Redis container running (for schema caching)
- ✅ Postgres container running (for application data)
- ✅ Tableau Server accessible with VizQL API
- ✅ Backend running locally with hot reload
- ✅ Frontend running locally with hot reload

### Initial Setup Steps
1. **Clear Redis cache:**
   ```bash
   docker exec -it <redis-container> redis-cli FLUSHDB
   ```

2. **Verify Tableau connection:**
   - Test connection in UI
   - Verify datasource access

3. **Enrich test datasources:**
   - Click "Enrich Schema for AI" button for each test datasource
   - Verify enrichment succeeds
   - Check Redis cache populated

---

## Test Datasources

### Recommended Datasources
1. **Superstore** (Sales data)
   - Typical fields: Sales, Profit, Quantity, Region, Category, State
   - Good for: Basic aggregations, grouping, filtering

2. **HR Analytics** (Employee data)
   - Typical fields: Salary, Department, Employee ID, Hire Date
   - Good for: Date aggregations, distinct counts

3. **Financial** (Revenue/Expenses)
   - Typical fields: Revenue, Expenses, Month, Account, Department
   - Good for: Multiple measures, date ranges

---

## Test Queries (20 Examples)

### Category 1: Basic Aggregations (5 queries)
1. ✅ "show total sales by region"
   - Expected: SUM(Sales) grouped by Region
   - Validates: Basic measure aggregation, dimension grouping

2. ✅ "average price per product category"
   - Expected: AVG(Price) grouped by Category
   - Validates: AVG aggregation, field name matching

3. ✅ "count of orders by month"
   - Expected: COUNT(Order ID) grouped by Month
   - Validates: COUNT aggregation, date grouping

4. ✅ "sum of profits for each state"
   - Expected: SUM(Profit) grouped by State
   - Validates: Multiple dimensions, field matching

5. ✅ "total revenue by year"
   - Expected: SUM(Revenue) grouped by Year
   - Validates: Date aggregation, year extraction

### Category 2: Advanced Aggregations (5 queries)
6. ✅ "distinct count of customers by region"
   - Expected: COUNTD(Customer ID) grouped by Region
   - Validates: COUNTD aggregation, distinct counts

7. ✅ "min and max sales by category"
   - Expected: MIN(Sales), MAX(Sales) grouped by Category
   - Validates: Multiple aggregations, MIN/MAX

8. ✅ "median sales per transaction"
   - Expected: MEDIAN(Sales)
   - Validates: MEDIAN aggregation

9. ✅ "standard deviation of prices by category"
   - Expected: STDEV(Price) grouped by Category
   - Validates: Statistical aggregations

10. ✅ "average profit margin by product"
    - Expected: AVG(Profit Margin) grouped by Product
    - Validates: Calculated fields, AVG

### Category 3: Filtering (5 queries)
11. ✅ "total sales by region for 2024"
    - Expected: SUM(Sales) grouped by Region, filtered by Year=2024
    - Validates: Date filtering, filter syntax

12. ✅ "top 10 customers by revenue"
    - Expected: SUM(Revenue) grouped by Customer, limit 10, sorted DESC
    - Validates: Top N queries, sorting

13. ✅ "sales by category where profit > 1000"
    - Expected: SUM(Sales) grouped by Category, filtered by Profit > 1000
    - Validates: Measure filtering, condition filters

14. ✅ "orders in Q1 2024 by region"
    - Expected: COUNT(Order ID) grouped by Region, filtered by Quarter=Q1, Year=2024
    - Validates: Date range filtering, quarter extraction

15. ✅ "products with zero sales"
    - Expected: Products where Sales = 0
    - Validates: Zero value filtering, null handling

### Category 4: Complex Queries (5 queries)
16. ✅ "year over year revenue comparison"
    - Expected: SUM(Revenue) grouped by Year, multiple years
    - Validates: Multi-year queries, time comparisons

17. ✅ "sales by region and category"
    - Expected: SUM(Sales) grouped by Region and Category
    - Validates: Multiple dimensions, cross-tabulation

18. ✅ "percentage of total sales by region"
    - Expected: SUM(Sales) / Total SUM(Sales) grouped by Region
    - Validates: Calculated percentages, table calculations

19. ✅ "monthly sales trend for 2023"
    - Expected: SUM(Sales) grouped by Month, filtered by Year=2023
    - Validates: Time series, monthly aggregation

20. ✅ "customers with more than 5 orders"
    - Expected: COUNT(Order ID) grouped by Customer, filtered by COUNT > 5
    - Validates: Aggregated filtering, having clauses

---

## Testing Process

### For Each Query

1. **Pre-test Setup:**
   - Ensure datasource schema is enriched (click "Enrich Schema" button)
   - Clear any previous query cache
   - Note baseline metrics (if available)

2. **Execute Query:**
   - Submit query through chat interface
   - Monitor backend logs for:
     - Schema enrichment status
     - Compressed context generation
     - Semantic validation results
     - Query execution

3. **Record Results:**
   - **Success/Fail:** Did query execute successfully?
   - **First Attempt:** Did it work on first try?
   - **Retries:** How many refinement attempts needed?
   - **Field Accuracy:** Were correct field names used?
   - **Aggregation Accuracy:** Were correct aggregations used?
   - **Token Usage:** Approximate tokens used (if available)
   - **Execution Time:** Total time from query to result

4. **Error Analysis (if failed):**
   - What was the error?
   - Was it caught by semantic validator?
   - Were suggestions helpful?
   - Did refinement fix it?

---

## Success Metrics

### Target Metrics (Post-Implementation)
- ✅ **First-attempt success rate:** ≥70% (target: 70%+)
- ✅ **Overall success rate:** ≥90% (after retries)
- ✅ **Field name accuracy:** ≥95% (correct field names used)
- ✅ **Semantic correctness:** ≥90% (correct aggregations, roles)
- ✅ **Token usage:** <2500 tokens per query (avg)
- ✅ **Query time:** <5 seconds (avg, including enrichment)

### Baseline Metrics (Pre-Implementation)
- First-attempt success rate: ~30%
- Overall success rate: ~50% (after 3 retries)
- Field hallucination rate: ~40%
- Token usage: ~4000 tokens per query
- Query time: 15-20 seconds (with retries)

---

## Test Execution Log

### Template for Recording Results

```
Query #: [1-20]
Query Text: "[user query]"
Datasource: [datasource name]

Results:
- First Attempt: [SUCCESS/FAIL]
- Retries Needed: [0-3]
- Final Status: [SUCCESS/FAIL]
- Field Names Used: [list]
- Aggregations Used: [list]
- Errors Encountered: [list]
- Suggestions Provided: [list]
- Token Usage: [approx tokens]
- Execution Time: [seconds]

Notes: [any observations]
```

---

## Validation Checklist

### For Each Successful Query
- [ ] Correct field names used (exact match from schema)
- [ ] MEASURE fields have aggregation functions
- [ ] DIMENSION fields don't have aggregation functions
- [ ] Aggregation functions match field data types
- [ ] Filters use correct field names
- [ ] Query executes successfully
- [ ] Results match user intent

### For Each Failed Query
- [ ] Error message is clear and actionable
- [ ] Semantic validator caught the error
- [ ] Suggestions were provided
- [ ] Suggestions were helpful
- [ ] Refinement attempt improved the query
- [ ] Root cause identified

---

## Edge Cases to Test

### Schema Edge Cases
1. **Large Datasources:** Test with datasource having 200+ fields
   - Verify field truncation works
   - Verify top fields are selected

2. **Hidden Fields:** Test datasource with hidden fields
   - Verify hidden fields are excluded

3. **Calculated Fields:** Test with calculated fields
   - Verify calculated fields are handled

4. **Field Aliases:** Test with fields that have aliases
   - Verify aliases are respected

### Query Edge Cases
1. **Empty Results:** Query that returns no data
   - Verify graceful handling

2. **Very Long Field Names:** Fields with long names
   - Verify truncation doesn't break matching

3. **Special Characters:** Field names with special chars
   - Verify escaping works

4. **Case Sensitivity:** Test exact case matching
   - Verify "Sales" vs "sales" vs "SALES"

---

## Performance Testing

### Cache Performance
- [ ] First enrichment: 2-5 seconds
- [ ] Cached enrichment: <50ms
- [ ] Cache hit rate: >80% after initial enrichment

### Query Performance
- [ ] Query construction: <3 seconds
- [ ] Validation: <100ms
- [ ] Execution: <2 seconds
- [ ] Total end-to-end: <5 seconds

### Token Usage
- [ ] Compressed context: <2500 tokens
- [ ] Full prompt: <3500 tokens
- [ ] Reduction vs baseline: 30-40%

---

## Regression Testing

### Ensure No Breaking Changes
- [ ] Basic queries still work without enrichment
- [ ] Fallback to basic schema works
- [ ] Error handling graceful
- [ ] Existing API endpoints unchanged
- [ ] Frontend UI still functional

---

## Test Results Summary

### Overall Statistics
- **Total Queries Tested:** [count]
- **First-Attempt Success:** [count] ([percentage]%)
- **Overall Success:** [count] ([percentage]%)
- **Average Retries:** [number]
- **Average Token Usage:** [number]
- **Average Execution Time:** [seconds]

### Error Breakdown
- **Field Name Errors:** [count]
- **Aggregation Errors:** [count]
- **Semantic Errors:** [count]
- **Execution Errors:** [count]
- **Other Errors:** [count]

### Improvement Metrics
- **First-Attempt Improvement:** [baseline]% → [current]% ([+X]%)
- **Field Accuracy Improvement:** [baseline]% → [current]% ([+X]%)
- **Token Reduction:** [baseline] → [current] ([-X]%)
- **Time Reduction:** [baseline]s → [current]s ([-X]s)

---

## Known Issues & Limitations

### Issues Found During Testing
1. [Issue description]
   - **Impact:** [High/Medium/Low]
   - **Workaround:** [if any]
   - **Fix:** [planned fix]

### Limitations
1. **Large Datasources:** Fields truncated to 200 (by design)
2. **Cache TTL:** 1 hour (may need adjustment)
3. **Manual Enrichment:** Requires UI button click (by design)

---

## Next Steps After Testing

1. **If Success Rate <70%:**
   - Analyze error patterns
   - Review prompt improvements
   - Consider additional few-shot examples
   - Enhance semantic rules

2. **If Success Rate ≥70%:**
   - Document results
   - Prepare for production deployment
   - Plan monitoring and alerting
   - Gather user feedback

---

## Test Execution Schedule

### Day 1: Basic Queries (Queries 1-10)
- Focus: Core functionality
- Goal: Verify basic improvements work

### Day 2: Advanced Queries (Queries 11-20)
- Focus: Edge cases and complex scenarios
- Goal: Verify robustness

### Day 3: Performance & Regression
- Focus: Performance metrics and regression
- Goal: Ensure no breaking changes

---

**Test Plan Version:** 1.0  
**Last Updated:** February 5, 2026  
**Owner:** Engineering Team
