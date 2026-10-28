"""Build recipes: the exact configure / cmake / meson / make command lines per
component and platform.

A recipe is a list of :class:`Step` whose strings may contain ``{placeholders}``
(``{prefix}``, ``{src_<id>}``, ``{build_<id>}``, ``{inst}``, ``{jobs}``). The
builder fills them with real paths; ``CONFIGURE.txt`` in the source archive is
rendered from the SAME recipes with shell-variable placeholders, so the
published configure lines are exactly the ones the build ran.

Every dependency is built static into ``{prefix}``; the component itself is
installed into ``{inst}`` and its payload copied into the archive stage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from . import ffmpeg_features as ff
from .platforms import arch_of, os_of

MACOS_MIN = "12.0"


@dataclass
class Step:
    title: str
    argv: List[str]
    cwd: str
    env: Dict[str, str] = field(default_factory=dict)

    def render(self, values: Dict[str, str]) -> "Step":
        def sub(s: str) -> str:
            return s.format_map(values)

        return Step(self.title, [sub(a) for a in self.argv], sub(self.cwd), {k: sub(v) for k, v in self.env.items()})


# --------------------------------------------------------------------------- flags


def cflags(platform: str) -> str:
    osname = os_of(platform)
    if osname == "macos":
        return f"-O2 -arch {arch_of(platform)} -mmacosx-version-min={MACOS_MIN}"
    if osname == "linux":
        return "-O2 -fPIC"
    return "-O2"


def ldflags(platform: str) -> str:
    osname = os_of(platform)
    if osname == "macos":
        return f"-arch {arch_of(platform)} -mmacosx-version-min={MACOS_MIN}"
    if osname == "linux":
        return "-static-libgcc -static-libstdc++"
    return "-static -static-libgcc -static-libstdc++"


def base_env(platform: str) -> Dict[str, str]:
    env = {
        "CFLAGS": cflags(platform),
        "CXXFLAGS": cflags(platform),
        "LDFLAGS": ldflags(platform),
        "PKG_CONFIG_PATH": "{prefix}/lib/pkgconfig",
    }
    if os_of(platform) == "macos":
        env["MACOSX_DEPLOYMENT_TARGET"] = MACOS_MIN
    return env


def cmake_common(platform: str, install_prefix: str = "{prefix}") -> List[str]:
    args = [
        "-G",
        "Ninja",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={install_prefix}",
        "-DCMAKE_PREFIX_PATH={prefix}",
        "-DCMAKE_INSTALL_LIBDIR=lib",
        "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
        # CMake 4 refuses projects declaring cmake_minimum_required < 3.5.
        "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
    ]
    if os_of(platform) == "macos":
        args += [f"-DCMAKE_OSX_DEPLOYMENT_TARGET={MACOS_MIN}", f"-DCMAKE_OSX_ARCHITECTURES={arch_of(platform)}"]
    return args


def cmake_steps(platform: str, sid: str, extra: List[str], install_prefix: str = "{prefix}") -> List[Step]:
    src, bld = "{src_%s}" % sid, "{build_%s}" % sid
    env = base_env(platform)
    return [
        Step(f"{sid}: configure", ["cmake", "-S", src, "-B", bld] + cmake_common(platform, install_prefix) + extra, bld, env),
        Step(f"{sid}: build", ["cmake", "--build", bld, "--parallel", "{jobs}"], bld, env),
        Step(f"{sid}: install", ["cmake", "--install", bld], bld, env),
    ]


def autotools_triple(platform: str) -> str:
    osname, arch = os_of(platform), arch_of(platform)
    cpu = "aarch64" if arch == "arm64" else "x86_64"
    return {"macos": f"{cpu}-apple-darwin", "linux": f"{cpu}-pc-linux-gnu", "windows": f"{cpu}-w64-mingw32"}[osname]


# --------------------------------------------------------------------------- deps


def lame(platform: str) -> List[Step]:
    env = base_env(platform)
    src = "{src_lame}"
    configure = [
        "sh",
        "./configure",
        "--prefix={prefix}",
        f"--build={autotools_triple(platform)}",
        "--disable-shared",
        "--enable-static",
        "--disable-frontend",
        "--disable-decoder",
        "--disable-gtktest",
        "--disable-dependency-tracking",
    ]
    return [
        Step("lame: configure", configure, src, env),
        Step("lame: build", ["make", "-j{jobs}"], src, env),
        Step("lame: install", ["make", "install"], src, env),
    ]


def libogg(platform: str) -> List[Step]:
    return cmake_steps(platform, "libogg", ["-DBUILD_SHARED_LIBS=OFF", "-DINSTALL_DOCS=OFF"])


def libvorbis(platform: str) -> List[Step]:
    extra = ["-DBUILD_SHARED_LIBS=OFF"]
    if os_of(platform) == "linux":
        # The CMake build leaves vorbis.pc's Libs.private (@VORBIS_LIBS@) empty,
        # so a static link misses libm; glibc keeps it apart from libc.
        extra.append("-DVORBIS_LIBS=-lm")
    return cmake_steps(platform, "libvorbis", extra)


def opus(platform: str) -> List[Step]:
    return cmake_steps(
        platform,
        "opus",
        [
            "-DBUILD_SHARED_LIBS=OFF",
            "-DOPUS_BUILD_SHARED_LIBRARY=OFF",
            "-DOPUS_BUILD_TESTING=OFF",
            "-DOPUS_BUILD_PROGRAMS=OFF",
            "-DOPUS_DRED=OFF",
            "-DOPUS_OSCE=OFF",
        ],
    )


def libsndfile(platform: str) -> List[Step]:
    # WAV I/O for the Rubber Band CLI: no external codecs (FLAC/Vorbis/Opus/MPEG).
    return cmake_steps(
        platform,
        "libsndfile",
        [
            "-DBUILD_SHARED_LIBS=OFF",
            "-DENABLE_EXTERNAL_LIBS=OFF",
            "-DENABLE_MPEG=OFF",
            "-DBUILD_PROGRAMS=OFF",
            "-DBUILD_EXAMPLES=OFF",
            "-DBUILD_TESTING=OFF",
            "-DENABLE_CPACK=OFF",
            "-DENABLE_PACKAGE_CONFIG=OFF",
            "-DINSTALL_PKGCONFIG_MODULE=ON",
        ],
    )


def zlib(platform: str) -> List[Step]:
    return cmake_steps(
        platform,
        "zlib",
        ["-DZLIB_BUILD_SHARED=OFF", "-DZLIB_BUILD_STATIC=ON", "-DZLIB_BUILD_TESTING=OFF"],
    )


# --------------------------------------------------------------------------- components


def ffmpeg(platform: str) -> List[Step]:
    osname = os_of(platform)
    env = base_env(platform)
    threads = "--enable-w32threads" if osname == "windows" else "--enable-pthreads"
    configure = [
        "sh",
        "{src_ffmpeg}/configure",
        "--prefix={inst}",
        "--pkg-config-flags=--static",
        "--extra-cflags=-I{prefix}/include " + cflags(platform),
        "--extra-ldflags=-L{prefix}/lib " + ldflags(platform),
        "--disable-shared",
        "--enable-static",
        "--disable-debug",
        "--disable-doc",
        "--disable-ffplay",
        # LGPL only: never --enable-gpl / --enable-nonfree / --enable-version3.
        "--disable-everything",
        "--disable-autodetect",
        threads,
        "--disable-network",
        "--disable-postproc",
        "--enable-libmp3lame",
        "--enable-libopus",
        "--enable-libvorbis",
    ]
    extra_encoders = []
    if osname == "macos":
        # System framework (LGPL-compatible): the HE-AAC encoder for live streaming.
        configure.append("--enable-audiotoolbox")
        extra_encoders.append("aac_at")
    configure += ff.configure_flags(extra_encoders)
    steps = [Step("ffmpeg: configure", configure, "{build_ffmpeg}", env)]
    steps.append(Step("ffmpeg: build", ["make", "-j{jobs}"], "{build_ffmpeg}", env))
    steps.append(Step("ffmpeg: install", ["make", "install"], "{build_ffmpeg}", env))
    return lame(platform) + libogg(platform) + libvorbis(platform) + opus(platform) + steps


def rubberband(platform: str) -> List[Step]:
    env = base_env(platform)
    fft = "vdsp" if os_of(platform) == "macos" else "builtin"
    setup = [
        "meson",
        "setup",
        "{build_rubberband}",
        "{src_rubberband}",
        "--prefix={inst}",
        "--libdir=lib",
        "--buildtype=release",
        "--default-library=static",
        "-Dprefer_static=true",
        f"-Dfft={fft}",
        "-Dresampler=builtin",
        "-Dcmdline=enabled",
        "-Djni=disabled",
        "-Dladspa=disabled",
        "-Dlv2=disabled",
        "-Dvamp=disabled",
        "-Dtests=disabled",
    ]
    return libsndfile(platform) + [
        Step("rubberband: configure", setup, "{src_rubberband}", env),
        Step("rubberband: build", ["meson", "compile", "-C", "{build_rubberband}", "-j", "{jobs}"], "{src_rubberband}", env),
        Step("rubberband: install", ["meson", "install", "-C", "{build_rubberband}"], "{src_rubberband}", env),
    ]


def taglib(platform: str) -> List[Step]:
    osname = os_of(platform)
    zlib_lib = "{prefix}/lib/libzs.a" if osname == "windows" else "{prefix}/lib/libz.a"
    extra = [
        "-DBUILD_SHARED_LIBS=ON",
        "-DBUILD_TESTING=OFF",
        "-DBUILD_EXAMPLES=OFF",
        "-DBUILD_BINDINGS=ON",
        "-DVISIBILITY_HIDDEN=ON",
        "-DWITH_ZLIB=ON",
        "-DZLIB_INCLUDE_DIR={prefix}/include",
        "-DZLIB_LIBRARY=" + zlib_lib,
    ]
    if osname == "macos":
        # Load from the archive's own lib/: ids are @rpath/..., rpath @loader_path.
        extra += ["-DCMAKE_MACOSX_RPATH=ON", "-DCMAKE_INSTALL_NAME_DIR=@rpath", "-DCMAKE_INSTALL_RPATH=@loader_path"]
    elif osname == "linux":
        extra += ["-DCMAKE_INSTALL_RPATH=$ORIGIN"]
    else:
        # MinGW would name them libtag.dll / libtag_c.dll; the contract wants
        # bin/tag.dll + bin/tag_c.dll (and tag_c.dll must import "tag.dll").
        extra += ["-DCMAKE_SHARED_LIBRARY_PREFIX="]
    return zlib(platform) + cmake_steps(platform, "taglib", extra, install_prefix="{inst}")


RECIPES = {"ffmpeg": ffmpeg, "rubberband": rubberband, "taglib": taglib}


def steps_for(component: str, platform: str) -> List[Step]:
    return RECIPES[component](platform)


def render_configure_txt(component: str, version: str, platforms: List[str]) -> str:
    """Human-readable, exact command lines for every platform."""
    placeholder = _Placeholders()
    lines = [
        f"# Exact build commands for {component} {version}, per platform.",
        "# Generated from harmonia_components/recipes.py (the",
        "# same code the build runs). Placeholders: $PREFIX = static dependency",
        "# prefix, $INST = install dir of the component, $SRC_<id> = the unpacked",
        "# upstream tarball from upstream/, $BUILD_<id> = its build dir, $JOBS = make -j.",
        "# Each step runs in the directory shown with the environment shown.",
        "",
    ]
    for platform in platforms:
        lines.append(f"## {platform}")
        for step in steps_for(component, platform):
            s = step.render(placeholder)
            lines.append(f"# {s.title}  (cwd: {s.cwd})")
            for k in sorted(s.env):
                lines.append(f"export {k}={_shell_quote(s.env[k])}")
            lines.append(" ".join(_shell_quote(a) for a in s.argv))
        lines.append("")
    return "\n".join(lines)


def _shell_quote(arg: str) -> str:
    """Quote for pasting into sh: placeholders like ``$PREFIX`` stay
    expandable (double quotes); literal ``$ORIGIN`` (an rpath) stays literal."""
    import shlex

    if "$" not in arg or "$ORIGIN" in arg:
        return shlex.quote(arg)
    if all(c.isalnum() or c in "$_-=/.,:+@%" for c in arg):
        return arg
    return '"' + arg.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`") + '"'


class _Placeholders(dict):
    def __missing__(self, key: str) -> str:
        return "$" + key.upper()
