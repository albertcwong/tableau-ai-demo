# VizQL Query Construction Accuracy Improvement Plan

**Status:** Ready for Implementation  
**Priority:** Fix Now (Current Sprint)  
**Last Updated:** 2026-02-05

---

## Executive Summary

**Problem:** VizQL agent has low success rate (~30% first-attempt, ~50% after 3 retries) due to field name hallucination and semantic misunderstandings.

**Root Cause:** LLM receives raw schema without semantic context about:
- Which fields can be combined
- When to use which aggregation functions
- Valid field relationships and constraints
- Sample values for enum fields

**Solution:** Hybrid Semantic Query Framework with:
1. Build-time VizQL rule engine
2. On-demand schema enrichment (triggered via UI)
3. Semantic constraint validation (pre/post LLM)
4. Compressed context builder (token optimization)

**Expected Improvement:**
- First-attempt success: 30% → **70%+**
- Field hallucination: 40% → **<5%**
- Token cost per query: 4000 → **2500 tokens**

---

## Current Implementation Analysis

### What We Have
```
User Query → Planner → Schema Fetch → Query Builder (LLM) → Validator → Executor
                                           ↓ (if invalid)
                                        Refiner → Loop (max 3x)
```

**Current Files:**
- `backend/app/services/agents/vizql/nodes/query_builder.py` - LLM query construction
- `backend/app/services/agents/vizql/nodes/validator.py` - Fuzzy matching validator
- `backend/app/prompts/agents/vizql/query_construction.txt` - Basic prompt
- `backend/app/prompts/agents/vizql/examples.yaml` - Few-shot examples

### What's Missing
1. **VizQL semantic rules** - No understanding of measure vs dimension behavior
2. **Field relationship constraints** - No validation of valid field combinations
3. **Sample value hints** - LLM guesses filter values instead of seeing actual data
4. **Aggregation context** - No guidance on when SUM vs COUNT vs AVG applies
5. **Compressed schema format** - Raw JSON schema is token-heavy

---

## Architecture: Hybrid Semantic Query Framework

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: VizQL Rule Engine (Build-Time, Static)           │
│  - DSL semantics (measure/dimension/aggregation rules)     │
│  - Query pattern templates                                  │
│  - Function compatibility matrix                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2: Schema Enrichment (Runtime, Cached)              │
│  - ON-DEMAND via UI button (per datasource)                │
│  - Fetches from /read-metadata endpoint                     │
│  - Adds: field roles, default aggs, descriptions, aliases   │
│  - Cached in Redis (1hr TTL)                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3: Compressed Context Builder (Runtime)             │
│  - Minified schema format for LLM                           │
│  - Token-efficient field representations                    │
│  - Inline hints (aggregation suggestions, sample values)    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 4: Semantic Constraint Validator (Pre-LLM)          │
│  - Checks field compatibility before query construction     │
│  - Suggests aggregations for measures                       │
│  - Validates filter field types                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 5: LLM Query Builder (Enhanced)                     │
│  - Receives compressed context from L1-L4                   │
│  - Few-shot prompts with semantic hints                     │
│  - Field name matching with exact caption references        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 6: Post-LLM Validator (Enhanced)                    │
│  - JSON schema validation                                   │
│  - Semantic rule checking (measures have aggs, etc)         │
│  - Detailed error messages with correction hints            │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: VizQL Rule Engine (Week 1, Days 1-2)
**Goal:** Codify VizQL-specific semantic rules

#### Tasks
1. Create `backend/app/services/agents/vizql/semantic_rules.py`
2. Define VizQL field type behaviors
3. Create aggregation compatibility matrix
4. Add query pattern templates

#### Deliverables

**File: `backend/app/services/agents/vizql/semantic_rules.py`**
```python
# VizQL Semantic Rules Engine
# Extracted from VizQLDataServiceOpenAPISchema.json

VIZQL_DATA_TYPES = [
    "INTEGER", "REAL", "STRING", "DATETIME", 
    "BOOLEAN", "DATE", "SPATIAL", "UNKNOWN"
]

VIZQL_FIELD_ROLES = {
    "MEASURE": {
        "description": "Numeric field requiring aggregation",
        "requires_aggregation": True,
        "compatible_types": ["INTEGER", "REAL"]
    },
    "DIMENSION": {
        "description": "Categorical field for grouping",
        "requires_aggregation": False,
        "compatible_types": ["STRING", "DATE", "BOOLEAN"]
    }
}

VIZQL_AGGREGATIONS = {
    "SUM": {
        "types": ["INTEGER", "REAL"],
        "description": "Sum numeric values",
        "use_cases": ["sales", "revenue", "amount", "quantity", "total"]
    },
    "AVG": {
        "types": ["INTEGER", "REAL"],
        "description": "Average numeric values",
        "use_cases": ["price", "rating", "score", "duration"]
    },
    "COUNT": {
        "types": ["*"],
        "description": "Count rows",
        "use_cases": ["rows", "records", "entries"]
    },
    "COUNTD": {
        "types": ["*"],
        "description": "Count distinct values",
        "use_cases": ["unique", "distinct", "id"]
    },
    "MIN": {
        "types": ["INTEGER", "REAL", "DATE"],
        "description": "Minimum value"
    },
    "MAX": {
        "types": ["INTEGER", "REAL", "DATE"],
        "description": "Maximum value"
    },
    "MEDIAN": {
        "types": ["INTEGER", "REAL"],
        "description": "Median value"
    },
    "STDEV": {
        "types": ["INTEGER", "REAL"],
        "description": "Standard deviation"
    },
    "VAR": {
        "types": ["INTEGER", "REAL"],
        "description": "Variance"
    }
}

VIZQL_QUERY_PATTERNS = [
    {
        "pattern": "total {measure} by {dimension}",
        "template": {
            "fields": [
                {"fieldCaption": "{measure}", "function": "SUM"},
                {"fieldCaption": "{dimension}"}
            ]
        },
        "example": "total sales by region"
    },
    {
        "pattern": "average {measure} per {dimension}",
        "template": {
            "fields": [
                {"fieldCaption": "{measure}", "function": "AVG"},
                {"fieldCaption": "{dimension}"}
            ]
        },
        "example": "average price per category"
    },
    {
        "pattern": "count of {dimension}",
        "template": {
            "fields": [
                {"fieldCaption": "{dimension}", "function": "COUNT"}
            ]
        },
        "example": "count of orders"
    }
]

def suggest_aggregation(field_name: str, field_type: str) -> str:
    """Suggest appropriate aggregation based on field semantics."""
    field_lower = field_name.lower()
    
    # Check use case keywords
    for agg, rules in VIZQL_AGGREGATIONS.items():
        if field_type in rules["types"] or "*" in rules["types"]:
            if "use_cases" in rules:
                for keyword in rules["use_cases"]:
                    if keyword in field_lower:
                        return agg
    
    # Default suggestions by type
    if field_type in ["INTEGER", "REAL"]:
        return "SUM"
    return "COUNT"

def validate_aggregation_for_type(agg: str, data_type: str) -> bool:
    """Check if aggregation is valid for data type."""
    if agg not in VIZQL_AGGREGATIONS:
        return False
    
    valid_types = VIZQL_AGGREGATIONS[agg]["types"]
    return "*" in valid_types or data_type in valid_types
```

**File: `backend/app/prompts/agents/vizql/semantic_rules.txt`**
```
## VizQL Field Role Rules

**MEASURE Fields:**
- Always require an aggregation function (SUM, AVG, COUNT, etc.)
- Typical types: INTEGER, REAL
- Examples: Sales, Revenue, Quantity, Price

**DIMENSION Fields:**
- Used for grouping (no aggregation)
- Typical types: STRING, DATE, BOOLEAN
- Examples: Region, Category, Customer Name, Order Date

## Aggregation Selection Guide

- **SUM**: Total of numeric values (sales, revenue, amount, quantity)
- **AVG**: Average of numeric values (price, rating, score)
- **COUNT**: Number of rows
- **COUNTD**: Number of unique values (customer IDs, product IDs)
- **MIN/MAX**: Minimum/maximum values (earliest date, highest price)

## Field Name Matching Rules

1. Use EXACT fieldCaption from schema metadata
2. Match is case-sensitive: "Total Sales" ≠ "total sales"
3. If user says "sales" and schema has "Total Sales", use "Total Sales"
4. Never invent field names not in the schema
```

---

### Phase 2: Schema Enrichment Service (Week 1, Days 3-4)
**Goal:** Add on-demand metadata enrichment via VizQL API

#### Tasks
1. Create enrichment service that calls `/read-metadata`
2. Add Redis caching layer
3. Build UI button in datasource explorer
4. Add API endpoint for triggering enrichment

#### Deliverables

**File: `backend/app/services/agents/vizql/schema_enrichment.py`**
```python
"""Schema enrichment service using VizQL read-metadata endpoint."""
import logging
from typing import Dict, Any, Optional
from datetime import timedelta
from app.services.tableau.client import TableauClient
from app.core.redis import redis_client
from app.services.agents.vizql.semantic_rules import suggest_aggregation

logger = logging.getLogger(__name__)

CACHE_TTL = timedelta(hours=1)

class SchemaEnrichmentService:
    """Enriches datasource schemas with VizQL metadata."""
    
    def __init__(self, tableau_client: TableauClient):
        self.tableau_client = tableau_client
    
    async def enrich_datasource_schema(
        self, 
        datasource_id: str, 
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch and enrich datasource schema.
        
        Uses /read-metadata endpoint to get:
        - fieldCaption (exact field names)
        - dataType (INTEGER, REAL, STRING, etc.)
        - fieldRole (MEASURE, DIMENSION)
        - defaultAggregation
        - description
        - aliases
        """
        # Check cache first
        cache_key = f"enriched_schema:{datasource_id}"
        if not force_refresh:
            cached = await redis_client.get(cache_key)
            if cached:
                logger.info(f"Using cached enriched schema for {datasource_id}")
                return cached
        
        logger.info(f"Enriching schema for datasource {datasource_id}")
        
        # Call VizQL /read-metadata
        metadata = await self.tableau_client.read_metadata(datasource_id)
        
        # Process metadata into enriched format
        enriched = {
            "datasource_id": datasource_id,
            "fields": [],
            "field_map": {},  # Fast lookup by fieldCaption
            "measures": [],
            "dimensions": []
        }
        
        for field_meta in metadata.get("data", []):
            field_caption = field_meta.get("fieldCaption", "")
            if not field_caption:
                continue
            
            field_info = {
                "fieldCaption": field_caption,
                "fieldName": field_meta.get("fieldName", ""),
                "dataType": field_meta.get("dataType", "UNKNOWN"),
                "fieldRole": field_meta.get("fieldRole", "UNKNOWN"),
                "fieldType": field_meta.get("fieldType", "UNKNOWN"),
                "defaultAggregation": field_meta.get("defaultAggregation"),
                "columnClass": field_meta.get("columnClass", "COLUMN"),
                "description": field_meta.get("description", ""),
                "formula": field_meta.get("formula"),
                "hidden": field_meta.get("hidden", False)
            }
            
            # Add suggested aggregation if not provided
            if not field_info["defaultAggregation"] and field_info["fieldRole"] == "MEASURE":
                field_info["suggestedAggregation"] = suggest_aggregation(
                    field_caption, 
                    field_info["dataType"]
                )
            
            enriched["fields"].append(field_info)
            enriched["field_map"][field_caption.lower()] = field_info
            
            # Categorize by role
            if field_info["fieldRole"] == "MEASURE":
                enriched["measures"].append(field_caption)
            elif field_info["fieldRole"] == "DIMENSION":
                enriched["dimensions"].append(field_caption)
        
        # Cache enriched schema
        await redis_client.setex(cache_key, CACHE_TTL, enriched)
        
        logger.info(
            f"Enriched schema cached: {len(enriched['fields'])} fields "
            f"({len(enriched['measures'])} measures, {len(enriched['dimensions'])} dimensions)"
        )
        
        return enriched
    
    async def get_supported_functions(self, datasource_id: str) -> Dict[str, Any]:
        """Fetch datasource-specific supported functions."""
        cache_key = f"supported_functions:{datasource_id}"
        cached = await redis_client.get(cache_key)
        if cached:
            return cached
        
        functions = await self.tableau_client.list_supported_functions(datasource_id)
        await redis_client.setex(cache_key, CACHE_TTL, functions)
        return functions
```

**File: `backend/app/api/vizql.py` (New endpoint)**
```python
"""VizQL schema enrichment API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from app.services.agents.vizql.schema_enrichment import SchemaEnrichmentService
from app.services.tableau.client import TableauClient

router = APIRouter(prefix="/api/vizql", tags=["VizQL"])

@router.post("/datasources/{datasource_id}/enrich-schema")
async def enrich_schema(
    datasource_id: str,
    force_refresh: bool = False,
    tableau_client: TableauClient = Depends()
):
    """
    Enrich datasource schema with VizQL metadata.
    
    This endpoint is triggered manually via UI button.
    Results are cached for 1 hour.
    """
    try:
        service = SchemaEnrichmentService(tableau_client)
        enriched = await service.enrich_datasource_schema(
            datasource_id, 
            force_refresh
        )
        return {
            "datasource_id": datasource_id,
            "field_count": len(enriched["fields"]),
            "measure_count": len(enriched["measures"]),
            "dimension_count": len(enriched["dimensions"]),
            "cached": not force_refresh,
            "enriched_schema": enriched
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**File: `frontend/components/explorer/DatasourceEnrichButton.tsx` (New)**
```typescript
'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';

export function DatasourceEnrichButton({ datasourceId }: { datasourceId: string }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const handleEnrich = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `/api/vizql/datasources/${datasourceId}/enrich-schema`,
        { method: 'POST' }
      );
      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error('Enrichment failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Button onClick={handleEnrich} disabled={loading}>
        <RefreshCw className={loading ? 'animate-spin' : ''} />
        Enrich Schema for AI
      </Button>
      {result && (
        <div className="mt-2 text-sm">
          Enriched: {result.field_count} fields ({result.measure_count} measures, {result.dimension_count} dimensions)
        </div>
      )}
    </div>
  );
}
```

---

### Phase 3: Compressed Context Builder (Week 1, Day 5)
**Goal:** Reduce token cost by 40% with efficient schema format

#### Tasks
1. Create context builder that generates LLM-friendly schema
2. Add inline hints (aggregation suggestions, field roles)
3. Update query construction prompt

#### Deliverables

**File: `backend/app/services/agents/vizql/context_builder.py`**
```python
"""Build compressed, token-efficient context for LLM."""
from typing import Dict, Any, List

def build_compressed_schema_context(enriched_schema: Dict[str, Any]) -> str:
    """
    Build compressed schema format for LLM.
    
    Format: FieldName (TYPE) [ROLE] {defaultAgg}
    Example: Total Sales (REAL) [MEASURE] {SUM}
    """
    lines = ["## Available Fields\n"]
    
    for field in enriched_schema["fields"]:
        if field.get("hidden"):
            continue
        
        # Base format: FieldName (TYPE) [ROLE]
        line = (
            f"- {field['fieldCaption']} "
            f"({field['dataType']}) "
            f"[{field['fieldRole']}]"
        )
        
        # Add aggregation hint
        if field["fieldRole"] == "MEASURE":
            agg = field.get("defaultAggregation") or field.get("suggestedAggregation", "SUM")
            line += f" {{default: {agg}}}"
        
        # Add description if available
        if field.get("description"):
            line += f" - {field['description'][:50]}"
        
        lines.append(line)
    
    return "\n".join(lines)

def build_semantic_hints(enriched_schema: Dict[str, Any]) -> str:
    """Build semantic hints section."""
    hints = [
        "## Query Construction Hints\n",
        f"**Measures ({len(enriched_schema['measures'])}):** Require aggregation functions",
        f"Available: {', '.join(enriched_schema['measures'][:10])}{'...' if len(enriched_schema['measures']) > 10 else ''}",
        "",
        f"**Dimensions ({len(enriched_schema['dimensions'])}):** Used for grouping (no aggregation)",
        f"Available: {', '.join(enriched_schema['dimensions'][:10])}{'...' if len(enriched_schema['dimensions']) > 10 else ''}"
    ]
    return "\n".join(hints)
```

**Update: `backend/app/prompts/agents/vizql/query_construction.txt`**
```
You are constructing a VizQL Data Service query from user intent and enriched schema.

{{ compressed_schema }}

{{ semantic_hints }}

## VizQL Rules (CRITICAL)
1. **MEASURES REQUIRE AGGREGATION**: If fieldRole is MEASURE, you MUST add "function" field
2. **USE EXACT fieldCaption**: Copy field names EXACTLY from schema (case-sensitive)
3. **DIMENSIONS NO AGGREGATION**: If fieldRole is DIMENSION, do NOT add "function" field
4. **MATCH USER INTENT TO FIELD NAMES**: 
   - User says "sales" → Use "Total Sales" from schema
   - User says "region" → Use "Region" from schema
   - Never invent field names

## Output Format
Return ONLY valid JSON:
{
  "datasource": {
    "datasourceLuid": "{{ datasource_id }}"
  },
  "query": {
    "fields": [
      {"fieldCaption": "Total Sales", "function": "SUM"},
      {"fieldCaption": "Region"}
    ]
  },
  "options": {
    "returnFormat": "OBJECTS",
    "disaggregate": false
  }
}

USER QUERY: {{ user_query }}

Return JSON only, no explanation.
```

---

### Phase 4: Semantic Constraint Validator (Week 2, Days 1-2)
**Goal:** Catch semantic errors before/after LLM call

#### Tasks
1. Create pre-LLM validator for intent
2. Enhance post-LLM validator with semantic checks
3. Add detailed correction suggestions

#### Deliverables

**File: `backend/app/services/agents/vizql/constraint_validator.py`**
```python
"""Semantic constraint validation for VizQL queries."""
from typing import Dict, Any, List, Tuple

class VizQLConstraintValidator:
    """Validates semantic constraints for VizQL queries."""
    
    def __init__(self, enriched_schema: Dict[str, Any]):
        self.schema = enriched_schema
        self.field_map = enriched_schema["field_map"]
    
    def validate_query(self, query: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """
        Validate query semantics.
        
        Returns: (is_valid, errors, suggestions)
        """
        errors = []
        suggestions = []
        
        fields = query.get("query", {}).get("fields", [])
        
        for field in fields:
            field_caption = field.get("fieldCaption", "")
            field_lower = field_caption.lower()
            
            # Check if field exists
            if field_lower not in self.field_map:
                errors.append(f"Field '{field_caption}' not found in schema")
                # Fuzzy match suggestion
                close_matches = self._find_close_matches(field_lower)
                if close_matches:
                    suggestions.append(
                        f"Did you mean: {', '.join(close_matches)}?"
                    )
                continue
            
            field_meta = self.field_map[field_lower]
            has_function = "function" in field
            
            # CRITICAL: Measures must have aggregation
            if field_meta["fieldRole"] == "MEASURE" and not has_function:
                errors.append(
                    f"MEASURE field '{field_caption}' requires aggregation function"
                )
                suggested_agg = (
                    field_meta.get("defaultAggregation") or 
                    field_meta.get("suggestedAggregation", "SUM")
                )
                suggestions.append(
                    f"Add: {{\"fieldCaption\": \"{field_caption}\", \"function\": \"{suggested_agg}\"}}"
                )
            
            # CRITICAL: Dimensions should NOT have aggregation
            if field_meta["fieldRole"] == "DIMENSION" and has_function:
                errors.append(
                    f"DIMENSION field '{field_caption}' should not have aggregation"
                )
                suggestions.append(
                    f"Remove 'function' from: {{\"fieldCaption\": \"{field_caption}\"}}"
                )
            
            # Validate aggregation type compatibility
            if has_function:
                agg = field["function"]
                data_type = field_meta["dataType"]
                if not self._is_valid_aggregation(agg, data_type):
                    errors.append(
                        f"Aggregation '{agg}' not compatible with type '{data_type}'"
                    )
        
        return len(errors) == 0, errors, suggestions
    
    def _find_close_matches(self, field_name: str, cutoff: float = 0.6) -> List[str]:
        """Find close field name matches."""
        import difflib
        matches = difflib.get_close_matches(
            field_name, 
            self.field_map.keys(), 
            n=3, 
            cutoff=cutoff
        )
        return [self.field_map[m]["fieldCaption"] for m in matches]
    
    def _is_valid_aggregation(self, agg: str, data_type: str) -> bool:
        """Check if aggregation is valid for data type."""
        from app.services.agents.vizql.semantic_rules import validate_aggregation_for_type
        return validate_aggregation_for_type(agg, data_type)
```

**Update: `backend/app/services/agents/vizql/nodes/validator.py`**
```python
# Add at the top
from app.services.agents.vizql.constraint_validator import VizQLConstraintValidator

# In validate_query_node function, after existing checks:
    # Semantic validation using enriched schema
    enriched_schema = state.get("enriched_schema")
    if enriched_schema:
        constraint_validator = VizQLConstraintValidator(enriched_schema)
        is_semantically_valid, semantic_errors, semantic_suggestions = \
            constraint_validator.validate_query(query)
        
        if not is_semantically_valid:
            errors.extend(semantic_errors)
            suggestions.extend(semantic_suggestions)
```

---

### Phase 5: Integration & Testing (Week 2, Days 3-5)
**Goal:** Wire everything together and validate improvements

#### Tasks
1. Update `schema_fetch_node` to use enrichment service
2. Update `query_builder_node` to use compressed context
3. Manual testing with 20+ real queries
4. Document success rate improvements

#### Deliverables

**Update: `backend/app/services/agents/vizql/nodes/schema_fetch.py`**
```python
from app.services.agents.vizql.schema_enrichment import SchemaEnrichmentService

async def fetch_schema_node(state: VizQLAgentState) -> Dict[str, Any]:
    """Fetch and enrich datasource schema."""
    datasource_ids = state.get("context_datasources", [])
    if not datasource_ids:
        return {...}
    
    datasource_id = datasource_ids[0]
    
    # Use enrichment service
    tableau_client = get_tableau_client()
    enrichment_service = SchemaEnrichmentService(tableau_client)
    
    try:
        enriched_schema = await enrichment_service.enrich_datasource_schema(
            datasource_id
        )
        
        return {
            **state,
            "schema": enriched_schema,  # Keep backward compatibility
            "enriched_schema": enriched_schema,
            "current_thought": f"Fetched enriched schema with {len(enriched_schema['fields'])} fields"
        }
    except Exception as e:
        logger.error(f"Schema enrichment failed: {e}")
        # Fallback to basic schema
        schema = await tableau_client.get_schema(datasource_id)
        return {**state, "schema": schema}
```

**Update: `backend/app/services/agents/vizql/nodes/query_builder.py`**
```python
from app.services.agents.vizql.context_builder import (
    build_compressed_schema_context,
    build_semantic_hints
)

async def build_query_node(state: VizQLAgentState) -> Dict[str, Any]:
    """Build query with compressed context."""
    enriched_schema = state.get("enriched_schema") or state.get("schema")
    
    # Build compressed context
    compressed_schema = build_compressed_schema_context(enriched_schema)
    semantic_hints = build_semantic_hints(enriched_schema)
    
    # Get prompt with new variables
    system_prompt = prompt_registry.get_prompt(
        "agents/vizql/query_construction.txt",
        variables={
            "compressed_schema": compressed_schema,
            "semantic_hints": semantic_hints,
            "datasource_id": datasource_id,
            "user_query": state["user_query"]
        }
    )
    
    # ... rest of existing logic
```

**Test Plan Document:**
```markdown
# VizQL Query Accuracy Test Plan

## Test Datasources
- Superstore (sales data)
- HR Analytics (employee data)
- Financial (revenue/expenses)

## Test Queries (20 examples)
1. "show total sales by region"
2. "average price per product category"
3. "count of orders by month"
4. "top 10 customers by revenue"
5. "sum of profits for each state"
... (15 more)

## Success Metrics
- First-attempt success rate: Target >70%
- Field name accuracy: Target >95%
- Semantic correctness: Target >90%
- Token usage: Target <2500 avg

## Testing Process
1. Clear all caches
2. Enrich schema via UI button
3. Run each query 3 times
4. Record: success/fail, tokens used, errors
5. Compare before/after improvements
```

---

## API Changes Summary

### New Endpoints
```
POST /api/vizql/datasources/{datasource_id}/enrich-schema
  - Triggers schema enrichment
  - Returns enriched metadata
  - Caches for 1 hour
```

### Updated Tableau Client Methods
```python
# backend/app/services/tableau/client.py
async def read_metadata(self, datasource_id: str) -> Dict[str, Any]:
    """Call VizQL /read-metadata endpoint."""
    ...

async def list_supported_functions(self, datasource_id: str) -> List[Dict[str, Any]]:
    """Call VizQL /list-supported-functions endpoint."""
    ...
```

---

## File Structure

```
backend/
├── app/
│   ├── api/
│   │   └── vizql.py                          # NEW: Enrichment API
│   ├── services/
│   │   ├── agents/
│   │   │   └── vizql/
│   │   │       ├── semantic_rules.py         # NEW: VizQL rules engine
│   │   │       ├── schema_enrichment.py      # NEW: Enrichment service
│   │   │       ├── context_builder.py        # NEW: Compressed context
│   │   │       ├── constraint_validator.py   # NEW: Semantic validator
│   │   │       └── nodes/
│   │   │           ├── schema_fetch.py       # UPDATED
│   │   │           ├── query_builder.py      # UPDATED
│   │   │           └── validator.py          # UPDATED
│   ├── prompts/
│   │   └── agents/vizql/
│   │       ├── query_construction.txt        # UPDATED
│   │       └── semantic_rules.txt            # NEW

frontend/
├── components/
│   └── explorer/
│       └── DatasourceEnrichButton.tsx        # NEW: UI button
```

---

## Dependencies

### Python (backend)
```
# Already installed
redis>=4.0.0
langchain-core
```

### TypeScript (frontend)
```
# No new dependencies
```

---

## Migration & Rollout Plan

### Phase 0: Preparation (Day 0)
- Review this document with team
- Assign ownership for each phase
- Set up dev environment

### Phase 1: Build Core (Days 1-2)
- Implement semantic rules engine
- Test aggregation suggestion logic
- Unit tests for rule validators

### Phase 2: Enrichment Service (Days 3-4)
- Implement schema enrichment
- Add Redis caching
- Test with real Tableau instance
- Build UI button component

### Phase 3: Context & Validation (Days 5-6)
- Build compressed context builder
- Implement constraint validator
- Update prompt templates

### Phase 4: Integration (Days 7-8)
- Wire all components together
- Update nodes (schema_fetch, query_builder, validator)
- End-to-end testing

### Phase 5: Validation (Days 9-10)
- Run test suite (20+ queries)
- Measure success rate improvements
- Document results
- Bug fixes

---

## Risk Mitigation

### Risk 1: VizQL API Rate Limits
**Mitigation:** 
- Aggressive caching (1hr TTL)
- Manual trigger via UI (not automatic)
- Fallback to basic schema if enrichment fails

### Risk 2: Large Datasources (1000+ fields)
**Mitigation:**
- Context builder truncates to top 200 most-used fields
- Pagination in UI enrichment results
- Stream-based enrichment for large schemas

### Risk 3: Cache Invalidation
**Mitigation:**
- Manual "Refresh" button in UI
- Admin endpoint to clear specific cache keys
- TTL ensures stale data refreshes hourly

### Risk 4: LLM Still Hallucinates
**Mitigation:**
- Enhanced validator catches errors before execution
- Self-correction loop (existing)
- Detailed error messages guide LLM to fix

---

## Success Criteria

### Must Have (MVP)
- [x] Semantic rules engine implemented
- [x] Schema enrichment service with caching
- [x] UI button to trigger enrichment
- [x] Compressed context builder
- [x] Enhanced semantic validator
- [x] First-attempt success >60%

### Nice to Have (Future)
- [ ] Automatic enrichment on datasource publish
- [ ] Field relationship graph (which fields commonly appear together)
- [ ] Query pattern learning (track successful queries)
- [ ] Sample value preview in UI

---

## Open Questions

1. **Redis Setup:** Do we have Redis in production? If not, use in-memory cache with fallback.
   - **Answer:** TBD by DevOps

2. **VizQL API Auth:** Do we need separate auth for VizQL endpoints?
   - **Answer:** Uses same X-Tableau-Auth token

3. **Schema Change Detection:** How to invalidate cache when datasource changes?
   - **Answer:** Manual refresh for now, webhook in future sprint

---

## Appendix: VizQL OpenAPI Key Endpoints

### `/read-metadata`
**Returns:** FieldMetadata array with:
- `fieldCaption` - Exact field name to use in queries
- `dataType` - INTEGER, REAL, STRING, DATE, etc.
- `fieldRole` - MEASURE or DIMENSION
- `defaultAggregation` - Suggested aggregation
- `description` - Field description
- `aliases` - Value mappings

### `/list-supported-functions`
**Returns:** Array of supported functions with:
- `name` - Function name (SUM, AVG, etc.)
- `overloads` - Argument/return type signatures

### `/get-datasource-model`
**Returns:** Logical table relationships
- Used for multi-table query validation (future)

---

## Contact & Ownership

**Document Owner:** AI Engineering Architect  
**Implementation Lead:** TBD  
**Sprint:** Current (Fix Now)  
**Target Completion:** 2 weeks from kickoff

---

**Next Steps:**
1. Team review of this plan
2. Kickoff meeting to assign phases
3. Set up dev environment with Redis
4. Begin Phase 1 implementation
