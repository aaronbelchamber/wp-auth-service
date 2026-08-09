"""
Dependency container and state storage classes for WordPress Auth Service.
"""

import threading
from typing import Optional, Dict, Any, List
from wp_auth_lib.cache import Cache
from .storage import APIKeyStorage
from .endpoint_storage import EndpointStorage
from .activity_storage import ActivityStorage
from .api.middleware import APIKeyAuthMiddleware


class CredentialStore:
    """
    Thread-safe container for captured OAuth callback credentials.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {}

    def set_credentials(self, user_login: str, password: str, site_url: Optional[str] = None) -> None:
        """Store captured credentials atomically."""
        with self._lock:
            self._data = {
                "user_login": user_login,
                "password": password,
                "site_url": site_url,
                "status": "captured"
            }

    def get_credentials(self) -> Dict[str, Any]:
        """Retrieve stored captured credentials atomically."""
        with self._lock:
            return dict(self._data)

    def clear(self) -> None:
        """Clear captured credentials."""
        with self._lock:
            self._data.clear()


class ActivityLogger:
    """
    Object-oriented logger wrapper for persistent activity logging.
    """

    def __init__(self, activity_storage: Optional[ActivityStorage] = None) -> None:
        self.activity_storage = activity_storage

    def log(self, action: str, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log activity safely with guard check."""
        if self.activity_storage:
            try:
                self.activity_storage.log_activity(action=action, status=status, details=details)
            except Exception:
                pass


class ServiceContainer:
    """
    Central dependency container for FastAPI request context.
    """

    def __init__(
        self,
        cache: Cache,
        api_key_storage: APIKeyStorage,
        api_key_middleware: APIKeyAuthMiddleware,
        endpoint_storage: EndpointStorage,
        activity_storage: ActivityStorage,
    ) -> None:
        self.cache = cache
        self.api_key_storage = api_key_storage
        self.api_key_middleware = api_key_middleware
        self.endpoint_storage = endpoint_storage
        self.activity_storage = activity_storage
        self.logger = ActivityLogger(activity_storage)
        self.credential_store = CredentialStore()
