#!/usr/bin/env python3
"""Generate an Ed25519 signing key pair for component manifests.

    python keygen.py --private-out /secure/place/harmonia-components-1.key [--key-id harmonia-components-1]

Writes the private seed (base64, the value of the repository secret
``COMPONENTS_SIGNING_KEY``; ``sign.py`` reads it from the env var
``HARMONIA_COMPONENTS_SIGNING_KEY``) ONLY to ``--private-out`` (mode 0600,
refuses to overwrite, refuses a path inside this git repository) and prints
the key id + public key to commit as keys/<key id>.pub and to pin in the
desktop app. Never commit the seed.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harmonia_components import signing  # noqa: E402


def _inside_repo(path: Path) -> bool:
    try:
        top = subprocess.run(
            ["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "--show-toplevel"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return False
    try:
        path.resolve().relative_to(Path(top).resolve())
        return True
    except ValueError:
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--private-out", required=True, type=Path, help="file to write the private seed to")
    ap.add_argument("--key-id", default=signing.DEFAULT_KEY_ID)
    args = ap.parse_args(argv)
    out = args.private_out
    if _inside_repo(out.parent if not out.exists() else out):
        ap.error(f"refusing to write a private key inside the git repository: {out}")
    seed, pub = signing.generate()
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as fh:
        fh.write(seed + "\n")
    print(f"key id: {args.key_id}")
    print(f"public key: {pub}")
    print(f"private seed written to {out} (its content is the value of the COMPONENTS_SIGNING_KEY repository secret)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
