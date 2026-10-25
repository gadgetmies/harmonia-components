"""Shared helpers for the harmonia-components tests (no network)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harmonia_components import config  # noqa: E402

LGPL_TEXT = """ffmpeg is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 2.1 of the License, or (at your option) any later version.
"""

GPL_TEXT = """ffmpeg is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""


def buildconf(flags: str) -> str:
    lines = "\n".join("    " + f for f in flags.split())
    return (
        "ffmpeg version 7.1.5 Copyright (c) 2000-2025 the FFmpeg developers\n"
        "  built with Apple clang version 17.0.0\n"
        f"  configuration: {flags}\n"
        "  libavutil      59. 39.100 / 59. 39.100\n"
        "\n  configuration:\n" + lines + "\n"
    )


def write_payload(stage: Path, component: str, platform: str) -> None:
    """Create a minimal valid stage directory for ``component``."""
    from harmonia_components.archive import required_payload

    for rel in required_payload(component, platform):
        p = stage / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x7fELF fake " + rel.encode())
        p.chmod(0o755)
    if component == "taglib" and not platform.startswith("windows"):
        ext = "dylib" if platform.startswith("macos") else "so"
        (stage / "lib" / f"libtag.{ext}").write_bytes(b"fake libtag")
    (stage / "licenses").mkdir(parents=True, exist_ok=True)
    (stage / "licenses" / "COPYING.txt").write_text("licence text\n")
    (stage / "BUILD-INFO.txt").write_text(f"component: {component}\nplatform: {platform}\n")


def fake_components() -> dict:
    src = config.Source("fake", "1.0", "https://example.invalid/fake-1.0.tar.gz", "0" * 64, ["COPYING"])
    return {
        "ffmpeg": config.Component("ffmpeg", "7.1.5", "LGPL-2.1-or-later", "attr ffmpeg", ["ffmpeg", "ffprobe"], [], [src]),
        "taglib": config.Component("taglib", "2.3.2", "LGPL-2.1-only OR MPL-1.1", "attr taglib", [], ["tag_c"], [src]),
    }


def write_source_stage(stage: Path, upstream_names=("fake-1.0.tar.gz",)) -> None:
    (stage / "upstream").mkdir(parents=True, exist_ok=True)
    for n in upstream_names:
        (stage / "upstream" / n).write_bytes(b"tarball")
    (stage / "build").mkdir(parents=True, exist_ok=True)
    (stage / "build" / "build.py").write_text("print('hi')\n")
    (stage / "CONFIGURE.txt").write_text("./configure\n")
    (stage / "changes.diff").write_text("")
