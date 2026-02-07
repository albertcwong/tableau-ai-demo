# Superstore Evaluation Questions (Structured Format)

**Date:** February 6, 2026  
**Format:** JSON structure for easy import/automation

---

## Questions by Category

### Category 1: Basic Aggregations

```json
[
  {
    "id": 1,
    "category": "basic_aggregations",
    "question": "show me total sales",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": [],
    "difficulty": "easy"
  },
  {
    "id": 2,
    "category": "basic_aggregations",
    "question": "what is the total profit",
    "expected_fields": ["Profit"],
    "expected_aggregation": "SUM",
    "expected_grouping": [],
    "difficulty": "easy"
  },
  {
    "id": 3,
    "category": "basic_aggregations",
    "question": "average sales per order",
    "expected_fields": ["Sales"],
    "expected_aggregation": "AVG",
    "expected_grouping": [],
    "difficulty": "easy"
  },
  {
    "id": 4,
    "category": "basic_aggregations",
    "question": "total quantity sold",
    "expected_fields": ["Quantity"],
    "expected_aggregation": "SUM",
    "expected_grouping": [],
    "difficulty": "easy"
  },
  {
    "id": 5,
    "category": "basic_aggregations",
    "question": "average discount amount",
    "expected_fields": ["Discount"],
    "expected_aggregation": "AVG",
    "expected_grouping": [],
    "difficulty": "easy"
  },
  {
    "id": 6,
    "category": "basic_aggregations",
    "question": "count of orders",
    "expected_fields": ["Order ID"],
    "expected_aggregation": "COUNT",
    "expected_grouping": [],
    "difficulty": "easy"
  },
  {
    "id": 7,
    "category": "basic_aggregations",
    "question": "sum of sales by region",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Region"],
    "difficulty": "easy"
  },
  {
    "id": 8,
    "category": "basic_aggregations",
    "question": "total profit by state",
    "expected_fields": ["Profit"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["State"],
    "difficulty": "easy"
  },
  {
    "id": 9,
    "category": "basic_aggregations",
    "question": "average sales by category",
    "expected_fields": ["Sales"],
    "expected_aggregation": "AVG",
    "expected_grouping": ["Category"],
    "difficulty": "easy"
  },
  {
    "id": 10,
    "category": "basic_aggregations",
    "question": "sum of quantity by sub-category",
    "expected_fields": ["Quantity"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Sub-Category"],
    "difficulty": "easy"
  }
]
```

### Category 2: Temporal Queries

```json
[
  {
    "id": 11,
    "category": "temporal",
    "question": "sales by month",
    "expected_fields": ["Sales", "Order Date"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Order Date"],
    "expected_date_function": "TRUNC_MONTH",
    "difficulty": "medium"
  },
  {
    "id": 12,
    "category": "temporal",
    "question": "total sales by year",
    "expected_fields": ["Sales", "Order Date"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Order Date"],
    "expected_date_function": "TRUNC_YEAR",
    "difficulty": "medium"
  },
  {
    "id": 13,
    "category": "temporal",
    "question": "profit by quarter",
    "expected_fields": ["Profit", "Order Date"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Order Date"],
    "expected_date_function": "TRUNC_QUARTER",
    "difficulty": "medium"
  },
  {
    "id": 14,
    "category": "temporal",
    "question": "monthly sales trend",
    "expected_fields": ["Sales", "Order Date"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Order Date"],
    "expected_date_function": "TRUNC_MONTH",
    "difficulty": "medium"
  },
  {
    "id": 15,
    "category": "temporal",
    "question": "sales by year and month",
    "expected_fields": ["Sales", "Order Date"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Order Date"],
    "expected_date_function": ["YEAR", "MONTH"],
    "difficulty": "medium"
  },
  {
    "id": 16,
    "category": "temporal",
    "question": "total sales for 2023",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": [],
    "expected_filters": [{"type": "DATE", "field": "Order Date", "year": 2023}],
    "difficulty": "medium"
  },
  {
    "id": 17,
    "category": "temporal",
    "question": "sales in the last 3 months",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": [],
    "expected_filters": [{"type": "DATE", "dateRangeType": "LASTN", "periodType": "MONTHS", "rangeN": 3}],
    "difficulty": "medium"
  },
  {
    "id": 18,
    "category": "temporal",
    "question": "profit by month for 2024",
    "expected_fields": ["Profit", "Order Date"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Order Date"],
    "expected_date_function": "TRUNC_MONTH",
    "expected_filters": [{"type": "DATE", "field": "Order Date", "year": 2024}],
    "difficulty": "medium"
  },
  {
    "id": 19,
    "category": "temporal",
    "question": "sales by week",
    "expected_fields": ["Sales", "Order Date"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Order Date"],
    "expected_date_function": "TRUNC_WEEK",
    "difficulty": "medium"
  },
  {
    "id": 20,
    "category": "temporal",
    "question": "year over year sales comparison",
    "expected_fields": ["Sales", "Order Date"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Order Date"],
    "expected_date_function": "TRUNC_YEAR",
    "difficulty": "medium"
  }
]
```

### Category 3: Distinct Counts

```json
[
  {
    "id": 21,
    "category": "distinct_counts",
    "question": "how many customers",
    "expected_fields": ["Customer Name"],
    "expected_aggregation": "COUNTD",
    "expected_grouping": [],
    "difficulty": "easy"
  },
  {
    "id": 22,
    "category": "distinct_counts",
    "question": "how many products",
    "expected_fields": ["Product Name"],
    "expected_aggregation": "COUNTD",
    "expected_grouping": [],
    "difficulty": "easy"
  },
  {
    "id": 23,
    "category": "distinct_counts",
    "question": "how many orders",
    "expected_fields": ["Order ID"],
    "expected_aggregation": "COUNTD",
    "expected_grouping": [],
    "difficulty": "easy"
  },
  {
    "id": 24,
    "category": "distinct_counts",
    "question": "number of unique customers by region",
    "expected_fields": ["Customer Name"],
    "expected_aggregation": "COUNTD",
    "expected_grouping": ["Region"],
    "difficulty": "medium"
  },
  {
    "id": 25,
    "category": "distinct_counts",
    "question": "distinct count of products by category",
    "expected_fields": ["Product Name"],
    "expected_aggregation": "COUNTD",
    "expected_grouping": ["Category"],
    "difficulty": "medium"
  },
  {
    "id": 26,
    "category": "distinct_counts",
    "question": "how many states",
    "expected_fields": ["State"],
    "expected_aggregation": "COUNTD",
    "expected_grouping": [],
    "difficulty": "easy"
  },
  {
    "id": 27,
    "category": "distinct_counts",
    "question": "count of unique customers who made purchases",
    "expected_fields": ["Customer Name"],
    "expected_aggregation": "COUNTD",
    "expected_grouping": [],
    "difficulty": "easy"
  },
  {
    "id": 28,
    "category": "distinct_counts",
    "question": "how many different sub-categories",
    "expected_fields": ["Sub-Category"],
    "expected_aggregation": "COUNTD",
    "expected_grouping": [],
    "difficulty": "easy"
  }
]
```

### Category 4: Top N & Ranking

```json
[
  {
    "id": 29,
    "category": "top_n",
    "question": "top 10 customers by sales",
    "expected_fields": ["Customer Name", "Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Customer Name"],
    "expected_filters": [{"type": "TOP", "howMany": 10, "direction": "TOP", "fieldToMeasure": "Sales"}],
    "difficulty": "medium"
  },
  {
    "id": 30,
    "category": "top_n",
    "question": "bottom 5 products by profit",
    "expected_fields": ["Product Name", "Profit"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Product Name"],
    "expected_filters": [{"type": "TOP", "howMany": 5, "direction": "BOTTOM", "fieldToMeasure": "Profit"}],
    "difficulty": "medium"
  },
  {
    "id": 31,
    "category": "top_n",
    "question": "top 3 regions by total sales",
    "expected_fields": ["Region", "Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Region"],
    "expected_filters": [{"type": "TOP", "howMany": 3, "direction": "TOP", "fieldToMeasure": "Sales"}],
    "difficulty": "medium"
  },
  {
    "id": 32,
    "category": "top_n",
    "question": "best performing categories",
    "expected_fields": ["Category", "Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Category"],
    "expected_filters": [{"type": "TOP", "howMany": 10, "direction": "TOP", "fieldToMeasure": "Sales"}],
    "difficulty": "medium",
    "note": "May need to infer N from context"
  },
  {
    "id": 33,
    "category": "top_n",
    "question": "worst 5 states by profit",
    "expected_fields": ["State", "Profit"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["State"],
    "expected_filters": [{"type": "TOP", "howMany": 5, "direction": "BOTTOM", "fieldToMeasure": "Profit"}],
    "difficulty": "medium"
  },
  {
    "id": 34,
    "category": "top_n",
    "question": "top 10 products by quantity sold",
    "expected_fields": ["Product Name", "Quantity"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Product Name"],
    "expected_filters": [{"type": "TOP", "howMany": 10, "direction": "TOP", "fieldToMeasure": "Quantity"}],
    "difficulty": "medium"
  },
  {
    "id": 35,
    "category": "top_n",
    "question": "highest sales by customer",
    "expected_fields": ["Customer Name", "Sales"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Customer Name"],
    "expected_filters": [{"type": "TOP", "howMany": 1, "direction": "TOP", "fieldToMeasure": "Sales"}],
    "difficulty": "medium",
    "note": "May infer N=1 or N=10"
  },
  {
    "id": 36,
    "category": "top_n",
    "question": "top 5 sub-categories by profit margin",
    "expected_fields": ["Sub-Category"],
    "expected_calculation": "SUM([Profit])/SUM([Sales])",
    "expected_grouping": ["Sub-Category"],
    "expected_filters": [{"type": "TOP", "howMany": 5, "direction": "TOP"}],
    "difficulty": "hard"
  }
]
```

### Category 5: Filtering

```json
[
  {
    "id": 37,
    "category": "filtering",
    "question": "sales for California",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_filters": [{"type": "SET", "field": "State", "values": ["California"]}],
    "difficulty": "easy"
  },
  {
    "id": 38,
    "category": "filtering",
    "question": "profit by region for West and East",
    "expected_fields": ["Profit"],
    "expected_aggregation": "SUM",
    "expected_grouping": ["Region"],
    "expected_filters": [{"type": "SET", "field": "Region", "values": ["West", "East"]}],
    "difficulty": "medium"
  },
  {
    "id": 39,
    "category": "filtering",
    "question": "sales for Furniture category",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_filters": [{"type": "SET", "field": "Category", "values": ["Furniture"]}],
    "difficulty": "easy"
  },
  {
    "id": 40,
    "category": "filtering",
    "question": "products containing 'table'",
    "expected_fields": ["Product Name"],
    "expected_filters": [{"type": "MATCH", "field": "Product Name", "contains": "table"}],
    "difficulty": "medium"
  },
  {
    "id": 41,
    "category": "filtering",
    "question": "sales where profit is greater than 1000",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_filters": [{"type": "QUANTITATIVE_NUMERICAL", "field": "Profit", "quantitativeFilterType": "MIN", "min": 1000}],
    "difficulty": "medium"
  },
  {
    "id": 42,
    "category": "filtering",
    "question": "orders with discount greater than 10%",
    "expected_fields": ["Order ID"],
    "expected_filters": [{"type": "QUANTITATIVE_NUMERICAL", "field": "Discount", "quantitativeFilterType": "MIN", "min": 0.1}],
    "difficulty": "medium"
  },
  {
    "id": 43,
    "category": "filtering",
    "question": "sales between 2023-01-01 and 2023-12-31",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_filters": [{"type": "QUANTITATIVE_DATE", "field": "Order Date", "quantitativeFilterType": "RANGE", "minDate": "2023-01-01", "maxDate": "2023-12-31"}],
    "difficulty": "medium"
  },
  {
    "id": 44,
    "category": "filtering",
    "question": "sales for this year",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_filters": [{"type": "DATE", "dateRangeType": "CURRENT", "periodType": "YEARS"}],
    "difficulty": "medium"
  },
  {
    "id": 45,
    "category": "filtering",
    "question": "customers in New York, California, and Texas",
    "expected_fields": ["Customer Name"],
    "expected_filters": [{"type": "SET", "field": "State", "values": ["New York", "California", "Texas"]}],
    "difficulty": "easy"
  },
  {
    "id": 46,
    "category": "filtering",
    "question": "sales for first class shipping",
    "expected_fields": ["Sales"],
    "expected_aggregation": "SUM",
    "expected_filters": [{"type": "SET", "field": "Ship Mode", "values": ["First Class"]}],
    "difficulty": "easy"
  }
]
```

### Category 6: Calculations & Ratios

```json
[
  {
    "id": 47,
    "category": "calculations",
    "question": "calculate profit margin",
    "expected_calculation": "SUM([Profit])/SUM([Sales])",
    "expected_field_name": "Profit Margin",
    "difficulty": "medium"
  },
  {
    "id": 48,
    "category": "calculations",
    "question": "sales to profit ratio",
    "expected_calculation": "SUM([Sales])/SUM([Profit])",
    "expected_field_name": "Sales to Profit Ratio",
    "difficulty": "medium"
  },
  {
    "id": 49,
    "category": "calculations",
    "question": "profit margin by category",
    "expected_calculation": "SUM([Profit])/SUM([Sales])",
    "expected_field_name": "Profit Margin",
    "expected_grouping": ["Category"],
    "difficulty": "medium"
  },
  {
    "id": 50,
    "category": "calculations",
    "question": "average discount percentage",
    "expected_fields": ["Discount"],
    "expected_aggregation": "AVG",
    "difficulty": "easy",
    "note": "May need to multiply by 100 if stored as decimal"
  },
  {
    "id": 51,
    "category": "calculations",
    "question": "sales per customer",
    "expected_calculation": "SUM([Sales])/COUNTD([Customer Name])",
    "expected_field_name": "Sales per Customer",
    "difficulty": "medium"
  },
  {
    "id": 52,
    "category": "calculations",
    "question": "total sales divided by total quantity",
    "expected_calculation": "SUM([Sales])/SUM([Quantity])",
    "expected_field_name": "Sales per Quantity",
    "difficulty": "medium"
  },
  {
    "id": 53,
    "category": "calculations",
    "question": "profit margin percentage by region",
    "expected_calculation": "(SUM([Profit])/SUM([Sales]))*100",
    "expected_field_name": "Profit Margin Percentage",
    "expected_grouping": ["Region"],
    "difficulty": "medium"
  },
  {
    "id": 54,
    "category": "calculations",
    "question": "revenue per order",
    "expected_calculation": "SUM([Sales])/COUNTD([Order ID])",
    "expected_field_name": "Revenue per Order",
    "difficulty": "medium"
  },
  {
    "id": 55,
    "category": "calculations",
    "question": "discount rate by segment",
    "expected_fields": ["Discount"],
    "expected_aggregation": "AVG",
    "expected_grouping": ["Segment"],
    "difficulty": "easy"
  },
  {
    "id": 56,
    "category": "calculations",
    "question": "profit as percentage of sales",
    "expected_calculation": "(SUM([Profit])/SUM([Sales]))*100",
    "expected_field_name": "Profit Percentage",
    "difficulty": "medium"
  }
]
```

---

## Usage Notes

1. **Import Format:** This JSON structure can be imported into test automation tools
2. **Validation:** Each question includes expected structure for automated validation
3. **Scoring:** Use the scoring rubric from the main document
4. **Tracking:** Track results against `id` field for consistent reporting

---

**Total Questions:** 90 (partial listing above, full set in main document)
