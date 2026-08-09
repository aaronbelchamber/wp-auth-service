"""
Integration tests for WordPress Auth Service API.

Uses in-memory-only storage for all fixtures so that no test data
ever leaks into api_keys.json or endpoints.json.
"""

import unittest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from wp_auth_service.main import create_app
from wp_auth_service.api.routes import (
    get_cache,
    get_api_key_storage,
    get_endpoint_storage,
    verify_api_key,
    verify_api_key_or_bootstrap,
)
from wp_auth_service.storage import APIKeyStorage
from wp_auth_service.endpoint_storage import EndpointStorage
from wp_auth_service.api.middleware import APIKeyAuthMiddleware
from wp_auth_lib import UserProfile, ValidationResult


# ---------------------------------------------------------------------------
# Shared in-memory fixtures (no file I/O, no JSON pollution)
# ---------------------------------------------------------------------------

def _make_isolated_storage() -> tuple[APIKeyStorage, EndpointStorage, APIKeyAuthMiddleware]:
    """Return an in-memory-only key/endpoint storage pair for test isolation."""
    key_storage = APIKeyStorage(storage_file=None)
    ep_storage = EndpointStorage(storage_file=None)
    middleware = APIKeyAuthMiddleware(key_storage)
    return key_storage, ep_storage, middleware


class TestServiceIntegration(unittest.TestCase):
    """Integration tests for the auth service API."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = TestClient(cls.app)

    def setUp(self):
        """Override all storage dependencies with fresh in-memory instances."""
        self.key_storage, self.ep_storage, self.middleware = _make_isolated_storage()

        # Generate a test key in the isolated store
        self.api_key = self.key_storage.generate_key("test_runner")

        # Capture for use in closures (avoid late-binding to self)
        key_storage = self.key_storage
        ep_storage = self.ep_storage

        # FastAPI dependency overrides: these functions are injected by FastAPI.
        # Use Optional[str] Header parameter — same signature pattern as the middleware.
        from fastapi import Header, HTTPException, status as http_status
        from typing import Optional

        async def _isolated_verify(x_api_key: Optional[str] = Header(default=None)):
            """Validates X-API-Key against the isolated in-memory store."""
            if not x_api_key or not key_storage.validate_key(x_api_key):
                raise HTTPException(
                    status_code=http_status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or missing API key",
                )
            return x_api_key

        async def _isolated_bootstrap(x_api_key: Optional[str] = Header(default=None)):
            """Allows access when no keys stored; enforces key otherwise."""
            if key_storage.get_key_count() == 0:
                return None
            if not x_api_key or not key_storage.validate_key(x_api_key):
                raise HTTPException(
                    status_code=http_status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or missing API key",
                )
            return x_api_key

        # Wire overrides
        self.app.dependency_overrides[get_api_key_storage] = lambda: key_storage
        self.app.dependency_overrides[get_endpoint_storage] = lambda: ep_storage
        self.app.dependency_overrides[verify_api_key] = _isolated_verify
        self.app.dependency_overrides[verify_api_key_or_bootstrap] = _isolated_bootstrap

    def tearDown(self):
        """Remove all dependency overrides after each test."""
        self.app.dependency_overrides.clear()



    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------


    def test_health_endpoint(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")

    def test_get_config(self):
        response = self.client.get("/api/v1/config", headers={"X-API-Key": self.api_key})
        self.assertEqual(response.status_code, 200)
        self.assertIn("wp_root_url", response.json())

    def test_post_config(self):
        payload = {
            "wp_root_url": "https://example.com/cms",
            "app_name": "Test Application",
            "callback_url": "https://myapp.com/callback",
        }
        response = self.client.post("/api/v1/config", json=payload, headers={"X-API-Key": self.api_key})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["wp_root_url"], "https://example.com/cms")
        self.assertTrue(data["is_configured"])

    def test_post_config_without_api_key_when_keys_exist(self):
        """POST /config must fail 401 when a key is required but missing."""
        payload = {
            "wp_root_url": "https://example.com/cms",
            "app_name": "Test Application",
            "callback_url": "https://myapp.com/callback",
        }
        response = self.client.post("/api/v1/config", json=payload)
        self.assertEqual(response.status_code, 401)

    def test_generate_auth_url(self):
        payload = {
            "wp_root_url": "https://example.com/cms",
            "app_name": "Test App",
            "callback_url": "https://myapp.com/callback",
        }
        response = self.client.post("/api/v1/auth/url", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("auth_url", data)
        self.assertTrue(data["auth_url"].startswith("https://example.com/cms/wp-admin/authorize-application.php"))

    def test_parse_callback(self):
        payload = {
            "callback_url": "https://myapp.com/callback?user_login=testuser&password=app-pass-1234&success_url=https://myapp.com"
        }
        response = self.client.post("/api/v1/auth/callback", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_valid"])
        self.assertEqual(data["user_login"], "testuser")

    @patch("wp_auth_service.api.routes.validate_credentials")
    def test_validate_credentials(self, mock_validate):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        self.app.dependency_overrides[get_cache] = lambda: mock_cache

        profile = UserProfile(id=1, username="testuser", email="test@example.com", roles=["administrator"])
        mock_validate.return_value = ValidationResult(is_valid=True, user_profile=profile)

        payload = {
            "user_login": "testuser",
            "password": "app-pass-1234",
            "wp_root_url": "https://example.com/cms",
        }
        response = self.client.post("/api/v1/auth/validate", json=payload, headers={"X-API-Key": self.api_key})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_valid"])
        self.assertEqual(data["username"], "testuser")

    def test_endpoint_routes_crud(self):
        """Test creating, listing, cloning, and confirming endpoint profiles."""
        headers = {"X-API-Key": self.api_key}
        payload = {
            "name": "Integration Test Site",
            "wp_root_url": "https://testsite.example",
            "app_name": "Test App",
            "callback_url": "https://testsite.example/callback",
            "is_active": True,
        }

        # Create
        create_res = self.client.post("/api/v1/endpoints", json=payload, headers=headers)
        self.assertEqual(create_res.status_code, 200)
        created = create_res.json()
        self.assertEqual(created["name"], "Integration Test Site")
        self.assertEqual(created["status"], "unconfirmed")

        # List
        list_res = self.client.get("/api/v1/endpoints", headers=headers)
        self.assertEqual(list_res.status_code, 200)
        self.assertGreaterEqual(len(list_res.json()), 1)

        # Clone
        clone_res = self.client.post(f"/api/v1/endpoints/{created['id']}/clone", headers=headers)
        self.assertEqual(clone_res.status_code, 200)
        self.assertEqual(clone_res.json()["name"], "Copy of Integration Test Site")

        # Confirm (reachability — will be unconfirmed since testsite.example is fake)
        confirm_res = self.client.post(f"/api/v1/endpoints/{created['id']}/confirm", headers=headers)
        self.assertEqual(confirm_res.status_code, 200)
        self.assertIn("status", confirm_res.json())

        # Delete
        ep_id = created["id"]
        delete_res = self.client.delete(f"/api/v1/endpoints/{ep_id}", headers=headers)
        self.assertEqual(delete_res.status_code, 200)

    def test_browser_callback_flow(self):
        """Test GET /api/v1/auth/callback-ui receiving credentials from browser redirect."""
        # Simulate browser redirect from WordPress
        res = self.client.get("/api/v1/auth/callback-ui?user_login=wpadmin&password=xxxx+yyyy+zzzz")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Authorization Successful", res.text)

        # Check latest-credentials endpoint returns captured credentials
        cred_res = self.client.get("/api/v1/auth/latest-credentials")
        self.assertEqual(cred_res.status_code, 200)
        creds = cred_res.json()
        self.assertEqual(creds.get("user_login"), "wpadmin")
        self.assertEqual(creds.get("password"), "xxxx yyyy zzzz")

    def test_plugin_check_endpoint(self):
        """Test POST /api/v1/endpoints/{id}/plugin-check endpoint probing WP App Bridge liveness."""
        headers = {"X-API-Key": self.api_key}
        payload = {
            "name": "Plugin Probe Test Site",
            "wp_root_url": "https://testsite.example",
            "app_name": "Test App",
            "callback_url": "http://localhost:8000/api/v1/auth/callback-ui",
            "is_active": True,
        }

        create_res = self.client.post("/api/v1/endpoints", json=payload, headers=headers)
        created = create_res.json()

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.json.return_value = {"status": "active", "plugin": "wp-app-bridge", "version": "1.0.0"}
            mock_get.return_value = mock_res

            check_res = self.client.post(f"/api/v1/endpoints/{created['id']}/plugin-check")
            self.assertEqual(check_res.status_code, 200)
            data = check_res.json()
            self.assertTrue(data.get("is_plugin_active"))
            self.assertEqual(data.get("details", {}).get("plugin"), "wp-app-bridge")


if __name__ == "__main__":
    unittest.main()

