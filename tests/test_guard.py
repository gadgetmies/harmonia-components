import unittest

from tests._util import GPL_TEXT, LGPL_TEXT, buildconf
from harmonia_components import guard

LGPL_FLAGS = "--prefix=/x --disable-everything --disable-autodetect --enable-libmp3lame --enable-encoder=aac,libmp3lame"


class GuardTest(unittest.TestCase):
    def test_parses_both_configuration_forms(self):
        flags = guard.parse_buildconf(buildconf(LGPL_FLAGS))
        self.assertEqual(flags, LGPL_FLAGS.split())

    def test_lgpl_build_passes(self):
        self.assertEqual(guard.check_build(buildconf(LGPL_FLAGS), LGPL_TEXT), LGPL_FLAGS.split())

    def test_forbidden_flags_fail(self):
        for bad in ("--enable-gpl", "--enable-nonfree", "--enable-version3"):
            with self.subTest(flag=bad), self.assertRaises(guard.LicenseGuardError):
                guard.check_build(buildconf(LGPL_FLAGS + " " + bad), LGPL_TEXT)

    def test_disable_gpl_is_fine(self):
        guard.check_flags(["--disable-gpl", "--disable-nonfree"])

    def test_license_text_variants(self):
        with self.assertRaises(guard.LicenseGuardError):
            guard.check_license_text(GPL_TEXT)
        with self.assertRaises(guard.LicenseGuardError):
            guard.check_license_text("This version of ffmpeg has nonfree parts compiled in.\nTherefore it is not legally redistributable.\n")
        with self.assertRaises(guard.LicenseGuardError):
            guard.check_license_text(LGPL_TEXT.replace("2.1", "3"))
        guard.check_license_text(LGPL_TEXT)

    def test_missing_configuration_fails(self):
        with self.assertRaises(guard.LicenseGuardError):
            guard.check_build("ffmpeg version 7.1.5\n", LGPL_TEXT)


if __name__ == "__main__":
    unittest.main()
