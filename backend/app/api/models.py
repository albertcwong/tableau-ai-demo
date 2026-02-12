"""API request/response models."""
from typing import Optional, Literal, Union, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class AddContextRequest(BaseModel):
    """Request model for adding context."""
    conversation_id: int
    object_id: str
    object_type: Literal["datasource", "view"]
    object_name: Optional[str] = None


class RemoveContextRequest(BaseModel):
    """Request model for removing context."""
    conversation_id: int
    object_id: str


class ChatContextObject(BaseModel):
    """Model for a context object."""
    object_id: str
    object_type: Literal["datasource", "view"]
    object_name: Optional[str] = None
    added_at: str


class ChatContextResponse(BaseModel):
    """Response model for chat context."""
    conversation_id: int
    objects: list[ChatContextObject]


# Agent Message Models
class AgentMessageContent(BaseModel):
    """Base model for agent message content."""
    type: Literal["text", "image", "binary", "table", "json"] = Field(default="text", description="Content type")
    data: Union[str, bytes, Dict[str, Any]] = Field(..., description="Content data")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata (e.g., filename, mime_type)")


class AgentMessageChunk(BaseModel):
    """Structured message chunk from agent streaming."""
    message_type: Literal["reasoning", "final_answer", "error", "progress", "metadata"] = Field(
        ..., 
        description="Type of message: reasoning steps, final answer, error, progress update, or metadata"
    )
    content: AgentMessageContent = Field(..., description="Message content")
    step_index: Optional[int] = Field(default=None, description="Index of reasoning step (for reasoning type)")
    step_name: Optional[str] = Field(default=None, description="Name/description of reasoning step")
    timestamp: Optional[float] = Field(default=None, description="Unix timestamp when this chunk was generated")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata (e.g., vizql_query)")
    
    def to_sse_format(self) -> str:
        """Convert to Server-Sent Events format."""
        import json
        data = self.model_dump_json()
        return f"data: {data}\n\n"
    
    @classmethod
    def from_sse_line(cls, line: str) -> Optional["AgentMessageChunk"]:
        """Parse from Server-Sent Events line."""
        if not line.startswith("data: "):
            return None
        try:
            import json
            data = json.loads(line[6:])  # Remove "data: " prefix
            return cls(**data)
        except Exception:
            return None


class AgentMessageComplete(BaseModel):
    """Complete structured agent message (for non-streaming responses)."""
    message_type: Literal["final_answer", "error"]
    content: AgentMessageContent
    reasoning_steps: Optional[list[AgentMessageContent]] = Field(
        default=None, 
        description="List of reasoning steps if available"
    )
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


# Tableau API Models
class DatasourceResponse(BaseModel):
    """Response model for a Tableau datasource."""
    id: str
    name: str
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    content_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ViewResponse(BaseModel):
    """Response model for a Tableau view."""
    id: str
    name: str
    workbook_id: Optional[str] = None
    workbook_name: Optional[str] = None
    datasource_id: Optional[str] = None
    content_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class QueryDatasourceRequest(BaseModel):
    """Request model for querying a datasource."""
    datasource_id: str
    filters: Optional[Dict[str, Any]] = None
    columns: Optional[List[str]] = None
    limit: Optional[int] = Field(default=1000, ge=1, le=100000)


class QueryDatasourceResponse(BaseModel):
    """Response model for datasource query results."""
    datasource_id: str
    columns: List[str]
    data: List[List[Any]]
    row_count: int


class EmbedUrlResponse(BaseModel):
    """Response model for view embed URL."""
    view_id: str
    workbook_id: Optional[str] = None
    url: str
    token: Optional[str] = None


class ErrorResponse(BaseModel):
    """Response model for errors."""
    detail: str
    error: Optional[str] = None


class ProjectResponse(BaseModel):
    """Response model for a Tableau project."""
    id: str
    name: str
    description: Optional[str] = None
    parent_project_id: Optional[str] = None
    content_permissions: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WorkbookResponse(BaseModel):
    """Response model for a Tableau workbook."""
    id: str
    name: str
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    content_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProjectContentsResponse(BaseModel):
    """Response model for project contents."""
    project_id: str
    datasources: List[DatasourceResponse]
    workbooks: List[WorkbookResponse]
    projects: List[ProjectResponse]


class ColumnSchema(BaseModel):
    """Schema for a datasource column."""
    name: str
    data_type: Optional[str] = None
    remote_type: Optional[str] = None
    is_measure: bool
    is_dimension: bool


class PaginationInfo(BaseModel):
    """Pagination metadata from Tableau API."""
    page_number: int
    page_size: int
    total_available: int


class PaginatedDatasourcesResponse(BaseModel):
    """Paginated response model for datasources."""
    datasources: List[DatasourceResponse]
    pagination: PaginationInfo


class PaginatedWorkbooksResponse(BaseModel):
    """Paginated response model for workbooks."""
    workbooks: List[WorkbookResponse]
    pagination: PaginationInfo


class PaginatedViewsResponse(BaseModel):
    """Paginated response model for views."""
    views: List[ViewResponse]
    pagination: PaginationInfo


class DatasourceSchemaResponse(BaseModel):
    """Response model for datasource schema."""
    datasource_id: str
    columns: List[ColumnSchema]


class DatasourceSampleResponse(BaseModel):
    """Response model for datasource sample data."""
    datasource_id: str
    columns: List[str]
    data: List[List[Any]]
    row_count: int
    query: Optional[Dict[str, Any]] = None


class ExecuteVDSQueryRequest(BaseModel):
    """Request model for executing a VizQL Data Service query."""
    datasource_id: str
    query: Dict[str, Any]


class ExecuteVDSQueryResponse(BaseModel):
    """Response model for executing a VizQL Data Service query."""
    columns: List[str]
    data: List[List[Any]]
    row_count: int


# Agent Configuration Models
class AgentVersionResponse(BaseModel):
    """Response model for an agent version configuration."""
    version: str
    is_enabled: bool
    is_default: bool
    description: Optional[str] = None


class AgentConfigResponse(BaseModel):
    """Response model for agent configuration."""
    agent_name: str
    versions: List[AgentVersionResponse]
    default_version: Optional[str] = None


class AgentVersionUpdate(BaseModel):
    """Request model for updating agent version configuration."""
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None
    description: Optional[str] = None


class AgentSettingsResponse(BaseModel):
    """Response model for agent-level settings."""
    agent_name: str
    max_build_retries: Optional[int] = None
    max_execution_retries: Optional[int] = None


class AgentSettingsUpdate(BaseModel):
    """Request model for updating agent-level settings."""
    max_build_retries: Optional[int] = Field(None, ge=1, le=10)
    max_execution_retries: Optional[int] = Field(None, ge=1, le=10)
