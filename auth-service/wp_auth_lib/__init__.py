"""
WordPress Authentication Library

A standalone, framework-free authentication module for WordPress Application Passwords
Authorization Flow. This library provides URL generation, callback parsing, and credential
validation without external dependencies.
"""

from .auth import (
    generate_auth_url,
    parse_callback_url,
    validate_credentials,
    get_session,
    save_session,
    delete_session,
    health_check,
)
from .types import UserProfile, AuthConfig, CallbackResult, AppSession, ValidationResult
from .exceptions import (
    AuthError,
    NetworkError,
    ValidationError,
    AuthenticationError,
    ConfigurationError,
    WPConnectionError,
    WPAuthError,
    WPApiError,
    WPDataError,
)

__version__ = "1.0.0"
__all__ = [
    "generate_auth_url",
    "parse_callback_url",
    "validate_credentials",
    "get_session",
    "save_session",
    "delete_session",
    "health_check",
    "UserProfile",
    "AuthConfig",
    "CallbackResult",
    "AppSession",
    "ValidationResult",
    "AuthError",
    "NetworkError",
    "ValidationError",
    "AuthenticationError",
    "ConfigurationError",
    "WPConnectionError",
    "WPAuthError",
    "WPApiError",
    "WPDataError",
]

