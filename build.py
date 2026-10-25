#!/usr/bin/env python3
"""Build Harmonia component archives for one platform.

    python build.py --platform macos-arm64 --out DIST [--component ffmpeg ...]
    python build.py --sources-only --out DIST          # the source archives

Writes ``<component>-<version>-<platform>.tar.gz`` (and, unless
``--no-sources``, ``<component>-<version>-source.tar.gz``) into ``--out``.
Builds run natively: build each platform on that platform (see README.md).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harmonia_components import builder, config, platforms  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--platform", help="target platform id (default: this machine)")
    ap.add_argument("--out", required=True, type=Path, help="directory for the archives")
    ap.add_argument("--component", action="append", choices=config.COMPONENT_NAMES, help="repeatable; default all")
    ap.add_argument("--work", type=Path, help="build tree (default: <out>/../work)")
    ap.add_argument("--cache", type=Path, help="download cache (default: <out>/../cache)")
    ap.add_argument("--jobs", type=int, default=builder.default_jobs())
    ap.add_argument("--sources-only", action="store_true", help="only write the source archives")
    ap.add_argument("--no-sources", action="store_true", help="do not write the source archives")
    args = ap.parse_args(argv)

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    work = (args.work or out.parent / "work").resolve()
    cache = (args.cache or out.parent / "cache").resolve()
    components = builder.sources_needed(args.component)

    if not args.sources_only:
        platform = platforms.validate(args.platform) if args.platform else platforms.current_platform()
        here = platforms.current_platform()
        if platform != here:
            ap.error(f"cross builds are not supported: this machine is {here}, asked for {platform}")
        for name in components:
            builder.build_component(name, platform, out, work, cache, args.jobs)
    if not args.no_sources:
        for name in components:
            builder.build_source_archive(name, out, work, cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())
