"""Pydantic models for API request/response schemas."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# Tableau API Models

class DatasourceResponse(BaseModel):
    """Datasource response model."""
    id: str = Field(..., description="Datasource ID")
    name: str = Field(..., description="Datasource name")
    project_id: Optional[str] = Field(None, description="Project ID")
    project_name: Optional[str] = Field(None, description="Project name")
    content_url: Optional[str] = Field(None, description="Content URL")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "datasource-123",
                "name": "Sales Data",
                "project_id": "project-456",
                "project_name": "Finance",
                "content_url": "sales_data",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T00:00:00Z",
            }
        }


class ViewResponse(BaseModel):
    """View response model."""
    id: str = Field(..., description="View ID")
    name: str = Field(..., description="View name")
    workbook_id: Optional[str] = Field(None, description="Workbook ID")
    workbook_name: Optional[str] = Field(None, description="Workbook name")
    datasource_id: Optional[str] = Field(None, description="Datasource ID")
    content_url: Optional[str] = Field(None, description="Content URL")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "view-123",
                "name": "Sales Dashboard",
                "workbook_id": "workbook-456",
                "workbook_name": "Sales Analytics",
                "datasource_id": "datasource-789",
                "content_url": "sales_dashboard",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T00:00:00Z",
            }
        }


class QueryDatasourceRequest(BaseModel):
    """Request model for querying a datasource."""
    datasource_id: str = Field(..., description="Datasource ID to query")
    filters: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional filters to apply (e.g., {'year': '2024', 'region': 'West'})"
    )
    columns: Optional[List[str]] = Field(
        None,
        description="Optional list of column names to return"
    )
    limit: Optional[int] = Field(
        None,
        ge=1,
        le=10000,
        description="Optional limit on number of rows (1-10000)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "datasource_id": "datasource-123",
                "filters": {"year": "2024", "region": "West"},
                "columns": ["sales", "region", "date"],
                "limit": 1000,
            }
        }


class QueryDatasourceResponse(BaseModel):
    """Response model for datasource query."""
    datasource_id: str = Field(..., description="Datasource ID that was queried")
    columns: List[str] = Field(..., description="Column names")
    data: List[List[Any]] = Field(..., description="Query results as rows")
    row_count: int = Field(..., description="Number of rows returned")
    
    class Config:
        json_schema_extra = {
            "example": {
                "datasource_id": "datasource-123",
                "columns": ["sales", "region", "date"],
                "data": [
                    [1000.0, "West", "2024-01-01"],
                    [1500.0, "East", "2024-01-02"],
                ],
                "row_count": 2,
            }
        }


class EmbedUrlResponse(BaseModel):
    """Response model for view embed URL."""
    view_id: str = Field(..., description="View ID")
    workbook_id: Optional[str] = Field(None, description="Workbook ID")
    url: str = Field(..., description="Embedding URL")
    token: Optional[str] = Field(None, description="Authentication token")
    
    class Config:
        json_schema_extra = {
            "example": {
                "view_id": "view-123",
                "workbook_id": "workbook-456",
                "url": "https://tableau.example.com/views/SalesDashboard",
                "token": "auth-token-xyz",
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "Tableau API Error",
                "detail": "Authentication failed: Invalid credentials",
            }
        }


# Phase 5A: Object Explorer Models

class ProjectResponse(BaseModel):
    """Project response model."""
    id: str = Field(..., description="Project ID")
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    parent_project_id: Optional[str] = Field(None, description="Parent project ID")
    content_permissions: Optional[str] = Field(None, description="Content permissions")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "project-123",
                "name": "Finance",
                "description": "Finance department projects",
                "parent_project_id": None,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T00:00:00Z",
            }
        }


class WorkbookResponse(BaseModel):
    """Workbook response model."""
    id: str = Field(..., description="Workbook ID")
    name: str = Field(..., description="Workbook name")
    project_id: Optional[str] = Field(None, description="Project ID")
    project_name: Optional[str] = Field(None, description="Project name")
    content_url: Optional[str] = Field(None, description="Content URL")
    created_at: Optional[str] = Field(..., description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "workbook-123",
                "name": "Sales Analytics",
                "project_id": "project-456",
                "project_name": "Finance",
                "content_url": "sales_analytics",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T00:00:00Z",
            }
        }


class ProjectContentsResponse(BaseModel):
    """Project contents response model."""
    project_id: str = Field(..., description="Project ID")
    datasources: List[DatasourceResponse] = Field(default_factory=list, description="Datasources in project")
    workbooks: List[WorkbookResponse] = Field(default_factory=list, description="Workbooks in project")
    projects: List[ProjectResponse] = Field(default_factory=list, description="Nested projects")


class ColumnSchema(BaseModel):
    """Column schema model."""
    name: str = Field(..., description="Column name")
    data_type: Optional[str] = Field(None, description="Data type")
    remote_type: Optional[str] = Field(None, description="Remote type")
    is_measure: bool = Field(default=False, description="Whether column is a measure")
    is_dimension: bool = Field(default=False, description="Whether column is a dimension")


class DatasourceSchemaResponse(BaseModel):
    """Datasource schema response model."""
    datasource_id: str = Field(..., description="Datasource ID")
    columns: List[ColumnSchema] = Field(..., description="Column schema information")


class DatasourceSampleResponse(BaseModel):
    """Datasource sample data response model."""
    datasource_id: str = Field(..., description="Datasource ID")
    columns: List[str] = Field(..., description="Column names")
    data: List[List[Any]] = Field(..., description="Sample data rows")
    row_count: int = Field(..., description="Number of rows returned")


# Phase 5B: Chat Context Models

class ChatContextObject(BaseModel):
    """Chat context object model."""
    object_id: str = Field(..., description="Object ID (datasource or view)")
    object_type: str = Field(..., description="Object type: 'datasource' or 'view'")
    object_name: Optional[str] = Field(None, description="Object name")
    added_at: str = Field(..., description="Timestamp when object was added to context")


class AddContextRequest(BaseModel):
    """Request model for adding object to chat context."""
    conversation_id: int = Field(..., description="Conversation ID")
    object_id: str = Field(..., description="Object ID (datasource or view)")
    object_type: str = Field(..., description="Object type: 'datasource' or 'view'")
    object_name: Optional[str] = Field(None, description="Object name for display")


class RemoveContextRequest(BaseModel):
    """Request model for removing object from chat context."""
    conversation_id: int = Field(..., description="Conversation ID")
    object_id: str = Field(..., description="Object ID to remove")


class ChatContextResponse(BaseModel):
    """Chat context response model."""
    conversation_id: int = Field(..., description="Conversation ID")
    objects: List[ChatContextObject] = Field(default_factory=list, description="Objects in context")
