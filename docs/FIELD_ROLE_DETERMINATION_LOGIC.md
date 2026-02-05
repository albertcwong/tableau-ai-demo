# Field Role Determination Logic

**Date:** February 5, 2026  
**Purpose:** Document the logic used to determine whether a field is a MEASURE or DIMENSION

---

## Overview

The field role determination logic is used consistently across the application to categorize fields as either **MEASURE** or **DIMENSION**. This logic is implemented in `TableauClient.get_datasource_schema()` and should be reused in schema enrichment and other field processing.

---

## Primary Logic: `columnClass` from VizQL Data Service API

The **primary indicator** for field role is the `columnClass` field from the VizQL Data Service API `/read-metadata` endpoint.

### Rules

1. **If `columnClass == "MEASURE"`**
   - `is_measure = True`
   - `is_dimension = False`

2. **If `columnClass in ["COLUMN", "BIN", "GROUP"]`**
   - `is_measure = False`
   - `is_dimension = True`

3. **If `columnClass` is missing or unknown**
   - Use fallback logic (see below)

---

## Fallback Logic

When `columnClass` is not available or has an unknown value, use the following fallback logic:

### Step 1: Check Data Type and Aggregation

```python
data_type = field.get("dataType", "")
is_numeric = data_type in ["INTEGER", "REAL"]
has_aggregation = default_agg in ["SUM", "AVG", "MEDIAN", "COUNT", "COUNTD", "MIN", "MAX", "STDEV", "VAR", "AGG"]
```

### Step 2: Apply Rules

1. **If numeric AND has aggregation AND no explicit columnClass**
   - `is_measure = True`
   - `is_dimension = False`

2. **If `columnClass in ["CALCULATION", "TABLE_CALCULATION"]`**
   - `is_measure = has_aggregation AND is_numeric`
   - `is_dimension = not is_measure`

3. **Default (unknown types)**
   - `is_measure = False`
   - `is_dimension = True`

---

## Implementation Reference

**File:** `backend/app/services/tableau/client.py`  
**Method:** `get_datasource_schema()`  
**Lines:** 1509-1541

```python
# Determine if measure or dimension based on columnClass (primary indicator)
column_class = field.get("columnClass", "")
default_agg = field.get("defaultAggregation", "")

# Use columnClass as primary indicator
# MEASURE = measure, COLUMN/BIN/GROUP = dimension
if column_class == "MEASURE":
    is_measure = True
    is_dimension = False
elif column_class in ["COLUMN", "BIN", "GROUP"]:
    is_measure = False
    is_dimension = True
else:
    # Fallback: use defaultAggregation if columnClass not available or unknown
    data_type = field.get("dataType", "")
    is_numeric = data_type in ["INTEGER", "REAL"]
    has_aggregation = default_agg in ["SUM", "AVG", "MEDIAN", "COUNT", "COUNTD", "MIN", "MAX", "STDEV", "VAR", "AGG"]
    
    if is_numeric and has_aggregation and not column_class:
        is_measure = True
        is_dimension = False
    elif column_class in ["CALCULATION", "TABLE_CALCULATION"]:
        is_measure = has_aggregation and is_numeric
        is_dimension = not is_measure
    else:
        # Default to dimension for unknown types
        is_measure = False
        is_dimension = True
```

---

## Why Not Use Metadata API `role` Field?

The Tableau Metadata API provides a `role` field that can be "MEASURE" or "DIMENSION", but:

1. **Inconsistency:** The Metadata API `role` field is not always reliable and may return "UNKNOWN" or incorrect values
2. **Proven Logic:** The `columnClass`-based logic has been tested and works correctly in the UI sidepanel
3. **Data Source:** VizQL Data Service API is the primary source for query construction, so using its `columnClass` ensures consistency

---

## Usage in Schema Enrichment

The schema enrichment service (`SchemaEnrichmentService.enrich_datasource_schema()`) should use this same logic to ensure consistency with the UI.

**Note:** Metadata API can still be used for:
- Field descriptions (if more detailed)
- Field formulas (for calculated fields)
- Additional metadata not available in VizQL

But **field role determination** should always use the `columnClass`-based logic documented here.

---

## Testing

When testing field role determination:

1. Verify fields with `columnClass == "MEASURE"` are categorized as measures
2. Verify fields with `columnClass in ["COLUMN", "BIN", "GROUP"]` are categorized as dimensions
3. Verify fallback logic works for fields without explicit `columnClass`
4. Compare results with UI sidepanel categorization (should match exactly)

---

## Related Files

- `backend/app/services/tableau/client.py` - `get_datasource_schema()` method
- `backend/app/services/agents/vizql/schema_enrichment.py` - Schema enrichment service
- `frontend/components/explorer/ThreePanelLayout.tsx` - UI that uses `is_measure`/`is_dimension` flags

---

**Last Updated:** February 5, 2026
