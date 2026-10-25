import unittest

from tests import _util  # noqa: F401
from harmonia_components import depcheck

OTOOL = """/x/lib/libtag_c.2.dylib:
\t@rpath/libtag_c.2.dylib (compatibility version 2.0.0, current version 2.3.2)
\t@rpath/libtag.2.dylib (compatibility version 2.0.0, current version 2.3.2)
\t/usr/lib/libc++.1.dylib (compatibility version 1.0.0, current version 2000.67.0)
\t/System/Library/Frameworks/Accelerate.framework/Versions/A/Accelerate (compatibility version 1.0.0)
"""

READELF = """
 0x0000000000000001 (NEEDED)             Shared library: [libtag.so.2]
 0x0000000000000001 (NEEDED)             Shared library: [libm.so.6]
 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
 0x000000000000000f (RUNPATH)            Library runpath: [$ORIGIN]
"""

OBJDUMP = """
\tDLL Name: KERNEL32.dll
\tDLL Name: msvcrt.dll
\tDLL Name: tag.dll
"""


class DepcheckTest(unittest.TestCase):
    def test_parsers(self):
        self.assertEqual(depcheck.parse_otool(OTOOL)[1], "@rpath/libtag.2.dylib")
        self.assertEqual(depcheck.parse_readelf_needed(READELF), ["libtag.so.2", "libm.so.6", "libc.so.6"])
        self.assertEqual(depcheck.parse_objdump_dlls(OBJDUMP), ["KERNEL32.dll", "msvcrt.dll", "tag.dll"])

    def test_macos_rules(self):
        deps = depcheck.parse_otool(OTOOL)[1:]
        self.assertEqual(depcheck.disallowed("macos-arm64", deps, own={"libtag.2.dylib"}), [])
        self.assertEqual(depcheck.disallowed("macos-arm64", ["/opt/homebrew/lib/libmp3lame.0.dylib"]), ["/opt/homebrew/lib/libmp3lame.0.dylib"])
        # an own library referenced by absolute build path is not relocatable
        self.assertEqual(depcheck.disallowed("macos-arm64", ["/build/inst/lib/libtag.2.dylib"], own={"libtag.2.dylib"}), ["/build/inst/lib/libtag.2.dylib"])

    def test_linux_rules(self):
        self.assertEqual(depcheck.disallowed("linux-x86_64", ["libtag.so.2", "libm.so.6", "libc.so.6"], own={"libtag.so.2"}), [])
        self.assertEqual(depcheck.disallowed("linux-arm64", ["libstdc++.so.6", "libgcc_s.so.1"]), ["libstdc++.so.6", "libgcc_s.so.1"])

    def test_windows_rules(self):
        self.assertEqual(depcheck.disallowed("windows-x86_64", ["KERNEL32.dll", "msvcrt.dll", "tag.dll"], own={"tag.dll"}), [])
        self.assertEqual(depcheck.disallowed("windows-x86_64", ["libwinpthread-1.dll"]), ["libwinpthread-1.dll"])


if __name__ == "__main__":
    unittest.main()
