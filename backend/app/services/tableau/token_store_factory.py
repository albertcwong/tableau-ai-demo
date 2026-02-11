"""Factory for getting the appropriate token store based on auth type."""
from app.models.tableau_auth import TableauAuthType
from app.services.tableau.pat_token_store import pat_token_store
from app.services.tableau.memory_token_store import memory_token_store
from app.services.tableau.token_store import TableauTokenStore


def get_token_store(auth_type: str) -> TableauTokenStore:
    """Get the appropriate token store for the given auth type.
    
    Args:
        auth_type: Authentication type (e.g., "pat", "connected_app")
        
    Returns:
        Token store instance
    """
    auth_type_lower = auth_type.lower()
    
    if auth_type_lower == TableauAuthType.PAT.value:
        return pat_token_store
    else:
        # Connected App, Standard, Connected App OAuth all use in-memory cache
        return memory_token_store
