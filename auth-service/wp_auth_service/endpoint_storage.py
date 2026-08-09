"""
Endpoint profile storage for WordPress Auth Service.

Provides storage and management for multiple WordPress endpoint configurations.
"""

import json
import uuid
from typing import Optional, Dict, List, Any
from pathlib import Path
from datetime import datetime, timezone


class EndpointStorage:
    """
    Storage interface for WordPress endpoint profiles.
    
    Manages multiple WordPress endpoint configurations with support for
    cloning, active selection, reachability status, and file persistence.
    """
    
    def __init__(self, storage_file: Optional[str] = None):
        """
        Initialize endpoint storage.
        
        Args:
            storage_file: Optional path to JSON storage file for persistence.
        """
        self._profiles: Dict[str, Dict[str, Any]] = {}
        self.storage_file = storage_file
        
        if storage_file:
            self._load_from_file()
            
    def _load_from_file(self) -> None:
        """Load endpoint profiles from storage file if available."""
        if not self.storage_file:
            return
        try:
            file_path = Path(self.storage_file)
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    self._profiles = json.load(f)
        except Exception:
            self._profiles = {}

    def _save_to_file(self) -> None:
        """Persist endpoint profiles to storage file."""
        if not self.storage_file:
            return
        try:
            file_path = Path(self.storage_file)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self._profiles, f, indent=2)
        except Exception:
            pass

    def list_profiles(self) -> List[Dict[str, Any]]:
        """
        Return a list of all endpoint profiles.
        
        Returns:
            List of profile dictionaries.
        """
        return list(self._profiles.values())

    def get_profile(self, endpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific endpoint profile by ID.
        
        Args:
            endpoint_id: ID of the endpoint profile.
            
        Returns:
            Profile dict if found, None otherwise.
        """
        return self._profiles.get(endpoint_id)

    def create_profile(
        self,
        name: str,
        wp_root_url: str,
        app_name: str,
        callback_url: str,
        is_active: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new endpoint profile.
        
        Args:
            name: Descriptive profile name.
            wp_root_url: WordPress site URL.
            app_name: Application name.
            callback_url: Redirect callback URL.
            is_active: Whether this profile should be active.
            
        Returns:
            The created profile dictionary.
        """
        endpoint_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # If this is the first profile, automatically mark it as active
        if not self._profiles:
            is_active = True
        elif is_active:
            self._clear_active_flags()

        profile = {
            "id": endpoint_id,
            "name": name,
            "wp_root_url": wp_root_url,
            "app_name": app_name,
            "callback_url": callback_url,
            "status": "unconfirmed",
            "is_active": is_active,
            "created_at": now,
            "updated_at": now,
        }
        self._profiles[endpoint_id] = profile
        self._save_to_file()
        return profile

    def update_profile(
        self,
        endpoint_id: str,
        name: Optional[str] = None,
        wp_root_url: Optional[str] = None,
        app_name: Optional[str] = None,
        callback_url: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update an existing endpoint profile.
        
        Args:
            endpoint_id: Profile ID to update.
            name: Optional new name.
            wp_root_url: Optional new WordPress URL.
            app_name: Optional new application name.
            callback_url: Optional new callback URL.
            status: Optional status string ("confirmed" / "unconfirmed").
            
        Returns:
            Updated profile dict if found, None otherwise.
        """
        profile = self._profiles.get(endpoint_id)
        if not profile:
            return None

        if name is not None:
            profile["name"] = name
        if wp_root_url is not None:
            profile["wp_root_url"] = wp_root_url
        if app_name is not None:
            profile["app_name"] = app_name
        if callback_url is not None:
            profile["callback_url"] = callback_url
        if status is not None:
            profile["status"] = status
            
        profile["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_to_file()
        return profile

    def clone_profile(self, endpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Clone an existing endpoint profile.
        
        Args:
            endpoint_id: Profile ID to clone.
            
        Returns:
            New cloned profile dict if original exists, None otherwise.
        """
        source = self._profiles.get(endpoint_id)
        if not source:
            return None

        new_name = f"Copy of {source['name']}"
        return self.create_profile(
            name=new_name,
            wp_root_url=source["wp_root_url"],
            app_name=source["app_name"],
            callback_url=source["callback_url"],
            is_active=False
        )

    def delete_profile(self, endpoint_id: str) -> bool:
        """
        Delete an endpoint profile by ID.
        
        Args:
            endpoint_id: Profile ID to delete.
            
        Returns:
            True if deleted, False if not found.
        """
        if endpoint_id not in self._profiles:
            return False
            
        was_active = self._profiles[endpoint_id].get("is_active", False)
        del self._profiles[endpoint_id]
        
        # If deleted active profile, mark the first available profile active
        if was_active and self._profiles:
            first_id = next(iter(self._profiles))
            self._profiles[first_id]["is_active"] = True
            
        self._save_to_file()
        return True

    def set_active(self, endpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Set a profile as the active endpoint.
        
        Args:
            endpoint_id: Profile ID to set active.
            
        Returns:
            Target profile dict if found, None otherwise.
        """
        if endpoint_id not in self._profiles:
            return None
            
        self._clear_active_flags()
        self._profiles[endpoint_id]["is_active"] = True
        self._profiles[endpoint_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_to_file()
        return self._profiles[endpoint_id]

    def get_active(self) -> Optional[Dict[str, Any]]:
        """
        Get the currently active endpoint profile.
        
        Returns:
            Active profile dict if set, or first profile if available, else None.
        """
        for profile in self._profiles.values():
            if profile.get("is_active"):
                return profile
        if self._profiles:
            first = next(iter(self._profiles.values()))
            first["is_active"] = True
            self._save_to_file()
            return first
        return None

    def _clear_active_flags(self) -> None:
        """Helper to set is_active=False for all stored profiles."""
        for profile in self._profiles.values():
            profile["is_active"] = False
