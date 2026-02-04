# MCP Server Integration Tests

This directory contains integration tests for the MCP (Model Context Protocol) server implementation.

## Overview

These tests verify that the MCP server works correctly across different transport mechanisms (stdio for IDE, SSE for web) and handles various workflows including:

- Tool invocation from IDE (stdio simulation)
- Tool invocation from web (SSE transport)
- Conversation management flows
- Authentication flows
- Resource access patterns
- Load testing with concurrent connections
- Error handling across MCP boundaries

## Running the Tests

### Prerequisites

1. Install test dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Ensure database is set up (tests use in-memory SQLite):
   ```bash
   # Tests automatically create/destroy test database
   ```

### Run All Integration Tests

```bash
cd backend
pytest tests/integration/ -v
```

### Run Specific Test

```bash
pytest tests/integration/test_mcp_flow.py::test_complete_mcp_workflow_from_ide -v
```

### Run with Coverage

```bash
pytest tests/integration/ --cov=mcp_server --cov-report=html
```

## Test Structure

### `test_mcp_flow.py`

Main integration test file containing:

1. **`test_complete_mcp_workflow_from_ide`**: Tests complete workflow simulating IDE usage
   - Authenticates with Tableau
   - Lists datasources
   - Queries a datasource
   - Verifies results

2. **`test_mcp_conversation_via_sse`**: Tests conversation management via SSE transport
   - Creates conversation
   - Adds messages
   - Retrieves conversation as resource

3. **`test_conversation_flow_via_mcp`**: Tests complete conversation lifecycle
   - Creates conversation
   - Adds user and assistant messages
   - Retrieves conversation and messages
   - Lists conversations

4. **`test_authentication_flow_via_mcp`**: Tests authentication workflow
   - Signs in to Tableau
   - Gets current token
   - Refreshes token

5. **`test_resource_access_patterns`**: Tests MCP resource access
   - Creates conversation with messages
   - Accesses conversation resource via URI template
   - Verifies resource content

6. **`test_mcp_load_handling`**: Load testing
   - Tests 50 concurrent conversation creations
   - Tests 50 concurrent tool invocations
   - Checks for memory leaks

7. **`test_error_handling_across_mcp_boundary`**: Error handling tests
   - Invalid conversation IDs
   - Invalid tool names
   - Missing required arguments

8. **`test_sse_endpoint_connection`**: SSE endpoint tests
   - Verifies SSE endpoint exists
   - Tests debug endpoints

9. **`test_tableau_tools_integration`**: Tableau tools integration
   - Lists datasources
   - Lists views
   - Gets embed URLs

## Mocking

Tests use mocking to avoid actual API calls:

- `TableauClient` is mocked to return test data
- Database operations use in-memory SQLite
- No actual network requests are made

## Success Criteria

All tests should pass with:
- ✅ IDE can complete full workflow via MCP
- ✅ Web can complete full workflow via MCP
- ✅ Concurrent connections handled correctly
- ✅ No memory leaks under load (< 10MB growth for 100 operations)
- ✅ Error handling works across MCP boundary

## Troubleshooting

### Import Errors

If you see import errors:
```bash
# Ensure backend is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Database Errors

Tests use in-memory SQLite. If you see database errors:
- Check that `Base.metadata.create_all()` is called in fixtures
- Verify `db_session` fixture is working correctly

### MCP Server Not Found

If tests fail with "MCP server not found":
- Ensure `mcp_server` package is importable
- Check that `mcp_server/server.py` exists and is valid

### Memory Leak Test Fails

If memory leak test fails:
- This might indicate actual memory leaks in the code
- Review tool implementations for unclosed resources
- Check database sessions are properly closed

## Continuous Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run MCP Integration Tests
  run: |
    cd backend
    pytest tests/integration/ -v --tb=short
```

## Future Enhancements

- [ ] Add tests for actual stdio transport (requires subprocess)
- [ ] Add tests for actual SSE transport (requires WebSocket client)
- [ ] Add performance benchmarks
- [ ] Add tests for resource caching
- [ ] Add tests for credential encryption/decryption
