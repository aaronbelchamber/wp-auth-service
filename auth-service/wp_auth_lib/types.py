"""
Type definitions and dataclasses for WordPress authentication library.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class UserProfile:
    """
    Represents a WordPress user profile returned from the /wp-json/wp/v2/users/me endpoint.
    
    Attributes:
        id: WordPress user ID
        username: WordPress username
        email: User email address
        display_name: Display name for the user
        roles: List of roles assigned to the user
        capabilities: Dictionary of user capabilities
        raw_data: Complete raw response from WordPress API
    """
    id: int
    username: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    roles: List[str] = field(default_factory=list)
    capabilities: Dict[str, bool] = field(default_factory=dict)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "UserProfile":
        """
        Create a UserProfile from WordPress API response data.
        
        Args:
            data: Raw JSON response from /wp-json/wp/v2/users/me
            
        Returns:
            UserProfile instance
        """
        username = data.get("username") or data.get("slug") or data.get("name", "")
        email = data.get("email") or data.get("user_email")
        roles = data.get("roles") or []
        caps = data.get("capabilities", {})
        if not roles and caps:
            roles = [r for r, enabled in caps.items() if enabled and isinstance(enabled, bool)]

        return cls(
            id=data.get("id", 0),
            username=username,
            email=email,
            display_name=data.get("name"),
            roles=roles,
            capabilities=caps,
            raw_data=data,
        )



@dataclass
class AuthConfig:
    """
    Configuration for WordPress authentication.
    
    Attributes:
        wp_root_url: Base URL of the WordPress site (e.g., https://example.com)
        app_name: Name of the application requesting authorization
        callback_url: URL where WordPress should redirect after authorization
        timeout: HTTP request timeout in seconds (default: 30)
    """
    wp_root_url: str
    app_name: str
    callback_url: str
    timeout: int = 30
    
    def __post_init__(self):
        """Normalize the WordPress root URL."""
        # Remove trailing slash
        self.wp_root_url = self.wp_root_url.rstrip("/")
        
        # Ensure protocol is present
        if not self.wp_root_url.startswith(("http://", "https://")):
            self.wp_root_url = f"https://{self.wp_root_url}"


@dataclass
class CallbackResult:
    """
    Result of parsing a WordPress authorization callback URL.
    
    Attributes:
        user_login: WordPress username from callback
        password: Generated application password/token from callback
        success_url: The success URL from the callback
        raw_url: The complete callback URL received
        is_valid: Whether the callback was successfully parsed
    """
    user_login: Optional[str] = None
    password: Optional[str] = None
    success_url: Optional[str] = None
    site_url: Optional[str] = None
    raw_url: Optional[str] = None
    is_valid: bool = False

    
    @property
    def has_credentials(self) -> bool:
        """Check if both user_login and password are present."""
        return bool(self.user_login and self.password)


@dataclass
class ValidationResult:
    """
    Result of validating WordPress credentials.
    
    Attributes:
        is_valid: Whether the credentials are valid
        user_profile: UserProfile if validation succeeded, None otherwise
        error_message: Error message if validation failed, None otherwise
        error_code: HTTP status code if validation failed, None otherwise
        validated_at: Timestamp when validation was performed
    """
    is_valid: bool
    user_profile: Optional[UserProfile] = None
    error_message: Optional[str] = None
    error_code: Optional[int] = None
    validated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AppSession:
    """
    Represents an application session entry stored in the WordPress DB.
    
    Attributes:
        app_id: Application identifier
        session_key: Session or state lookup key
        payload: JSON payload dictionary or string
        id: DB row ID
        user_id: WordPress user ID owner
        created_at: UNIX timestamp when entry was created
        updated_at: UNIX timestamp when entry was last updated
    """
    app_id: str
    session_key: str
    payload: Any
    id: Optional[int] = None
    user_id: Optional[int] = None
    created_at: Optional[int] = None
    updated_at: Optional[int] = None

