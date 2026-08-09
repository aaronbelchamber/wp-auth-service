"""
Configuration management for WordPress Auth Service.

Loads configuration from environment variables and provides defaults.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Attributes:
        wp_root_url: WordPress site URL
        app_name: Application name for authorization
        callback_url: Callback URL for WordPress authorization
        api_key: Default API key for service authentication
        cache_ttl: Cache time-to-live in seconds (default: 300)
        redis_url: Redis connection URL (optional, for distributed caching)
        service_port: Service port (default: 8000)
        service_host: Service host (default: 0.0.0.0)
        cors_origins: Allowed CORS origins (comma-separated)
        log_level: Logging level (default: INFO)
    """
    
    # WordPress Configuration
    wp_root_url: Optional[str] = Field(
        default=None,
        description="WordPress site URL"
    )
    app_name: Optional[str] = Field(
        default=None,
        description="Application name for authorization"
    )
    callback_url: Optional[str] = Field(
        default=None,
        description="Callback URL for WordPress authorization"
    )
    
    # API Authentication
    api_key: Optional[str] = Field(
        default=None,
        description="Default API key for service authentication"
    )
    
    # Cache Configuration
    cache_ttl: int = Field(
        default=300,
        description="Cache time-to-live in seconds"
    )
    redis_url: Optional[str] = Field(
        default=None,
        description="Redis connection URL for distributed caching"
    )
    
    # Service Configuration
    service_port: int = Field(
        default=8000,
        description="Service port"
    )
    service_host: str = Field(
        default="127.0.0.1",
        description="Service host"
    )
    
    # CORS Configuration
    cors_origins: str = Field(
        default="*",
        description="Allowed CORS origins (comma-separated)"
    )
    
    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins string into list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    def is_configured(self) -> bool:
        """Check if WordPress configuration is set."""
        return bool(self.wp_root_url and self.app_name and self.callback_url)


# Global settings instance
settings = Settings()
