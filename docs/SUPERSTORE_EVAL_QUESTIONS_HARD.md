# Superstore Evaluation Questions - Very Hard Difficulty

**Date:** February 6, 2026  
**Format:** JSON structure for easy import/automation  
**Difficulty:** Very Hard - Tests complex calculations, multi-step logic, and advanced VizQL features

---

## Questions by Category

### Category 1: Complex Calculations and Ratios

```json
[
  {
    "id": 101,
    "category": "complex_calculations",
    "question": "show me profit margin percentage by category, where profit margin is profit divided by sales",
    "expected_fields": ["Profit", "Sales"],
    "expected_calculations": [
      {
        "fieldCaption": "Profit Margin",
        "calculation": "SUM([Profit]) / SUM([Sales])"
      }
    ],
    "expected_grouping": ["Category"],
    "difficulty": "very_hard",
    "notes": "Requires creating calculated field with ratio, ensuring proper aggregation order"
  },
  {
    "id": 102,
    "category": "complex_calculations",
    "question": "what is the average order value for orders with profit greater than 100, where order value is sum of sales",
    "expected_fields": ["Sales"],
    "expected_aggregation": "AVG",
    "expected_grouping": ["Order ID"],
    "expected_filters": [
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": "Profit",
        "quantitativeFilterType": "MIN",
        "min": 100
      }
    ],
    "difficulty": "very_hard",
    "notes": "Requires filtering on aggregated measure (profit per order), then calculating AVG of sales per order"
  },
  {
    "id": 103,
    "category": "complex_calculations",
    "question": "calculate the discount impact on profit by region, where discount impact is sum of profit times discount rate",
    "expected_fields": ["Profit", "Discount"],
    "expected_calculations": [
      {
        "fieldCaption": "Discount Impact",
        "calculation": "SUM([Profit]) * AVG([Discount])"
      }
    ],
    "expected_grouping": ["Region"],
    "difficulty": "very_hard",
    "notes": "Complex calculation mixing SUM and AVG aggregations"
  },
  {
    "id": 104,
    "category": "complex_calculations",
    "question": "show me the ratio of sales to quantity for each product, where the ratio is greater than 100",
    "expected_fields": ["Sales", "Quantity"],
    "expected_calculations": [
      {
        "fieldCaption": "Sales per Unit",
        "calculation": "SUM([Sales]) / SUM([Quantity])"
      }
    ],
    "expected_grouping": ["Product Name"],
    "expected_filters": [
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": "Sales per Unit",
        "quantitativeFilterType": "MIN",
        "min": 100
      }
    ],
    "difficulty": "very_hard",
    "notes": "Requires calculated field in filter - may need to filter on aggregated calculation"
  },
  {
    "id": 105,
    "category": "complex_calculations",
    "question": "what percentage of total sales does each region represent",
    "expected_fields": ["Sales"],
    "expected_calculations": [
      {
        "fieldCaption": "Sales Percentage",
        "calculation": "SUM([Sales]) / TOTAL(SUM([Sales]))"
      }
    ],
    "expected_grouping": ["Region"],
    "difficulty": "very_hard",
    "notes": "Requires table calculation or window function to calculate percentage of total"
  }
]
```

### Category 2: Multi-Step Analytical Queries

```json
[
  {
    "id": 106,
    "category": "multi_step_analytics",
    "question": "find the top 5 customers by total sales, then show their average profit margin",
    "expected_fields": ["Sales", "Profit"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Customer Name"],
    "expected_filters": [
      {
        "type": "TOP",
        "field": {"fieldCaption": "Customer Name"},
        "filterType": "TOP",
        "howMany": 5,
        "direction": "TOP",
        "fieldToMeasure": {
          "fieldCaption": "Sales",
          "function": "SUM"
        }
      }
    ],
    "expected_calculations": [
      {
        "fieldCaption": "Profit Margin",
        "calculation": "SUM([Profit]) / SUM([Sales])"
      }
    ],
    "difficulty": "very_hard",
    "notes": "Requires TOP filter combined with calculated field for profit margin"
  },
  {
    "id": 107,
    "category": "multi_step_analytics",
    "question": "show me products that have sales above the average sales per product, grouped by category",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Product Name", "Category"],
    "expected_filters": [
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": "Sales",
        "quantitativeFilterType": "MIN",
        "min": "AVG(Sales)" // This requires subquery or window function
      }
    ],
    "difficulty": "very_hard",
    "notes": "Requires comparing against average - may need table calculation or complex filter"
  },
  {
    "id": 108,
    "category": "multi_step_analytics",
    "question": "identify months where sales growth rate decreased compared to previous month",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Order Date"],
    "expected_calculations": [
      {
        "fieldCaption": "Sales Growth",
        "calculation": "SUM([Sales]) - LOOKUP(SUM([Sales]), -1)"
      },
      {
        "fieldCaption": "Growth Rate",
        "calculation": "(SUM([Sales]) - LOOKUP(SUM([Sales]), -1)) / LOOKUP(SUM([Sales]), -1)"
      }
    ],
    "expected_filters": [
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": "Growth Rate",
        "quantitativeFilterType": "MAX",
        "max": 0
      }
    ],
    "difficulty": "very_hard",
    "notes": "Requires table calculation with LOOKUP function for previous period comparison"
  },
  {
    "id": 109,
    "category": "multi_step_analytics",
    "question": "show me the cumulative sales by month for the last 12 months",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Order Date"],
    "expected_calculations": [
      {
        "fieldCaption": "Cumulative Sales",
        "calculation": "RUNNING_SUM(SUM([Sales]))"
      }
    ],
    "expected_filters": [
      {
        "type": "DATE",
        "field": {"fieldCaption": "Order Date"},
        "filterType": "DATE",
        "periodType": "MONTHS",
        "dateRangeType": "LASTN",
        "rangeN": 12
      }
    ],
    "difficulty": "very_hard",
    "notes": "Requires table calculation RUNNING_SUM combined with date filter"
  },
  {
    "id": 110,
    "category": "multi_step_analytics",
    "question": "find regions where the profit margin is below the overall average profit margin",
    "expected_fields": ["Profit", "Sales"],
    "expected_grouping": ["Region"],
    "expected_calculations": [
      {
        "fieldCaption": "Profit Margin",
        "calculation": "SUM([Profit]) / SUM([Sales])"
      },
      {
        "fieldCaption": "Overall Avg Margin",
        "calculation": "WINDOW_AVG(SUM([Profit]) / SUM([Sales]))"
      }
    ],
    "expected_filters": [
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": "Profit Margin",
        "quantitativeFilterType": "MAX",
        "max": "WINDOW_AVG(SUM([Profit]) / SUM([Sales]))"
      }
    ],
    "difficulty": "very_hard",
    "notes": "Requires comparing regional margin against overall average using window functions"
  }
]
```

### Category 3: Complex Filtering Logic

```json
[
  {
    "id": 111,
    "category": "complex_filtering",
    "question": "show me sales for products in Furniture category that have profit margin above 20% and were sold in West or East regions",
    "expected_fields": ["Sales", "Profit"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Product Name"],
    "expected_filters": [
      {
        "type": "SET",
        "field": {"fieldCaption": "Category"},
        "filterType": "SET",
        "values": ["Furniture"]
      },
      {
        "type": "SET",
        "field": {"fieldCaption": "Region"},
        "filterType": "SET",
        "values": ["West", "East"]
      },
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": "Profit Margin",
        "quantitativeFilterType": "MIN",
        "min": 0.2
      }
    ],
    "expected_calculations": [
      {
        "fieldCaption": "Profit Margin",
        "calculation": "SUM([Profit]) / SUM([Sales])"
      }
    ],
    "difficulty": "very_hard",
    "notes": "Multiple filters including calculated field filter"
  },
  {
    "id": 112,
    "category": "complex_filtering",
    "question": "find orders placed in Q4 2023 where the discount was between 10% and 20%, and the profit was negative",
    "expected_fields": ["Order ID"],
    "expected_filters": [
      {
        "type": "QUANTITATIVE_DATE",
        "field": {"fieldCaption": "Order Date"},
        "filterType": "QUANTITATIVE_DATE",
        "quantitativeFilterType": "RANGE",
        "minDate": "2023-10-01",
        "maxDate": "2023-12-31"
      },
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": {"fieldCaption": "Discount"},
        "filterType": "QUANTITATIVE_NUMERICAL",
        "quantitativeFilterType": "RANGE",
        "min": 0.1,
        "max": 0.2
      },
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": {"fieldCaption": "Profit"},
        "filterType": "QUANTITATIVE_NUMERICAL",
        "quantitativeFilterType": "MAX",
        "max": 0
      }
    ],
    "difficulty": "very_hard",
    "notes": "Multiple quantitative filters with date range and negative profit condition"
  },
  {
    "id": 113,
    "category": "complex_filtering",
    "question": "show me customers who have placed more than 10 orders and whose total sales exceed 50000",
    "expected_fields": ["Sales", "Order ID"],
    "expected_aggregation": ["SUM", "COUNTD"],
    "expected_grouping": ["Customer Name"],
    "expected_filters": [
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": "Order Count",
        "quantitativeFilterType": "MIN",
        "min": 10
      },
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": "Sales",
        "quantitativeFilterType": "MIN",
        "min": 50000
      }
    ],
    "expected_calculations": [
      {
        "fieldCaption": "Order Count",
        "calculation": "COUNTD([Order ID])"
      }
    ],
    "difficulty": "very_hard",
    "notes": "Requires filtering on aggregated count and sum simultaneously"
  },
  {
    "id": 114,
    "category": "complex_filtering",
    "question": "find products that start with 'Office' and have average sales per order greater than 1000",
    "expected_fields": ["Sales"],
    "expected_aggregation": "AVG",
    "expected_grouping": ["Product Name", "Order ID"],
    "expected_filters": [
      {
        "type": "MATCH",
        "field": {"fieldCaption": "Product Name"},
        "filterType": "MATCH",
        "startsWith": "Office"
      },
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": "Sales",
        "quantitativeFilterType": "MIN",
        "min": 1000
      }
    ],
    "difficulty": "very_hard",
    "notes": "Combines text matching filter with quantitative filter on aggregated measure"
  },
  {
    "id": 115,
    "category": "complex_filtering",
    "question": "show me sales for the top 3 states by profit, but only for products in Technology category",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["State"],
    "expected_filters": [
      {
        "type": "TOP",
        "field": {"fieldCaption": "State"},
        "filterType": "TOP",
        "howMany": 3,
        "direction": "TOP",
        "fieldToMeasure": {
          "fieldCaption": "Profit",
          "function": "SUM"
        }
      },
      {
        "type": "SET",
        "field": {"fieldCaption": "Category"},
        "filterType": "SET",
        "values": ["Technology"]
      }
    ],
    "difficulty": "very_hard",
    "notes": "TOP filter combined with category filter - requires context filter understanding"
  }
]
```

### Category 4: Advanced Temporal Analysis

```json
[
  {
    "id": 116,
    "category": "temporal_analysis",
    "question": "calculate year-over-year sales growth percentage by region",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Region", "Order Date"],
    "expected_calculations": [
      {
        "fieldCaption": "YoY Growth",
        "calculation": "(SUM([Sales]) - LOOKUP(SUM([Sales]), -12)) / LOOKUP(SUM([Sales]), -12) * 100"
      }
    ],
    "difficulty": "very_hard",
    "notes": "Requires LOOKUP with -12 offset for year-over-year comparison, grouped by month"
  },
  {
    "id": 117,
    "category": "temporal_analysis",
    "question": "show me the 3-month moving average of sales by month",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Order Date"],
    "expected_calculations": [
      {
        "fieldCaption": "3-Month Moving Avg",
        "calculation": "WINDOW_AVG(SUM([Sales]), -2, 0)"
      }
    ],
    "difficulty": "very_hard",
    "notes": "Requires window function with range for moving average calculation"
  },
  {
    "id": 118,
    "category": "temporal_analysis",
    "question": "find the month with the highest sales in each year, and show the difference from the yearly average",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Order Date"],
    "expected_calculations": [
      {
        "fieldCaption": "Yearly Avg",
        "calculation": "WINDOW_AVG(SUM([Sales]))"
      },
      {
        "fieldCaption": "Difference from Avg",
        "calculation": "SUM([Sales]) - WINDOW_AVG(SUM([Sales]))"
      }
    ],
    "expected_filters": [
      {
        "type": "TOP",
        "field": {"fieldCaption": "Order Date"},
        "filterType": "TOP",
        "howMany": 1,
        "direction": "TOP",
        "fieldToMeasure": {
          "fieldCaption": "Sales",
          "function": "SUM"
        }
      }
    ],
    "difficulty": "very_hard",
    "notes": "Combines TOP filter with window calculation for yearly context"
  },
  {
    "id": 119,
    "category": "temporal_analysis",
    "question": "show me sales for the last complete quarter compared to the same quarter in the previous year",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Order Date"],
    "expected_calculations": [
      {
        "fieldCaption": "Previous Year Same Quarter",
        "calculation": "LOOKUP(SUM([Sales]), -4)"
      },
      {
        "fieldCaption": "Quarter Comparison",
        "calculation": "SUM([Sales]) - LOOKUP(SUM([Sales]), -4)"
      }
    ],
    "expected_filters": [
      {
        "type": "DATE",
        "field": {"fieldCaption": "Order Date"},
        "filterType": "DATE",
        "periodType": "QUARTERS",
        "dateRangeType": "LAST",
        "rangeN": 1
      }
    ],
    "difficulty": "very_hard",
    "notes": "Requires date filter for last quarter plus LOOKUP for year-over-year quarter comparison"
  },
  {
    "id": 120,
    "category": "temporal_analysis",
    "question": "calculate the percentage of annual sales that occurred in each month",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Order Date"],
    "expected_calculations": [
      {
        "fieldCaption": "Monthly % of Annual",
        "calculation": "SUM([Sales]) / TOTAL(SUM([Sales])) * 100"
      }
    ],
    "difficulty": "very_hard",
    "notes": "Requires table calculation TOTAL() to get annual sum for percentage calculation"
  }
]
```

### Category 5: Complex Grouping and Hierarchies

```json
[
  {
    "id": 121,
    "category": "complex_grouping",
    "question": "show me sales by region and category, but only include categories where the region's sales exceed 100000",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Region", "Category"],
    "expected_filters": [
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": "Sales",
        "quantitativeFilterType": "MIN",
        "min": 100000
      }
    ],
    "difficulty": "very_hard",
    "notes": "Filter on aggregated measure with multi-level grouping"
  },
  {
    "id": 122,
    "category": "complex_grouping",
    "question": "find the top 5 sub-categories within each category by profit",
    "expected_fields": ["Profit"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Category", "Sub-Category"],
    "expected_filters": [
      {
        "type": "TOP",
        "field": {"fieldCaption": "Sub-Category"},
        "filterType": "TOP",
        "howMany": 5,
        "direction": "TOP",
        "fieldToMeasure": {
          "fieldCaption": "Profit",
          "function": "SUM"
        }
      }
    ],
    "difficulty": "very_hard",
    "notes": "TOP filter within category hierarchy - requires understanding of filter context"
  },
  {
    "id": 123,
    "category": "complex_grouping",
    "question": "show me the ratio of sales between the top and bottom performing states within each region",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Region", "State"],
    "expected_calculations": [
      {
        "fieldCaption": "Top State Sales",
        "calculation": "WINDOW_MAX(SUM([Sales]))"
      },
      {
        "fieldCaption": "Bottom State Sales",
        "calculation": "WINDOW_MIN(SUM([Sales]))"
      },
      {
        "fieldCaption": "Top to Bottom Ratio",
        "calculation": "WINDOW_MAX(SUM([Sales])) / WINDOW_MIN(SUM([Sales]))"
      }
    ],
    "difficulty": "very_hard",
    "notes": "Requires window functions to find min/max within region, then calculate ratio"
  },
  {
    "id": 124,
    "category": "complex_grouping",
    "question": "calculate the percentage contribution of each city to its state's total sales",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["State", "City"],
    "expected_calculations": [
      {
        "fieldCaption": "State Total",
        "calculation": "WINDOW_SUM(SUM([Sales]))"
      },
      {
        "fieldCaption": "City % of State",
        "calculation": "SUM([Sales]) / WINDOW_SUM(SUM([Sales])) * 100"
      }
    ],
    "difficulty": "very_hard",
    "notes": "Requires window sum within state grouping for percentage calculation"
  },
  {
    "id": 125,
    "category": "complex_grouping",
    "question": "show me products that rank in the top 3 by sales within their category, and include their profit margin",
    "expected_fields": ["Sales", "Profit"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Category", "Product Name"],
    "expected_filters": [
      {
        "type": "TOP",
        "field": {"fieldCaption": "Product Name"},
        "filterType": "TOP",
        "howMany": 3,
        "direction": "TOP",
        "fieldToMeasure": {
          "fieldCaption": "Sales",
          "function": "SUM"
        }
      }
    ],
    "expected_calculations": [
      {
        "fieldCaption": "Profit Margin",
        "calculation": "SUM([Profit]) / SUM([Sales])"
      }
    ],
    "difficulty": "very_hard",
    "notes": "TOP filter within category plus calculated profit margin field"
  }
]
```

### Category 6: Conditional Aggregations

```json
[
  {
    "id": 126,
    "category": "conditional_aggregations",
    "question": "calculate total sales for profitable orders only, where profit is greater than zero",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_filters": [
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": {"fieldCaption": "Profit"},
        "filterType": "QUANTITATIVE_NUMERICAL",
        "quantitativeFilterType": "MIN",
        "min": 0.01
      }
    ],
    "difficulty": "very_hard",
    "notes": "Filter on profit before aggregating sales"
  },
  {
    "id": 127,
    "category": "conditional_aggregations",
    "question": "show me the average sales for orders with discount above 15%, grouped by region",
    "expected_fields": ["Sales"],
    "expected_aggregation": "AVG",
    "expected_grouping": ["Region"],
    "expected_filters": [
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": {"fieldCaption": "Discount"},
        "filterType": "QUANTITATIVE_NUMERICAL",
        "quantitativeFilterType": "MIN",
        "min": 0.15
      }
    ],
    "difficulty": "very_hard",
    "notes": "Filter on discount, then calculate AVG sales per order by region"
  },
  {
    "id": 128,
    "category": "conditional_aggregations",
    "question": "find the sum of sales where the profit margin exceeds 25%, by product category",
    "expected_fields": ["Sales", "Profit"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Category"],
    "expected_filters": [
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": "Profit Margin",
        "quantitativeFilterType": "MIN",
        "min": 0.25
      }
    ],
    "expected_calculations": [
      {
        "fieldCaption": "Profit Margin",
        "calculation": "SUM([Profit]) / SUM([Sales])"
      }
    ],
    "difficulty": "very_hard",
    "notes": "Filter on calculated profit margin field"
  },
  {
    "id": 129,
    "category": "conditional_aggregations",
    "question": "calculate the count of orders where sales per order is above the overall average sales per order",
    "expected_fields": ["Sales", "Order ID"],
    "expected_aggregation": ["AVG", "COUNTD"],
    "expected_grouping": ["Order ID"],
    "expected_calculations": [
      {
        "fieldCaption": "Sales per Order",
        "calculation": "SUM([Sales])"
      },
      {
        "fieldCaption": "Overall Avg",
        "calculation": "WINDOW_AVG(SUM([Sales]))"
      }
    ],
    "expected_filters": [
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": "Sales per Order",
        "quantitativeFilterType": "MIN",
        "min": "WINDOW_AVG(SUM([Sales]))"
      }
    ],
    "difficulty": "very_hard",
    "notes": "Complex: filter orders by comparing against overall average, then count"
  },
  {
    "id": 130,
    "category": "conditional_aggregations",
    "question": "show me total profit for products that have been sold in at least 5 different states",
    "expected_fields": ["Profit", "State"],
    "expected_aggregation": ["SUM", "COUNTD"],
    "expected_grouping": ["Product Name"],
    "expected_filters": [
      {
        "type": "QUANTITATIVE_NUMERICAL",
        "field": "State Count",
        "quantitativeFilterType": "MIN",
        "min": 5
      }
    ],
    "expected_calculations": [
      {
        "fieldCaption": "State Count",
        "calculation": "COUNTD([State])"
      }
    ],
    "difficulty": "very_hard",
    "notes": "Filter products by count of distinct states, then sum profit"
  }
]
```

---

## Summary

**Total Questions:** 30  
**Difficulty Level:** Very Hard  
**Categories:**
- Complex Calculations and Ratios: 5 questions
- Multi-Step Analytical Queries: 5 questions
- Complex Filtering Logic: 5 questions
- Advanced Temporal Analysis: 5 questions
- Complex Grouping and Hierarchies: 5 questions
- Conditional Aggregations: 5 questions

**Key Challenges Tested:**
1. Calculated fields with complex formulas
2. Window functions and table calculations
3. Multi-level filtering (including filters on calculated fields)
4. TOP filters within hierarchies
5. Year-over-year and period-over-period comparisons
6. Conditional aggregations based on calculated metrics
7. Percentage of total calculations
8. Moving averages and cumulative calculations
9. Complex multi-filter combinations
10. Filtering on aggregated measures

**Expected Success Rate:** 40-60% (very challenging for current agent capabilities)
