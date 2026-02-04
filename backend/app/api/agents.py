"""Agent API endpoints."""
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.services.agents.vds_agent import VDSAgent
from app.services.agents.summary_agent import SummaryAgent
from app.services.agents.router import AgentRouter
from app.services.tableau.client import TableauClient
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])

# Shared Tableau client instance
_tableau_client: Optional[TableauClient] = None


def get_tableau_client() -> TableauClient:
    """Get or create Tableau client instance."""
    global _tableau_client
    if _tableau_client is None:
        _tableau_client = TableauClient()
    return _tableau_client


# Request/Response Models
class ConstructVizQLRequest(BaseModel):
    """Request model for constructing VizQL query."""
    user_query: str = Field(..., description="Natural language query")
    datasource_id: str = Field(..., description="Datasource ID")


class ConstructVizQLResponse(BaseModel):
    """Response model for VizQL query construction."""
    vizql: str = Field(..., description="Generated VizQL query")
    explanation: str = Field(..., description="Explanation of the query")
    valid: bool = Field(..., description="Whether the query is valid")
    measures: List[str] = Field(default_factory=list)
    dimensions: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)


class ExecuteVizQLRequest(BaseModel):
    """Request model for executing VizQL query."""
    datasource_id: str = Field(..., description="Datasource ID")
    vizql_query: str = Field(..., description="VizQL query to execute")


class ExecuteVizQLResponse(BaseModel):
    """Response model for VizQL query execution."""
    data: List[List[Any]] = Field(default_factory=list)
    columns: List[str] = Field(default_factory=list)
    row_count: int = Field(default=0)
    vizql_query: str = Field(..., description="Executed query")


class ExportViewsRequest(BaseModel):
    """Request model for exporting views."""
    view_ids: List[str] = Field(..., description="List of view IDs to export")
    format: str = Field(default="json", description="Export format (json, csv, excel)")


class ExportViewsResponse(BaseModel):
    """Response model for view export."""
    datasets: List[Dict[str, Any]] = Field(default_factory=list)
    total_rows: int = Field(default=0)
    view_count: int = Field(default=0)
    format: str = Field(..., description="Export format used")


class GenerateSummaryRequest(BaseModel):
    """Request model for generating summary."""
    view_ids: List[str] = Field(..., description="List of view IDs to summarize")
    format: str = Field(default="html", description="Report format (html, markdown, pdf)")
    include_visualizations: bool = Field(default=True, description="Include visualization URLs")


class GenerateSummaryResponse(BaseModel):
    """Response model for summary generation."""
    content: str = Field(..., description="Report content")
    format: str = Field(..., description="Report format")
    visualizations: List[Dict[str, str]] = Field(default_factory=list)
    view_count: int = Field(default=0)
    total_rows: int = Field(default=0)


class AggregateViewsRequest(BaseModel):
    """Request model for aggregating views."""
    view_ids: List[str] = Field(..., description="List of view IDs to aggregate")
    aggregation_type: str = Field(default="sum", description="Aggregation type (sum, avg, count, max, min)")
    column: Optional[str] = Field(None, description="Column name to aggregate (optional)")


class AggregateViewsResponse(BaseModel):
    """Response model for view aggregation."""
    total: float = Field(default=0.0)
    by_view: Dict[str, float] = Field(default_factory=dict)
    aggregation_type: str = Field(..., description="Aggregation type used")
    column: Optional[str] = Field(None, description="Column aggregated")


class ClassifyIntentRequest(BaseModel):
    """Request model for intent classification."""
    query: str = Field(..., description="User query to classify")


class ClassifyIntentResponse(BaseModel):
    """Response model for intent classification."""
    agent: str = Field(..., description="Recommended agent name")
    intent: str = Field(..., description="Intent classification")


class RouteQueryRequest(BaseModel):
    """Request model for routing query."""
    query: str = Field(..., description="User query to route")


class RouteQueryResponse(BaseModel):
    """Response model for query routing."""
    agent: str = Field(..., description="Selected agent")
    intent: str = Field(..., description="Intent classification")
    result: Dict[str, Any] = Field(..., description="Agent execution result")


# VizQL Agent Endpoints
@router.post("/vds/construct-query", response_model=ConstructVizQLResponse)
async def construct_vizql_query(request: ConstructVizQLRequest):
    """Construct a VizQL query from natural language."""
    try:
        tableau_client = get_tableau_client()
        agent = VDSAgent(tableau_client=tableau_client)
        
        # Get datasource schema
        schema = await agent.analyze_datasource(request.datasource_id)
        
        # Construct query
        datasource_context = {
            "id": request.datasource_id,
            "datasource_id": request.datasource_id,
            **schema
        }
        
        result = agent.construct_query(request.user_query, datasource_context)
        
        return ConstructVizQLResponse(
            vizql=result["vizql"],
            explanation=result["explanation"],
            valid=result["valid"],
            measures=result.get("measures", []),
            dimensions=result.get("dimensions", []),
            filters=result.get("filters", {})
        )
    except Exception as e:
        logger.error(f"Error constructing VizQL query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to construct VizQL query: {str(e)}"
        )


@router.post("/vds/execute-query", response_model=ExecuteVizQLResponse)
async def execute_vizql_query(request: ExecuteVizQLRequest):
    """Execute a VizQL query."""
    try:
        tableau_client = get_tableau_client()
        agent = VDSAgent(tableau_client=tableau_client)
        
        # Validate query
        if not agent.validate_query(request.vizql_query):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid VizQL query syntax"
            )
        
        # Execute query using Tableau Data API
        result = await tableau_client.query_datasource(
            datasource_id=request.datasource_id,
            filters=None,
            columns=None,
            limit=None
        )
        
        return ExecuteVizQLResponse(
            data=result.get("data", []),
            columns=result.get("columns", []),
            row_count=result.get("row_count", 0),
            vizql_query=request.vizql_query
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing VizQL query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute VizQL query: {str(e)}"
        )


# Summary Agent Endpoints
@router.post("/summary/export-views", response_model=ExportViewsResponse)
async def export_views(request: ExportViewsRequest):
    """Export data from multiple views."""
    try:
        tableau_client = get_tableau_client()
        agent = SummaryAgent(tableau_client=tableau_client)
        
        result = await agent.export_views(
            view_ids=request.view_ids,
            format=request.format
        )
        
        return ExportViewsResponse(
            datasets=result.get("datasets", []),
            total_rows=result.get("total_rows", 0),
            view_count=result.get("view_count", 0),
            format=result.get("format", request.format)
        )
    except Exception as e:
        logger.error(f"Error exporting views: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export views: {str(e)}"
        )


@router.post("/summary/generate-summary", response_model=GenerateSummaryResponse)
async def generate_summary(request: GenerateSummaryRequest):
    """Generate a summary report from multiple views."""
    try:
        tableau_client = get_tableau_client()
        agent = SummaryAgent(tableau_client=tableau_client)
        
        result = await agent.generate_report(
            view_ids=request.view_ids,
            format=request.format,
            include_visualizations=request.include_visualizations
        )
        
        return GenerateSummaryResponse(
            content=result.get("content", ""),
            format=result.get("format", request.format),
            visualizations=result.get("visualizations", []),
            view_count=result.get("view_count", 0),
            total_rows=result.get("total_rows", 0)
        )
    except Exception as e:
        logger.error(f"Error generating summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {str(e)}"
        )


@router.post("/summary/aggregate-views", response_model=AggregateViewsResponse)
async def aggregate_views(request: AggregateViewsRequest):
    """Aggregate data across multiple views."""
    try:
        tableau_client = get_tableau_client()
        agent = SummaryAgent(tableau_client=tableau_client)
        
        result = await agent.aggregate_across_views(
            view_ids=request.view_ids,
            aggregation_type=request.aggregation_type,
            column=request.column
        )
        
        return AggregateViewsResponse(
            total=result.get("total", 0.0),
            by_view=result.get("by_view", {}),
            aggregation_type=result.get("aggregation_type", request.aggregation_type),
            column=result.get("column")
        )
    except Exception as e:
        logger.error(f"Error aggregating views: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to aggregate views: {str(e)}"
        )


# Router Endpoints
@router.post("/router/classify", response_model=ClassifyIntentResponse)
async def classify_intent(request: ClassifyIntentRequest):
    """Classify user intent and recommend agent."""
    try:
        tableau_client = get_tableau_client()
        router = AgentRouter(tableau_client=tableau_client)
        
        agent_name = router.classify(request.query)
        intent = router.classify_intent(request.query)
        
        return ClassifyIntentResponse(
            agent=agent_name,
            intent=intent.value
        )
    except Exception as e:
        logger.error(f"Error classifying intent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to classify intent: {str(e)}"
        )


@router.post("/router/route", response_model=RouteQueryResponse)
async def route_query(request: RouteQueryRequest):
    """Route query to appropriate agent and execute."""
    try:
        tableau_client = get_tableau_client()
        router = AgentRouter(tableau_client=tableau_client)
        
        result = await router.route_and_execute(request.query)
        
        return RouteQueryResponse(
            agent=result.get("agent", "analyst_agent"),
            intent=result.get("intent", "unknown"),
            result=result.get("result", {})
        )
    except Exception as e:
        logger.error(f"Error routing query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to route query: {str(e)}"
        )
