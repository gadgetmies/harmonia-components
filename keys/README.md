# Public signing keys

Each `<key id>.pub` file holds one Ed25519 public key: base64 (standard,
padded) of the raw 32-byte key, on one line. A release's `KEY_ID` file names
the key that signed its `manifest.json`; `verify.py --keys-dir keys` trusts
every `.pub` file in this directory.

Only public keys belong here. Private seeds are never committed (see
`MAINTAINERS.md`).

| key id | status |
|---|---|
| `harmonia-components-1` | active (generated 2026-10-28) |
