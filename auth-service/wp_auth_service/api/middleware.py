"""
API key authentication middleware for FastAPI.
"""

from fastapi import HTTPException, Request, status
from fastapi.security import APIKeyHeader
from typing import Optional
from ..storage import APIKeyStorage


class APIKeyAuthMiddleware:
    """
    Middleware for API key authentication using X-API-Key header.
    """
    
    def __init__(self, storage: APIKeyStorage, auto_error: bool = True):
        """
        Initialize API key authentication middleware.
        
        Args:
            storage: API key storage instance
            auto_error: Whether to automatically raise HTTP errors (default: True)
        """
        self.storage = storage
        self.auto_error = auto_error
        self.api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
    
    async def __call__(self, request: Request) -> Optional[str]:
        """
        Validate API key from request header.
        
        Args:
            request: FastAPI request object
            
        Returns:
            API key if valid
            
        Raises:
            HTTPException: If API key is missing or invalid
        """
        api_key = await self.api_key_header(request)
        
        if not api_key:
            if self.storage.validate_key(""):
                return None
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key missing. Provide X-API-Key header.",
                )
            return None
        
        if not self.storage.validate_key(api_key):
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid API key.",
                )
            return None
        
        return api_key

