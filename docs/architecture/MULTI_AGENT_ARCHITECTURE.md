# Multi-Agent Architecture for Tableau AI Demo

## Overview

This document outlines the architectural updates to support three specialized agents:

1. **analyst_agent** (existing) - General Tableau queries and exploration
2. **vds_agent** (new) - VizQL Data Service query construction and execution
3. **summary_agent** (new) - Multi-view data export and summarization

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     FRONTEND - Multi-Agent Dashboard                 │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  Agent Selector: [Analyst] [VizQL] [Summary]                    ││
│  └─────────────────────────────────────────────────────────────────┘│
│  ┌──────────────┬──────────────────┬──────────────────────────────┐│
│  │ Analyst      │ VizQL Panel      │ Summary Panel                ││
│  │ Chat Panel   │ • Schema Viewer  │ • View Selector              ││
│  │ • Messages   │ • Query Builder  │ • Export Options             ││
│  │ • Model      │ • Validator      │ • Progress Tracker           ││
│  │ • Context    │ • Results        │ • Summary Viewer             ││
│  └──────┬───────┴──────┬───────────┴──────┬───────────────────────┘│
└─────────┼──────────────┼──────────────────┼──────────────────────────┘
          │              │                  │
          │ REST/WS      │ REST/WS          │ REST/WS
          │              │                  │
┌─────────▼──────────────▼──────────────────▼──────────────────────────┐
│                    BACKEND - Master Agent Router                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Intent Classifier                                               │ │
│  │  • Analyzes user query                                           │ │
│  │  • Routes to appropriate agent                                   │ │
│  │  • Manages context passing                                       │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  ┌──────────────────┬─────────────────────┬─────────────────────────┐│
│  │  analyst_agent   │  vds_agent          │  summary_agent          ││
│  │  ┌────────────┐  │  ┌────────────────┐ │  ┌────────────────────┐││
│  │  │ Prompts    │  │  │ VizQL Builder  │ │  │ Export Manager     │││
│  │  │ • General  │  │  │ • NL→VizQL     │ │  │ • Multi-view query │││
│  │  │ • Context  │  │  │ • Schema aware │ │  │ • Batch processing │││
│  │  └────────────┘  │  │ • Validator    │ │  │ • LLM summarizer   │││
│  │  ┌────────────┐  │  └────────────────┘ │  └────────────────────┘││
│  │  │ Tools      │  │  ┌────────────────┐ │  ┌────────────────────┐││
│  │  │ • List DS  │  │  │ Tools          │ │  │ Tools              │││
│  │  │ • List V   │  │  │ • Construct    │ │  │ • Export views     │││
│  │  │ • Query    │  │  │ • Execute      │ │  │ • Batch export     │││
│  │  │ • Embed    │  │  │ • Validate     │ │  │ • Summarize        │││
│  │  └────────────┘  │  │ • Schema       │ │  │ • Generate report  │││
│  └──────────────────┴──└────────────────┘─┴─└────────────────────┘─┘│
└───────────────────────────┬────────────────────────────────────────────┘
                            │
                            │ Calls MCP Tools
                            │
┌───────────────────────────▼────────────────────────────────────────────┐
│                         MCP SERVER LAYER                                │
│  ┌────────────────────────────────────────────────────────────────────┐│
│  │  EXISTING TOOLS                                                     ││
│  │  • tableau_list_datasources                                         ││
│  │  • tableau_list_views                                               ││
│  │  • tableau_query_datasource                                         ││
│  │  • tableau_get_view_embed_url                                       ││
│  │  • chat_* (conversation management)                                 ││
│  │  • auth_* (authentication)                                          ││
│  └────────────────────────────────────────────────────────────────────┘│
│  ┌────────────────────────────────────────────────────────────────────┐│
│  │  NEW VIZQL TOOLS                                                    ││
│  │  • tableau_construct_vizql(user_query, datasource_id)              ││
│  │  • tableau_execute_vizql(datasource_id, vizql_query)               ││
│  │  • tableau_get_datasource_schema(datasource_id)                    ││
│  │  • tableau_validate_vizql(vizql_query)                             ││
│  └────────────────────────────────────────────────────────────────────┘│
│  ┌────────────────────────────────────────────────────────────────────┐│
│  │  NEW EXPORT TOOLS                                                   ││
│  │  • tableau_export_view_data(view_id, format)                       ││
│  │  • tableau_export_crosstab(view_id, rows, cols, measure)           ││
│  │  • tableau_batch_export(view_ids, format)                          ││
│  │  • tableau_export_summary(view_ids, summary_type)                  ││
│  └────────────────────────────────────────────────────────────────────┘│
└───────────────────────────┬────────────────────────────────────────────┘
                            │
                            │ REST API / GraphQL
                            │
┌───────────────────────────▼────────────────────────────────────────────┐
│                       TABLEAU SERVER                                    │
│  • REST API                                                             │
│  • Metadata API (GraphQL)                                               │
│  • VizQL Data Service                                                   │
│  • Connected Apps (JWT)                                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

## Agent Specializations

### 1. Analyst Agent (Existing - Enhanced)

**Purpose:** General-purpose Tableau interaction

**Capabilities:**
- List and explore datasources
- List and embed views
- Execute simple queries
- Natural language conversation

**Tools:**
- `tableau_list_datasources`
- `tableau_list_views`
- `tableau_query_datasource`
- `tableau_get_view_embed_url`

**System Prompt:**
```
You are a Tableau Analyst Agent. Your role is to help users explore and understand 
their Tableau data through natural language conversation. You can list datasources, 
views, query data, and embed visualizations.
```

### 2. VizQL Agent (New)

**Purpose:** Advanced VizQL query construction and execution

**Capabilities:**
- Understand datasource schemas
- Translate natural language to VizQL
- Construct optimized queries
- Validate query syntax
- Execute VizQL queries

**Tools:**
- `tableau_construct_vizql`
- `tableau_execute_vizql`
- `tableau_get_datasource_schema`
- `tableau_validate_vizql`
- `tableau_query_datasource` (for execution)

**System Prompt:**
```
You are a VizQL Expert Agent. Your specialty is understanding Tableau datasource 
schemas and constructing VizQL Data Service queries. When given a user question 
and datasource context, you:

1. Analyze the datasource schema
2. Identify relevant fields (dimensions, measures, calculated fields)
3. Construct a valid VizQL query
4. Validate syntax before execution
5. Optimize for performance

Always explain your query construction choices and validate before executing.
```

**Example Workflow:**
```python
# User: "Show me total sales by region for Q1 2024"
# Agent workflow:

1. Get schema: tableau_get_datasource_schema(datasource_id="sales_ds")
   → Returns: {columns: ["Region", "Sales", "Date"], measures: ["Sales"], ...}

2. Construct query: tableau_construct_vizql(
     user_query="total sales by region for Q1 2024",
     datasource_id="sales_ds"
   )
   → Returns: {
       vizql: "SELECT SUM([Sales]) AS total_sales, [Region] 
               FROM datasource 
               WHERE [Date] >= '2024-01-01' AND [Date] < '2024-04-01'
               GROUP BY [Region]",
       valid: true,
       explanation: "Aggregating Sales by Region with Q1 date filter"
     }

3. Execute: tableau_execute_vizql(
     datasource_id="sales_ds",
     vizql_query=<constructed_query>
   )
   → Returns: {data: [...], columns: [...], row_count: 5}
```

### 3. Summary Agent (New)

**Purpose:** Multi-view data export and summarization

**Capabilities:**
- Export data from multiple views
- Perform cross-view aggregations
- Generate natural language summaries
- Create downloadable reports (HTML, PDF, CSV)
- Track export progress

**Tools:**
- `tableau_export_view_data`
- `tableau_export_crosstab`
- `tableau_batch_export`
- `tableau_export_summary`
- `tableau_list_views` (for view selection)

**System Prompt:**
```
You are a Tableau Summary Agent. Your role is to export, aggregate, and summarize 
data from multiple Tableau views. You can:

1. Export data from views in various formats (CSV, JSON, Excel)
2. Perform cross-view aggregations
3. Generate natural language summaries of findings
4. Create comprehensive reports

When summarizing, focus on key insights, trends, and actionable findings.
```

**Example Workflow:**
```python
# User: "Export and summarize sales and marketing performance views"
# Agent workflow:

1. List relevant views: tableau_list_views(search="sales OR marketing")
   → Returns: [
       {id: "view1", name: "Sales Dashboard"},
       {id: "view2", name: "Marketing Performance"}
     ]

2. Batch export: tableau_batch_export(
     view_ids=["view1", "view2"],
     format="json"
   )
   → Returns: {
       exports: [
         {view_id: "view1", data: [...], row_count: 1000},
         {view_id: "view2", data: [...], row_count: 500}
       ]
     }

3. Summarize: Use LLM to analyze data and generate:
   → Summary: "Sales performance shows 15% growth YoY, with strongest 
              performance in Q4. Marketing campaigns generated 2.3M 
              impressions with 4.2% conversion rate..."
   
4. Generate report: tableau_export_summary(
     view_ids=["view1", "view2"],
     summary_type="html"
   )
   → Returns downloadable HTML report with charts and insights
```

## Master Agent Router

**Purpose:** Intelligent routing to specialized agents

**Algorithm:**
```python
class AgentRouter:
    def __init__(self):
        self.classifier = IntentClassifier()
        self.agents = {
            "analyst": AnalystAgent(),
            "vds": VDSAgent(),
            "summary": SummaryAgent()
        }
    
    def classify_intent(self, query: str, context: dict) -> str:
        """
        Classify user intent using LLM or rule-based classification.
        
        Keywords:
        - VizQL: "construct query", "vizql", "query syntax", "schema"
        - Summary: "summarize", "export", "report", "download", "aggregate"
        - Analyst: default fallback
        """
        # Use LLM to classify
        prompt = f"""
        Classify the following user query into one of three agent types:
        1. vds_agent - for VizQL query construction and advanced queries
        2. summary_agent - for data export and summarization
        3. analyst_agent - for general Tableau exploration
        
        Query: {query}
        Context: {context}
        
        Respond with only the agent name.
        """
        return self.llm_client.complete(prompt).strip()
    
    async def route(self, query: str, context: dict) -> dict:
        """Route query to appropriate agent."""
        agent_name = self.classify_intent(query, context)
        agent = self.agents[agent_name]
        
        return await agent.execute(
            query=query,
            context=context,
            tools=agent.allowed_tools
        )
    
    async def execute_workflow(self, query: str, steps: list) -> dict:
        """
        Execute multi-agent workflow.
        
        Example:
        steps = [
            ("vds", "construct_query"),
            ("analyst", "execute_query"),
            ("summary", "summarize_results")
        ]
        """
        results = {}
        context = {}
        
        for agent_name, action in steps:
            agent = self.agents[agent_name]
            result = await agent.execute_action(
                action=action,
                query=query,
                context=context
            )
            results[action] = result
            context.update(result)  # Pass results to next step
        
        return results
```

## Frontend Dashboard

### Component Structure

```typescript
// app/agents/page.tsx
export default function AgentsDashboard() {
  const [activeAgent, setActiveAgent] = useState<AgentType>('analyst');
  const [context, setContext] = useState<AgentContext>({});
  
  return (
    <div className="dashboard">
      <AgentSelector
        active={activeAgent}
        onChange={setActiveAgent}
      />
      
      <div className="panels">
        {activeAgent === 'analyst' && (
          <AnalystPanel context={context} />
        )}
        {activeAgent === 'vizql' && (
          <VizQLPanel context={context} />
        )}
        {activeAgent === 'summary' && (
          <SummaryPanel context={context} />
        )}
      </div>
      
      <ContextPanel context={context} />
    </div>
  );
}
```

### VizQL Panel

```typescript
// components/agents/VizQLPanel.tsx
export function VizQLPanel({ context }: { context: AgentContext }) {
  const [schema, setSchema] = useState<DataSourceSchema | null>(null);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<QueryResults | null>(null);
  
  return (
    <div className="vizql-panel">
      <SchemaViewer
        datasourceId={context.selectedDatasource}
        onSchemaLoad={setSchema}
      />
      
      <QueryBuilder
        schema={schema}
        query={query}
        onChange={setQuery}
      />
      
      <QueryValidator query={query} />
      
      <button onClick={() => executeQuery(query)}>
        Execute Query
      </button>
      
      {results && <ResultsViewer results={results} />}
    </div>
  );
}
```

### Summary Panel

```typescript
// components/agents/SummaryPanel.tsx
export function SummaryPanel({ context }: { context: AgentContext }) {
  const [selectedViews, setSelectedViews] = useState<string[]>([]);
  const [exportFormat, setExportFormat] = useState<'csv' | 'json' | 'excel'>('csv');
  const [summary, setSummary] = useState<Summary | null>(null);
  
  return (
    <div className="summary-panel">
      <ViewSelector
        selectedViews={selectedViews}
        onChange={setSelectedViews}
      />
      
      <ExportOptions
        format={exportFormat}
        onChange={setExportFormat}
      />
      
      <button onClick={() => exportAndSummarize(selectedViews, exportFormat)}>
        Export & Summarize
      </button>
      
      {summary && (
        <SummaryViewer
          summary={summary}
          onDownload={(format) => downloadReport(summary, format)}
        />
      )}
    </div>
  );
}
```

## API Endpoints

### Agent Router Endpoints

```python
# POST /api/agents/route
{
  "query": "Show me sales by region",
  "context": {"datasource_id": "ds-123"}
}
→ {
  "agent": "vds_agent",
  "result": {...}
}

# POST /api/agents/execute-workflow
{
  "query": "Query and summarize sales data",
  "steps": [
    {"agent": "vds", "action": "construct_query"},
    {"agent": "analyst", "action": "execute_query"},
    {"agent": "summary", "action": "summarize"}
  ]
}
→ {
  "results": {
    "construct_query": {...},
    "execute_query": {...},
    "summarize": {...}
  }
}
```

### VizQL Agent Endpoints

```python
# POST /api/agents/vds/construct-query
{
  "user_query": "Total sales by region for 2024",
  "datasource_id": "ds-123"
}
→ {
  "vizql": "SELECT SUM([Sales])...",
  "valid": true,
  "explanation": "..."
}

# POST /api/agents/vds/execute-query
{
  "datasource_id": "ds-123",
  "vizql_query": "SELECT..."
}
→ {
  "data": [...],
  "columns": [...],
  "row_count": 100
}

# GET /api/agents/vds/schema/{datasource_id}
→ {
  "columns": [...],
  "measures": [...],
  "dimensions": [...],
  "calculated_fields": [...]
}
```

### Summary Agent Endpoints

```python
# POST /api/agents/summary/export-views
{
  "view_ids": ["view1", "view2"],
  "format": "csv"
}
→ {
  "exports": [
    {"view_id": "view1", "data": [...], "row_count": 1000},
    {"view_id": "view2", "data": [...], "row_count": 500}
  ]
}

# POST /api/agents/summary/generate-summary
{
  "view_ids": ["view1", "view2"],
  "format": "html"
}
→ {
  "summary": "Sales performance shows...",
  "html": "<html>...</html>",
  "download_url": "/downloads/report-123.html"
}
```

## MCP Tools

### VizQL Tools

```python
@mcp.tool()
async def tableau_construct_vizql(
    user_query: str,
    datasource_id: str
) -> Dict[str, Any]:
    """Construct VizQL query from natural language."""
    ...

@mcp.tool()
async def tableau_execute_vizql(
    datasource_id: str,
    vizql_query: str
) -> Dict[str, Any]:
    """Execute VizQL query."""
    ...

@mcp.tool()
async def tableau_get_datasource_schema(
    datasource_id: str
) -> Dict[str, Any]:
    """Get datasource schema."""
    ...

@mcp.tool()
async def tableau_validate_vizql(
    vizql_query: str
) -> Dict[str, Any]:
    """Validate VizQL syntax."""
    ...
```

### Export Tools

```python
@mcp.tool()
async def tableau_export_view_data(
    view_id: str,
    format: str = "csv"
) -> Dict[str, Any]:
    """Export view data."""
    ...

@mcp.tool()
async def tableau_batch_export(
    view_ids: List[str],
    format: str = "json"
) -> Dict[str, Any]:
    """Batch export multiple views."""
    ...

@mcp.tool()
async def tableau_export_summary(
    view_ids: List[str],
    summary_type: str = "html"
) -> Dict[str, Any]:
    """Generate summary report."""
    ...
```

## Implementation Phases

1. **Phase 10.1-10.2**: VizQL Agent + MCP Tools (2-3 weeks)
2. **Phase 10.3-10.4**: Summary Agent + MCP Tools (2-3 weeks)
3. **Phase 10.5**: Master Agent Router (1 week)
4. **Phase 11.1-11.3**: Frontend Dashboard (2-3 weeks)
5. **Phase 11.4**: API Endpoints (1 week)
6. **Phase 11.5**: End-to-End Testing (1 week)

**Total Estimated Time**: 9-12 weeks

## Key Architectural Benefits

1. **Separation of Concerns**: Each agent has clear responsibilities
2. **Reusability**: Tools exposed via MCP can be used by all agents
3. **Scalability**: Easy to add new agents without changing core infrastructure
4. **Flexibility**: Router enables multi-agent workflows
5. **Testability**: Each agent can be tested independently
6. **Extensibility**: Frontend dashboard supports any number of agents

## Next Steps

1. Review and approve architectural design
2. Create detailed technical specifications for each agent
3. Set up development environment with agent scaffolding
4. Begin Phase 10.1 implementation (VizQL Agent)
