"""
Unit tests for API key lifecycle management in APIKeyStorage.
"""

import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from wp_auth_service.storage import APIKeyStorage


class APIKeyStorageLifecycleTest(unittest.TestCase):
    """Tests for key expiry pruning and lifecycle methods."""

    def _storage_in_tmpdir(self) -> APIKeyStorage:
        """Create a fresh APIKeyStorage backed by a temp file."""
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.write(b"{}")
        tmp.close()
        return APIKeyStorage(storage_file=str(tmp.name))

    def test_fresh_storage_is_empty(self):
        s = self._storage_in_tmpdir()
        self.assertEqual(s.get_key_count(), 0)

    def test_generated_key_is_stored(self):
        s = self._storage_in_tmpdir()
        key = s.generate_key("test")
        self.assertTrue(s.validate_key(key))
        self.assertEqual(s.get_key_count(), 1)

    def test_prune_expired_removes_old_keys(self):
        s = self._storage_in_tmpdir()
        # Inject an artificially old key directly into _keys
        old_dt = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        s._keys["old_key_value"] = {
            "name": "stale",
            "created_at": old_dt,
            "last_used": None,
        }
        s._save_to_file()

        pruned = s.prune_expired_keys(max_age_days=30)
        self.assertEqual(pruned, 1)
        self.assertFalse(s.validate_key("old_key_value"))

    def test_prune_keeps_recent_keys(self):
        s = self._storage_in_tmpdir()
        recent_dt = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        s._keys["recent_key_value"] = {
            "name": "fresh",
            "created_at": recent_dt,
            "last_used": None,
        }
        s._save_to_file()

        pruned = s.prune_expired_keys(max_age_days=30)
        self.assertEqual(pruned, 0)
        self.assertTrue(s.validate_key("recent_key_value"))

    def test_generate_key_triggers_prune(self):
        """Generating a new key should auto-prune expired ones."""
        s = self._storage_in_tmpdir()
        old_dt = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        s._keys["zombie_key"] = {
            "name": "old",
            "created_at": old_dt,
            "last_used": None,
        }
        s._save_to_file()

        _new_key = s.generate_key("rotated")
        # zombie_key should be gone; only the new key remains
        self.assertFalse(s.validate_key("zombie_key"))
        self.assertEqual(s.get_key_count(), 1)

    def test_list_keys_triggers_prune(self):
        """list_keys should silently prune expired keys."""
        s = self._storage_in_tmpdir()
        old_dt = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
        s._keys["expired_list_key"] = {
            "name": "old",
            "created_at": old_dt,
            "last_used": None,
        }
        s._save_to_file()

        keys = s.list_keys()
        self.assertEqual(len(keys), 0)
        self.assertFalse(s.validate_key("expired_list_key"))

    def test_revoke_key_removes_it(self):
        s = self._storage_in_tmpdir()
        key = s.generate_key("todelete")
        self.assertTrue(s.revoke_key(key))
        self.assertFalse(s.validate_key(key))
        self.assertEqual(s.get_key_count(), 0)


if __name__ == "__main__":
    unittest.main()
