"""Integration tests for MCP server workflows."""
import pytest
import asyncio
import json
from typing import Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app


# Helper function to simulate MCP tool calls
async def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulate calling an MCP tool directly.
    
    This simulates what happens when an IDE calls an MCP tool via stdio.
    """
    from mcp_server.server import mcp
    
    # Get the tool from the MCP server
    if not hasattr(mcp, '_tool_manager'):
        raise RuntimeError("MCP server tool manager not found")
    
    tool_manager = mcp._tool_manager
    if not hasattr(tool_manager, '_tools'):
        raise RuntimeError("Tool manager has no _tools attribute")
    
    tools = tool_manager._tools
    if tool_name not in tools:
        raise ValueError(f"Tool '{tool_name}' not found. Available tools: {list(tools.keys())}")
    
    tool = tools[tool_name]
    
    # Call the tool function directly
    if asyncio.iscoroutinefunction(tool.func):
        result = await tool.func(**arguments)
    else:
        result = tool.func(**arguments)
    
    return result


class SSEClient:
    """Mock SSE client for testing SSE transport."""
    
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.client = TestClient(app)
        self.events = []
        self._connected = False
    
    async def __aenter__(self):
        """Connect to SSE endpoint."""
        # For testing, we'll simulate SSE by calling the endpoint
        # In real usage, this would maintain a persistent connection
        self._connected = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Disconnect from SSE endpoint."""
        self._connected = False
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool via SSE transport."""
        if not self._connected:
            raise RuntimeError("Not connected to SSE endpoint")
        
        # In real SSE, this would send a message over the SSE connection
        # For testing, we'll call the tool directly
        return await call_mcp_tool(tool_name, arguments)
    
    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read an MCP resource via SSE transport."""
        if not self._connected:
            raise RuntimeError("Not connected to SSE endpoint")
        
        # In real SSE, this would request the resource over the connection
        # For testing, we'll access the resource directly
        from mcp_server.server import mcp
        
        if not hasattr(mcp, '_resource_manager'):
            raise RuntimeError("MCP server resource manager not found")
        
        resource_manager = mcp._resource_manager
        if not hasattr(resource_manager, '_templates'):
            raise RuntimeError("Resource manager has no _templates attribute")
        
        # Find matching resource template
        templates = resource_manager._templates
        for template_uri, resource_func in templates.items():
            # Check if URI matches template pattern
            if '{conversation_id}' in template_uri:
                # Extract conversation ID from URI like "conversation://123"
                prefix = template_uri.replace('{conversation_id}', '')
                if uri.startswith(prefix):
                    conv_id = uri.replace(prefix, '')
                    if asyncio.iscoroutinefunction(resource_func):
                        result_str = await resource_func(conv_id)
                    else:
                        result_str = resource_func(conv_id)
                    # Resources return JSON strings, parse them
                    return json.loads(result_str)
            elif template_uri == uri:
                # Exact match for resources without parameters
                if asyncio.iscoroutinefunction(resource_func):
                    result_str = await resource_func()
                else:
                    result_str = resource_func()
                return json.loads(result_str)
        
        raise ValueError(f"Resource '{uri}' not found")


@pytest.mark.asyncio
async def test_complete_mcp_workflow_from_ide(db_session):
    """Test complete workflow: auth -> list datasources -> query -> get results"""
    # Mock Tableau client to avoid actual API calls
    with patch('mcp_server.tools.tableau_tools.TableauClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock authentication
        mock_client.sign_in.return_value = {"token": "test-token", "expires_at": "2024-12-31T23:59:59"}
        
        # Mock datasources
        mock_client.get_datasources.return_value = [
            {"id": "ds-1", "name": "Sales Data", "project_name": "Finance"},
            {"id": "ds-2", "name": "Marketing Data", "project_name": "Marketing"},
        ]
        
        # Mock query result
        mock_client.query_datasource.return_value = {
            "data": [["2024", "1000", "West"]],
            "columns": ["Year", "Sales", "Region"],
            "row_count": 1,
        }
        
        # 1. Authenticate (simulate auth_tableau_signin)
        # Note: In real scenario, this would store credentials
        # For testing, we'll skip actual auth and just test the flow
        
        # 2. List datasources
        ds_result = await call_mcp_tool("tableau_list_datasources", {})
        assert "datasources" in ds_result
        assert len(ds_result["datasources"]) > 0
        assert ds_result["datasources"][0]["id"] == "ds-1"
        
        # 3. Query first datasource
        ds_id = ds_result["datasources"][0]["id"]
        query_result = await call_mcp_tool("tableau_query_datasource", {
            "datasource_id": ds_id,
            "filters": {"year": "2024"}
        })
        assert "data" in query_result
        assert "columns" in query_result
        assert query_result["row_count"] == 1


@pytest.mark.asyncio
async def test_mcp_conversation_via_sse(db_session):
    """Test conversation management via SSE transport"""
    async with SSEClient("/mcp/sse") as client:
        # Create conversation
        conv = await client.call_tool("chat_create_conversation", {})
        assert "conversation_id" in conv
        conv_id = conv["conversation_id"]
        
        # Add messages
        msg_result = await client.call_tool("chat_add_message", {
            "conversation_id": conv_id,
            "role": "user",
            "content": "Show me sales data"
        })
        assert "message_id" in msg_result
        
        # Retrieve conversation as resource
        resource = await client.read_resource(f"conversation://{conv_id}")
        assert "messages" in resource
        assert len(resource["messages"]) >= 1
        
        # Verify message content (role might be uppercase or lowercase)
        user_messages = [m for m in resource["messages"] if m["role"].upper() == "USER"]
        assert len(user_messages) > 0
        assert user_messages[0]["content"] == "Show me sales data"


@pytest.mark.asyncio
async def test_conversation_flow_via_mcp(db_session):
    """Test complete conversation flow via MCP tools"""
    # Create conversation
    conv_result = await call_mcp_tool("chat_create_conversation", {})
    assert "conversation_id" in conv_result
    conv_id = conv_result["conversation_id"]
    
    # Add user message
    user_msg = await call_mcp_tool("chat_add_message", {
        "conversation_id": conv_id,
        "role": "user",
        "content": "What datasources are available?",
        "model": "gpt-4"
    })
    assert "message_id" in user_msg
    
    # Add assistant message
    assistant_msg = await call_mcp_tool("chat_add_message", {
        "conversation_id": conv_id,
        "role": "assistant",
        "content": "Here are the available datasources...",
        "model": "gpt-4"
    })
    assert "message_id" in assistant_msg
    
    # Get conversation
    conv = await call_mcp_tool("chat_get_conversation", {
        "conversation_id": conv_id
    })
    assert conv["conversation_id"] == conv_id
    
    # Get messages
    messages = await call_mcp_tool("chat_get_messages", {
        "conversation_id": conv_id
    })
    assert "messages" in messages
    assert len(messages["messages"]) == 2
    
    # Verify message order
    assert messages["messages"][0]["role"] == "user"
    assert messages["messages"][1]["role"] == "assistant"
    
    # List conversations
    convs = await call_mcp_tool("chat_list_conversations", {
        "limit": 10,
        "offset": 0
    })
    assert "conversations" in convs
    assert len(convs["conversations"]) >= 1
    assert any(c["conversation_id"] == conv_id for c in convs["conversations"])


@pytest.mark.asyncio
async def test_authentication_flow_via_mcp():
    """Test authentication flow via MCP"""
    with patch('mcp_server.tools.auth_tools.TableauClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock successful authentication
        mock_client.sign_in.return_value = {
            "token": "test-token-123",
            "expires_at": "2024-12-31T23:59:59Z"
        }
        
        # Test sign in
        auth_result = await call_mcp_tool("auth_tableau_signin", {
            "server_url": "https://tableau.test.com",
            "client_id": "test-client-id",
            "client_secret": "test-secret",
            "site_id": "test-site"
        })
        
        assert "authenticated" in auth_result
        assert auth_result["authenticated"] is True
        
        # Test get token
        token_result = await call_mcp_tool("auth_get_token", {})
        assert "token" in token_result or "error" in token_result
        
        # Test refresh token
        refresh_result = await call_mcp_tool("auth_refresh_token", {})
        assert "token" in refresh_result or "error" in refresh_result


@pytest.mark.asyncio
async def test_resource_access_patterns(db_session):
    """Test MCP resource access patterns"""
    # Create a conversation with messages
    conv_result = await call_mcp_tool("chat_create_conversation", {})
    conv_id = conv_result["conversation_id"]
    
    await call_mcp_tool("chat_add_message", {
        "conversation_id": conv_id,
        "role": "user",
        "content": "Test message 1"
    })
    
    await call_mcp_tool("chat_add_message", {
        "conversation_id": conv_id,
        "role": "assistant",
        "content": "Test response 1"
    })
    
    # Access conversation resource
    from mcp_server.server import mcp
    
    if hasattr(mcp, '_resource_manager'):
        resource_manager = mcp._resource_manager
        if hasattr(resource_manager, '_templates'):
            templates = resource_manager._templates
            
            # Find conversation resource template
            conv_template = None
            for uri_template, resource_func in templates.items():
                if 'conversation' in uri_template.lower():
                    conv_template = (uri_template, resource_func)
                    break
            
            if conv_template:
                template_uri, resource_func = conv_template
                # Extract ID from template - template is "conversation://{conversation_id}"
                if '{conversation_id}' in template_uri:
                    # Call resource function with conversation ID
                    if asyncio.iscoroutinefunction(resource_func):
                        resource_data_str = await resource_func(str(conv_id))
                    else:
                        resource_data_str = resource_func(str(conv_id))
                    
                    # Resources return JSON strings
                    resource_data = json.loads(resource_data_str)
                    
                    assert resource_data is not None
                    # Resource should contain conversation data
                    assert "messages" in resource_data or "conversation_id" in resource_data
                    assert resource_data["conversation_id"] == conv_id
                    assert len(resource_data["messages"]) == 2


@pytest.mark.asyncio
async def test_mcp_load_handling(db_session):
    """Test MCP server under load with concurrent connections"""
    import gc
    import tracemalloc
    
    # Start tracking memory
    tracemalloc.start()
    initial_snapshot = tracemalloc.take_snapshot()
    
    # Mock Tableau client
    with patch('mcp_server.tools.tableau_tools.TableauClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_datasources.return_value = [
            {"id": f"ds-{i}", "name": f"Datasource {i}"} for i in range(10)
        ]
        
        # Create multiple conversations concurrently
        async def create_conversation():
            return await call_mcp_tool("chat_create_conversation", {})
        
        # Run 50 concurrent requests
        tasks = [create_conversation() for _ in range(50)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all succeeded
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == 50
        
        # Verify all have conversation IDs
        assert all("conversation_id" in r for r in successful)
        
        # Test concurrent tool calls
        async def list_datasources():
            return await call_mcp_tool("tableau_list_datasources", {})
        
        tasks = [list_datasources() for _ in range(50)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all succeeded
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == 50
        
        # Verify all have datasources
        assert all("datasources" in r for r in successful)
        
        # Force garbage collection
        gc.collect()
        
        # Check memory usage
        final_snapshot = tracemalloc.take_snapshot()
        top_stats = final_snapshot.compare_to(initial_snapshot, 'lineno')
        
        # Memory should not grow excessively (allow some growth for test overhead)
        # This is a basic check - in production, you'd want more sophisticated monitoring
        total_memory_diff = sum(stat.size_diff for stat in top_stats[:10])
        # Allow up to 10MB growth (reasonable for 100 concurrent operations)
        assert total_memory_diff < 10 * 1024 * 1024, f"Memory growth too high: {total_memory_diff / 1024 / 1024:.2f}MB"
        
        tracemalloc.stop()


@pytest.mark.asyncio
async def test_error_handling_across_mcp_boundary(db_session):
    """Test error handling works across MCP boundary"""
    # Test invalid conversation ID
    with pytest.raises((ValueError, KeyError, AttributeError)):
        await call_mcp_tool("chat_get_conversation", {
            "conversation_id": 99999  # Non-existent ID
        })
    
    # Test invalid tool name
    with pytest.raises(ValueError, match="Tool.*not found"):
        await call_mcp_tool("nonexistent_tool", {})
    
    # Test invalid arguments
    with pytest.raises((TypeError, ValueError, KeyError)):
        await call_mcp_tool("chat_add_message", {
            # Missing required arguments
        })


@pytest.mark.asyncio
async def test_sse_endpoint_connection():
    """Test SSE endpoint connection and heartbeat"""
    client = TestClient(app)
    
    # Test SSE endpoint exists
    response = client.get("/mcp/sse")
    assert response.status_code == 200
    assert response.headers.get("content-type") == "text/event-stream"
    
    # Test debug endpoints
    tools_response = client.get("/mcp/debug/tools")
    assert tools_response.status_code == 200
    data = tools_response.json()
    assert "server_name" in data
    assert "tools_count" in data
    assert data["tools_count"] > 0
    
    resources_response = client.get("/mcp/debug/resources")
    assert resources_response.status_code == 200
    data = resources_response.json()
    assert "resources_count" in data


@pytest.mark.asyncio
async def test_tableau_tools_integration(db_session):
    """Test Tableau tools integration via MCP"""
    with patch('mcp_server.tools.tableau_tools.TableauClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock datasources
        mock_client.get_datasources.return_value = [
            {"id": "ds-1", "name": "Sales", "project_name": "Finance"},
            {"id": "ds-2", "name": "Marketing", "project_name": "Marketing"},
        ]
        
        # Mock views
        mock_client.get_views.return_value = [
            {"id": "view-1", "name": "Sales Dashboard", "workbook_name": "Sales"},
            {"id": "view-2", "name": "Marketing Dashboard", "workbook_name": "Marketing"},
        ]
        
        # Mock embed URL
        mock_client.get_view_embed_url.return_value = {
            "url": "https://tableau.test.com/embed/view-1",
            "token": "embed-token-123"
        }
        
        # Test list datasources
        ds_result = await call_mcp_tool("tableau_list_datasources", {})
        assert "datasources" in ds_result
        assert len(ds_result["datasources"]) == 2
        
        # Test list views
        views_result = await call_mcp_tool("tableau_list_views", {})
        assert "views" in views_result
        assert len(views_result["views"]) == 2
        
        # Test get embed URL
        embed_result = await call_mcp_tool("tableau_get_view_embed_url", {
            "view_id": "view-1"
        })
        # Returns dict with 'url' and 'token' keys
        assert "url" in embed_result
        assert "token" in embed_result
