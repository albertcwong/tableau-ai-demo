"""User feedback and learning system for agents."""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.chat import Message, MessageRole
from app.services.ai.client import UnifiedAIClient
from app.core.config import settings

logger = logging.getLogger(__name__)


class FeedbackManager:
    """Manages user feedback and learning for agents."""
    
    def __init__(self, db: Session, model: str = "gpt-4", provider: str = "openai"):
        """Initialize feedback manager.
        
        Args:
            db: Database session
            model: Model to use for learning
            provider: Provider name (e.g., "openai", "apple", "vertex")
        """
        self.db = db
        self.model = model
        self.provider = provider
        self.ai_client = UnifiedAIClient(
            gateway_url=settings.BACKEND_API_URL
        )
    
    async def record_correction(
        self,
        conversation_id: int,
        original_query: str,
        original_result: Dict[str, Any],
        correction: str,
        corrected_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Record a user correction to a query or result.
        
        Args:
            conversation_id: Conversation ID
            original_query: Original user query
            original_result: Original agent result
            correction: User's correction/feedback
            corrected_result: Corrected result (if provided)
            
        Returns:
            Recorded feedback information
        """
        # Save correction as a message
        correction_message = Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=f"[CORRECTION] {correction}",
            model_used=self.model,
            extra_metadata={
                "type": "correction",
                "original_query": original_query,
                "original_result": str(original_result)[:500],
                "corrected_result": str(corrected_result)[:500] if corrected_result else None
            }
        )
        self.db.add(correction_message)
        safe_commit(self.db)
        
        # Extract learning from correction
        learning = await self._extract_learning(
            original_query=original_query,
            original_result=original_result,
            correction=correction
        )
        
        return {
            "feedback_id": correction_message.id,
            "learning": learning,
            "recorded_at": correction_message.created_at.isoformat()
        }
    
    async def apply_feedback_to_query(
        self,
        query: str,
        conversation_id: int,
        agent_type: str
    ) -> Dict[str, Any]:
        """Apply learned feedback to refine a query.
        
        Args:
            query: New query to refine
            conversation_id: Conversation ID
            agent_type: Type of agent
            
        Returns:
            Refined query with feedback applied
        """
        # Get feedback history for this conversation
        feedback_history = self._get_feedback_history(conversation_id, agent_type)
        
        if not feedback_history:
            return {"refined_query": query, "changes": []}
        
        # Use AI to apply feedback
        refinement_prompt = self._build_refinement_prompt(
            query=query,
            feedback_history=feedback_history,
            agent_type=agent_type
        )
        
        response = await self.ai_client.chat(
            model=self.model,
            provider=self.provider,
            messages=[
                {"role": "system", "content": self._get_refinement_system_prompt(agent_type)},
                {"role": "user", "content": refinement_prompt}
            ]
        )
        
        refined_query = self._parse_refined_query(response.content, query)
        
        return {
            "refined_query": refined_query,
            "changes": self._identify_changes(query, refined_query),
            "feedback_applied": len(feedback_history)
        }
    
    async def learn_preferences(
        self,
        conversation_id: int,
        user_preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Learn from user preferences.
        
        Args:
            conversation_id: Conversation ID
            user_preferences: Dictionary of user preferences
            
        Returns:
            Learned preferences summary
        """
        # Save preferences as metadata
        preference_message = Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=f"[PREFERENCES] {str(user_preferences)}",
            model_used=self.model,
            extra_metadata={
                "type": "preferences",
                "preferences": user_preferences
            }
        )
        self.db.add(preference_message)
        safe_commit(self.db)
        
        return {
            "preferences_id": preference_message.id,
            "preferences": user_preferences,
            "recorded_at": preference_message.created_at.isoformat()
        }
    
    def _get_feedback_history(
        self,
        conversation_id: int,
        agent_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get feedback history for conversation."""
        # Query messages with non-null extra_metadata
        # Filter in Python for JSON key existence (more reliable across databases)
        query = self.db.query(Message).filter_by(
            conversation_id=conversation_id
        ).filter(
            Message.extra_metadata.isnot(None)
        )
        
        messages = query.order_by(Message.created_at.desc()).limit(50).all()  # Get more, filter in Python
        
        # Filter messages that have "type" key in extra_metadata
        feedback_messages = []
        for msg in messages:
            metadata = msg.extra_metadata
            if isinstance(metadata, dict) and "type" in metadata:
                msg_type = metadata.get("type")
                # Filter by agent_type if specified
                if agent_type is None or msg_type in ["correction", "preferences"]:
                    feedback_messages.append(msg)
        
        # Process feedback messages
        feedback = []
        for msg in feedback_messages[:10]:  # Limit to 10 most recent
            metadata = msg.extra_metadata or {}
            if metadata.get("type") == "correction":
                feedback.append({
                    "type": "correction",
                    "original_query": metadata.get("original_query"),
                    "correction": msg.content.replace("[CORRECTION] ", ""),
                    "timestamp": msg.created_at.isoformat()
                })
            elif metadata.get("type") == "preferences":
                feedback.append({
                    "type": "preferences",
                    "preferences": metadata.get("preferences", {}),
                    "timestamp": msg.created_at.isoformat()
                })
        
        return feedback
    
    async def _extract_learning(
        self,
        original_query: str,
        original_result: Dict[str, Any],
        correction: str
    ) -> Dict[str, Any]:
        """Extract learning from correction."""
        learning_prompt = f"""Extract learning from this user correction.

Original Query: {original_query}
Original Result: {str(original_result)[:500]}
User Correction: {correction}

Identify:
1. What was wrong with the original result?
2. What should be done differently next time?
3. Any patterns or preferences revealed?

Return structured learning points."""

        response = await self.ai_client.chat(
            model=self.model,
            provider=self.provider,
            messages=[
                {"role": "system", "content": "You extract learning points from user corrections."},
                {"role": "user", "content": learning_prompt}
            ]
        )
        
        return {
            "learning_points": response.content,
            "extracted_at": datetime.utcnow().isoformat()
        }
    
    def _build_refinement_prompt(
        self,
        query: str,
        feedback_history: List[Dict[str, Any]],
        agent_type: str
    ) -> str:
        """Build prompt for query refinement."""
        prompt = f"""Refine this query based on user feedback history.

New Query: {query}
Agent Type: {agent_type}

Feedback History:
"""
        for i, feedback in enumerate(feedback_history, 1):
            if feedback["type"] == "correction":
                prompt += f"\n{i}. Correction: {feedback.get('correction')}"
                prompt += f"\n   Original Query: {feedback.get('original_query')}"
            elif feedback["type"] == "preferences":
                prompt += f"\n{i}. Preferences: {feedback.get('preferences')}"
        
        prompt += "\n\nRefine the query to incorporate lessons from feedback history."
        
        return prompt
    
    def _get_refinement_system_prompt(self, agent_type: str) -> str:
        """Get system prompt for refinement."""
        agent_specific = {
            "vizql": "Focus on query structure, field names, and aggregations based on feedback.",
            "summary": "Focus on summary style, detail level, and insight selection based on feedback.",
            "general": "Focus on answer style, detail level, and format based on feedback."
        }
        
        base = "You refine queries based on user feedback to better match their preferences."
        specific = agent_specific.get(agent_type, "")
        
        return f"{base}\n{specific}"
    
    def _parse_refined_query(self, response: str, original_query: str) -> str:
        """Parse refined query from response."""
        # Try to extract query from response
        lines = response.split("\n")
        for line in lines:
            if "query:" in line.lower() or "refined:" in line.lower():
                refined = line.split(":", 1)[-1].strip()
                if refined:
                    return refined
        
        # If no structured format, use response as-is (may contain explanation)
        # Try to extract just the query part
        if original_query.lower() in response.lower():
            # Response might contain explanation + query
            # Return original if we can't parse
            return original_query
        
        return response.strip() if response.strip() else original_query
    
    def _identify_changes(self, original: str, refined: str) -> List[str]:
        """Identify changes between original and refined query."""
        changes = []
        
        # Simple comparison
        if original.lower() != refined.lower():
            changes.append("Query modified based on feedback")
        
        # Could add more sophisticated diff analysis here
        
        return changes
