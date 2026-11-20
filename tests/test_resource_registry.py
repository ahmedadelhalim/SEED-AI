import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from core.resource_registry import ResourceRegistry
from memory import store

class ResourceRegistryTests(TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.database_path = Path(temporary_directory.name) / "resources.sqlite"
        patcher = patch.object(store, "DB_PATH", self.database_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.registry = ResourceRegistry()

    def test_resource_registration_and_retrieval(self):
        res = self.registry.register_resource(
            resource_id="git-repo-1",
            resource_type="repository",
            name="SEED-AI Repo",
            path_or_uri="D:/SEED-AI",
            metadata={"branch": "main", "protected": True}
        )
        self.assertEqual(res["resource_id"], "git-repo-1")
        self.assertEqual(res["resource_type"], "repository")
        self.assertEqual(res["metadata"]["branch"], "main")

        fetched = self.registry.get_resource("git-repo-1")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["name"], "SEED-AI Repo")

        all_res = self.registry.list_resources()
        self.assertEqual(len(all_res), 1)

        repos = self.registry.list_resources("repository")
        self.assertEqual(len(repos), 1)

        other = self.registry.list_resources("database")
        self.assertEqual(len(other), 0)

        deleted = self.registry.unregister_resource("git-repo-1")
        self.assertTrue(deleted)
        self.assertIsNone(self.registry.get_resource("git-repo-1"))

if __name__ == "__main__":
    import unittest
    unittest.main()
