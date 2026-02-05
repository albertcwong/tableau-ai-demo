"""VizQL schema enrichment API endpoints."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.services.tableau.client import TableauClient, TableauClientError
from app.services.agents.vizql.schema_enrichment import SchemaEnrichmentService
from app.core.database import get_db
from app.api.auth import get_current_user
from app.api.tableau import get_tableau_client
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vizql", tags=["vizql"])


@router.post("/datasources/{datasource_id}/enrich-schema")
async def enrich_schema(
    datasource_id: str,
    force_refresh: bool = False,
    include_statistics: bool = True,
    x_tableau_config_id: Optional[str] = Header(None, alias="X-Tableau-Config-Id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tableau_client: TableauClient = Depends(get_tableau_client),
):
    """
    Enrich datasource schema with VizQL metadata.
    
    This endpoint is triggered manually via UI button.
    Results are cached for 1 hour.
    
    Args:
        datasource_id: Datasource LUID to enrich
        force_refresh: If True, bypass cache and refresh from API
        include_statistics: If True, include field statistics (cardinality, sample values, min/max/null%)
        x_tableau_config_id: Optional Tableau config ID header
        db: Database session
        current_user: Current authenticated user
        tableau_client: Tableau client instance
        
    Returns:
        Dictionary with enrichment statistics and enriched schema
    """
    try:
        service = SchemaEnrichmentService(tableau_client)
        enriched = await service.enrich_datasource_schema(
            datasource_id, 
            force_refresh,
            include_statistics=include_statistics
        )
        
        return {
            "datasource_id": datasource_id,
            "field_count": len(enriched["fields"]),
            "measure_count": len(enriched["measures"]),
            "dimension_count": len(enriched["dimensions"]),
            "cached": not force_refresh,
            "enriched_schema": enriched
        }
        
    except TableauClientError as e:
        logger.error(f"Tableau client error enriching schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tableau API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error enriching schema: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enrich schema: {str(e)}"
        )


@router.get("/datasources/{datasource_id}/supported-functions")
async def get_supported_functions(
    datasource_id: str,
    x_tableau_config_id: Optional[str] = Header(None, alias="X-Tableau-Config-Id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tableau_client: TableauClient = Depends(get_tableau_client),
):
    """
    Get supported functions for a datasource.
    
    Args:
        datasource_id: Datasource LUID
        x_tableau_config_id: Optional Tableau config ID header
        db: Database session
        current_user: Current authenticated user
        tableau_client: Tableau client instance
        
    Returns:
        List of supported function objects
    """
    try:
        service = SchemaEnrichmentService(tableau_client)
        functions = await service.get_supported_functions(datasource_id)
        
        return {
            "datasource_id": datasource_id,
            "functions": functions,
            "function_count": len(functions)
        }
        
    except TableauClientError as e:
        logger.error(f"Tableau client error fetching functions: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tableau API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching functions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch supported functions: {str(e)}"
        )
