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
    Manages persistent logging of auth service activities with 14-day automated expiration,
    test event categorization, and activity log purging.
    Follows Object-Oriented Programming (OOP) principles.
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

    def is_entry_a_test(self, entry: Dict[str, Any]) -> bool:
        """Check if an activity entry represents a test or diagnostic probe."""
        if not isinstance(entry, dict):
            return False
        if entry.get("is_test") is True:
            return True
        action = str(entry.get("action", "")).lower()
        details = entry.get("details") or {}
        if isinstance(details, dict):
            if details.get("is_test") is True:
                return True
            session_key = str(details.get("session_key", ""))
            if session_key.startswith("onboarding_test"):
                return True
            app_name = str(details.get("app_name", "")).lower()
            if "test" in app_name:
                return True
        if any(k in action for k in ["plugin_check", "probe", "onboard_test"]):
            return True
        return False

    def log_activity(
        self,
        action: str,
        status: str,
        endpoint_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: str = "127.0.0.1",
        is_test: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Record a new activity entry and perform 14-day expiration cleanup."""
        self.purge_expired_logs()
        logs = self._load_logs()

        details = details or {}
        entry_draft = {
            "action": action,
            "details": details,
            "is_test": is_test
        }
        if is_test is None:
            is_test = self.is_entry_a_test(entry_draft)

        entry = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": int(time.time()),
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "action": action,
            "status": status,
            "endpoint_id": endpoint_id or "default",
            "ip_address": ip_address,
            "is_test": is_test,
            "details": details
        }

        logs.insert(0, entry)
        if len(logs) > 1000:
            logs = logs[:1000]

        self._save_logs(logs)
        return entry

    def list_activities(self, limit: int = 50, filter_type: str = "all") -> List[Dict[str, Any]]:
        """Return recent activity log entries with filtering options ('all', 'real_only', 'tests_only')."""
        logs = self._load_logs()
        annotated = []
        for l in logs:
            l_copy = dict(l)
            l_copy["is_test"] = self.is_entry_a_test(l)
            annotated.append(l_copy)

        if filter_type == "real_only":
            annotated = [l for l in annotated if not l.get("is_test")]
        elif filter_type == "tests_only":
            annotated = [l for l in annotated if l.get("is_test")]
        return annotated[:limit]

    def clear_activities(self, test_only: bool = False) -> int:
        """Clear activity log entries (either test logs only or all logs)."""
        logs = self._load_logs()
        if test_only:
            remaining = [l for l in logs if not self.is_entry_a_test(l)]
        else:
            remaining = []
        deleted_count = len(logs) - len(remaining)
        self._save_logs(remaining)
        return deleted_count

    def get_activity_detail(self, log_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full activity log details by log ID."""
        logs = self._load_logs()
        for entry in logs:
            if entry.get("id") == log_id:
                entry_copy = dict(entry)
                entry_copy["is_test"] = self.is_entry_a_test(entry)
                return entry_copy
        return None
