"""The source archive's build/ copy of the repository (no network)."""
import unittest

from tests import _util  # noqa: F401
from harmonia_components import builder


class SourceIgnoreTest(unittest.TestCase):
    def test_repo_internals_and_build_output_are_left_out(self):
        names = [".git", ".venv", "dist", "release", "work", "cache", "__pycache__", "build.py", ".github", "keys"]
        ignored = builder._source_ignore(".", names)
        for n in (".git", ".venv", "dist", "release", "work", "cache", "__pycache__"):
            self.assertIn(n, ignored)
        for n in ("build.py", ".github", "keys"):
            self.assertNotIn(n, ignored)

    def test_private_key_material_is_never_copied(self):
        names = ["harmonia-components-1.key", "seed.seed", "signing.pem", "harmonia-components-1.pub", "x.log"]
        ignored = builder._source_ignore(".", names)
        self.assertEqual(sorted(ignored), ["harmonia-components-1.key", "seed.seed", "signing.pem", "x.log"])


if __name__ == "__main__":
    unittest.main()
