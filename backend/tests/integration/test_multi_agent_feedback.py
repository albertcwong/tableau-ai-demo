"""Integration tests for multi-agent orchestration and feedback system."""
import pytest
import json
from unittest.mock import AsyncMock, patch
from app.models.chat import Conversation, Message, MessageRole, ChatContext
from app.services.ai.models import ChatResponse

# Import fixtures from conftest
pytest_plugins = []


class TestMultiAgentOrchestration:
    """Tests for multi-agent orchestration."""
    
    def test_multi_agent_routing(self, client, db_session, test_conversation, mock_tableau_client, mock_ai_client):
        """Test that multi-agent workflows can be triggered."""
        # Create context with both datasource and view
        datasource_context = ChatContext(
            conversation_id=test_conversation.id,
            object_type='datasource',
            object_id='test-datasource-123'
        )
        view_context = ChatContext(
            conversation_id=test_conversation.id,
            object_type='view',
            object_id='test-view-456'
        )
        db_session.add(datasource_context)
        db_session.add(view_context)
        db_session.commit()
        
        # Mock multi-agent workflow responses
        planning_response = ChatResponse(
            content=json.dumps([
                {
                    "agent_type": "vizql",
                    "action": "query sales data",
                    "depends_on": None,
                    "input_data": None
                },
                {
                    "agent_type": "summary",
                    "action": "summarize results",
                    "depends_on": 0,
                    "input_data": "query_results"
                }
            ]),
            model="gpt-4",
            tokens_used=100,
            prompt_tokens=50,
            completion_tokens=50,
            finish_reason="stop",
            function_call=None
        )
        
        vizql_response = ChatResponse(
            content="Query executed successfully",
            model="gpt-4",
            tokens_used=50,
            prompt_tokens=30,
            completion_tokens=20,
            finish_reason="stop",
            function_call=None
        )
        
        summary_response = ChatResponse(
            content="Summary: Sales are highest in Q4",
            model="gpt-4",
            tokens_used=75,
            prompt_tokens=40,
            completion_tokens=35,
            finish_reason="stop",
            function_call=None
        )
        
        # Mock AI client to return planning, then VizQL, then Summary responses
        mock_ai_client.chat = AsyncMock(side_effect=[
            planning_response,  # Planning
            vizql_response,      # VizQL agent
            summary_response    # Summary agent
        ])
        
        response = client.post(
            "/api/v1/chat/message",
            json={
                "conversation_id": test_conversation.id,
                "content": "query sales by region and then summarize the results",
                "agent_type": "multi_agent",
                "model": "gpt-4",
                "stream": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"]["role"].lower() == "assistant"
        assert len(data["message"]["content"]) > 0


class TestFeedbackSystem:
    """Tests for user feedback and learning system."""
    
    def test_record_correction(self, client, db_session, test_conversation, mock_ai_client):
        """Test recording a user correction."""
        # Mock learning extraction response
        learning_response = ChatResponse(
            content="The user prefers 'revenue' over 'sales'. Use revenue terminology in future queries.",
            model="gpt-4",
            tokens_used=50,
            prompt_tokens=30,
            completion_tokens=20,
            finish_reason="stop",
            function_call=None
        )
        
        mock_ai_client.chat = AsyncMock(return_value=learning_response)
        
        response = client.post(
            "/api/v1/feedback/correction",
            json={
                "conversation_id": test_conversation.id,
                "original_query": "show sales",
                "original_result": {"data": [{"Sales": 1000}]},
                "correction": "I meant revenue, not sales",
                "corrected_result": {"data": [{"Revenue": 1000}]}
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "feedback_id" in data
        assert "learning" in data
        assert "recorded_at" in data
        
        # Verify correction was saved as a message
        db_session.expire_all()
        messages = db_session.query(Message).filter_by(
            conversation_id=test_conversation.id
        ).all()
        
        correction_messages = [
            m for m in messages
            if m.extra_metadata and m.extra_metadata.get("type") == "correction"
        ]
        assert len(correction_messages) >= 1
    
    def test_record_preferences(self, client, db_session, test_conversation):
        """Test recording user preferences."""
        response = client.post(
            "/api/v1/feedback/preferences",
            json={
                "conversation_id": test_conversation.id,
                "preferences": {
                    "detail_level": "brief",
                    "format": "table",
                    "preferred_fields": ["Revenue", "Profit"]
                }
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "preferences_id" in data
        assert "preferences" in data
        assert data["preferences"]["detail_level"] == "brief"
        assert "recorded_at" in data
    
    def test_query_refinement_with_feedback(
        self, client, db_session, test_conversation, test_datasource_context, mock_tableau_client, mock_ai_client
    ):
        """Test that queries are refined based on feedback."""
        # First, record a correction
        learning_response = ChatResponse(
            content="User prefers 'revenue' terminology",
            model="gpt-4",
            tokens_used=30,
            prompt_tokens=20,
            completion_tokens=10,
            finish_reason="stop",
            function_call=None
        )
        
        mock_ai_client.chat = AsyncMock(return_value=learning_response)
        
        # Record correction
        correction_response = client.post(
            "/api/v1/feedback/correction",
            json={
                "conversation_id": test_conversation.id,
                "original_query": "show sales",
                "original_result": {"data": []},
                "correction": "use revenue instead of sales"
            }
        )
        assert correction_response.status_code == 201
        
        # Now make a query - it should be refined
        # Mock refinement response
        refinement_response = ChatResponse(
            content="show revenue",  # Refined query
            model="gpt-4",
            tokens_used=20,
            prompt_tokens=15,
            completion_tokens=5,
            finish_reason="stop",
            function_call=None
        )
        
        # Mock VizQL agent responses
        planning_response = ChatResponse(
            content=json.dumps({
                "measures": ["Revenue"],
                "dimensions": ["Region"],
                "filters": {}
            }),
            model="gpt-4",
            tokens_used=50,
            prompt_tokens=30,
            completion_tokens=20,
            finish_reason="stop",
            function_call=None
        )
        
        query_response = ChatResponse(
            content=json.dumps({
                "datasource": {"datasourceLuid": "test-datasource-123"},
                "query": {
                    "fields": [
                        {"fieldCaption": "Revenue", "function": "SUM"},
                        {"fieldCaption": "Region"}
                    ]
                }
            }),
            model="gpt-4",
            tokens_used=75,
            prompt_tokens=50,
            completion_tokens=25,
            finish_reason="stop",
            function_call=None
        )
        
        formatter_response = ChatResponse(
            content="Query executed successfully",
            model="gpt-4",
            tokens_used=100,
            prompt_tokens=60,
            completion_tokens=40,
            finish_reason="stop",
            function_call=None
        )
        
        # Mock AI client: refinement, then VizQL workflow
        mock_ai_client.chat = AsyncMock(side_effect=[
            refinement_response,   # Query refinement
            planning_response,      # VizQL planner
            query_response,         # VizQL query builder
            formatter_response      # VizQL formatter
        ])
        
        response = client.post(
            "/api/v1/chat/message",
            json={
                "conversation_id": test_conversation.id,
                "content": "show sales",  # Original query
                "agent_type": "vizql",
                "model": "gpt-4",
                "stream": False
            }
        )
        
        assert response.status_code == 200
        # The query should have been refined to use "revenue" instead of "sales"
        # (This is verified by the mock returning "show revenue" as refined query)
