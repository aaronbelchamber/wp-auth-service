import unittest
from wp_auth_service.endpoint_storage import EndpointStorage


class TestEndpointStorage(unittest.TestCase):
    """Unit tests for EndpointStorage class."""

    def setUp(self):
        """Initialize in-memory endpoint storage for testing."""
        self.storage = EndpointStorage(storage_file=None)

    def test_create_and_list_profile(self):
        """Test creating and listing endpoint profiles."""
        profile = self.storage.create_profile(
            name="Primary CMS",
            wp_root_url="https://example.com",
            app_name="App 1",
            callback_url="https://app.com/callback"
        )
        self.assertEqual(profile["name"], "Primary CMS")
        self.assertEqual(profile["status"], "unconfirmed")
        self.assertTrue(profile["is_active"])

        profiles = self.storage.list_profiles()
        self.assertEqual(len(profiles), 1)

    def test_update_profile(self):
        """Test updating endpoint profile fields and status."""
        p = self.storage.create_profile("Site A", "https://sitea.com", "App A", "https://sitea.com/cb")
        updated = self.storage.update_profile(p["id"], name="Site A Updated", status="confirmed")
        self.assertIsNotNone(updated)
        self.assertEqual(updated["name"], "Site A Updated")
        self.assertEqual(updated["status"], "confirmed")

    def test_clone_profile(self):
        """Test cloning an existing endpoint profile."""
        original = self.storage.create_profile("Prod", "https://prod.com", "ProdApp", "https://prod.com/cb")
        cloned = self.storage.clone_profile(original["id"])
        self.assertIsNotNone(cloned)
        self.assertEqual(cloned["name"], "Copy of Prod")
        self.assertEqual(cloned["wp_root_url"], "https://prod.com")
        self.assertNotEqual(cloned["id"], original["id"])

    def test_delete_profile(self):
        """Test deleting an endpoint profile."""
        p1 = self.storage.create_profile("Site 1", "https://s1.com", "App1", "https://s1.com/cb")
        p2 = self.storage.create_profile("Site 2", "https://s2.com", "App2", "https://s2.com/cb")

        deleted = self.storage.delete_profile(p1["id"])
        self.assertTrue(deleted)
        self.assertEqual(len(self.storage.list_profiles()), 1)

    def test_active_endpoint_switching(self):
        """Test setting active endpoint profile."""
        p1 = self.storage.create_profile("P1", "https://p1.com", "A1", "https://p1.com/cb")
        p2 = self.storage.create_profile("P2", "https://p2.com", "A2", "https://p2.com/cb")

        active = self.storage.set_active(p2["id"])
        self.assertTrue(active["is_active"])
        self.assertFalse(self.storage.get_profile(p1["id"])["is_active"])


if __name__ == "__main__":
    unittest.main()
