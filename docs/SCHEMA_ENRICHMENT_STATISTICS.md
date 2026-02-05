# Schema Enrichment Statistics

**Date:** February 5, 2026  
**Purpose:** Document the field statistics included in schema enrichment

---

## Overview

The schema enrichment service can optionally include detailed field statistics to provide better context for AI query generation. These statistics help the LLM understand the data distribution and characteristics of each field.

---

## Field Statistics Included

### 1. Cardinality (Distinct Count)

**What it is:** The number of distinct/unique values in a field.

**How it's calculated:**
- For **dimensions**: Uses `COUNTD()` function on the field
- For **measures**: Not typically calculated (measures are aggregated)

**Use case:** Helps determine if a field is:
- High cardinality (e.g., Customer ID, Transaction ID) → Good for filtering
- Low cardinality (e.g., Status, Category) → Good for grouping
- Very low cardinality (e.g., Yes/No) → Boolean-like field

**Example:**
```json
{
  "fieldCaption": "Region",
  "cardinality": 5
}
```

---

### 2. Sample Values

**What it is:** A sample of actual values from the field (up to 10 distinct values).

**How it's calculated:**
- For **dimensions**: Queries the field with `disaggregate: true` to get raw values
- For **measures**: Not typically provided (measures are aggregated)

**Use case:** 
- Helps LLM understand what values exist in the field
- Useful for generating accurate filters
- Shows data format and examples

**Example:**
```json
{
  "fieldCaption": "Status",
  "sample_values": ["Active", "Inactive", "Pending", "Cancelled"]
}
```

---

### 3. Min/Max Values

**What it is:** Minimum and maximum values for numeric fields.

**How it's calculated:**
- For **measures**: Uses `MIN()` and `MAX()` aggregations
- For **dimensions**: Only calculated if the dimension is numeric

**Use case:**
- Helps understand the range of numeric values
- Useful for generating appropriate filters
- Shows data scale (e.g., sales in thousands vs millions)

**Example:**
```json
{
  "fieldCaption": "Sales",
  "min": 0.0,
  "max": 1500000.0
}
```

---

### 4. Null Percentage

**What it is:** Percentage of null/missing values in the field.

**How it's calculated:**
- Compares `COUNT(*)` vs `COUNT(field)` to determine null percentage
- Currently experimental - may not be available for all fields

**Use case:**
- Helps understand data quality
- Useful for determining if null handling is needed in queries

**Example:**
```json
{
  "fieldCaption": "Email",
  "null_percentage": 15.5
}
```

---

## API Usage

### Enabling Statistics

Statistics are included by default when enriching a schema. To disable:

```python
enriched = await service.enrich_datasource_schema(
    datasource_id,
    force_refresh=False,
    include_statistics=False  # Disable statistics
)
```

### API Endpoint

```http
POST /api/v1/vizql/datasources/{datasource_id}/enrich-schema
```

**Query Parameters:**
- `force_refresh` (bool): Bypass cache
- `include_statistics` (bool): Include field statistics (default: true)

---

## Performance Considerations

**Important:** Fetching statistics requires additional queries to the VizQL Data Service API for each field. This can significantly increase enrichment time:

- **Without statistics:** ~2-5 seconds per datasource
- **With statistics:** ~5-15 seconds per datasource (depends on number of fields)

**Recommendations:**
1. Statistics are cached along with the enriched schema (1 hour TTL)
2. Consider disabling statistics for very large datasources (>100 fields)
3. Statistics can be fetched incrementally if needed

---

## Response Format

### Field Object with Statistics

```json
{
  "fieldCaption": "Sales",
  "fieldName": "[Sales]",
  "dataType": "REAL",
  "fieldRole": "MEASURE",
  "defaultAggregation": "SUM",
  "cardinality": null,
  "sample_values": [],
  "min": 0.0,
  "max": 1500000.0,
  "null_percentage": null
}
```

### Dimension Example

```json
{
  "fieldCaption": "Region",
  "fieldName": "[Region]",
  "dataType": "STRING",
  "fieldRole": "DIMENSION",
  "cardinality": 5,
  "sample_values": ["North", "South", "East", "West", "Central"],
  "min": null,
  "max": null,
  "null_percentage": null
}
```

---

## Implementation Details

### Statistics Query Logic

**For Dimensions:**
```json
{
  "query": {
    "fields": [
      {"fieldCaption": "Region"},
      {"fieldCaption": "Region", "function": "COUNTD"}
    ]
  },
  "options": {
    "returnFormat": "OBJECTS",
    "disaggregate": true
  }
}
```

**For Measures:**
```json
{
  "query": {
    "fields": [
      {"fieldCaption": "Sales", "function": "MIN"},
      {"fieldCaption": "Sales", "function": "MAX"},
      {"fieldCaption": "Sales", "function": "COUNT"}
    ]
  },
  "options": {
    "returnFormat": "OBJECTS",
    "disaggregate": false
  }
}
```

---

## Error Handling

Statistics fetching is designed to be non-blocking:
- If statistics cannot be fetched for a field, the field is still enriched without statistics
- Errors are logged at debug level
- Partial statistics are returned if available

---

## Future Enhancements

Potential improvements:
1. **Batch queries:** Query multiple fields in a single request
2. **Incremental loading:** Fetch statistics on-demand
3. **More statistics:** Median, quartiles, standard deviation
4. **Value distribution:** Histogram data for numeric fields
5. **Common values:** Most frequent values for dimensions

---

## Related Files

- `backend/app/services/tableau/client.py` - `get_field_statistics()` method
- `backend/app/services/agents/vizql/schema_enrichment.py` - Enrichment service
- `backend/app/api/vizql.py` - API endpoint
- `frontend/lib/api.ts` - Frontend API client
- `frontend/components/explorer/DatasourceEnrichButton.tsx` - UI display

---

**Last Updated:** February 5, 2026
