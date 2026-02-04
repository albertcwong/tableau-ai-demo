"""Base translator interface."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional, AsyncIterator
from app.services.gateway.router import ProviderContext


class BaseTranslator(ABC):
    """Base class for request/response translators."""
    
    @abstractmethod
    def transform_request(
        self,
        request: Dict[str, Any],
        context: Optional[ProviderContext] = None
    ) -> Tuple[str, Dict[str, Any], Dict[str, str]]:
        """
        Transform OpenAI-compatible request to provider-specific format.
        
        Args:
            request: OpenAI-compatible request dict
            context: Provider context (optional)
            
        Returns:
            Tuple of (url, payload, headers)
        """
        pass
    
    @abstractmethod
    def normalize_response(
        self,
        response: Dict[str, Any],
        context: Optional[ProviderContext] = None
    ) -> Dict[str, Any]:
        """
        Normalize provider-specific response to OpenAI format.
        
        Args:
            response: Provider-specific response dict
            context: Provider context (optional)
            
        Returns:
            OpenAI-compatible response dict
        """
        pass
    
    def normalize_stream_chunk(
        self,
        chunk: Dict[str, Any],
        context: Optional[ProviderContext] = None
    ) -> Dict[str, Any]:
        """
        Normalize a streaming chunk to OpenAI format.
        
        Args:
            chunk: Provider-specific streaming chunk
            context: Provider context (optional)
            
        Returns:
            OpenAI-compatible streaming chunk
        """
        # Default implementation: try to normalize as regular response
        return self.normalize_response(chunk, context)
