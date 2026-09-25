# DATUM -- status

Last updated: 2026-09-24. GitHub and Vercel are both live. Studio Dev
contract deploy has been attempted twice (documented below) and is
currently blocked by an infra-side FeeManager revert, not by anything in
this repo.

## Deploy status

| Target | Status |
|---|---|
| GitHub push | **Live.** https://github.com/Fortune9thx/datum, public, `main`. |
| Vercel deploy | **Live.** https://datum-gamma.vercel.app, fails closed everywhere (see below). |
| Studio Dev (chain 61997) contract deploy | **Attempted twice, both reverted.** `FeeValueMustBeNonZero`, infra-side. See "Hosted deploy proof" below. |

No contract address exists for this project yet. `NEXT_PUBLIC_DATUM_CONTRACT_ADDRESS`
is unset in Vercel; the frontend's `probeContract()` correctly reports
`no-address` and shows nothing but zeros and an honest banner.

## Hosted deploy proof (2026-09-24)

Deployer: `bradbury-deploy` (`0xc6e6d3b2accaececeb40ad4bd3df123ddcb4e537`),
already unlocked in the `genlayer` CLI's own session on this machine --
balance 60.10303647329982136 GEN before and after every attempt below (all
reverts were free; no GEN was actually spent). Network: `studio-dev`,
chain 61997, confirmed via `genlayer config get`.

### Attempt A -- minimal Hello, same Depends line, CLI

Studio UI was not used for this attempt: this is a non-interactive session
with no browser/wallet-extension access, so the CLI (which already had an
unlocked, funded account for this network) was used instead of the UI.

`artifacts/smoke/Hello.py` (295 bytes):

```python
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
from genlayer import *


class Hello(gl.Contract):
    greeting: str

    def __init__(self):
        self.greeting = "hello"

    @gl.public.view
    def get_greeting(self) -> str:
        return self.greeting
```

Three separate fee configurations were tried, all with the identical
result:

```
$ genlayer deploy --contract artifacts/smoke/Hello.py --args []
Error: Transaction reverted: EVM tx 0x40874d2f...25f3f. FeeValueMustBeNonZero(1)

$ genlayer deploy --contract artifacts/smoke/Hello.py --args [] --fee-preset standard
Error: Transaction reverted: EVM tx 0xb117ac96...8f9338. FeeValueMustBeNonZero(1)

$ genlayer deploy --contract artifacts/smoke/Hello.py --args [] --fees {distribution...} --fee-value 100000000000010352
Error: Transaction reverted: EVM tx 0xbe2705dc...81c3. FeeValueMustBeNonZero(3)
```

Method: CLI. Timestamp: 2026-09-24T21:13-21:14Z. Result: **FINISHED_WITH_ERROR
(reverted before execution)**, not FINALIZED. The `(1)` / `(3)` arguments
to `FeeValueMustBeNonZero` change with the fee distribution passed, which
means the revert is coming from the consensus/FeeManager contract's own
per-message-allocation accounting on Studio Dev, not from anything
contract-specific -- it happens identically for a 295-byte, zero-argument,
zero-logic contract.

### Attempt B -- DATUM bundle, same header, CLI

```
$ genlayer deploy --contract artifacts/Datum.bundled.py --args [] --fee-value 100000000000010352
Error: Transaction reverted: EVM tx 0xfe45b144...5d7b. FeeValueMustBeNonZero(1)
```

Method: CLI. Timestamp: 2026-09-24T21:15Z. Result: **FINISHED_WITH_ERROR**,
identical failure mode to Attempt A.

### Conclusion

A failed and B failed, with the exact same error, on the exact same fee
accounting path, regardless of contract size or content. Per this
project's own rule for that outcome: **hosted deploy is currently broken
on Studio Dev, and no further GEN was spent chasing it.**

This is a genuinely different failure signature than the previously-
documented `invalid_contract` / "runner malformed" bug
(genlayer-studio#1757) that blocked a prior Studio Dev deploy on this
machine -- that one failed at contract *loading*; this one reverts on-chain
during the FeeManager's own message-fee distribution, before the contract
is even reached. Both point at the same practical conclusion for a
steward reading this: **Studio Dev's hosted deploy path is not currently
usable from this machine, for reasons outside this repo's code.**
`docs/localnet.md` documents the equivalent flow run locally instead, as
evidence the contract itself works.

**Never claim "contracts may only be 300 bytes"** -- that is not what
either failure was. The GenVM size ceiling remains ~52,224 bytes, and
DATUM's bundle (40,881 bytes) is well inside it, independently confirmed
by `genvm-lint lint` and the bundler's own size check below.

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
Lint passed (3 checks)

$ PYTHONIOENCODING=utf-8 genvm-lint lint artifacts/Datum.bundled.py
Lint passed (3 checks)
```

(`PYTHONIOENCODING=utf-8` is required only because this Windows console's
default `cp1252` codec can't print the tool's own checkmark character --
an unrelated, separately-observed Windows console encoding issue, not a
GenLayer toolchain problem.)

### 2. `genvm-lint check` / `validate` / `schema` -- FAIL

These commands actually try to load and execute the contract module
against a GenVM runner bundle. All three fail identically:

```
$ PYTHONIOENCODING=utf-8 genvm-lint check artifacts/Datum.bundled.py
Warning: could not resolve latest GenVM version from genlayerlabs/genvm-manager
  (HTTP Error 403: rate limit exceeded); checking the local cache

Lint passed (3 checks)
Validation failed
  Failed to load contract: name gl is not defined
```

`schema` produces the identical "Failed to load contract" failure.

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

The same failure occurs for `sdk_version=v0.3.0-rc7` and
`sdk_version=v0.2.16` (the latter has a *cached* tarball under
`~/.cache/gltest-direct/genvm-universal-v0.2.16.tar.xz` from a prior
project, but gltest's own resolution logic did not pick it up for this
run -- not investigated further, out of scope for this session).

**Root cause, as far as this session could observe it:** GitHub API rate
limiting (explicitly reported by `genvm-lint`'s own warning above) is
blocking runner-bundle resolution/download for `gltest` and
`genvm-lint`'s runtime-dependent commands alike. This matches the
long-standing, cross-project "genvm-lint / gltest broken locally" gap
already on file for this machine, and is separate from (see above) the
FeeManager-side revert blocking the hosted deploy path.

### 4. Primary verified coverage -- `contracts/datum_lib.py` unit tests

`datum_lib.py` has zero genlayer imports, so it needs no runner and no
network access at all. This includes the adjudication prompt builder
(`_adjudication_prompt`), relocated into this module specifically so it
is testable the same way:

```
$ python -m pytest tests/direct/test_datum_lib.py -q
59 passed in 0.21s
```

This is DATUM's actual, currently-trustworthy test evidence: every create
refusal, the constitution hash freeze, unit conversion, volatile-key
neutralization, the full envelope acceptance/rejection logic (agree ->
YES/NO, missing -> INCONCLUSIVE, conflict -> INCONCLUSIVE, preliminary
blocked, station mismatch, quake-outside-bbox), the economics math (fee
split, appeal bond floor, payout dust), and the adjudication prompt's
depth/lat-lon fields for QUAKES, are all exercised directly.

### 5. Bundle size check -- PASSES

```
$ python scripts/build_bundle.py
Wrote artifacts/Datum.bundled.py (40881 bytes)
OK: bundle is under the 52224-byte ceiling (11343 bytes to spare)
```

## Frontend

Live at https://datum-gamma.vercel.app. Verified in-browser (desktop and
375px mobile, zero console errors): the marketing long-scroll at `/`, and
`/app`, `/app/create`, `/app/stations`, `/app/portfolio`, `/app/activity`,
`/app/docs`, `/app/e/:id` all render, all fail closed with an honest,
state-specific banner (no address / no code / RPC down / live), and
`/board` + `/e/:id` redirect to their `/app` equivalents including on a
direct URL load (no 404 on refresh).

Writes (`create_event`, `accept_event`, `adjudicate`, `finalize`, `appeal`,
`re_adjudicate`, `lapse_appeal`, `cancel_event`, `expire_event`, `claim`,
`recover_refund`, `reclaim_bonds`) are wired through `genlayer-js` against
an injected wallet, correctly disabled with a specific reason string
(no address / no code / RPC down / no wallet / wrong chain) whenever any
of those is true. They remain **unexercised end-to-end** -- there is no
live contract yet to write to.

## What the user should run themselves once Studio Dev's FeeManager issue clears

```bash
cd C:\Users\HP\Desktop\datum
genlayer deploy --contract artifacts/Datum.bundled.py --args []
```

If that still reverts with `FeeValueMustBeNonZero`, the platform-side
issue documented above has not yet been fixed upstream -- retry later
rather than experimenting further with fee parameters, since three
different configurations all failed identically in this session.

Once a deploy succeeds:

```bash
cd C:\Users\HP\Desktop\datum\frontend
vercel env add NEXT_PUBLIC_DATUM_CONTRACT_ADDRESS production
vercel env add NEXT_PUBLIC_DATUM_CONTRACT_ADDRESS preview
vercel --prod --yes
```

Then confirm `eth_getCode` is non-empty and the live banner on
https://datum-gamma.vercel.app shows the address.

## Open questions / missing prerequisites found (not blocking)

- No `gh` CLI or Vercel CLI auth issues -- both worked directly.
- The `bradbury-deploy` keystore's raw password was never read or printed;
  the `genlayer` CLI's own unlocked session was used for the deploy
  attempts instead, so no secret left the CLI's own key management.
- Studio Dev UI (browser + MetaMask) was not exercised in this session --
  no interactive browser/wallet access. If the user tries the UI path and
  it also reverts on fee accounting, that corroborates this being a
  platform-wide issue rather than a CLI-specific one.
