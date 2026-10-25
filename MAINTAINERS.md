# Maintainer guide: signing key, secrets, releases

The release workflow needs one secret and one variable:

| name | kind | value |
|---|---|---|
| `COMPONENTS_SIGNING_KEY` | repository **secret** | the private Ed25519 seed: base64 of the raw 32 bytes, exactly as `keygen.py` writes it (one line) |
| `COMPONENTS_KEY_ID` | repository **variable** (a secret also works) | the key id, e.g. `harmonia-components-1` (default when unset) |

and the matching public key committed as `keys/<key id>.pub`. A release
without these fails in its first job, before any build starts.

## 1. Create the signing key (once, on your own machine)

```sh
git clone https://github.com/gadgetmies/harmonia-components
cd harmonia-components
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python keygen.py --private-out ~/harmonia-components-1.key --key-id harmonia-components-1
```

It prints:

```
key id: harmonia-components-1
public key: <44 base64 characters>
private seed written to /Users/<you>/harmonia-components-1.key (...)
```

`keygen.py` writes the private seed with mode 0600, refuses to overwrite a
file, and refuses any path inside this repository. **The private seed must
never be committed, pasted into an issue, or stored in the repository.**

Store the private seed safely: copy the file's one line into a password
manager entry (for example "Harmonia components signing key
harmonia-components-1"), set the secret in step 2, then delete the file:

```sh
rm ~/harmonia-components-1.key
```

## 2. Set the repository secret and variable

**Web UI:** github.com/gadgetmies/harmonia-components → **Settings** →
**Secrets and variables** → **Actions**:

- **Secrets** tab → **New repository secret** → Name `COMPONENTS_SIGNING_KEY`,
  Secret: the one line from the key file (the base64 seed) → **Add secret**.
- **Variables** tab → **New repository variable** → Name `COMPONENTS_KEY_ID`,
  Value `harmonia-components-1` → **Add variable**.

**Or with the GitHub CLI** (before deleting the key file):

```sh
gh secret set COMPONENTS_SIGNING_KEY --repo gadgetmies/harmonia-components < ~/harmonia-components-1.key
gh variable set COMPONENTS_KEY_ID --repo gadgetmies/harmonia-components --body harmonia-components-1
```

Optional: the publish job runs in the GitHub environment
`components-release` (created on first use). Under **Settings** →
**Environments** → `components-release` you can add required reviewers, so
every release waits for your approval before it is signed and published.

## 3. Publish the public key

```sh
printf '%s\n' '<public key printed by keygen.py>' > keys/harmonia-components-1.pub
```

Also fill in the "Public signing key" table in `README.md`, then commit and
push:

```sh
git add keys/harmonia-components-1.pub README.md
git commit -m "Publish the harmonia-components-1 public key"
git push origin main
```

## 4. Pin the same public key in the desktop app

In the Harmonia desktop app, add the key to `TRUSTED_KEYS` in
`apps/desktop/component_store.py`:

```python
TRUSTED_KEYS = {"harmonia-components-1": "<public key printed by keygen.py>"}
```

A packaged app trusts only these keys, so it refuses every manifest until
this is shipped.

## 5. Cut a release

Optional dry run first (builds every platform, no signing, no release): on
GitHub → **Actions** → **release** → **Run workflow**, enter the release id
(e.g. `2026.10.25.1`) and untick **publish**. The unsigned release directory
is kept as the workflow artifact `component-release-<release>-unsigned`.

Then push the tag (release id = tag = `YYYY.MM.DD.N`, never reused):

```sh
git checkout main && git pull
git tag 2026.10.25.1
git push origin 2026.10.25.1
```

(Or **Run workflow** with **publish** ticked: the workflow creates the tag
itself on the commit it ran on.)

When the run is green, the release is at
`https://github.com/gadgetmies/harmonia-components/releases/tag/2026.10.25.1`
and is the one `releases/latest/download/manifest.json` serves. Check it as
described in `README.md` → "Verifying a download".

A version bump of a component means: update `versions.toml` (download the new
tarball and record its sha256), push, and cut a new release.

## Key rotation

Generate `harmonia-components-2` (steps 1, 3, 4 with the new id), ship a desktop app that trusts both keys, then switch `COMPONENTS_SIGNING_KEY` + `COMPONENTS_KEY_ID` to the new key and keep `keys/harmonia-components-1.pub` for verifying old releases.
If a private key leaks, remove it from the desktop's `TRUSTED_KEYS` at once, rotate as above, and mark the affected releases in `keys/README.md`.
