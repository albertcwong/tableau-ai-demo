"""Debug API endpoints for viewing graph execution."""
from fastapi import APIRouter, Query
from typing import Optional
from app.services.debug import get_debugger

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/executions")
async def get_executions(
    limit: int = Query(10, ge=1, le=100),
    agent_type: Optional[str] = Query(None)
):
    """Get recent graph executions for debugging."""
    debugger = get_debugger()
    executions = debugger.get_recent_executions(limit=limit, agent_type=agent_type)
    return {
        "executions": executions,
        "count": len(executions)
    }


@router.get("/executions/{execution_id}")
async def get_execution(execution_id: str):
    """Get a specific execution record."""
    debugger = get_debugger()
    execution = debugger.get_execution(execution_id)
    
    if not execution:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return execution


@router.post("/executions/clear")
async def clear_executions():
    """Clear all execution records."""
    debugger = get_debugger()
    debugger.clear()
    return {"message": "Execution records cleared"}
