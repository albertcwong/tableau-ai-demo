"""Tableau API endpoints."""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.models import (
    DatasourceResponse,
    ViewResponse,
    QueryDatasourceRequest,
    QueryDatasourceResponse,
    EmbedUrlResponse,
    ErrorResponse,
    ProjectResponse,
    WorkbookResponse,
    ProjectContentsResponse,
    DatasourceSchemaResponse,
    DatasourceSampleResponse,
    ColumnSchema,
)
from app.services.tableau.client import (
    TableauClient,
    TableauClientError,
    TableauAuthenticationError,
    TableauAPIError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tableau", tags=["tableau"])


def get_tableau_client() -> TableauClient:
    """
    Dependency for getting Tableau client instance.
    
    Creates a new client instance for each request.
    The client handles authentication automatically.
    
    Raises:
        HTTPException: If Tableau configuration is missing or invalid
    """
    try:
        return TableauClient()
    except ValueError as e:
        logger.error(f"Tableau client initialization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Tableau service configuration error: {str(e)}. Please check your environment variables.",
        )


def _normalize_datasource(ds: dict) -> DatasourceResponse:
    """Normalize Tableau datasource response to our model."""
    project = ds.get("project", {})
    return DatasourceResponse(
        id=ds.get("id", ""),
        name=ds.get("name", ""),
        project_id=project.get("id") if isinstance(project, dict) else None,
        project_name=project.get("name") if isinstance(project, dict) else None,
        content_url=ds.get("contentUrl"),
        created_at=ds.get("createdAt"),
        updated_at=ds.get("updatedAt"),
    )


def _normalize_view(view: dict) -> ViewResponse:
    """Normalize Tableau view response to our model."""
    workbook = view.get("workbook", {})
    datasource = view.get("datasource", {})
    return ViewResponse(
        id=view.get("id", ""),
        name=view.get("name", ""),
        workbook_id=workbook.get("id") if isinstance(workbook, dict) else None,
        workbook_name=workbook.get("name") if isinstance(workbook, dict) else None,
        datasource_id=datasource.get("id") if isinstance(datasource, dict) else None,
        content_url=view.get("contentUrl"),
        created_at=view.get("createdAt"),
        updated_at=view.get("updatedAt"),
    )


@router.get(
    "/datasources",
    response_model=List[DatasourceResponse],
    summary="List all datasources",
    description="Retrieve a list of all datasources from Tableau Server.",
    responses={
        200: {"description": "List of datasources"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_datasources(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    page_size: int = Query(100, ge=1, le=1000, description="Number of results per page"),
    page_number: int = Query(1, ge=1, description="Page number (1-indexed)"),
    client: TableauClient = Depends(get_tableau_client),
) -> List[DatasourceResponse]:
    """
    List all datasources.
    
    Returns a paginated list of datasources. Optionally filtered by project.
    """
    try:
        datasources = await client.get_datasources(
            project_id=project_id,
            page_size=page_size,
            page_number=page_number,
        )
        
        return [_normalize_datasource(ds) for ds in datasources]
        
    except TableauAuthenticationError as e:
        logger.error(f"Authentication error listing datasources: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Tableau authentication failed: {str(e)}",
        )
    except TableauAPIError as e:
        logger.error(f"API error listing datasources: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tableau API error: {str(e)}",
        )
    except TableauClientError as e:
        logger.error(f"Client error listing datasources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tableau client error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error listing datasources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )
    finally:
        await client.close()


@router.get(
    "/views",
    response_model=List[ViewResponse],
    summary="List all views",
    description="Retrieve a list of all views from Tableau Server. Optionally filtered by datasource or workbook.",
    responses={
        200: {"description": "List of views"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_views(
    datasource_id: Optional[str] = Query(None, description="Filter by datasource ID"),
    workbook_id: Optional[str] = Query(None, description="Filter by workbook ID"),
    page_size: int = Query(100, ge=1, le=1000, description="Number of results per page"),
    page_number: int = Query(1, ge=1, description="Page number (1-indexed)"),
    client: TableauClient = Depends(get_tableau_client),
) -> List[ViewResponse]:
    """
    List all views.
    
    Returns a paginated list of views. Optionally filtered by datasource or workbook.
    """
    try:
        views = await client.get_views(
            datasource_id=datasource_id,
            workbook_id=workbook_id,
            page_size=page_size,
            page_number=page_number,
        )
        
        return [_normalize_view(view) for view in views]
        
    except TableauAuthenticationError as e:
        logger.error(f"Authentication error listing views: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Tableau authentication failed: {str(e)}",
        )
    except TableauAPIError as e:
        logger.error(f"API error listing views: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tableau API error: {str(e)}",
        )
    except TableauClientError as e:
        logger.error(f"Client error listing views: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tableau client error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error listing views: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )
    finally:
        await client.close()


@router.post(
    "/query",
    response_model=QueryDatasourceResponse,
    summary="Query a datasource",
    description="Query a Tableau datasource with optional filters and column selection.",
    responses={
        200: {"description": "Query results"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        404: {"model": ErrorResponse, "description": "Datasource not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def query_datasource(
    request: QueryDatasourceRequest,
    client: TableauClient = Depends(get_tableau_client),
) -> QueryDatasourceResponse:
    """
    Query a datasource.
    
    Executes a query against the specified datasource with optional filters,
    column selection, and row limit.
    """
    try:
        result = await client.query_datasource(
            datasource_id=request.datasource_id,
            filters=request.filters,
            columns=request.columns,
            limit=request.limit,
        )
        
        return QueryDatasourceResponse(
            datasource_id=request.datasource_id,
            columns=result["columns"],
            data=result["data"],
            row_count=result["row_count"],
        )
        
    except TableauAuthenticationError as e:
        logger.error(f"Authentication error querying datasource: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Tableau authentication failed: {str(e)}",
        )
    except TableauAPIError as e:
        error_msg = str(e)
        # Check if it's a 404 (datasource not found)
        if "404" in error_msg or "not found" in error_msg.lower():
            logger.warning(f"Datasource not found: {request.datasource_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Datasource '{request.datasource_id}' not found",
            )
        logger.error(f"API error querying datasource: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tableau API error: {str(e)}",
        )
    except TableauClientError as e:
        logger.error(f"Client error querying datasource: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tableau client error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error querying datasource: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )
    finally:
        await client.close()


@router.get(
    "/views/{view_id}/embed-url",
    response_model=EmbedUrlResponse,
    summary="Get view embed URL",
    description="Get the embedding URL and authentication token for a Tableau view.",
    responses={
        200: {"description": "Embed URL and token"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        404: {"model": ErrorResponse, "description": "View not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_view_embed_url(
    view_id: str,
    filters: Optional[str] = Query(None, description="Optional filters as JSON string (e.g., '{\"Region\":\"West\"}')"),
    client: TableauClient = Depends(get_tableau_client),
) -> EmbedUrlResponse:
    """
    Get embedding URL for a view.
    
    Returns the URL and authentication token needed to embed the view
    in an iframe or using the Tableau Embedding API.
    
    Filters can be provided as a JSON string in the query parameter.
    Example: ?filters={"Region":"West","Year":"2024"}
    """
    try:
        # Parse filters if provided as query param
        parsed_filters = None
        if filters:
            import json
            try:
                parsed_filters = json.loads(filters)
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid JSON in filters parameter: {str(e)}",
                )
        
        result = await client.get_view_embed_url(
            view_id=view_id,
            filters=parsed_filters,
        )
        
        return EmbedUrlResponse(
            view_id=result["view_id"],
            workbook_id=result.get("workbook_id"),
            url=result["url"],
            token=result.get("token"),
        )
        
    except TableauAuthenticationError as e:
        logger.error(f"Authentication error getting embed URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Tableau authentication failed: {str(e)}",
        )
    except TableauAPIError as e:
        error_msg = str(e)
        # Check if it's a 404 (view not found)
        if "404" in error_msg or "not found" in error_msg.lower():
            logger.warning(f"View not found: {view_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"View '{view_id}' not found",
            )
        logger.error(f"API error getting embed URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tableau API error: {str(e)}",
        )
    except TableauClientError as e:
        logger.error(f"Client error getting embed URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tableau client error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error getting embed URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )
    finally:
        await client.close()


def _normalize_project(project: dict) -> ProjectResponse:
    """Normalize Tableau project response to our model."""
    parent_project = project.get("parentProject", {})
    return ProjectResponse(
        id=project.get("id", ""),
        name=project.get("name", ""),
        description=project.get("description"),
        parent_project_id=parent_project.get("id") if isinstance(parent_project, dict) else None,
        content_permissions=project.get("contentPermissions"),
        created_at=project.get("createdAt"),
        updated_at=project.get("updatedAt"),
    )


def _normalize_workbook(wb: dict) -> WorkbookResponse:
    """Normalize Tableau workbook response to our model."""
    project = wb.get("project", {})
    return WorkbookResponse(
        id=wb.get("id", ""),
        name=wb.get("name", ""),
        project_id=project.get("id") if isinstance(project, dict) else None,
        project_name=project.get("name") if isinstance(project, dict) else None,
        content_url=wb.get("contentUrl"),
        created_at=wb.get("createdAt"),
        updated_at=wb.get("updatedAt"),
    )


@router.get(
    "/projects",
    response_model=List[ProjectResponse],
    summary="List all projects",
    description="Retrieve a list of all projects from Tableau Server.",
    responses={
        200: {"description": "List of projects"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_projects(
    parent_project_id: Optional[str] = Query(None, description="Filter by parent project ID"),
    page_size: int = Query(100, ge=1, le=1000, description="Number of results per page"),
    page_number: int = Query(1, ge=1, description="Page number (1-indexed)"),
    client: TableauClient = Depends(get_tableau_client),
) -> List[ProjectResponse]:
    """
    List all projects.
    
    Returns a paginated list of projects. Optionally filtered by parent project.
    """
    try:
        projects = await client.get_projects(
            parent_project_id=parent_project_id,
            page_size=page_size,
            page_number=page_number,
        )
        
        return [_normalize_project(p) for p in projects]
        
    except TableauAuthenticationError as e:
        logger.error(f"Authentication error listing projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Tableau authentication failed: {str(e)}",
        )
    except TableauAPIError as e:
        logger.error(f"API error listing projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tableau API error: {str(e)}",
        )
    except TableauClientError as e:
        logger.error(f"Client error listing projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tableau client error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error listing projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )
    finally:
        await client.close()


@router.get(
    "/projects/{project_id}/contents",
    response_model=ProjectContentsResponse,
    summary="Get project contents",
    description="Get datasources, workbooks, and nested projects within a project.",
    responses={
        200: {"description": "Project contents"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        404: {"model": ErrorResponse, "description": "Project not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_project_contents(
    project_id: str,
    client: TableauClient = Depends(get_tableau_client),
) -> ProjectContentsResponse:
    """
    Get contents of a project.
    
    Returns datasources, workbooks, and nested projects within the specified project.
    """
    try:
        contents = await client.get_project_contents(project_id=project_id)
        
        return ProjectContentsResponse(
            project_id=contents["project_id"],
            datasources=[_normalize_datasource(ds) for ds in contents["datasources"]],
            workbooks=[_normalize_workbook(wb) for wb in contents["workbooks"]],
            projects=[_normalize_project(p) for p in contents["projects"]],
        )
        
    except TableauAuthenticationError as e:
        logger.error(f"Authentication error getting project contents: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Tableau authentication failed: {str(e)}",
        )
    except TableauAPIError as e:
        error_msg = str(e)
        if "404" in error_msg or "not found" in error_msg.lower():
            logger.warning(f"Project not found: {project_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found",
            )
        logger.error(f"API error getting project contents: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tableau API error: {str(e)}",
        )
    except TableauClientError as e:
        logger.error(f"Client error getting project contents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tableau client error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error getting project contents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )
    finally:
        await client.close()


@router.get(
    "/workbooks",
    response_model=List[WorkbookResponse],
    summary="List all workbooks",
    description="Retrieve a list of all workbooks from Tableau Server. Optionally filtered by project.",
    responses={
        200: {"description": "List of workbooks"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_workbooks(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    page_size: int = Query(100, ge=1, le=1000, description="Number of results per page"),
    page_number: int = Query(1, ge=1, description="Page number (1-indexed)"),
    client: TableauClient = Depends(get_tableau_client),
) -> List[WorkbookResponse]:
    """
    List all workbooks.
    
    Returns a paginated list of workbooks. Optionally filtered by project.
    """
    try:
        workbooks = await client.get_workbooks(
            project_id=project_id,
            page_size=page_size,
            page_number=page_number,
        )
        
        return [_normalize_workbook(wb) for wb in workbooks]
        
    except TableauAuthenticationError as e:
        logger.error(f"Authentication error listing workbooks: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Tableau authentication failed: {str(e)}",
        )
    except TableauAPIError as e:
        logger.error(f"API error listing workbooks: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tableau API error: {str(e)}",
        )
    except TableauClientError as e:
        logger.error(f"Client error listing workbooks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tableau client error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error listing workbooks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )
    finally:
        await client.close()


@router.get(
    "/workbooks/{workbook_id}/views",
    response_model=List[ViewResponse],
    summary="List views in workbook",
    description="Retrieve a list of views within a workbook.",
    responses={
        200: {"description": "List of views"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        404: {"model": ErrorResponse, "description": "Workbook not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_workbook_views(
    workbook_id: str,
    page_size: int = Query(100, ge=1, le=1000, description="Number of results per page"),
    page_number: int = Query(1, ge=1, description="Page number (1-indexed)"),
    client: TableauClient = Depends(get_tableau_client),
) -> List[ViewResponse]:
    """
    List views in a workbook.
    
    Returns a paginated list of views within the specified workbook.
    """
    try:
        views = await client.get_workbook_views(
            workbook_id=workbook_id,
            page_size=page_size,
            page_number=page_number,
        )
        
        return [_normalize_view(view) for view in views]
        
    except TableauAuthenticationError as e:
        logger.error(f"Authentication error listing workbook views: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Tableau authentication failed: {str(e)}",
        )
    except TableauAPIError as e:
        error_msg = str(e)
        if "404" in error_msg or "not found" in error_msg.lower():
            logger.warning(f"Workbook not found: {workbook_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workbook '{workbook_id}' not found",
            )
        logger.error(f"API error listing workbook views: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tableau API error: {str(e)}",
        )
    except TableauClientError as e:
        logger.error(f"Client error listing workbook views: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tableau client error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error listing workbook views: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )
    finally:
        await client.close()


@router.get(
    "/datasources/{datasource_id}/schema",
    response_model=DatasourceSchemaResponse,
    summary="Get datasource schema",
    description="Get schema information (columns, data types) for a datasource.",
    responses={
        200: {"description": "Datasource schema"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        404: {"model": ErrorResponse, "description": "Datasource not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_datasource_schema(
    datasource_id: str,
    client: TableauClient = Depends(get_tableau_client),
) -> DatasourceSchemaResponse:
    """
    Get datasource schema.
    
    Returns column information including names, data types, and whether columns are measures or dimensions.
    """
    try:
        schema = await client.get_datasource_schema(datasource_id=datasource_id)
        
        return DatasourceSchemaResponse(
            datasource_id=schema["datasource_id"],
            columns=[
                ColumnSchema(
                    name=col["name"],
                    data_type=col.get("data_type"),
                    remote_type=col.get("remote_type"),
                    is_measure=col.get("is_measure", False),
                    is_dimension=col.get("is_dimension", False),
                )
                for col in schema["columns"]
            ],
        )
        
    except TableauAuthenticationError as e:
        logger.error(f"Authentication error getting datasource schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Tableau authentication failed: {str(e)}",
        )
    except TableauAPIError as e:
        error_msg = str(e)
        if "404" in error_msg or "not found" in error_msg.lower():
            logger.warning(f"Datasource not found: {datasource_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Datasource '{datasource_id}' not found",
            )
        logger.error(f"API error getting datasource schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tableau API error: {str(e)}",
        )
    except TableauClientError as e:
        logger.error(f"Client error getting datasource schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tableau client error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error getting datasource schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )
    finally:
        await client.close()


@router.get(
    "/datasources/{datasource_id}/sample",
    response_model=DatasourceSampleResponse,
    summary="Get datasource sample data",
    description="Get sample data rows from a datasource.",
    responses={
        200: {"description": "Sample data"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        404: {"model": ErrorResponse, "description": "Datasource not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_datasource_sample(
    datasource_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Number of rows to return"),
    client: TableauClient = Depends(get_tableau_client),
) -> DatasourceSampleResponse:
    """
    Get sample data from a datasource.
    
    Returns a limited number of rows from the datasource for preview purposes.
    """
    try:
        sample = await client.get_datasource_sample(datasource_id=datasource_id, limit=limit)
        
        return DatasourceSampleResponse(
            datasource_id=sample["datasource_id"],
            columns=sample["columns"],
            data=sample["data"],
            row_count=sample["row_count"],
        )
        
    except TableauAuthenticationError as e:
        logger.error(f"Authentication error getting datasource sample: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Tableau authentication failed: {str(e)}",
        )
    except TableauAPIError as e:
        error_msg = str(e)
        if "404" in error_msg or "not found" in error_msg.lower():
            logger.warning(f"Datasource not found: {datasource_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Datasource '{datasource_id}' not found",
            )
        logger.error(f"API error getting datasource sample: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tableau API error: {str(e)}",
        )
    except TableauClientError as e:
        logger.error(f"Client error getting datasource sample: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tableau client error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error getting datasource sample: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )
    finally:
        await client.close()
