"""
Core authentication functions for WordPress Application Passwords Authorization Flow.

This module provides URL generation, callback parsing, and credential validation
using only Python standard library (no external dependencies).
"""

import base64
import json
import urllib.parse
import urllib.request
from typing import Optional, Any
from .types import AuthConfig, CallbackResult, UserProfile, ValidationResult, AppSession
from .exceptions import ValidationError, NetworkError, AuthenticationError, APIError



def generate_auth_url(wp_root_url: str, app_name: str, callback_url: str) -> str:
    """
    Generate a WordPress authorization URL for the Application Passwords flow.
    
    This function constructs the proper authorization link that redirects users
    to WordPress's native authorization page where they can approve the application
    and generate an application password.
    
    Args:
        wp_root_url: Base URL of the WordPress site (e.g., https://example.com)
        app_name: Name of the application requesting authorization
        callback_url: URL where WordPress should redirect after authorization
        
    Returns:
        Complete authorization URL string
        
    Raises:
        ValidationError: If any required parameter is missing or invalid
        
    Example:
        >>> url = generate_auth_url(
        ...     "https://example.com",
        ...     "My App",
        ...     "https://myapp.com/callback"
        ... )
        >>> print(url)
        https://example.com/wp-admin/authorize-application.php?app_name=My+App&success_url=https%3A%2F%2Fmyapp.com%2Fcallback
    """
    # Validate inputs
    if not wp_root_url or not isinstance(wp_root_url, str):
        raise ValidationError("wp_root_url must be a non-empty string")
    if not app_name or not isinstance(app_name, str):
        raise ValidationError("app_name must be a non-empty string")
    if not callback_url or not isinstance(callback_url, str):
        raise ValidationError("callback_url must be a non-empty string")
    
    # Normalize wp_root_url
    wp_root_url = wp_root_url.rstrip("/")
    if not wp_root_url.startswith(("http://", "https://")):
        wp_root_url = f"https://{wp_root_url}"
    
    # Validate callback_url format
    try:
        parsed_callback = urllib.parse.urlparse(callback_url)
        if not parsed_callback.scheme or not parsed_callback.netloc:
            raise ValidationError("callback_url must be a valid URL with scheme and domain")
    except Exception as e:
        raise ValidationError(f"Invalid callback_url format: {e}")
    
    # Build query parameters
    params = {
        "app_name": app_name,
        "success_url": callback_url,
    }
    
    # Encode parameters
    query_string = urllib.parse.urlencode(params)
    
    # Construct complete URL
    auth_url = f"{wp_root_url}/wp-admin/authorize-application.php?{query_string}"
    
    return auth_url


def parse_callback_url(callback_url: str) -> CallbackResult:
    """
    Parse a WordPress authorization callback URL to extract credentials.
    
    When WordPress redirects to the callback URL after successful authorization,
    it includes the user_login and generated application password in the query
    parameters. This function extracts those credentials.
    
    Args:
        callback_url: The full callback URL received from WordPress redirect
        
   _returns:
        CallbackResult containing extracted credentials or error information
        
    Raises:
        ValidationError: If the callback URL is malformed
        
    Example:
        >>> result = parse_callback_url(
        ...     "https://myapp.com/callback?user_login=john&password=abc123&success_url=https://myapp.com/success"
        ... )
        >>> print(result.user_login)
        john
        >>> print(result.password)
        abc123
    """
    if not callback_url or not isinstance(callback_url, str):
        raise ValidationError("callback_url must be a non-empty string")
    
    result = CallbackResult(raw_url=callback_url)
    
    try:
        parsed = urllib.parse.urlparse(callback_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        
        # Extract user_login & site_url (WordPress returns these as callback query params)
        user_login = query_params.get("user_login", [None])[0]
        password = query_params.get("password", [None])[0]
        success_url = query_params.get("success_url", [None])[0]
        site_url = query_params.get("site_url", [None])[0]
        
        # Validate that we have the required credentials
        if user_login and password:
            result.user_login = user_login
            result.password = password
            result.success_url = success_url
            result.site_url = site_url
            result.is_valid = True
        else:
            result.is_valid = False

            
    except Exception as e:
        raise ValidationError(f"Failed to parse callback URL: {e}")
    
    return result


def validate_credentials(
    user_login: str,
    password: str,
    wp_root_url: str,
    timeout: int = 30
) -> ValidationResult:
    """
    Validate WordPress credentials by making an authenticated request to the WordPress API.
    
    This function performs a secure HTTP Basic Auth request to the WordPress REST API
    endpoint /wp-json/wp/v2/users/me to verify the credentials and fetch user profile.
    
    Args:
        user_login: WordPress username
        password: WordPress application password/token
        wp_root_url: Base URL of the WordPress site
        timeout: HTTP request timeout in seconds (default: 30)
        
    Returns:
        ValidationResult with user profile if successful, error details if failed
        
    Raises:
        ValidationError: If required parameters are invalid
        NetworkError: If network request fails (timeout, connection error)
        AuthenticationError: If credentials are invalid (401/403 response)
        APIError: If WordPress API returns unexpected error
        
    Example:
        >>> result = validate_credentials("john", "abc123", "https://example.com")
        >>> if result.is_valid:
        ...     print(f"Authenticated as {result.user_profile.username}")
        ... else:
        ...     print(f"Authentication failed: {result.error_message}")
    """
    # Validate inputs
    if not user_login or not isinstance(user_login, str):
        raise ValidationError("user_login must be a non-empty string")
    if not password or not isinstance(password, str):
        raise ValidationError("password must be a non-empty string")
    if not wp_root_url or not isinstance(wp_root_url, str):
        raise ValidationError("wp_root_url must be a non-empty string")
    
    # Normalize wp_root_url
    wp_root_url = wp_root_url.rstrip("/")
    if not wp_root_url.startswith(("http://", "https://")):
        wp_root_url = f"https://{wp_root_url}"
    
    # Construct API endpoint URL candidates (context=edit returns username, email & roles)
    candidate_urls = [
        f"{wp_root_url}/?rest_route=/wp/v2/users/me&context=edit",
        f"{wp_root_url}/index.php?rest_route=/wp/v2/users/me&context=edit",
        f"{wp_root_url}/wp-json/wp/v2/users/me?context=edit",
        f"{wp_root_url}/?rest_route=/wp/v2/users/me",
        f"{wp_root_url}/index.php?rest_route=/wp/v2/users/me",
        f"{wp_root_url}/wp-json/wp/v2/users/me"
    ]

    
    # Create Basic Auth header
    credentials = f"{user_login}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    auth_header = f"Basic {encoded_credentials}"
    
    last_exception = None
    for api_url in candidate_urls:
        try:
            request = urllib.request.Request(
                api_url,
                headers={
                    "Authorization": auth_header,
                    "Content-Type": "application/json",
                    "User-Agent": "WPAuthLib/1.0"
                }
            )
            
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status_code = response.getcode()
                
                if status_code == 200:
                    try:
                        response_data = json.loads(response.read().decode("utf-8"))
                        user_profile = UserProfile.from_api_response(response_data)
                        return ValidationResult(
                            is_valid=True,
                            user_profile=user_profile
                        )
                    except json.JSONDecodeError as e:
                        raise APIError(f"Failed to parse WordPress API response: {e}")
                elif status_code in (401, 403):
                    return ValidationResult(
                        is_valid=False,
                        error_message="Invalid credentials",
                        error_code=status_code
                    )
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return ValidationResult(
                    is_valid=False,
                    error_message="Invalid credentials",
                    error_code=e.code
                )
            elif e.code == 404:
                last_exception = e
                continue # Try next candidate URL
            else:
                raise APIError(f"HTTP error from WordPress API: {e.code} - {e.reason}")
        except urllib.error.URLError as e:
            if isinstance(e.reason, TimeoutError):
                raise NetworkError(f"Request timed out after {timeout} seconds")
            else:
                raise NetworkError(f"Network error: {e.reason}")
        except Exception as e:
            raise NetworkError(f"Unexpected error during request: {e}")

    if last_exception:
        raise APIError(f"HTTP error from WordPress API: {last_exception.code} - {last_exception.reason}")
    raise APIError("WordPress REST API user validation route not reachable.")


def get_session(wp_root_url: str, user_login: str, password: str, app_id: str, session_key: str, timeout: int = 30) -> AppSession:
    """Fetch session payload from WordPress plugin belchamber-auth-bridge via REST API."""
    wp_root_url = wp_root_url.rstrip("/")
    query_part = f"app_id={urllib.parse.quote(app_id)}&session_key={urllib.parse.quote(session_key)}"
    candidate_urls = [
        f"{wp_root_url}/?rest_route=/auth-bridge/v1/session&{query_part}",
        f"{wp_root_url}/index.php?rest_route=/auth-bridge/v1/session&{query_part}",
        f"{wp_root_url}/wp-json/auth-bridge/v1/session?{query_part}"
    ]
    
    credentials = f"{user_login}:{password}"
    auth_header = f"Basic {base64.b64encode(credentials.encode('utf-8')).decode('utf-8')}"
    
    last_err = None
    for api_url in candidate_urls:
        req = urllib.request.Request(api_url, headers={
            "Authorization": auth_header,
            "Accept": "application/json",
            "User-Agent": "WPAuthLib/1.0"
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return AppSession(
                    id=data.get("id"),
                    user_id=data.get("user_id"),
                    app_id=data.get("app_id"),
                    session_key=data.get("session_key"),
                    payload=data.get("payload"),
                    created_at=data.get("created_at"),
                    updated_at=data.get("updated_at")
                )
        except urllib.error.HTTPError as e:
            if e.code == 404:
                last_err = e
                continue
            elif e.code in (401, 403):
                raise AuthenticationError("Invalid WordPress authentication credentials")
            raise APIError(f"WordPress API error: {e.code}")
        except Exception as e:
            raise NetworkError(f"Failed to fetch session: {e}")

    if last_err:
        raise APIError("Session entry not found")
    raise APIError("WordPress REST API session route not reachable")


def save_session(wp_root_url: str, user_login: str, password: str, app_id: str, session_key: str, payload: Any, timeout: int = 30) -> dict:
    """Create or update session payload in WordPress plugin belchamber-auth-bridge via REST API."""
    wp_root_url = wp_root_url.rstrip("/")
    candidate_urls = [
        f"{wp_root_url}/?rest_route=/auth-bridge/v1/session",
        f"{wp_root_url}/index.php?rest_route=/auth-bridge/v1/session",
        f"{wp_root_url}/wp-json/auth-bridge/v1/session"
    ]
    
    credentials = f"{user_login}:{password}"
    auth_header = f"Basic {base64.b64encode(credentials.encode('utf-8')).decode('utf-8')}"
    
    body_data = json.dumps({
        "app_id": app_id,
        "session_key": session_key,
        "payload": payload
    }).encode("utf-8")
    
    last_err = None
    for api_url in candidate_urls:
        req = urllib.request.Request(api_url, data=body_data, headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "WPAuthLib/1.0"
        }, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                last_err = e
                continue
            elif e.code in (401, 403):
                raise AuthenticationError("Invalid WordPress authentication credentials")
            raise APIError(f"WordPress API error: {e.code}")
        except Exception as e:
            raise NetworkError(f"Failed to save session: {e}")

    if last_err:
        raise APIError(f"WordPress API error: {last_err.code}")
    raise APIError("WordPress REST API session route not reachable")


def delete_session(wp_root_url: str, user_login: str, password: str, app_id: str, session_key: str, timeout: int = 30) -> dict:
    """Delete session entry from WordPress plugin belchamber-auth-bridge via REST API."""
    wp_root_url = wp_root_url.rstrip("/")
    query_part = f"app_id={urllib.parse.quote(app_id)}&session_key={urllib.parse.quote(session_key)}"
    candidate_urls = [
        f"{wp_root_url}/?rest_route=/auth-bridge/v1/session&{query_part}",
        f"{wp_root_url}/index.php?rest_route=/auth-bridge/v1/session&{query_part}",
        f"{wp_root_url}/wp-json/auth-bridge/v1/session?{query_part}"
    ]
    
    credentials = f"{user_login}:{password}"
    auth_header = f"Basic {base64.b64encode(credentials.encode('utf-8')).decode('utf-8')}"
    
    last_err = None
    for api_url in candidate_urls:
        req = urllib.request.Request(api_url, headers={
            "Authorization": auth_header,
            "Accept": "application/json",
            "User-Agent": "WPAuthLib/1.0"
        }, method="DELETE")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                last_err = e
                continue
            elif e.code in (401, 403):
                raise AuthenticationError("Invalid WordPress authentication credentials")
            raise APIError(f"WordPress API error: {e.code}")
        except Exception as e:
            raise NetworkError(f"Failed to delete session: {e}")

    if last_err:
        raise APIError("Session entry not found or already deleted")
    raise APIError("WordPress REST API session route not reachable")


def health_check(wp_root_url: str, timeout: int = 10) -> dict:
    """Diagnostic health check verifying WordPress site reachability and REST API plugin route status."""
    wp_root_url = wp_root_url.rstrip("/")
    api_url = f"{wp_root_url}/wp-json/"
    
    req = urllib.request.Request(api_url, headers={"User-Agent": "WPAuthLib-HealthCheck/1.0"})
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            namespaces = data.get("namespaces", [])
            plugin_installed = "auth-bridge/v1" in namespaces
            return {
                "reachable": True,
                "wp_name": data.get("name"),
                "namespaces": namespaces,
                "plugin_installed": plugin_installed,
            }
    except Exception as e:
        return {
            "reachable": False,
            "error": str(e),
            "plugin_installed": False,
        }

