"""
API module for WordPress Auth Service.
"""

from .middleware import APIKeyAuthMiddleware
from .routes import router

__all__ = ["APIKeyAuthMiddleware", "router"]
