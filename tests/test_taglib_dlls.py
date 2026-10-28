"""Which TagLib DLLs a Windows archive ships (no network)."""
import tempfile
import unittest
from pathlib import Path

from tests import _util  # noqa: F401
from harmonia_components import builder


class TaglibDllsTest(unittest.TestCase):
    def names(self, files):
        d = Path(tempfile.mkdtemp())
        for f in files:
            (d / f).write_bytes(b"MZ")
        return [p.name for p in builder.taglib_dlls(d)]

    def test_mingw_names(self):
        self.assertEqual(self.names(["libtag.dll", "libtag_c.dll", "libzs.dll", "libtag.dll.a"]),
                         ["libtag.dll", "libtag_c.dll"])


if __name__ == "__main__":
    unittest.main()
