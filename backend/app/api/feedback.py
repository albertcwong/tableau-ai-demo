"""Feedback API endpoints for user corrections and preferences."""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.agents.feedback import FeedbackManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


class CorrectionRequest(BaseModel):
    """Request model for recording a correction."""
    conversation_id: int = Field(..., description="Conversation ID")
    original_query: str = Field(..., description="Original user query")
    original_result: dict = Field(..., description="Original agent result")
    correction: str = Field(..., description="User's correction or feedback")
    corrected_result: Optional[dict] = Field(None, description="Corrected result (optional)")


class CorrectionResponse(BaseModel):
    """Response model for correction recording."""
    feedback_id: int
    learning: dict
    recorded_at: str


class PreferenceRequest(BaseModel):
    """Request model for recording preferences."""
    conversation_id: int = Field(..., description="Conversation ID")
    preferences: dict = Field(..., description="User preferences dictionary")


class PreferenceResponse(BaseModel):
    """Response model for preference recording."""
    preferences_id: int
    preferences: dict
    recorded_at: str


@router.post("/correction", response_model=CorrectionResponse, status_code=status.HTTP_201_CREATED)
async def record_correction(
    request: CorrectionRequest,
    db: Session = Depends(get_db),
    authorization: Optional[str] = None
):
    """Record a user correction to improve future queries.
    
    This endpoint allows users to provide feedback when an agent's output
    doesn't match their expectations. The system learns from these corrections
    to improve future responses.
    """
    # Get API key from authorization header if provided
    api_key = None
    if authorization:
        # Extract API key from "Bearer <key>" format
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            api_key = parts[1]
    
    feedback_manager = FeedbackManager(db=db, api_key=api_key)
    
    try:
        result = await feedback_manager.record_correction(
            conversation_id=request.conversation_id,
            original_query=request.original_query,
            original_result=request.original_result,
            correction=request.correction,
            corrected_result=request.corrected_result
        )
        
        return CorrectionResponse(
            feedback_id=result["feedback_id"],
            learning=result["learning"],
            recorded_at=result["recorded_at"]
        )
    except Exception as e:
        logger.error(f"Error recording correction: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record correction: {str(e)}"
        )


@router.post("/preferences", response_model=PreferenceResponse, status_code=status.HTTP_201_CREATED)
async def record_preferences(
    request: PreferenceRequest,
    db: Session = Depends(get_db),
    authorization: Optional[str] = None
):
    """Record user preferences for future query refinement.
    
    Preferences can include:
    - Preferred detail level (brief, detailed, comprehensive)
    - Preferred format (table, list, narrative)
    - Preferred metrics or fields
    - Any other user-specific preferences
    """
    # Get API key from authorization header if provided
    api_key = None
    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            api_key = parts[1]
    
    feedback_manager = FeedbackManager(db=db, api_key=api_key)
    
    try:
        result = await feedback_manager.learn_preferences(
            conversation_id=request.conversation_id,
            user_preferences=request.preferences
        )
        
        return PreferenceResponse(
            preferences_id=result["preferences_id"],
            preferences=result["preferences"],
            recorded_at=result["recorded_at"]
        )
    except Exception as e:
        logger.error(f"Error recording preferences: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record preferences: {str(e)}"
        )
