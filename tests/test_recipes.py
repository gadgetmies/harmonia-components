import unittest

from tests import _util  # noqa: F401
from harmonia_components import config, ffmpeg_features, guard, recipes
from harmonia_components.platforms import PLATFORMS


class RecipeTest(unittest.TestCase):
    def test_ffmpeg_configure_is_lgpl_on_every_platform(self):
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                steps = recipes.steps_for("ffmpeg", platform)
                configure = next(s for s in steps if s.title == "ffmpeg: configure").argv
                guard.check_flags(configure)
                self.assertIn("--disable-everything", configure)
                self.assertIn("--disable-autodetect", configure)
                self.assertEqual("--enable-audiotoolbox" in configure, platform.startswith("macos"))

    def test_no_external_or_gpl_filter_enabled(self):
        for name in ffmpeg_features.EXCLUDED_FILTERS:
            self.assertNotIn(name, ffmpeg_features.AUDIO_FILTERS)
        for needed in ("loudnorm", "ebur128", "aresample", "atrim", "afade", "acrossfade", "amix",
                       "volume", "alimiter", "adelay", "asplit", "asetpts", "aformat", "concat", "sine"):
            self.assertIn(needed, ffmpeg_features.AUDIO_FILTERS)

    def test_contract_codecs_present(self):
        for enc in ("libmp3lame", "aac", "libopus", "libvorbis", "pcm_s16le", "pcm_f32le"):
            self.assertIn(enc, ffmpeg_features.ENCODERS)
        for mux in ("wav", "hls", "mp3", "ogg", "opus", "adts", "ipod", "pcm_f32le", "pcm_s16le", "null"):
            self.assertIn(mux, ffmpeg_features.MUXERS)
        for dec in ("mp3float", "aac", "alac", "flac", "vorbis", "opus", "wavpack", "pcm_s16be"):
            self.assertIn(dec, ffmpeg_features.DECODERS)
        no_video = {"h264", "libx264", "mpeg4", "png", "mjpeg"}
        self.assertFalse(no_video & set(ffmpeg_features.ENCODERS))

    def test_unknown_names_detected(self):
        available = {k: list(v) for k, v in ffmpeg_features.lists().items()}
        available["encoder"].append("aac_at")
        self.assertEqual(ffmpeg_features.unknown_names(available, ["aac_at"]), {})
        available["muxer"].remove("pcm_f32le")
        self.assertEqual(ffmpeg_features.unknown_names(available), {"muxer": ["pcm_f32le"]})

    def test_configure_txt_renders_every_platform(self):
        comps = config.load()
        for name, comp in comps.items():
            with self.subTest(component=name):
                text = recipes.render_configure_txt(name, comp.version, list(PLATFORMS))
                for platform in PLATFORMS:
                    self.assertIn(f"## {platform}", text)
                self.assertNotIn("{", text.replace("${", ""))
                self.assertIn("$PREFIX", text)

    def test_configure_txt_quoting_keeps_placeholders_expandable(self):
        q = recipes._shell_quote
        self.assertEqual(q("--prefix=$INST"), "--prefix=$INST")
        self.assertEqual(q("--extra-cflags=-I$PREFIX/include -O2"), '"--extra-cflags=-I$PREFIX/include -O2"')
        self.assertEqual(q("-DCMAKE_INSTALL_RPATH=$ORIGIN"), "'-DCMAKE_INSTALL_RPATH=$ORIGIN'")
        self.assertEqual(q("plain"), "plain")

    def test_taglib_rpath_per_os(self):
        def args(platform):
            return " ".join(a for s in recipes.steps_for("taglib", platform) for a in s.argv)

        self.assertIn("-DCMAKE_INSTALL_RPATH=@loader_path", args("macos-arm64"))
        self.assertIn("-DCMAKE_INSTALL_RPATH=$ORIGIN", args("linux-arm64"))
        self.assertIn("-DCMAKE_SHARED_LIBRARY_PREFIX=", args("windows-x86_64"))

    def test_static_vorbis_pc_names_libm_on_linux(self):
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                configure = next(s for s in recipes.libvorbis(platform) if s.title == "libvorbis: configure").argv
                self.assertEqual("-DVORBIS_LIBS=-lm" in configure, platform.startswith("linux"))

    def test_macos_deployment_target(self):
        env = recipes.base_env("macos-x86_64")
        self.assertEqual(env["MACOSX_DEPLOYMENT_TARGET"], "12.0")
        self.assertIn("-mmacosx-version-min=12.0", env["CFLAGS"])
        self.assertIn("-arch x86_64", env["CFLAGS"])


class VersionsTest(unittest.TestCase):
    def test_versions_toml_is_complete(self):
        comps = config.load()
        self.assertEqual(sorted(comps), sorted(config.COMPONENT_NAMES))
        for comp in comps.values():
            self.assertTrue(comp.sources)
            self.assertEqual(comp.sources[0].id, comp.name)
            self.assertEqual(comp.sources[0].version, comp.version)
            for s in comp.sources:
                self.assertEqual(len(s.sha256), 64)
                self.assertTrue(s.url.startswith("https://"))
                self.assertTrue(s.license_files)
        self.assertEqual(comps["ffmpeg"].attribution, "This software uses libraries from the FFmpeg project under the LGPLv2.1")
        self.assertEqual(comps["rubberband"].attribution, "This product uses the Rubber Band Library audio timestretcher from Breakfast Quay")


if __name__ == "__main__":
    unittest.main()
