#!/usr/bin/env python3
"""Verify a component release directory: signature, schema, every file's size
+ sha256, and every archive's layout.

    python verify.py DIST --public-key <base64> [--key-id harmonia-components-1]
    python verify.py DIST --trusted-keys keys.json      # {"key id": "base64 public key"}
    python verify.py DIST --keys-dir keys               # every keys/<key id>.pub
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harmonia_components import manifest, signing  # noqa: E402


def load_keys_dir(directory: Path) -> dict:
    """``{key id: base64 public key}`` from ``<directory>/<key id>.pub``."""
    return {p.stem: p.read_text(encoding="ascii").strip() for p in sorted(Path(directory).glob("*.pub"))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dist", type=Path)
    ap.add_argument("--public-key", help="base64 raw 32-byte Ed25519 public key")
    ap.add_argument("--key-id", default=signing.DEFAULT_KEY_ID)
    ap.add_argument("--trusted-keys", type=Path, help="JSON {key_id: public key}")
    ap.add_argument("--keys-dir", type=Path, help="directory of <key id>.pub files (base64 public key)")
    args = ap.parse_args(argv)
    if args.keys_dir:
        keys = load_keys_dir(args.keys_dir)
        if not keys:
            ap.error(f"no <key id>.pub files in {args.keys_dir}")
    elif args.trusted_keys:
        keys = json.loads(args.trusted_keys.read_text(encoding="utf-8"))
    elif args.public_key:
        keys = {args.key_id: args.public_key}
    else:
        ap.error("pass --public-key, --trusted-keys or --keys-dir")
    try:
        m = manifest.verify_release(args.dist, keys)
    except (manifest.ManifestError, signing.SignatureError, ValueError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK release {m['release']} (schema {m['schema']}, created {m['created_at']})")
    for comp in m["components"]:
        print(f"  {comp['name']} {comp['version']} [{comp['license']}]: source + {', '.join(sorted(comp['builds']))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
