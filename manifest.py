#!/usr/bin/env python3
"""Assemble ``manifest.json`` (schema 1) for a component release.

    python manifest.py --release 2026.10.20.1 --dist DIST [--created-at ISO]

Scans DIST for ``<component>-<version>-<platform>.tar.gz`` and the source
archives, checks every archive's layout, and writes DIST/manifest.json (the
exact bytes ``sign.py`` signs). A platform with no archive is simply absent
from ``builds`` ("not available for this platform").
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harmonia_components import manifest  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--release", required=True, help="release id, e.g. 2026.10.20.1")
    ap.add_argument("--dist", required=True, type=Path, help="directory holding the archives")
    ap.add_argument("--created-at", help="override created_at (UTC, YYYY-MM-DDTHH:MM:SSZ)")
    args = ap.parse_args(argv)
    m = manifest.assemble(args.release, args.dist, created_at=args.created_at)
    out = args.dist / manifest.MANIFEST
    out.write_bytes(manifest.dumps(m))
    for comp in m["components"]:
        print(f"{comp['name']} {comp['version']}: {', '.join(sorted(comp['builds']))}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
