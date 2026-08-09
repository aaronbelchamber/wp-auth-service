"""
API key storage interface for WordPress Auth Service.

Provides in-memory storage with optional file persistence for API keys.
"""

import json
import secrets
from typing import Optional, Dict, List
from pathlib import Path
from datetime import datetime, timezone


class APIKeyStorage:
    """
    Storage interface for API keys.
    
    Provides in-memory storage with optional file persistence for
    API keys used to authenticate service requests.
    """
    
    def __init__(self, storage_file: Optional[str] = None):
        """
        Initialize API key storage.
        
        Args:
            storage_file: Optional file path to persist API keys. If None, uses in-memory only.
        """
        self._keys: Dict[str, Dict[str, any]] = {}
        self.storage_file = storage_file
        
        if storage_file:
            self._load_from_file()
    
    def _load_from_file(self) -> None:
        """Load API keys from storage file if it exists."""
        if not self.storage_file:
            return
        
        try:
            file_path = Path(self.storage_file)
            if file_path.exists():
                with open(file_path, 'r') as f:
                    self._keys = json.load(f)
        except Exception:
            # If file is corrupted or unreadable, start fresh
            self._keys = {}
    
    def _save_to_file(self) -> None:
        """Save API keys to storage file."""
        if not self.storage_file:
            return
        
        try:
            file_path = Path(self.storage_file)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w') as f:
                json.dump(self._keys, f, indent=2)
        except Exception:
            # Silently fail on save to avoid breaking the service
            pass
    
    def generate_key(self, name: str = "default") -> str:
        """
        Generate a new API key.
        
        Args:
            name: Descriptive name for the API key
            
        Returns:
            Generated API key string
        """
        self.prune_expired_keys()
        api_key = secrets.token_urlsafe(32)
        
        self._keys[api_key] = {
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_used": None,
        }
        
        self._save_to_file()
        return api_key
    
    def validate_key(self, api_key: str) -> bool:
        """
        Validate an API key.

        Args:
            api_key: API key to validate

        Returns:
            True if key is valid, False otherwise.
            Returns True for an empty key only when no keys are stored (bootstrap mode).
        """
        # Bootstrap: no keys configured yet, allow empty-key access
        if not api_key:
            return not self._keys

        # Check against stored keys
        if api_key not in self._keys:
            # Fall back to env-configured key if present
            from .config import settings
            if settings.api_key and api_key == settings.api_key:
                return True
            return False

        # Update last-used timestamp
        self._keys[api_key]["last_used"] = datetime.now(timezone.utc).isoformat()
        self._save_to_file()
        return True

    
    def revoke_key(self, api_key: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            api_key: API key to revoke
            
        Returns:
            True if key was revoked, False if key didn't exist
        """
        if api_key not in self._keys:
            return False
        
        del self._keys[api_key]
        self._save_to_file()
        return True
    
    def prune_expired_keys(self, max_age_days: int = 30) -> int:
        """
        Delete API keys older than max_age_days.

        Args:
            max_age_days: Maximum key age in days before deletion (default 30).

        Returns:
            Number of keys pruned.
        """
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_days * 86400)
        to_delete = []
        for key, data in self._keys.items():
            created_raw = data.get("created_at")
            if not created_raw:
                continue
            try:
                # Handle both offset-aware and naive ISO strings
                if created_raw.endswith("Z"):
                    created_raw = created_raw[:-1] + "+00:00"
                created_dt = datetime.fromisoformat(created_raw)
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                if created_dt.timestamp() < cutoff:
                    to_delete.append(key)
            except (ValueError, OSError):
                continue

        for key in to_delete:
            del self._keys[key]

        if to_delete:
            self._save_to_file()

        return len(to_delete)

    def list_keys(self) -> List[Dict[str, any]]:
        """
        List all API keys (without exposing the actual keys).
        Automatically prunes expired keys before listing.

        Returns:
            List of key metadata
        """
        self.prune_expired_keys()
        return [
            {
                "name": key_data["name"],
                "created_at": key_data["created_at"],
                "last_used": key_data["last_used"],
                "key_preview": f"{api_key[:8]}...{api_key[-4:]}",
            }
            for api_key, key_data in self._keys.items()
        ]
    
    def get_key_count(self) -> int:
        """
        Get the number of stored API keys.
        
        Returns:
            Number of API keys
        """
        return len(self._keys)
    
    def clear_all(self) -> None:
        """Clear all API keys."""
        self._keys.clear()
        self._save_to_file()
