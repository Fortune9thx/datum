# DATUM -- status

Last updated: 2026-09-24, during initial build. No deploy attempt, no
GitHub push, no Vercel deploy have been made -- by explicit instruction for
this build session, not because any of the three failed.

## Deploy status

| Target | Status |
|---|---|
| Studio Dev (chain 61997) contract deploy | **Not attempted.** See "commands for the user" below. |
| GitHub push | **Not attempted.** Local git repo is initialized and committed on `main`. |
| Vercel deploy | **Not attempted.** |

No transaction hashes, no contract address, no Vercel URL exist for this
project yet. Any of those appearing anywhere else in this repo's docs is a
placeholder, not a real deployment artifact.

## Local toolchain: what actually happened (real captured output)

This machine has a pre-existing, long-standing gap affecting
`genvm-lint`'s runtime-dependent commands and `gltest`'s direct-mode
deploy, documented across every prior GenLayer project built on this
machine. DATUM hits the exact same wall. Below is the real, current
evidence for THIS project (not inherited/assumed from prior projects).

### 1. `genvm-lint lint` -- PASSES

Pure AST-based static safety checks, no runtime/runner needed.

```
$ PYTHONIOENCODING=utf-8 genvm-lint lint contracts/Datum.py
✓ Lint passed (3 checks)

$ PYTHONIOENCODING=utf-8 genvm-lint lint artifacts/Datum.bundled.py
✓ Lint passed (3 checks)
```

(`PYTHONIOENCODING=utf-8` is required only because this Windows console's
default `cp1252` codec can't print the tool's own `\u2713` checkmark
character -- an unrelated, separately-observed Windows console encoding
issue, not a GenLayer toolchain problem.)

### 2. `genvm-lint check` / `validate` / `schema` -- FAIL

These commands actually try to load and execute the contract module
against a GenVM runner bundle. All three fail identically:

```
$ PYTHONIOENCODING=utf-8 genvm-lint check artifacts/Datum.bundled.py
Warning: could not resolve latest GenVM version from genlayerlabs/genvm-manager
  (HTTP Error 403: rate limit exceeded); checking the local cache

✓ Lint passed (3 checks)
✗ Validation failed
  Failed to load contract: name 'gl' is not defined
```

`schema` produces the identical `Failed to load contract: name 'gl' is not
defined` failure.

### 3. `gltest` direct-mode deploy -- FAILS (different, earlier failure point)

`tests/direct/test_datum_contract.py` is written and would exercise the
real create/accept/adjudicate/claim flow, but its `contract` fixture
cannot get past `direct_deploy(...)`:

```
$ gltest tests/direct/test_datum_contract.py -q
...
Downloading https://github.com/genlayerlabs/genvm-manager/releases/download/v0.3.0/genvm-runners-all.tar.xz...
Downloading https://github.com/genlayerlabs/genvm-manager/releases/download/v0.3.0/genvm-universal.tar.xz...
E   FileNotFoundError: No GenVM runner bundle for v0.3.0; tried genvm-runners-all.tar.xz, genvm-universal.tar.xz
```

The same failure occurs for `sdk_version="v0.3.0-rc7"` and
`sdk_version="v0.2.16"` (the latter has a *cached* tarball under
`~/.cache/gltest-direct/genvm-universal-v0.2.16.tar.xz` from a prior
project, but gltest's own resolution logic did not pick it up for this
run -- not investigated further, out of scope for this session).

**Root cause, as far as this session could observe it:** GitHub API rate
limiting (explicitly reported by `genvm-lint`'s own warning above) is
blocking runner-bundle resolution/download for `gltest` and
`genvm-lint`'s runtime-dependent commands alike. This matches the
long-standing, cross-project "genvm-lint / gltest broken locally" gap
already on file for this machine, and is consistent with (though not
proven identical to) the open upstream bug genlayer-studio#1757
("invalid_contract runner malformed") that has separately blocked Studio
Dev's *hosted* deploy path on a prior project this session's owner ran.

### 4. Primary verified coverage -- `contracts/datum_lib.py` unit tests

`datum_lib.py` has zero genlayer imports, so it needs no runner and no
network access at all:

```
$ python -m pytest tests/direct/test_datum_lib.py -q
55 passed in 0.19s
```

This is DATUM's actual, currently-trustworthy test evidence: every create
refusal, the constitution hash freeze, unit conversion, volatile-key
neutralization, the full envelope acceptance/rejection logic (agree ->
YES/NO, missing -> INCONCLUSIVE, conflict -> INCONCLUSIVE, preliminary
blocked, station mismatch, quake-outside-bbox), and the economics math
(fee split, appeal bond floor, payout dust) are all exercised directly.

### 5. Bundle size check -- PASSES

```
$ python scripts/build_bundle.py
Wrote artifacts/Datum.bundled.py (40190 bytes)
OK: bundle is under the 52224-byte ceiling (12034 bytes to spare)
```

## Exact commands for the user to run themselves

### (a) Create + push the GitHub repo

```bash
cd C:\Users\HP\Desktop\datum
gh repo create datum --private --source=. --remote=origin
git push -u origin main
```

(Swap `--private` for `--public` if that's the intent; confirm `gh auth
status` is already logged in as the right account first.)

### (b) Deploy the frontend to Vercel

```bash
cd C:\Users\HP\Desktop\datum\frontend
npm install
vercel link
vercel env add NEXT_PUBLIC_DATUM_CONTRACT_ADDRESS   # once a contract exists
vercel --prod
```

### (c) Attempt the Studio Dev contract deploy

**Try a tiny Hello-world contract with the exact same `Depends` line first**
as a smoke test, per the spec's own guidance -- this isolates whether
genlayer-studio#1757 ("invalid_contract runner malformed") is still
blocking Studio Dev's hosted deploy path generally, before spending a real
transaction on DATUM itself:

```python
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
from genlayer import *

class Hello(gl.Contract):
    def __init__(self):
        pass

    @gl.public.view
    def ping(self) -> str:
        return "pong"
```

Deploy that first via the Studio Dev UI (https://studio-dev.genlayer.com)
or `genlayer deploy`. If that smoke test itself fails with an
`invalid_contract` / runner-malformed-shaped error, the blocker is
platform-side (genlayer-studio#1757) and DATUM's own deploy will hit the
same wall regardless of anything in this repo.

Once the smoke test succeeds, deploy DATUM itself:

```bash
cd C:\Users\HP\Desktop\datum
npm install
DATUM_KEYSTORE_PATH=/path/to/keystore.json DATUM_KEYSTORE_PASSWORD=... node scripts/deploy.mjs
```

`scripts/deploy.mjs` deploys `artifacts/Datum.bundled.py` (never the
un-bundled `contracts/Datum.py`) and writes `scripts/deployed.json` with
the resulting address and tx hash.

## Open questions / missing prerequisites found (not blocking, just noted)

- No `gh` CLI auth state was checked in this session (no GitHub action was
  attempted, per instruction).
- No Vercel project link was checked or created.
- No Studio Dev keystore/private key was found or expected in this repo
  (correctly -- none should ever be committed). The user will need to
  supply `DATUM_KEYSTORE_PATH` / `DATUM_KEYSTORE_PASSWORD` themselves.
- `frontend/node_modules` was never installed in this session, so the
  Next.js shell has not actually been run end-to-end (see docs/STEWARD.md).
