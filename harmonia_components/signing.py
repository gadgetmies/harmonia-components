"""Ed25519 signing of ``manifest.json`` (contract "Signed manifest").

* private key: base64 (standard) of the raw 32-byte seed
  (env ``HARMONIA_COMPONENTS_SIGNING_KEY`` in CI);
* public key: base64 of the raw 32-byte key;
* ``manifest.sig``: base64 (standard, padded) of the raw 64-byte signature over
  the exact ``manifest.json`` bytes; ``KEY_ID`` holds the key id.
"""
from __future__ import annotations

import base64
import binascii
from typing import Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

DEFAULT_KEY_ID = "harmonia-components-1"
_RAW = serialization.Encoding.Raw


class SignatureError(ValueError):
    pass


def _b64decode(value: str, size: int, what: str) -> bytes:
    try:
        raw = base64.b64decode(value.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SignatureError(f"{what}: not valid base64") from exc
    if len(raw) != size:
        raise SignatureError(f"{what}: expected {size} bytes, got {len(raw)}")
    return raw


def generate() -> Tuple[str, str]:
    """Return ``(private_seed_b64, public_key_b64)``."""
    key = Ed25519PrivateKey.generate()
    seed = key.private_bytes(_RAW, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    pub = key.public_key().public_bytes(_RAW, serialization.PublicFormat.Raw)
    return base64.b64encode(seed).decode(), base64.b64encode(pub).decode()


def public_key_of(seed_b64: str) -> str:
    key = Ed25519PrivateKey.from_private_bytes(_b64decode(seed_b64, 32, "signing key"))
    return base64.b64encode(key.public_key().public_bytes(_RAW, serialization.PublicFormat.Raw)).decode()


def sign(data: bytes, seed_b64: str) -> str:
    key = Ed25519PrivateKey.from_private_bytes(_b64decode(seed_b64, 32, "signing key"))
    return base64.b64encode(key.sign(data)).decode()


def verify(data: bytes, signature_b64: str, public_key_b64: str) -> None:
    pub = Ed25519PublicKey.from_public_bytes(_b64decode(public_key_b64, 32, "public key"))
    sig = _b64decode(signature_b64, 64, "signature")
    try:
        pub.verify(sig, data)
    except InvalidSignature as exc:
        raise SignatureError("manifest signature does not verify") from exc
