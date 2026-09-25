# DATUM -- status

Last updated: 2026-09-25. **The contract is deployed and live on Studio
Next.** GitHub, Vercel, and the contract are all live and wired together.
The long-running deploy blocker documented below was finally solved --
the root cause was fee-distribution parameters plus a CLI argument-parsing
gotcha, not the "client-side CLI bug" the earlier sections conclude. Those
earlier sections are kept verbatim as an audit trail of a wrong (then
corrected) diagnosis; **read the "SOLVED" section for what actually
happened.**

## Deploy status

| Target | Status |
|---|---|
| GitHub push | **Live.** https://github.com/Fortune9thx/datum, public, `main`. |
| Vercel deploy | **Live.** https://datum-gamma.vercel.app, reading the live contract. |
| Studio Next (chain 61997) contract deploy | **LIVE.** `0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3` |

- **Contract address:** `0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3`
- **Deploy tx:** `0x84b5319b1ca744c47a0c3c36894e69cf3466c0cc3c876f4fcecf8315c440ae03` (ACCEPTED)
- **Explorer:** https://explorer-studio-dev.genlayer.com/address/0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3
- **Deployer / treasury:** `0xC6E6d3b2acCaECeCeB40Ad4bD3dF123DDCB4e537`
- Machine-readable record: `deploy/deployments.json`

`NEXT_PUBLIC_DATUM_CONTRACT_ADDRESS` is set in Vercel (production,
preview, development); the live site's board shows the **LIVE** banner
with this address and reads real zeros from the real contract.

## SOLVED (2026-09-25): what the deploy blocker actually was

Two separate problems, stacked, both in how the CLI invocation was
constructed -- **not** a bug in the CLI itself, and not the network:

1. **Fee distribution, not fee value.** Every failed attempt passed only
   `--fee-value` (letting the CLI derive `distribution` itself, which
   defaults to `rotations: ["3"]`), or passed a partial `--fees`
   distribution. That reliably produced `FeeValueMustBeNonZero(N)` with
   the transaction never reaching the chain. Passing a **complete**
   `--fees` distribution copied from a real successful on-chain deploy --
   `rotations: [0]`, `appealRounds: 0`, plus the explicit
   `executionBudgetPerRound` / gas-price / time-unit-allocation fields --
   made the transaction broadcast and reach consensus on the first try.
   The earlier `rotations: [0]`-only attempt failed because the *rest* of
   the distribution was still missing, which is why that partial test
   was misread as "rotations makes no difference."
2. **`--args` argument parsing.** `--args '["0xADDRESS"]'` is parsed as a
   single argument whose value is a JSON **array**, not as an argument
   list -- so the contract received `['0x...']` where it expected a
   string, and the constructor crashed with
   `AttributeError: 'list' object has no attribute 'encode'`. This was
   only visible because the transaction finally reached the chain and
   produced a real GenVM traceback. Correct form for a single string
   argument: `--args '"0xADDRESS"'` (JSON-quoted). A bare `0x...` would be
   auto-detected as an *address* type, which this constructor's `str`
   parameter also rejects.

**The earlier "this is a client-side `genlayer` CLI bug" conclusion in the
sections below was wrong.** It was a reasonable read of the evidence at
the time (7 failures, nothing on-chain, other accounts succeeding) but the
actual cause was recoverable from the caller's side all along. Corrected
here rather than quietly edited out of the earlier sections, so the
reasoning trail stays auditable.

### Live verification performed

```
$ genlayer call 0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3 get_config
{"chain_id": 61997, "network": "studio-dev", "value_scale": 100, ...}   # real on-chain read

$ genlayer write 0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3 expire_event --args "999999999999" ...
tx 0x01809ec4ac941cb0b6feba525599153dfc0c1cc13e87cd2da295714fac31fe71
decoded leader result: b'\x01event not found'   # the contract's OWN UserError, executed on-chain
```

The write test deliberately targets a nonexistent event id: it proves the
real write path executes real contract logic and returns the contract's
own `USER_ERRORS` string from a real consensus round, without spending a
stake.

### Not yet smoke-tested live, and why

`create_event` (and every other payable method) could **not** be called
from the CLI: `genlayer write` has no flag for attaching native GEN to a
payable method (`--help` confirms; the underlying `genlayer-js`
`writeContract` supports `value`, the CLI simply does not expose it). A
real `create_event` therefore needs either the frontend with an injected
wallet, or a direct `genlayer-js` script with a decrypted keystore. This
is the one remaining unexercised path -- the contract is live and
verified for reads and non-payable writes, but no GEN has moved through
it yet.

### A real frontend bug this deploy exposed

`probeContract()` used `eth_getCode` to decide whether a contract is
live. A GenLayer intelligent contract is **not** an EVM contract:
`eth_getCode` returns `0x` for this live, responding address. The
frontend would therefore have shown "No code at this address. Studio Next
was reset. Redeploy." for a perfectly healthy contract. Fixed to use
`gen_getContractSchema`, which returns a full method schema for a live
contract and JSON-RPC error `-32001` for an address with nothing deployed
-- verified against both the live address and a bogus one. Only an actual
deploy could have surfaced this.

## Hosted deploy proof

Deployer: `bradbury-deploy` (`0xc6e6d3b2accaececeb40ad4bd3df123ddcb4e537`),
already unlocked in the `genlayer` CLI's own session on this machine --
balance 60.10303647329982136 GEN unchanged across every attempt below (all
reverts were free; no GEN was actually spent). Network: `studio-dev`,
chain 61997, confirmed via `genlayer config get`.

### 2026-09-24: initial attempts, wrongly concluded "network broken"

Three deploy attempts (a 295-byte zero-arg Hello contract, twice with
different fee configs, and the DATUM bundle once) all reverted identically
with `FeeValueMustBeNonZero`. At the time this was written up as "Studio
Dev's hosted deploy path is not currently usable" -- **that conclusion was
wrong**, corrected below.

### 2026-09-25: re-investigation, prompted by a direct steward request to check the explorer

**The network is healthy.** `curl https://explorer-studio-dev.genlayer.com/api/transactions?limit=15`
shows a steady stream of real `FINALIZED`/`ACCEPTED` transactions from
other accounts, including deploys, right up to the current time --
several with the identical `fee_value` this project's own CLI had
attempted (`100000000000010352`), successfully FINALIZED. One deploy in
particular (`0x7654c63882e5cd6264142b93aa3b2d847de431ce8f27ad47b8bf2e458868ac88`,
`FINALIZED`) used the exact same official Storage boilerplate example and
the exact same `Depends` hash this project is pinned to
(`5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng`).

**None of this project's own "reverted" transaction hashes exist on-chain
at all.** `curl https://explorer-studio-dev.genlayer.com/api/transactions/<hash>`
for every hash recorded in the 2026-09-24 attempts (and every hash from
the fresh attempts below) returns `{"detail":"Transaction not found"}`.
The `genlayer` CLI's own reported "Transaction reverted: ... EVM tx
0x..." is therefore **not describing a real, mined, reverted on-chain
transaction** -- it is a client-side failure (a local simulation or
pre-flight check inside the CLI/SDK) that happens before anything is
actually broadcast. The CLI's own error message is misleading about this.

**Re-attempted with several different configurations, all failing
identically, all client-side (no tx ever found on-chain):**

```
$ genlayer deploy --contract artifacts/Datum.bundled.py --args '["0xC6E6...4537"]' --fee-value 100000000000010352
Error: Transaction reverted: EVM tx 0x92fb53e9...bf8ce8. FeeValueMustBeNonZero(1)

$ genlayer deploy --contract artifacts/Datum.bundled.py --args '["0xC6E6...4537"]' \
    --fees '{"distribution":{"leaderTimeunitsAllocation":"100","validatorTimeunitsAllocation":"200","rotations":[0]}}' \
    --fee-value 100000000000010352
Error: Transaction reverted: EVM tx 0xce32d7ad...9e5e9c56. FeeValueMustBeNonZero(3)

$ genlayer deploy --contract artifacts/Datum.bundled.py --args '["0xC6E6...4537"]' --fee-value 500000000000000
Error: Transaction reverted: EVM tx 0x4758300f...d76fd80d4. FeeValueMustBeNonZero(1)

$ genlayer deploy --contract artifacts/smoke/Hello.py --args [] --fee-value 200000000000000
Error: Transaction reverted: EVM tx 0x88ed5648...0855a7dd6. FeeValueMustBeNonZero(1)
```

Notably, the successful on-chain deploy's actual `fee_value` was
`94643100002588` (~9.5e13 wei, ~0.0000946 GEN) -- roughly **1000x smaller**
than what this CLI's own `genlayer estimate-fees` returns
(`100000000000010352`, ~1e17 wei, ~0.1 GEN) for the same network. Explicitly
passing a `--fee-value` in that smaller order of magnitude was tried too
(see the third command above) and still failed identically -- so the bug
is not simply "the estimate is 1000x too high"; something about how this
CLI version constructs/validates the fee message allocation locally is
broken, independent of the number passed.

**Version check, to rule out a stale local CLI:** `npm view genlayer
dist-tags` shows `rc: '0.40.0-rc.3'` (published 2026-09-03) as the newest
available `genlayer` CLI release -- already installed, confirmed via
`genlayer --version`. The stable channel (`latest: '0.39.2'`) does not
know the `studio-dev` network at all (`Unknown network: studio-dev`), so
it cannot be used as a fallback for this network. **`0.40.0-rc.3` is the
only released CLI version that supports Studio Next, and it is the
version failing.** Whatever tool produced the successful transactions
above (Studio UI, a different `genlayer-js` build, or an internal script)
is evidently not hitting the same client-side bug this CLI's `deploy`
command has.

### Conclusion

**The network is not broken. This is a real, reproducible bug in the
`genlayer` CLI (v0.40.0-rc.3) deploy path on this machine** -- every
attempt fails identically regardless of contract size/content, `--args`,
or `--fee-value` magnitude, and none of them ever reach the chain at all
(confirmed via the explorer, not assumed). This supersedes the 2026-09-24
writeup's "hosted deploy path is not currently usable" conclusion, which
was reasonable given the evidence available at the time but is now known
to be too broad.

**Never claim "contracts may only be 300 bytes"** -- that was never what
either failure was. The GenVM size ceiling remains ~52,224 bytes, and
DATUM's bundle (40,784 bytes) is well inside it, independently confirmed
by `genvm-lint lint` and the bundler's own size check below.

### 2026-09-25 (later, same day): one more A/B pass, per explicit
    instruction ("hosted A/B once"), before declaring hosted dead

Studio UI was not used -- still a non-interactive session, no
browser/wallet-extension access, so no way to sign through the UI. CLI
used again as the only available client. Both attempts, one each:

```
$ genlayer deploy --contract artifacts/smoke/Hello.py --args [] --fee-value 100000000000010352
Error: Transaction reverted: EVM tx 0x37c6b540...3fbb898. FeeValueMustBeNonZero(1)

$ genlayer deploy --contract artifacts/Datum.bundled.py --args '["0xC6E6...4537"]' --fee-value 100000000000010352
Error: Transaction reverted: EVM tx 0xc71d4ab9...9719f614. FeeValueMustBeNonZero(1)
```

Both hashes confirmed `{"detail":"Transaction not found"}` on the
explorer -- neither ever reached the chain. Deployer balance unchanged
(58.102276059299813895 GEN before and after). Timestamp: 2026-09-25T10:46-10:47Z.

**A failed and B failed. Per this project's own rule: stop spending GEN.**
The CLI-specific client-side bug from the earlier writeup is confirmed
still open, not something that cleared between sessions. The real local
execution recipe is in `docs/STEWARD.md`'s "Local recipe" section --
91 tests (64 unit + 27 gltest direct-mode) passing, covering the happy
path AND the refusal path for every one of the 12 write methods, plus 5
dedicated comparator tests proving a leader that disagrees with an
independent re-fetch is rejected (see `docs/audit.md`'s "Witness
mismatch" section for what that does and does not prove about real
network-level validator disagreement).

### What to try next (still not attempted -- needs interactive access this session does not have)

1. **Studio UI** (https://studio-dev.genlayer.com) -- browser + wallet
   deploy. Given the CLI's failure is confirmed client-side and
   CLI-specific, the UI (a different client) may well work where the CLI
   does not.
2. **Raw `genlayer-js` SDK script**, bypassing the CLI's `deploy` command
   entirely (the pattern `scripts/deploy.mjs` already uses, matching
   `precedence-settler`'s proven-working approach on this same network) --
   needs a real keystore password, which this session does not have and
   will not ask for or guess.
3. If either works, please file the CLI bug upstream
   (`genlayerlabs/genlayer` or wherever `npm genlayer` is tracked) with
   the repro above -- a deploy that never reaches the chain but reports a
   misleading "Transaction reverted" is a real, currently-unfixed bug
   independent of this project.

## Local toolchain: what actually happened (real captured output)

> **Editorial note (2026-09-25):** an earlier revision of this document
> was accidentally truncated mid-rewrite (a `Write` tool call that lost
> everything from this heading onward, unnoticed until a later steward-
> requested strict pass caught the file was 262 lines in git history and
> 138 in the working tree). Restored and updated below with current
> figures. Flagging this plainly rather than quietly fixing it: it is
> exactly the kind of silent-content-loss mistake a rigorous review
> should be able to catch independently, and a reader deserves to know it
> happened rather than assume this document was always complete.

This machine has a long-documented, cross-project history of
`genvm-lint`'s runtime-dependent commands and `gltest`'s direct-mode
deploy failing with `name 'gl' is not defined`, assumed to be a
persistent local gap. **On this project, that assumption turned out to
be wrong.** It was three real, stacked, fixable bugs producing the same
generic symptom every time -- see CHANGELOG.md's 1.1.2 entry for the full
technical writeup. Below is the current, real, all-green evidence.

### 1. `genvm-lint lint` -- PASSES

Pure AST-based static safety checks, no runtime/runner needed.

```
$ PYTHONIOENCODING=utf-8 genvm-lint lint contracts/Datum.py
Lint passed (3 checks)

$ PYTHONIOENCODING=utf-8 genvm-lint lint artifacts/Datum.bundled.py
Lint passed (3 checks)
```

### 2. `genvm-lint check` / `validate` / `schema` -- PASS

```
$ PYTHONIOENCODING=utf-8 genvm-lint check artifacts/Datum.bundled.py
Lint passed (3 checks)
Validation passed
  Contract: Datum
  Methods: 22 (10 view, 12 write)
```

### 3. `gltest` direct-mode deploy -- PASSES, real execution proof

```
$ python -m pytest tests/direct/test_datum_contract.py -q
...........................                                              [100%]
27 passed in 21.13s
```

This deploys `artifacts/Datum.bundled.py` into a real GenVM sandbox
(rebuilding the bundle itself first, since gltest clears its own
`artifacts/` cache directory -- a same-name coincidence with the
bundler's output dir, unrelated to the fix above) and exercises, with
both a happy path AND a refusal test for every one of the 12 write
methods: `create_event` (real GEN attached via `direct_vm.value`) +
constitution-hash freeze + three create-time refusals (below-min-window,
single-publisher, below-min-lead); `accept_event` from a second account
(`direct_vm.prank(direct_bob)`) + a stranger unable to double-accept;
`adjudicate` refusing before window close, and succeeding with a mocked
LLM response through to a stored verdict; `cancel_event` restricted to
the creator, and refused once ACTIVE; `expire_event` slashing the create
bond once the window opens unaccepted, refused before the window starts
and after acceptance; `appeal` refusing a non-party and a post-window
attempt; `re_adjudicate` refusing on a non-APPEALED state, and correctly
resolving the appeal bond (refund if the verdict changed, forfeit if it
didn't) once it succeeds; `lapse_appeal` refusing before the 1h stall and
correctly restoring the prior verdict + forfeiting the bond after it;
`reclaim_bonds` succeeding as a documented no-op for a bonded party on a
terminal event, refusing a stranger and a non-terminal state; and `claim`
actually paying out and zeroing the ledger, refusing an address with
nothing owed. This is a genuine execution proof against real GenVM
storage/event/contract-class wiring, not a mock of the contract's own
logic -- `contracts/datum_lib.py`'s unit tests (below) already cover the
pure logic in isolation; this proves the `gl.contract.Contract` glue
around it actually works on this pinned runner, for every write method,
not just a subset.

**What this does not prove**, stated plainly rather than implied: no
genuine multi-validator disagreement (`gltest` direct-mode has one
in-process leader; it cannot simulate two real GenVM nodes actually
disagreeing at the network level), and no real GEN balance movement (the
`claimable` ledger and `direct_vm.value` are both proven at the
accounting level, not as an actual on-chain value transfer, since there
is no live contract to check a real balance delta against). See
`docs/audit.md`'s "Witness mismatch" section and `docs/localnet.md`.

`genlayer up` (the full Docker-based localnet simulator, a different
path than `gltest` direct-mode, and the one path that WOULD exercise real
multi-validator consensus) was not attempted -- this machine has no
Docker installed. `gltest` direct-mode is a real, if narrower, substitute
that does not need it. See `docs/localnet.md`.

### 4. Primary verified coverage -- `contracts/datum_lib.py` unit tests

`datum_lib.py` has zero genlayer imports, so it needs no runner and no
network access at all. This includes the adjudication prompt builder
(`_adjudication_prompt`) and, as of this session, five dedicated "lying
leader" tests that reproduce `adjudicate()`'s validator comparison logic
exactly (two independently-evaluated envelopes compared field-by-field,
never either side's own claimed verdict trusted) and prove a leader
whose independent re-fetch would disagree -- on usable/unusable status,
station id, tolerance, or window -- is rejected, while two genuinely
independent but formatting-different envelopes with the same underlying
readings still agree:

```
$ python -m pytest tests/direct/test_datum_lib.py -q
................................................................         [100%]
64 passed in 0.26s
```

This is DATUM's actual, currently-trustworthy test evidence: every create
refusal, the constitution hash freeze, unit conversion, volatile-key
neutralization, the full envelope acceptance/rejection logic (agree ->
YES/NO, missing -> INCONCLUSIVE, conflict -> INCONCLUSIVE, preliminary
blocked, station mismatch, quake-outside-bbox), the economics math (fee
split, appeal bond floor, payout dust), the adjudication prompt's
depth/lat-lon fields for QUAKES, and the lying-leader comparator
rejections, are all exercised directly.

### 5. Bundle size check -- PASSES

```
$ python scripts/build_bundle.py
Wrote artifacts/Datum.bundled.py (41489 bytes)
OK: bundle is under the 52224-byte ceiling (10735 bytes to spare)
```

## Frontend

Live at https://datum-gamma.vercel.app. Verified in-browser (desktop and
375px mobile, zero console errors): the marketing long-scroll at `/`, and
`/app`, `/app/create`, `/app/stations`, `/app/portfolio`, `/app/activity`,
`/app/docs`, `/app/e/:id` all render, all fail closed with an honest,
state-specific banner (no address / no code / RPC down / live), and
`/board` + `/e/:id` redirect to their `/app` equivalents including on a
direct URL load (no 404 on refresh).

All twelve writes (`create_event`, `accept_event`, `adjudicate`,
`finalize`, `appeal`, `re_adjudicate`, `lapse_appeal`, `cancel_event`,
`expire_event`, `claim`, `recover_refund`, `reclaim_bonds`) now have a UI
entry point on the ticket page, wired through `genlayer-js` against an
injected wallet, state/identity-gated as a client-side convenience
(the contract's own checks remain authoritative regardless), correctly
disabled with a specific reason string (no address / no code / RPC down /
no wallet / wrong chain) whenever any of those is true. Two real
value-attachment bugs (hardcoded `0n` instead of the required stake/bond
amounts on two buttons, a missing `value` parameter on the `re_adjudicate`
SDK wrapper) were found and fixed this session by checking every wired
call site against its contract-side requirement -- see CHANGELOG.md's
1.1.5/1.1.6 entries. All twelve writes remain **unexercised end-to-end
against a live network** -- there is no live contract yet to write to,
and no click-through UI test has been run, only a clean `next build`
(type-checks the call sites) and a live fail-closed render check.

## What the user should run themselves once the CLI deploy bug clears

`Datum.__init__` takes a required `treasury: str` address argument (added
this session -- the contract previously had no withdrawal path for
accumulated fees/forfeited bonds at all, see CHANGELOG.md's 1.1.3 entry).
Pass your own deployer address unless a separate treasury account exists:

```bash
cd C:\Users\HP\Desktop\datum
genlayer deploy --contract artifacts/Datum.bundled.py --args '["0xYOUR_DEPLOYER_ADDRESS"]'
```

If that still reverts with `FeeValueMustBeNonZero` and the transaction
hash is not found on the explorer, the CLI-specific bug documented above
has not yet been fixed upstream -- retry later, or try the Studio UI /a
raw SDK script (see "What to try next" above) rather than experimenting
further with fee parameters, since seven different configurations across
two sessions all failed identically.

Once a deploy succeeds:

```bash
cd C:\Users\HP\Desktop\datum\frontend
vercel env add NEXT_PUBLIC_DATUM_CONTRACT_ADDRESS production
vercel env add NEXT_PUBLIC_DATUM_CONTRACT_ADDRESS preview
vercel --prod --yes
```

Then confirm `eth_getCode` is non-empty and the live banner on
https://datum-gamma.vercel.app shows the address, and do one real smoke
transaction with real GEN at the smallest legal amounts: `create_event`,
then `accept_event` from a second account, then stop -- do not adjudicate
before the window closes. Document the result here, success or
UserError either way, before attempting anything further.

## Open questions / missing prerequisites found (not blocking)

- No `gh` CLI or Vercel CLI auth issues -- both worked directly.
- The `bradbury-deploy` keystore's raw password was never read or
  printed; the `genlayer` CLI's own unlocked session was used for every
  deploy attempt instead, so no secret left the CLI's own key management.
- Studio Dev UI (browser + MetaMask) was not exercised in any session so
  far -- no interactive browser/wallet access in this environment. If the
  user tries the UI path and it also fails, that would mean the issue is
  platform-wide rather than CLI-specific, contradicting the explorer
  evidence above -- worth documenting either way.
- A raw `genlayer-js` SDK script bypassing the CLI's `deploy` command
  (the approach `scripts/deploy.mjs` already implements) was also not
  attempted -- it needs a real keystore password, which no session so far
  has had or asked for.
