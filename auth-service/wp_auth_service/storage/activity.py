"""
Activity Storage module for tracking service events with 14-day persistent storage and auto-expiration.
"""

import json
import os
import time
import uuid
from typing import List, Dict, Any, Optional


class ActivityStorage:
    """
    Manages persistent logging of auth service activities with 14-day automated expiration.
    Follows Object-Oriented Programming principles.
    """

    def __init__(self, storage_file: str, max_age_days: int = 14):
        self.storage_file = storage_file
        self.max_age_days = max_age_days
        self._ensure_storage_exists()

    def _ensure_storage_exists(self) -> None:
        """Ensure storage directory and JSON file exist."""
        dirname = os.path.dirname(self.storage_file)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)
        if not os.path.exists(self.storage_file):
            self._save_logs([])

    def _load_logs(self) -> List[Dict[str, Any]]:
        """Load logs from JSON file safely."""
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_logs(self, logs: List[Dict[str, Any]]) -> None:
        """Save logs to JSON file safely."""
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(logs, f, indent=2)
        except Exception as e:
            print(f"Error saving activity logs: {e}")

    def purge_expired_logs(self) -> int:
        """Purge log entries older than max_age_days (14 days)."""
        cutoff = time.time() - (self.max_age_days * 86400)
        logs = self._load_logs()
        filtered = [l for l in logs if l.get("timestamp", 0) >= cutoff]
        removed_count = len(logs) - len(filtered)
        if removed_count > 0:
            self._save_logs(filtered)
        return removed_count

    def log_activity(
        self,
        action: str,
        status: str,
        endpoint_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: str = "127.0.0.1"
    ) -> Dict[str, Any]:
        """Record a new activity entry and perform 14-day expiration cleanup."""
        self.purge_expired_logs()
        logs = self._load_logs()

        entry = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": int(time.time()),
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "action": action,
            "status": status,
            "endpoint_id": endpoint_id or "default",
            "ip_address": ip_address,
            "details": details or {}
        }

        # Prepend new entry
        logs.insert(0, entry)
        # Cap at max 1000 entries to prevent memory inflation
        if len(logs) > 1000:
            logs = logs[:1000]

        self._save_logs(logs)
        return entry

    def list_activities(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent activity log entries."""
        logs = self._load_logs()
        return logs[:limit]

    def get_activity_detail(self, log_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full activity log details by log ID."""
        logs = self._load_logs()
        for entry in logs:
            if entry.get("id") == log_id:
                return entry
        return None
