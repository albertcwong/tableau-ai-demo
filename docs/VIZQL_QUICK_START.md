# VizQL Query Accuracy - Quick Start Guide

**For:** Engineering Team  
**Purpose:** Quick reference for using the new VizQL improvements

---

## How It Works

### User Flow
1. **User selects datasource** in UI
2. **User clicks "Enrich Schema for AI"** button (one-time per datasource)
3. **Schema enriched** and cached in Redis (1 hour)
4. **User asks query** in natural language
5. **Agent uses enriched schema** to build accurate query
6. **Semantic validator** catches errors before execution
7. **Query executes** successfully (70%+ first-attempt success)

---

## For Developers

### Using Enriched Schema in Code

```python
from app.services.agents.vizql.schema_enrichment import SchemaEnrichmentService
from app.services.tableau.client import TableauClient

# Initialize
tableau_client = TableauClient()
service = SchemaEnrichmentService(tableau_client)

# Enrich schema
enriched = await service.enrich_datasource_schema("datasource-luid")

# Access enriched data
measures = enriched["measures"]  # List of measure field names
dimensions = enriched["dimensions"]  # List of dimension field names
field_map = enriched["field_map"]  # Fast lookup: field_map["total sales"]
```

### Using Semantic Rules

```python
from app.services.agents.vizql.semantic_rules import suggest_aggregation

# Suggest aggregation for a field
agg = suggest_aggregation("Total Sales", "REAL", "MEASURE")
# Returns: "SUM"
```

### Using Constraint Validator

```python
from app.services.agents.vizql.constraint_validator import VizQLConstraintValidator

# Validate query
validator = VizQLConstraintValidator(enriched_schema)
is_valid, errors, suggestions = validator.validate_query(query)

if not is_valid:
    print(f"Errors: {errors}")
    print(f"Suggestions: {suggestions}")
```

### Using Compressed Context

```python
from app.services.agents.vizql.context_builder import build_full_compressed_context

# Build context for LLM
context = build_full_compressed_context(
    enriched_schema=enriched_schema,
    user_query="show total sales by region",
    required_measures=["sales"],
    required_dimensions=["region"]
)
```

---

## API Endpoints

### Enrich Schema
```bash
POST /api/v1/vizql/datasources/{datasource_id}/enrich-schema
Headers:
  Authorization: Bearer <token>
  X-Tableau-Config-Id: <config-id>

Response:
{
  "datasource_id": "ds-123",
  "field_count": 47,
  "measure_count": 23,
  "dimension_count": 24,
  "cached": false,
  "enriched_schema": {...}
}
```

### Get Supported Functions
```bash
GET /api/v1/vizql/datasources/{datasource_id}/supported-functions
Headers:
  Authorization: Bearer <token>
  X-Tableau-Config-Id: <config-id>

Response:
{
  "datasource_id": "ds-123",
  "functions": [...],
  "function_count": 15
}
```

---

## Frontend Components

### DatasourceEnrichButton
```tsx
import { DatasourceEnrichButton } from '@/components/explorer/DatasourceEnrichButton';

<DatasourceEnrichButton 
  datasourceId="ds-123"
  datasourceName="Sales Data"
  onEnriched={(result) => {
    console.log(`Enriched: ${result.field_count} fields`);
  }}
/>
```

---

## Troubleshooting

### Schema Enrichment Fails
**Symptoms:** Enrichment button shows error  
**Causes:**
- Tableau server not accessible
- VizQL API not available
- Authentication issues

**Solutions:**
- Check Tableau connection
- Verify VizQL API endpoint accessible
- Check authentication token

### Queries Still Failing
**Symptoms:** Low success rate persists  
**Causes:**
- Schema not enriched
- Cache expired
- Enrichment failed silently

**Solutions:**
- Click "Enrich Schema" button again
- Check Redis cache: `redis-cli GET enriched_schema:<id>`
- Check backend logs for enrichment errors

### High Token Usage
**Symptoms:** Token usage still high  
**Causes:**
- Large datasource (>200 fields)
- Enrichment not used
- Compressed context not applied

**Solutions:**
- Verify enriched_schema in state
- Check query_builder uses compressed context
- Verify field truncation working

---

## Monitoring

### Key Metrics to Track
- **Enrichment API calls:** `/api/v1/vizql/datasources/*/enrich-schema`
- **Cache hit rate:** Redis `enriched_schema:*` keys
- **Query success rate:** First-attempt vs retries
- **Token usage:** Per query (if logged)
- **Validation errors:** Semantic vs syntax errors

### Redis Keys to Monitor
```bash
# Check enrichment cache
redis-cli KEYS enriched_schema:*

# Check cache TTL
redis-cli TTL enriched_schema:<datasource-id>

# Check supported functions cache
redis-cli KEYS supported_functions:*
```

---

## Common Patterns

### Pattern 1: Enrich on Datasource Selection
```typescript
// In datasource selector component
const handleDatasourceSelect = async (datasourceId: string) => {
  // Auto-enrich when datasource selected
  try {
    await vizqlApi.enrichSchema(datasourceId);
  } catch (error) {
    // Silently fail, will use basic schema
    console.warn('Enrichment failed, using basic schema');
  }
};
```

### Pattern 2: Validate Before Execution
```python
# In executor node
enriched_schema = state.get("enriched_schema")
if enriched_schema:
    validator = VizQLConstraintValidator(enriched_schema)
    is_valid, errors, suggestions = validator.validate_query(query)
    if not is_valid:
        # Return errors before execution
        return {"error": errors, "suggestions": suggestions}
```

### Pattern 3: Fallback Chain
```python
# Always have fallback
enriched_schema = state.get("enriched_schema")
schema = enriched_schema or state.get("schema")  # Fallback to basic

if enriched_schema:
    # Use compressed context
    context = build_compressed_schema_context(enriched_schema)
else:
    # Use basic schema
    context = json.dumps(schema.get("columns", []))
```

---

## Best Practices

1. **Always Enrich Before Queries:**
   - Click "Enrich Schema" button for each datasource
   - Enrichment is cached, so one-time is enough

2. **Monitor Cache:**
   - Check Redis cache hit rate
   - Refresh if datasource schema changes

3. **Handle Fallbacks:**
   - Code should work with or without enrichment
   - Never assume enriched_schema exists

4. **Use Semantic Rules:**
   - Always use suggest_aggregation() for measures
   - Validate aggregations with validate_aggregation_for_type()

5. **Provide Good Errors:**
   - Use constraint validator suggestions
   - Format errors clearly for users

---

## File Reference

### Core Files
- `semantic_rules.py` - VizQL rules and aggregation logic
- `schema_enrichment.py` - Enrichment service
- `context_builder.py` - Compressed context generation
- `constraint_validator.py` - Semantic validation

### Node Files
- `schema_fetch.py` - Fetches and enriches schema
- `query_builder.py` - Builds query with compressed context
- `validator.py` - Validates query semantically
- `refiner.py` - Refines queries using suggestions

### API Files
- `api/vizql.py` - Enrichment endpoints

### Frontend Files
- `DatasourceEnrichButton.tsx` - UI button component
- `lib/api.ts` - API client functions

---

**Quick Start Version:** 1.0  
**Last Updated:** February 5, 2026
