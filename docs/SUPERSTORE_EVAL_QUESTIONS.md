# Superstore Dataset Evaluation Questions

**Date:** February 6, 2026  
**Purpose:** Comprehensive evaluation questions for VizQL agent testing  
**Dataset:** Tableau Superstore (Sales data)

---

## Question Categories

### Category 1: Basic Aggregations (10 questions)
**Focus:** Simple SUM, AVG, COUNT operations on measures

1. **"show me total sales"**
   - Expected: SUM(Sales)
   - Validates: Basic measure aggregation without grouping

2. **"what is the total profit"**
   - Expected: SUM(Profit)
   - Validates: Field name matching for "profit"

3. **"average sales per order"**
   - Expected: AVG(Sales)
   - Validates: AVG aggregation, understanding "per order" context

4. **"total quantity sold"**
   - Expected: SUM(Quantity)
   - Validates: Field name matching for "quantity"

5. **"average discount amount"**
   - Expected: AVG(Discount)
   - Validates: AVG on discount field

6. **"count of orders"**
   - Expected: COUNT(Order ID) or COUNTD(Order ID)
   - Validates: COUNT vs COUNTD understanding

7. **"sum of sales by region"**
   - Expected: SUM(Sales) grouped by Region
   - Validates: Basic grouping with aggregation

8. **"total profit by state"**
   - Expected: SUM(Profit) grouped by State
   - Validates: Multiple dimension grouping

9. **"average sales by category"**
   - Expected: AVG(Sales) grouped by Category
   - Validates: AVG with grouping

10. **"sum of quantity by sub-category"**
    - Expected: SUM(Quantity) grouped by Sub-Category
    - Validates: Hierarchical dimension understanding

---

### Category 2: Temporal Queries (10 questions)
**Focus:** Date functions, time-based grouping, date filters

11. **"sales by month"**
    - Expected: SUM(Sales) grouped by Order Date with TRUNC_MONTH function
    - Validates: Temporal grouping, date function application

12. **"total sales by year"**
    - Expected: SUM(Sales) grouped by Order Date with TRUNC_YEAR function
    - Validates: Year-level aggregation

13. **"profit by quarter"**
    - Expected: SUM(Profit) grouped by Order Date with TRUNC_QUARTER function
    - Validates: Quarter-level aggregation

14. **"monthly sales trend"**
    - Expected: SUM(Sales) grouped by Order Date with TRUNC_MONTH
    - Validates: Temporal trend understanding

15. **"sales by year and month"**
    - Expected: SUM(Sales) grouped by Order Date with YEAR and MONTH functions
    - Validates: Multiple date groupings

16. **"total sales for 2023"**
    - Expected: SUM(Sales) filtered by Order Date year = 2023
    - Validates: Date filtering, year extraction

17. **"sales in the last 3 months"**
    - Expected: SUM(Sales) with DATE filter (LASTN, MONTHS, rangeN=3)
    - Validates: Relative date filtering

18. **"profit by month for 2024"**
    - Expected: SUM(Profit) grouped by Order Date TRUNC_MONTH, filtered by year=2024
    - Validates: Combined temporal grouping and filtering

19. **"sales by week"**
    - Expected: SUM(Sales) grouped by Order Date with TRUNC_WEEK function
    - Validates: Week-level aggregation

20. **"year over year sales comparison"**
    - Expected: SUM(Sales) grouped by Order Date with TRUNC_YEAR
    - Validates: Multi-year comparison understanding

---

### Category 3: Distinct Counts & Cardinality (8 questions)
**Focus:** COUNTD, "how many" queries, distinct entity counting

21. **"how many customers"**
    - Expected: COUNTD(Customer Name) or COUNTD(Customer ID)
    - Validates: COUNTD function, "how many" pattern recognition

22. **"how many products"**
    - Expected: COUNTD(Product Name) or COUNTD(Product ID)
    - Validates: Distinct count on product dimension

23. **"how many orders"**
    - Expected: COUNTD(Order ID)
    - Validates: Distinct order counting

24. **"number of unique customers by region"**
    - Expected: COUNTD(Customer Name) grouped by Region
    - Validates: COUNTD with grouping

25. **"distinct count of products by category"**
    - Expected: COUNTD(Product Name) grouped by Category
    - Validates: COUNTD with dimension grouping

26. **"how many states"**
    - Expected: COUNTD(State)
    - Validates: Simple distinct count on dimension

27. **"count of unique customers who made purchases"**
    - Expected: COUNTD(Customer Name) or COUNTD(Customer ID)
    - Validates: Understanding "unique" requirement

28. **"how many different sub-categories"**
    - Expected: COUNTD(Sub-Category)
    - Validates: Distinct count on hierarchical dimension

---

### Category 4: Top N & Ranking (8 questions)
**Focus:** Top/bottom N queries, sorting, ranking

29. **"top 10 customers by sales"**
    - Expected: TOP filter with howMany=10, direction=TOP, fieldToMeasure=Sales SUM
    - Validates: Top N pattern recognition, TOP filter usage

30. **"bottom 5 products by profit"**
    - Expected: TOP filter with howMany=5, direction=BOTTOM, fieldToMeasure=Profit SUM
    - Validates: Bottom N queries, direction handling

31. **"top 3 regions by total sales"**
    - Expected: TOP filter with howMany=3, direction=TOP, fieldToMeasure=Sales SUM
    - Validates: Top N with dimension grouping

32. **"best performing categories"**
    - Expected: TOP filter on Category by Sales SUM (may need to infer N)
    - Validates: Implicit top N from "best performing"

33. **"worst 5 states by profit"**
    - Expected: TOP filter with howMany=5, direction=BOTTOM, fieldToMeasure=Profit SUM
    - Validates: "Worst" = bottom N

34. **"top 10 products by quantity sold"**
    - Expected: TOP filter with howMany=10, direction=TOP, fieldToMeasure=Quantity SUM
    - Validates: Top N with different measure

35. **"highest sales by customer"**
    - Expected: TOP filter on Customer Name by Sales SUM (may need to infer N=1 or top 10)
    - Validates: "Highest" = top N

36. **"top 5 sub-categories by profit margin"**
    - Expected: TOP filter on Sub-Category (may need calculation for profit margin)
    - Validates: Top N with calculated fields

---

### Category 5: Filtering (10 questions)
**Focus:** SET filters, MATCH filters, quantitative filters, date filters

37. **"sales for California"**
    - Expected: SUM(Sales) filtered by State = "California" (SET filter)
    - Validates: Single value SET filter

38. **"profit by region for West and East"**
    - Expected: SUM(Profit) grouped by Region, filtered by Region IN ["West", "East"]
    - Validates: Multi-value SET filter

39. **"sales for Furniture category"**
    - Expected: SUM(Sales) filtered by Category = "Furniture"
    - Validates: Category filtering

40. **"products containing 'table'"**
    - Expected: MATCH filter on Product Name with contains="table"
    - Validates: MATCH filter, substring matching

41. **"sales where profit is greater than 1000"**
    - Expected: SUM(Sales) with QUANTITATIVE_NUMERICAL filter on Profit SUM > 1000
    - Validates: Measure filtering, quantitative filters

42. **"orders with discount greater than 10%"**
    - Expected: Filter by Discount > 0.1 (QUANTITATIVE_NUMERICAL)
    - Validates: Percentage understanding, numeric filtering

43. **"sales between 2023-01-01 and 2023-12-31"**
    - Expected: SUM(Sales) with QUANTITATIVE_DATE filter (RANGE)
    - Validates: Date range filtering

44. **"sales for this year"**
    - Expected: SUM(Sales) with DATE filter (dateRangeType=CURRENT, periodType=YEARS)
    - Validates: Relative date filtering ("this year")

45. **"customers in New York, California, and Texas"**
    - Expected: Filter by State IN ["New York", "California", "Texas"]
    - Validates: Multi-value SET filter with multiple states

46. **"sales for first class shipping"**
    - Expected: SUM(Sales) filtered by Ship Mode = "First Class"
    - Validates: Ship Mode filtering

---

### Category 6: Calculations & Ratios (10 questions)
**Focus:** Calculated fields, profit margin, ratios, percentages

47. **"calculate profit margin"**
    - Expected: Calculation field with formula: SUM([Profit])/SUM([Sales])
    - Validates: Calculation field creation, profit margin formula

48. **"sales to profit ratio"**
    - Expected: Calculation: SUM([Sales])/SUM([Profit])
    - Validates: Ratio calculation

49. **"profit margin by category"**
    - Expected: Calculation SUM([Profit])/SUM([Sales]) grouped by Category
    - Validates: Calculated field with grouping

50. **"average discount percentage"**
    - Expected: AVG(Discount) - may need to multiply by 100 if stored as decimal
    - Validates: Percentage calculation understanding

51. **"sales per customer"**
    - Expected: SUM(Sales) / COUNTD(Customer Name) or calculation
    - Validates: Per-unit calculations

52. **"total sales divided by total quantity"**
    - Expected: Calculation: SUM([Sales])/SUM([Quantity])
    - Validates: Explicit division calculation

53. **"profit margin percentage by region"**
    - Expected: Calculation (SUM([Profit])/SUM([Sales])) * 100 grouped by Region
    - Validates: Percentage calculation with grouping

54. **"revenue per order"**
    - Expected: SUM(Sales) / COUNTD(Order ID) or calculation
    - Validates: Per-order calculations

55. **"discount rate by segment"**
    - Expected: AVG(Discount) grouped by Segment, or calculation
    - Validates: Rate calculation with grouping

56. **"profit as percentage of sales"**
    - Expected: Calculation: (SUM([Profit])/SUM([Sales])) * 100
    - Validates: Percentage calculation understanding

---

### Category 7: Multi-Dimension Grouping (8 questions)
**Focus:** Cross-tabulation, multiple dimensions, hierarchical grouping

57. **"sales by region and category"**
    - Expected: SUM(Sales) grouped by Region and Category
    - Validates: Multiple dimension grouping

58. **"profit by state and sub-category"**
    - Expected: SUM(Profit) grouped by State and Sub-Category
    - Validates: Cross-dimensional grouping

59. **"sales by segment and region"**
    - Expected: SUM(Sales) grouped by Segment and Region
    - Validates: Multiple categorical dimensions

60. **"quantity by category and ship mode"**
    - Expected: SUM(Quantity) grouped by Category and Ship Mode
    - Validates: Multiple dimensions with different measure

61. **"sales by year and region"**
    - Expected: SUM(Sales) grouped by Order Date (TRUNC_YEAR) and Region
    - Validates: Temporal + categorical grouping

62. **"profit by month and category"**
    - Expected: SUM(Profit) grouped by Order Date (TRUNC_MONTH) and Category
    - Validates: Temporal + categorical cross-tabulation

63. **"sales by customer segment and product category"**
    - Expected: SUM(Sales) grouped by Segment and Category
    - Validates: Business dimension grouping

64. **"quantity by state and sub-category"**
    - Expected: SUM(Quantity) grouped by State and Sub-Category
    - Validates: Geographic + product hierarchy grouping

---

### Category 8: Complex & Hierarchical Filters (8 questions)
**Focus:** Context filters, hierarchical dependencies, nested filters

65. **"given the top region, show me the top 3 customers"**
    - Expected: TOP filter on Region (context=true), then TOP filter on Customer Name (howMany=3)
    - Validates: Hierarchical TOP filters, context filter usage

66. **"for the best category, what are the top 5 products"**
    - Expected: TOP filter on Category (context=true), then TOP filter on Product Name (howMany=5)
    - Validates: "Given/for" pattern recognition, context filters

67. **"in Q1 2024, show me top 10 customers by sales"**
    - Expected: DATE filter for Q1 2024 (context=true), then TOP filter on Customer Name
    - Validates: Date context + TOP filter

68. **"within the West region, show sales by state"**
    - Expected: SET filter on Region="West" (context=true), then SUM(Sales) grouped by State
    - Validates: Context filter with grouping

69. **"for Furniture category, show profit by sub-category"**
    - Expected: SET filter on Category="Furniture" (context=true), then SUM(Profit) grouped by Sub-Category
    - Validates: Category context + hierarchical grouping

70. **"in 2023, what were the top 5 products by sales"**
    - Expected: DATE filter for 2023 (context=true), then TOP filter on Product Name
    - Validates: Year context + TOP filter

71. **"given the top 3 states, show me sales by city"**
    - Expected: TOP filter on State (howMany=3, context=true), then SUM(Sales) grouped by City
    - Validates: TOP context + geographic grouping

72. **"for the best performing segment, show profit by region"**
    - Expected: TOP filter on Segment (context=true), then SUM(Profit) grouped by Region
    - Validates: Segment context + regional grouping

---

### Category 9: Edge Cases & Special Scenarios (8 questions)
**Focus:** Zero values, nulls, special aggregations, edge cases

73. **"products with zero sales"**
    - Expected: Products where SUM(Sales) = 0 or Sales = 0
    - Validates: Zero value filtering

74. **"orders with no discount"**
    - Expected: Filter by Discount = 0 or Discount IS NULL
    - Validates: Zero/null filtering

75. **"states with negative profit"**
    - Expected: SUM(Profit) grouped by State, filtered by SUM(Profit) < 0
    - Validates: Negative value filtering

76. **"maximum sales amount"**
    - Expected: MAX(Sales)
    - Validates: MAX aggregation without grouping

77. **"minimum profit by category"**
    - Expected: MIN(Profit) grouped by Category
    - Validates: MIN aggregation with grouping

78. **"standard deviation of sales"**
    - Expected: STDEV(Sales)
    - Validates: Statistical aggregation

79. **"median profit by region"**
    - Expected: MEDIAN(Profit) grouped by Region
    - Validates: MEDIAN aggregation

80. **"variance of quantity"**
    - Expected: VAR(Quantity)
    - Validates: Statistical aggregation (VAR)

---

### Category 10: Advanced Calculations & Business Metrics (10 questions)
**Focus:** Complex calculations, business KPIs, advanced formulas

81. **"year over year growth rate"**
    - Expected: Complex calculation comparing current year to previous year
    - Validates: Time-based calculations, year-over-year logic

82. **"average order value"**
    - Expected: SUM(Sales) / COUNTD(Order ID)
    - Validates: Business metric calculation

83. **"customer lifetime value by segment"**
    - Expected: SUM(Sales) grouped by Customer Name and Segment (complex)
    - Validates: Business metric understanding

84. **"sales growth percentage"**
    - Expected: Calculation comparing periods
    - Validates: Growth calculation

85. **"profit margin by product"**
    - Expected: SUM([Profit])/SUM([Sales]) grouped by Product Name
    - Validates: Calculated field with high-cardinality grouping

86. **"discount impact on sales"**
    - Expected: Comparison of sales with/without discount, or correlation
    - Validates: Comparative analysis understanding

87. **"sales per square foot"** (if applicable)
    - Expected: May need to infer or handle missing dimension
    - Validates: Handling unavailable fields gracefully

88. **"return on sales by category"**
    - Expected: SUM([Profit])/SUM([Sales]) grouped by Category
    - Validates: Financial ratio calculation

89. **"average discount by customer segment"**
    - Expected: AVG(Discount) grouped by Segment
    - Validates: Average calculation with grouping

90. **"total revenue including discounts"**
    - Expected: SUM(Sales) - SUM(Sales * Discount) or similar
    - Validates: Complex calculation with multiple fields

---

## Evaluation Criteria

For each question, evaluate:

1. **Query Construction Success**
   - ✅ Query generated without errors
   - ✅ Correct field names used (exact match from schema)
   - ✅ Appropriate aggregations applied

2. **Semantic Correctness**
   - ✅ MEASURE fields have aggregation functions
   - ✅ DIMENSION fields used correctly (with/without aggregation as appropriate)
   - ✅ Date functions applied for temporal queries
   - ✅ COUNTD used for "how many" queries

3. **Filter Accuracy**
   - ✅ Correct filter types used (SET, MATCH, DATE, QUANTITATIVE)
   - ✅ Filter values match user intent
   - ✅ Context filters applied for hierarchical queries

4. **Calculation Accuracy**
   - ✅ Calculated fields have unique names (don't conflict with schema)
   - ✅ Calculation formulas are correct
   - ✅ Field names in calculations reference existing fields

5. **First Attempt Success**
   - ✅ Query executes successfully on first attempt
   - ✅ No validation errors
   - ✅ Results match user intent

6. **Error Handling** (if query fails)
   - ✅ Clear error messages
   - ✅ Helpful suggestions provided
   - ✅ Refinement attempts improve query

---

## Expected Field Names (Superstore Dataset)

**Measures:**
- Sales
- Profit
- Quantity
- Discount

**Dimensions:**
- Region (West, East, Central, South)
- State
- City
- Category (Furniture, Office Supplies, Technology)
- Sub-Category
- Product Name
- Customer Name
- Segment (Consumer, Corporate, Home Office)
- Ship Mode (Standard Class, Second Class, First Class, Same Day)
- Order Date
- Ship Date
- Order ID
- Customer ID
- Product ID

---

## Scoring Rubric

### Per Question Scoring (0-5 points):
- **5 points:** Perfect query, executes successfully, matches intent exactly
- **4 points:** Minor issues (e.g., field name slightly off but works)
- **3 points:** Query executes but missing some elements
- **2 points:** Query has errors but partially correct
- **1 point:** Query generated but major errors
- **0 points:** Query fails or completely incorrect

### Overall Metrics:
- **First Attempt Success Rate:** % of questions that work on first try
- **Overall Success Rate:** % of questions that work after retries
- **Field Accuracy:** % of questions with correct field names
- **Aggregation Accuracy:** % of questions with correct aggregations
- **Filter Accuracy:** % of questions with correct filters
- **Calculation Accuracy:** % of calculated fields with correct formulas

---

## Test Execution Notes

1. **Run questions in order** to test progressive complexity
2. **Record results** for each question (success/fail, retries, errors)
3. **Note edge cases** that fail or require special handling
4. **Track improvements** over time as agent is refined
5. **Focus on first-attempt success** as primary metric

---

**Total Questions:** 90  
**Estimated Test Time:** 2-3 hours for full evaluation  
**Recommended:** Run in batches of 10-15 questions per session
