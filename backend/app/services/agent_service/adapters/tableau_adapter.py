"""Tableau adapter protocol and implementation."""
from typing import Any, Dict, List, Optional, Protocol


class TableauAdapterProtocol(Protocol):
    """Protocol for Tableau data access - enables pluggable implementations."""

    @property
    def site_id(self) -> Optional[str]:
        ...

    async def get_datasource_schema(self, datasource_id: str) -> Dict[str, Any]:
        ...

    async def execute_vds_query(self, query: Dict[str, Any]) -> Dict[str, Any]:
        ...

    async def get_view_summary_expanded(
        self, view_id: str, max_rows_per_view: int = 5000
    ) -> Dict[str, Any]:
        ...

    async def get_view_image(
        self, view_id: str, width: int = 800, height: int = 600
    ) -> bytes:
        ...

    async def get_datasources(self, page_size: int = 100) -> Dict[str, Any]:
        ...

    async def get_view_type(self, view_id: str) -> Dict[str, Any]:
        ...

    async def read_metadata(self, datasource_id: str) -> Dict[str, Any]:
        ...

    async def get_metadata_api_fields(self, datasource_id: str) -> Dict[str, Dict[str, Any]]:
        ...

    async def get_field_statistics(
        self, datasource_id: str, field_name: str
    ) -> Dict[str, Any]:
        ...

    async def list_supported_functions(self, datasource_id: str) -> List[Dict[str, Any]]:
        ...

    async def get_view_embed_url(self, view_id: str) -> str:
        ...


class TableauAdapterImpl:
    """Adapter that wraps TableauClient - delegates to concrete implementation."""

    def __init__(self, client: Any):
        self._client = client

    @property
    def site_id(self) -> Optional[str]:
        return getattr(self._client, "site_id", None)

    async def get_datasource_schema(self, datasource_id: str) -> Dict[str, Any]:
        return await self._client.get_datasource_schema(datasource_id)

    async def execute_vds_query(self, query: Dict[str, Any]) -> Dict[str, Any]:
        return await self._client.execute_vds_query(query)

    async def get_view_summary_expanded(
        self, view_id: str, max_rows_per_view: int = 5000
    ) -> Dict[str, Any]:
        return await self._client.get_view_summary_expanded(
            view_id, max_rows_per_view=max_rows_per_view
        )

    async def get_view_image(
        self, view_id: str, width: int = 800, height: int = 600
    ) -> bytes:
        return await self._client.get_view_image(view_id, width=width, height=height)

    async def get_datasources(self, page_size: int = 100) -> Dict[str, Any]:
        return await self._client.get_datasources(page_size=page_size)

    async def get_view_type(self, view_id: str) -> Dict[str, Any]:
        return await self._client.get_view_type(view_id)

    async def read_metadata(self, datasource_id: str) -> Dict[str, Any]:
        return await self._client.read_metadata(datasource_id)

    async def get_metadata_api_fields(self, datasource_id: str) -> Dict[str, Dict[str, Any]]:
        return await self._client.get_metadata_api_fields(datasource_id)

    async def get_field_statistics(
        self, datasource_id: str, field_name: str
    ) -> Dict[str, Any]:
        return await self._client.get_field_statistics(datasource_id, field_name)

    async def list_supported_functions(self, datasource_id: str) -> List[Dict[str, Any]]:
        return await self._client.list_supported_functions(datasource_id)

    async def get_view_embed_url(self, view_id: str) -> str:
        return await self._client.get_view_embed_url(view_id=view_id)
