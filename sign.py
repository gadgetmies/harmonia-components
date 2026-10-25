#!/usr/bin/env python3
"""Sign a release's ``manifest.json`` with Ed25519.

    HARMONIA_COMPONENTS_SIGNING_KEY=<base64 seed> python sign.py DIST [--key-id harmonia-components-1]

Reads the private key (base64 of the raw 32-byte seed) ONLY from the env var
``HARMONIA_COMPONENTS_SIGNING_KEY`` (the CI secret), writes ``manifest.sig``
(base64 of the 64-byte signature over the exact manifest bytes) and ``KEY_ID``,
and prints the public key so it can be compared with the one pinned in the app.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harmonia_components import manifest, signing  # noqa: E402

ENV = "HARMONIA_COMPONENTS_SIGNING_KEY"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dist", type=Path, help="release directory containing manifest.json")
    ap.add_argument("--key-id", default=signing.DEFAULT_KEY_ID)
    args = ap.parse_args(argv)
    seed = os.environ.get(ENV, "").strip()
    if not seed:
        ap.error(f"{ENV} is not set")
    data = (args.dist / manifest.MANIFEST).read_bytes()
    sig = signing.sign(data, seed)
    (args.dist / manifest.SIGNATURE).write_text(sig + "\n", encoding="ascii")
    (args.dist / manifest.KEY_ID_FILE).write_text(args.key_id + "\n", encoding="utf-8")
    print(f"signed {args.dist / manifest.MANIFEST} with key {args.key_id}")
    print(f"public key: {signing.public_key_of(seed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
