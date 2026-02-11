"""Tableau API endpoints."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status

from app.services.tableau.token_cache import with_lock as token_cache_lock
from app.services.tableau.token_store_factory import get_token_store
from app.services.tableau.token_store import TokenEntry
from app.services.pat_encryption import decrypt_pat
from sqlalchemy.orm import Session

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
    ExecuteVDSQueryRequest,
    ExecuteVDSQueryResponse,
    ColumnSchema,
    PaginationInfo,
    PaginatedDatasourcesResponse,
    PaginatedWorkbooksResponse,
    PaginatedViewsResponse,
)
from app.services.tableau.client import (
    TableauClient,
    TableauClientError,
    TableauAuthenticationError,
    TableauAPIError,
)
from app.services.agents.vizql.schema_enrichment import SchemaEnrichmentService
from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User, TableauServerConfig, UserTableauServerMapping, UserTableauPAT
from sqlalchemy import or_

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tableau", tags=["tableau"])


async def get_tableau_client(
    x_tableau_config_id: Optional[str] = Header(None, alias="X-Tableau-Config-Id"),
    x_tableau_auth_type: Optional[str] = Header(None, alias="X-Tableau-Auth-Type"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TableauClient:
    """
    Dependency for getting Tableau client instance from user's selected configuration.
    
    Creates a new client instance for each request using the user's selected Tableau config.
    Falls back to environment variables if no config_id is provided.
    
    Raises:
        HTTPException: If Tableau configuration is missing or invalid
    """
    try:
        # If config_id is provided, use that config
        if x_tableau_config_id:
            try:
                config_id = int(x_tableau_config_id)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid Tableau config ID: {x_tableau_config_id}"
                )
            
            config = db.query(TableauServerConfig).filter(
                TableauServerConfig.id == config_id,
                TableauServerConfig.is_active == True
            ).first()
            
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Tableau server configuration {x_tableau_config_id} not found or inactive"
                )
            
            # Check if user has a custom Tableau username mapping for this Connected App
            # Priority: 1) Manual mapping, 2) Auth0 metadata, 3) App username
            mapping = db.query(UserTableauServerMapping).filter(
                UserTableauServerMapping.user_id == current_user.id,
                UserTableauServerMapping.tableau_server_config_id == config.id
            ).first()
            
            if mapping:
                tableau_username = mapping.tableau_username
            elif current_user.tableau_username:
                tableau_username = current_user.tableau_username
            else:
                tableau_username = current_user.username
            
            # Normalize config site_id for TableauClient (empty string = default site = None)
            if config.site_id and isinstance(config.site_id, str) and config.site_id.strip():
                site_id_for_client = config.site_id.strip() or None
            else:
                site_id_for_client = None  # Default site

            auth_type = (x_tableau_auth_type or "connected_app").lower()
            if auth_type == "connected_app" and not (config.client_id and config.client_secret):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Connected App credentials are not configured for this server. Use PAT authentication or contact your admin."
                )
            
            token_store = get_token_store(auth_type)
            invalidate_cb = lambda: token_store.invalidate(current_user.id, config.id, auth_type)

            # Check token store first
            token_entry = token_store.get(current_user.id, config.id, auth_type)
            if token_entry:
                client = TableauClient(
                    server_url=config.server_url,
                    site_id=token_entry.site_id or site_id_for_client,
                    api_version=config.api_version or "3.15",
                    client_id="pat-placeholder" if auth_type == "pat" else config.client_id,
                    client_secret="pat-placeholder" if auth_type == "pat" else config.client_secret,
                    username=tableau_username,
                    secret_id=config.secret_id or config.client_id,
                    verify_ssl=not getattr(config, 'skip_ssl_verify', False),
                    initial_token=token_entry.token,
                    initial_site_id=token_entry.site_id,
                    initial_site_content_url=token_entry.site_content_url,
                    on_401_invalidate=invalidate_cb,
                )
                # Ensure _pat_auth flag is set for PAT tokens
                if auth_type == "pat":
                    client._pat_auth = True
                return client

            # For PAT: if no token in cache, try to restore session from stored credentials
            if auth_type == "pat":
                if not getattr(config, 'allow_pat_auth', False):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="PAT authentication is not enabled for this server"
                    )
                pat_record = db.query(UserTableauPAT).filter(
                    UserTableauPAT.user_id == current_user.id,
                    UserTableauPAT.tableau_server_config_id == config.id,
                ).first()
                if not pat_record:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="No PAT configured. Please add one in Settings and connect.",
                        headers={"X-Error-Code": "TABLEAU_PAT_NOT_CONFIGURED"},
                    )
                try:
                    pat_secret = decrypt_pat(pat_record.pat_secret)
                except Exception as e:
                    logger.error(f"Failed to decrypt stored PAT: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to access stored credentials.",
                        headers={"X-Error-Code": "TABLEAU_CREDENTIAL_ERROR"},
                    )
                client = TableauClient(
                    server_url=config.server_url,
                    site_id=site_id_for_client,
                    api_version=config.api_version or "3.15",
                    client_id="pat-placeholder",
                    client_secret="pat-placeholder",
                    verify_ssl=not getattr(config, 'skip_ssl_verify', False),
                )
                try:
                    await client.sign_in_with_pat(pat_record.pat_name, pat_secret)
                except TableauAuthenticationError as e:
                    logger.warning(f"PAT restore failed (session expired/invalid): {e}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Tableau session expired. Please reconnect using the Connect button.",
                        headers={"X-Error-Code": "TABLEAU_SESSION_EXPIRED"},
                    )
                expires_at = client.token_expires_at or datetime.now(timezone.utc) + timedelta(minutes=8)
                token_entry = TokenEntry(
                    token=client.auth_token,
                    expires_at=expires_at,
                    site_id=client.site_id,
                    site_content_url=client.site_content_url,
                )
                token_store.set(current_user.id, config.id, auth_type, token_entry)
                client._pat_auth = True
                logger.info(f"Restored PAT session for user={current_user.id} config={config.id}")
                return client

            # For Connected App: sign in with lock to prevent parallel sign-ins
            async with token_cache_lock(current_user.id, config.id, auth_type):
                # Re-check token store after acquiring lock
                token_entry = token_store.get(current_user.id, config.id, auth_type)
                if token_entry:
                    client = TableauClient(
                        server_url=config.server_url,
                        site_id=token_entry.site_id or site_id_for_client,
                        api_version=config.api_version or "3.15",
                        client_id="pat-placeholder" if auth_type == "pat" else config.client_id,
                        client_secret="pat-placeholder" if auth_type == "pat" else config.client_secret,
                        username=tableau_username,
                        secret_id=config.secret_id or config.client_id,
                        verify_ssl=not getattr(config, 'skip_ssl_verify', False),
                        initial_token=token_entry.token,
                        initial_site_id=token_entry.site_id,
                        initial_site_content_url=token_entry.site_content_url,
                        on_401_invalidate=invalidate_cb,
                    )
                    # Ensure _pat_auth flag is set for PAT tokens
                    if auth_type == "pat":
                        client._pat_auth = True
                    return client

                # Sign in for Connected App
                client = TableauClient(
                    server_url=config.server_url,
                    site_id=site_id_for_client,
                    api_version=config.api_version or "3.15",
                    client_id=config.client_id,
                    client_secret=config.client_secret,
                    username=tableau_username,
                    secret_id=config.secret_id or config.client_id,
                    verify_ssl=not getattr(config, 'skip_ssl_verify', False),
                    on_401_invalidate=invalidate_cb,
                )
                await client.sign_in()
                
                # Cache the token
                expires_at = client.token_expires_at or datetime.now(timezone.utc) + timedelta(minutes=10)
                token_entry = TokenEntry(
                    token=client.auth_token,
                    expires_at=expires_at,
                    site_id=client.site_id,
                    site_content_url=client.site_content_url,
                )
                token_store.set(current_user.id, config.id, auth_type, token_entry)
                return client
        else:
            # Fallback to environment variables (legacy behavior)
            return TableauClient()
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Tableau client initialization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Tableau service configuration error: {str(e)}. Please check your environment variables or select a Tableau server configuration.",
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
    response_model=PaginatedDatasourcesResponse,
    summary="List all datasources",
    description="Retrieve a paginated list of all datasources from Tableau Server.",
    responses={
        200: {"description": "Paginated list of datasources"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_datasources(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    page_size: int = Query(100, ge=1, le=1000, description="Number of results per page"),
    page_number: int = Query(1, ge=1, description="Page number (1-indexed)"),
    search: Optional[str] = Query(None, description="Search term for datasource name (wildcard search)"),
    client: TableauClient = Depends(get_tableau_client),
) -> PaginatedDatasourcesResponse:
    """
    List all datasources.
    
    Returns a paginated list of datasources. Optionally filtered by project and/or name search.
    """
    try:
        result = await client.get_datasources(
            project_id=project_id,
            page_size=page_size,
            page_number=page_number,
            name_filter=search,
        )
        
        datasources = [_normalize_datasource(ds) for ds in result["items"]]
        pagination = result["pagination"]
        
        return PaginatedDatasourcesResponse(
            datasources=datasources,
            pagination=PaginationInfo(
                page_number=pagination["pageNumber"],
                page_size=pagination["pageSize"],
                total_available=pagination["totalAvailable"],
            ),
        )
        
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
        400: {"model": ErrorResponse, "description": "Embedding not supported for PAT authentication"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        404: {"model": ErrorResponse, "description": "View not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_view_embed_url(
    view_id: str,
    filters: Optional[str] = Query(None, description="Optional filters as JSON string (e.g., '{\"Region\":\"West\"}')"),
    x_tableau_auth_type: Optional[str] = Header(None, alias="X-Tableau-Auth-Type"),
    client: TableauClient = Depends(get_tableau_client),
) -> EmbedUrlResponse:
    """
    Get embedding URL for a view.
    
    Returns the URL and authentication token needed to embed the view
    in an iframe or using the Tableau Embedding API.
    
    Filters can be provided as a JSON string in the query parameter.
    Example: ?filters={"Region":"West","Year":"2024"}
    
    Note: View embedding is not supported when using Personal Access Token authentication.
    Users must connect with Connected App to embed views.
    """
    # Check if PAT auth is being used
    auth_type = (x_tableau_auth_type or "connected_app").lower()
    if auth_type == "pat":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="View embedding is not supported when using Personal Access Token authentication. Connect with Connected App to embed views."
        )
    
    # Also check client's internal PAT flag as a fallback
    if hasattr(client, '_pat_auth') and client._pat_auth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="View embedding is not supported when using Personal Access Token authentication. Connect with Connected App to embed views."
        )
    
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
    response_model=PaginatedWorkbooksResponse,
    summary="List all workbooks",
    description="Retrieve a paginated list of all workbooks from Tableau Server. Optionally filtered by project and/or name search.",
    responses={
        200: {"description": "Paginated list of workbooks"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_workbooks(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    page_size: int = Query(100, ge=1, le=1000, description="Number of results per page"),
    page_number: int = Query(1, ge=1, description="Page number (1-indexed)"),
    search: Optional[str] = Query(None, description="Search term for workbook name (wildcard search)"),
    client: TableauClient = Depends(get_tableau_client),
) -> PaginatedWorkbooksResponse:
    """
    List all workbooks.
    
    Returns a paginated list of workbooks. Optionally filtered by project and/or name search.
    """
    try:
        result = await client.get_workbooks(
            project_id=project_id,
            page_size=page_size,
            page_number=page_number,
            name_filter=search,
        )
        
        workbooks = [_normalize_workbook(wb) for wb in result["items"]]
        pagination = result["pagination"]
        
        return PaginatedWorkbooksResponse(
            workbooks=workbooks,
            pagination=PaginationInfo(
                page_number=pagination["pageNumber"],
                page_size=pagination["pageSize"],
                total_available=pagination["totalAvailable"],
            ),
        )
        
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
    response_model=PaginatedViewsResponse,
    summary="List views in workbook",
    description="Retrieve a paginated list of views within a workbook. Optionally filtered by name search.",
    responses={
        200: {"description": "Paginated list of views"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        404: {"model": ErrorResponse, "description": "Workbook not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_workbook_views(
    workbook_id: str,
    page_size: int = Query(100, ge=1, le=1000, description="Number of results per page"),
    page_number: int = Query(1, ge=1, description="Page number (1-indexed)"),
    search: Optional[str] = Query(None, description="Search term for view name/caption (wildcard search)"),
    client: TableauClient = Depends(get_tableau_client),
) -> PaginatedViewsResponse:
    """
    List views in a workbook.
    
    Returns a paginated list of views within the specified workbook. Optionally filtered by name search.
    """
    try:
        result = await client.get_workbook_views(
            workbook_id=workbook_id,
            page_size=page_size,
            page_number=page_number,
            name_filter=search,
        )
        
        views = [_normalize_view(view) for view in result["items"]]
        pagination = result["pagination"]
        
        return PaginatedViewsResponse(
            views=views,
            pagination=PaginationInfo(
                page_number=pagination["pageNumber"],
                page_size=pagination["pageSize"],
                total_available=pagination["totalAvailable"],
            ),
        )
        
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
    force_refresh: bool = Query(False, description="Bypass cache to fetch fresh schema (logs raw GraphQL/read-metadata)"),
    client: TableauClient = Depends(get_tableau_client),
) -> DatasourceSchemaResponse:
    """
    Get datasource schema.
    
    Uses SchemaEnrichmentService (Metadata API + VizQL + columnClass fallback) for accurate
    measure/dimension categorization. Falls back to VizQL-only schema if enrichment times out.
    """
    try:
        service = SchemaEnrichmentService(client)
        core_schema = await service.enrich_datasource_schema(
            datasource_id, force_refresh=force_refresh, include_statistics=False
        )
        fields = core_schema.get("fields", [])
        return DatasourceSchemaResponse(
            datasource_id=datasource_id,
            columns=[
                ColumnSchema(
                    name=f.get("fieldCaption", ""),
                    data_type=f.get("dataType"),
                    remote_type=f.get("dataType"),
                    is_measure=f.get("fieldRole") == "MEASURE",
                    is_dimension=f.get("fieldRole") == "DIMENSION",
                )
                for f in fields if f.get("fieldCaption")
            ],
        )
    except (TableauAuthenticationError, TableauAPIError) as e:
        raise  # Re-raise auth/API errors for proper handling below
    except Exception as enrich_err:
        logger.warning(f"Schema enrichment failed, falling back to VizQL-only: {enrich_err}")
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
        except Exception:
            raise enrich_err  # Raise original enrichment error
        
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
            query=sample.get("query"),
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


@router.post(
    "/datasources/{datasource_id}/execute-query",
    response_model=ExecuteVDSQueryResponse,
    summary="Execute VizQL Data Service query",
    description="Execute a VizQL Data Service query against a datasource.",
    responses={
        200: {"description": "Query results"},
        400: {"model": ErrorResponse, "description": "Invalid query"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def execute_vds_query(
    datasource_id: str,
    request: ExecuteVDSQueryRequest,
    client: TableauClient = Depends(get_tableau_client),
) -> ExecuteVDSQueryResponse:
    """
    Execute a VizQL Data Service query against a datasource.
    
    The query should follow the VizQL Data Service API format:
    {
        "datasource": {"datasourceLuid": "..."},
        "query": {
            "fields": [...],
            "filters": [...]
        },
        "options": {...}
    }
    """
    try:
        # Ensure datasource_id matches
        if request.datasource_id != datasource_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Datasource ID mismatch",
            )
        
        # Ensure query has correct datasource LUID
        query_obj = request.query.copy()
        if "datasource" not in query_obj:
            query_obj["datasource"] = {"datasourceLuid": datasource_id}
        else:
            query_obj["datasource"]["datasourceLuid"] = datasource_id
        
        # Execute query
        result = await client.execute_vds_query(query_obj, limit=1000)
        
        return ExecuteVDSQueryResponse(
            columns=result["columns"],
            data=result["data"],
            row_count=result["row_count"],
        )
        
    except ValueError as e:
        logger.error(f"Invalid query: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid query: {str(e)}",
        )
    except TableauAuthenticationError as e:
        logger.error(f"Authentication error executing query: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Tableau authentication failed: {str(e)}",
        )
    except TableauAPIError as e:
        logger.error(f"API error executing query: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tableau API error: {str(e)}",
        )
    except TableauClientError as e:
        logger.error(f"Client error executing query: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tableau client error: {str(e)}",
        )
