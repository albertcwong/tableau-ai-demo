"""Integration test fixtures."""
import pytest
from unittest.mock import AsyncMock

from app.main import app
from app.api.chat import get_tableau_client_optional


@pytest.fixture
def mock_tableau_for_chat():
    """Mock TableauClient for chat API - used by get_tableau_client_optional override."""
    mock = AsyncMock()
    mock.get_datasource_schema = AsyncMock(return_value={
        "columns": [
            {"name": "Sales", "data_type": "number", "is_measure": True, "is_dimension": False},
            {"name": "Region", "data_type": "string", "is_measure": False, "is_dimension": True},
            {"name": "Year", "data_type": "date", "is_measure": False, "is_dimension": True},
        ]
    })
    mock.get_view_data = AsyncMock(return_value={
        "columns": ["Region", "Sales"],
        "data": [["North", "1000"], ["South", "2000"], ["East", "1500"]],
        "row_count": 3,
    })
    mock.get_view = AsyncMock(return_value={
        "id": "test-view-456",
        "name": "Sales Dashboard",
        "workbook_id": "wb-123",
    })
    mock.execute_vds_query = AsyncMock(return_value={
        "columns": ["Region", "Sales"],
        "data": [{"Region": "North", "Sales": 1000}, {"Region": "South", "Sales": 2000}],
        "row_count": 2,
    })
    return mock


@pytest.fixture(autouse=True)
def override_tableau_client(mock_tableau_for_chat):
    """Override get_tableau_client_optional to return mock for integration tests."""
    async def _override():
        return mock_tableau_for_chat

    app.dependency_overrides[get_tableau_client_optional] = _override
    yield
    if get_tableau_client_optional in app.dependency_overrides:
        del app.dependency_overrides[get_tableau_client_optional]
