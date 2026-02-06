"""Tool for fetching datasource metadata via REST API."""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def get_datasource_metadata(
    datasource_id: str,
    site_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch datasource metadata via Tableau REST API.
    
    Args:
        datasource_id: Datasource LUID
        site_id: Optional site ID (for authentication)
        
    Returns:
        {
            "id": str,
            "name": str,
            "project": {...},
            "certificationNote": str,
            "tags": [...],
            "createdAt": str,
            "updatedAt": str
        }
    """
    try:
        from app.services.tableau.client import TableauClient
        
        tableau_client = TableauClient()
        
        # Get all datasources and find the one matching datasource_id
        # Note: Tableau REST API doesn't have a direct "get datasource by ID" endpoint
        # so we need to list and filter
        datasources = await tableau_client.get_datasources(page_size=1000)
        
        # Find matching datasource
        matching_ds = None
        for ds in datasources:
            if ds.get("id") == datasource_id or ds.get("luid") == datasource_id:
                matching_ds = ds
                break
        
        if not matching_ds:
            raise Exception(f"Datasource {datasource_id} not found")
        
        logger.info(f"✓ Fetched metadata for datasource: {matching_ds.get('name', datasource_id)}")
        
        return {
            "id": matching_ds.get("id"),
            "name": matching_ds.get("name"),
            "project": matching_ds.get("project", {}),
            "certificationNote": matching_ds.get("certificationNote"),
            "tags": matching_ds.get("tags", {}).get("tag", []) if isinstance(matching_ds.get("tags"), dict) else matching_ds.get("tags", []),
            "createdAt": matching_ds.get("createdAt"),
            "updatedAt": matching_ds.get("updatedAt"),
            "contentUrl": matching_ds.get("contentUrl"),
            "description": matching_ds.get("description")
        }
        
    except Exception as e:
        logger.error(f"Error fetching metadata for {datasource_id}: {e}", exc_info=True)
        raise Exception(f"Failed to fetch datasource metadata: {str(e)}")
