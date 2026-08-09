"""
Custom exception classes for WordPress authentication library.
"""


class AuthError(Exception):
    """Base exception for all authentication-related errors."""
    pass


class NetworkError(AuthError):
    """
    Exception raised when network-related errors occur.
    
    This includes timeouts, connection failures, and DNS resolution issues.
    """
    pass


class ValidationError(AuthError):
    """
    Exception raised when input validation fails.
    
    This includes malformed URLs, missing required parameters, and invalid data formats.
    """
    pass


class AuthenticationError(AuthError):
    """
    Exception raised when WordPress authentication fails.
    
    This includes invalid credentials, 401/403 responses, and authentication token issues.
    """
    pass


class ConfigurationError(AuthError):
    """
    Exception raised when configuration is invalid or missing.
    
    This includes missing environment variables, invalid configuration files, and
    improperly configured WordPress site settings.
    """
    pass


class APIError(AuthError):
    """
    Exception raised when WordPress API returns unexpected responses.
    
    This includes non-200 responses that aren't authentication failures, malformed JSON,
    and API rate limiting issues.
    """
    pass


class CacheError(AuthError):
    """
    Exception raised when cache operations fail.
    
    This includes cache connection failures, serialization errors, and cache miss handling.
    """
    pass


class WPConnectionError(NetworkError):
    """Exception raised when network connection to WordPress site fails or times out."""
    pass


class WPAuthError(AuthenticationError):
    """Exception raised when WordPress authentication credentials or app password fail."""
    pass


class WPApiError(APIError):
    """Exception raised when WordPress REST API route or plugin is missing/unreachable."""
    pass


class WPDataError(ValidationError):
    """Exception raised when session database query fails or payload is malformed."""
    pass

