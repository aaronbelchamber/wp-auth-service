import unittest
from unittest.mock import patch, MagicMock
import json
import io

from wp_auth_lib import (
    AppSession,
    WPConnectionError,
    WPAuthError,
    WPApiError,
    WPDataError,
    get_session,
    save_session,
    delete_session,
    health_check,
)

class TestWPAppBridge(unittest.TestCase):

    def test_app_session_dataclass(self):
        session = AppSession(
            app_id="demo_app",
            session_key="sess_123",
            payload={"theme": "dark"},
            id=1,
            user_id=42,
            created_at=1700000000,
            updated_at=1700000100
        )
        self.assertEqual(session.app_id, "demo_app")
        self.assertEqual(session.session_key, "sess_123")
        self.assertEqual(session.payload, {"theme": "dark"})
        self.assertEqual(session.user_id, 42)

    @patch("urllib.request.urlopen")
    def test_get_session_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "id": 10,
            "user_id": 5,
            "app_id": "test_app",
            "session_key": "k1",
            "payload": {"key": "val"},
            "created_at": 1700000000,
            "updated_at": 1700000000
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        session = get_session("https://example.com", "user", "pass", "test_app", "k1")
        self.assertEqual(session.id, 10)
        self.assertEqual(session.user_id, 5)
        self.assertEqual(session.payload, {"key": "val"})

    @patch("urllib.request.urlopen")
    def test_save_session_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "success": True,
            "action": "created",
            "app_id": "test_app",
            "session_key": "k1"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = save_session("https://example.com", "user", "pass", "test_app", "k1", {"state": "active"})
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("action"), "created")

    @patch("urllib.request.urlopen")
    def test_health_check_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "name": "My WordPress Site",
            "namespaces": ["wp/v2", "app/v1"]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = health_check("https://example.com")
        self.assertTrue(res["reachable"])
        self.assertTrue(res["plugin_installed"])
        self.assertEqual(res["wp_name"], "My WordPress Site")

if __name__ == "__main__":
    unittest.main()
