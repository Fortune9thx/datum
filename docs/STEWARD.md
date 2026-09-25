# DATUM -- steward notes

This document is for whoever picks this project up next (including a
future version of the original author).

## 30-second walkthrough

1. Open https://datum-gamma.vercel.app -- a paper/ink long-scroll
   explaining what DATUM settles and how, then `/app` for the live board.
2. The board shows a green **LIVE** banner with the deployed contract
   address `0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3` and an explorer
   link, and reads real zeros from the real contract. It is empty because
   no events have been created yet -- never placeholder or demo rows.
3. Read `/app/docs` in the app (or `README.md` in this repo) for the
   constitution, the equivalence rules, and the economics.
4. Verify the contract yourself in one command:
   `genlayer call 0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3 get_config`
   -- returns the real on-chain economics/config.
5. For the full logic proof: `python -m pytest tests/direct/ -q` -- 91
   passing (64 pure-logic + 27 against a live GenVM sandbox), covering
   every write method's happy path AND refusal path. Detail in
   `docs/localnet.md`.

## Evidence URLs

- Repo: https://github.com/Fortune9thx/datum
- Live app: https://datum-gamma.vercel.app
- **Contract (live, Studio Next / chain 61997):**
  `0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3`
  -- https://explorer-studio-dev.genlayer.com/address/0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3
- Deploy tx: `0x84b5319b1ca744c47a0c3c36894e69cf3466c0cc3c876f4fcecf8315c440ae03` (ACCEPTED)
- Live write proof (returns the contract's own UserError from a real
  consensus round):
  `0x01809ec4ac941cb0b6feba525599153dfc0c1cc13e87cd2da295714fac31fe71`
- Machine-readable deploy record: `deploy/deployments.json`
- Test commands: `python -m pytest tests/direct/ -q` (91 tests total: 64
  in `test_datum_lib.py`, 27 in `test_datum_contract.py`),
  `PYTHONIOENCODING=utf-8 genvm-lint check artifacts/Datum.bundled.py`
  for the full-runtime lint.

## The one thing still unexercised

No GEN has moved through the contract yet. `create_event` and every other
payable method needs a wallet: `genlayer write` has no flag for attaching
native GEN to a payable method (the underlying `genlayer-js`
`writeContract` supports `value`; the CLI does not expose it). Reads and
non-payable writes are both verified live on-chain -- a real payable call
is the remaining gap, and it needs either the frontend with an injected
wallet or a direct `genlayer-js` script with a decrypted keystore.

## What is genuinely done

- `contracts/datum_lib.py` -- the full rule set (constitution validation,
  publisher registry, unit conversion, volatile-key stripping, aggregation
  + equivalence acceptance, economics math, pagination, the adjudication
  prompt builder) with 64 passing plain-pytest unit tests, including 5
  "lying leader" comparator-rejection tests. Zero genlayer imports, zero
  toolchain dependency -- the most trustworthy part of the repo.
- `contracts/Datum.py` -- the full write/view API from the spec (22
  methods: 10 view, 12 write), wired to `datum_lib`'s logic via the
  bundler. `genvm-lint check` (full runtime validation, not just static
  lint) passes cleanly on the bundle.
- `scripts/build_bundle.py` -- regenerates `artifacts/Datum.bundled.py`
  (~41.5KB, well under the 52224-byte Studio ceiling) any time either
  source file changes. **Run it after every edit to `contracts/*.py` --
  the bundle is what actually gets deployed and tested, and it is not
  auto-regenerated on save.**
- `tests/direct/test_datum_contract.py` -- a real `gltest` direct-mode
  execution proof, 27/27 passing, covering a happy path AND a refusal
  path for every one of the 12 write methods (create/accept/adjudicate/
  finalize/appeal/re_adjudicate/lapse_appeal/cancel/expire/claim/
  recover_refund/reclaim_bonds), with real GEN attached via
  `direct_vm.value` and multi-account flows via `direct_vm.prank`.
- `frontend/` -- the Next.js web app, live at
  https://datum-gamma.vercel.app. A marketing long-scroll at `/`, and the
  app under `/app` (board), `/app/e/:id` (ticket), `/app/create`,
  `/app/stations`, `/app/portfolio`, `/app/activity`, `/app/docs`.
  `/board` and `/e/:id` redirect to their `/app` equivalents. Verified
  live in-browser (desktop + 375px mobile, zero console errors).

  It distinguishes four states via `probeContract()` in
  `src/lib/datum/network.ts` (which uses `gen_getContractSchema`, NOT
  `eth_getCode` -- a GenLayer contract returns `0x` from `eth_getCode`
  even when live, a real bug the deploy exposed): no address configured,
  address set but nothing deployed there (Studio Next was reset), RPC
  unreachable, and live. An unreachable RPC is never rendered as "no events" -- each state
  states what is actually true, and no view ever substitutes placeholder
  or demo rows for a live contract.
- GitHub push and Vercel production deploy are both live (see Evidence
  URLs above).

## What is NOT done yet, and why

1. **No GEN has moved through the contract yet.** The contract IS
   deployed and live (reads and non-payable writes both verified
   on-chain), but no payable method has been called: `genlayer write`
   cannot attach native GEN to a payable method. Needs the frontend with
   an injected wallet, or a `genlayer-js` script with a decrypted
   keystore. This is the single biggest remaining gap.
2. **No genuine multi-validator disagreement has been exercised.**
   `gltest` direct-mode's single-process leader can't simulate real
   validators disagreeing with each other. See `docs/audit.md`'s
   "witness mismatch" section and `docs/localnet.md`.
3. **QUAKES `depth` is advisory, not code-enforced** (unlike bbox/lat-lon,
   which is). See `docs/audit.md`'s last entry.
4. **No `genlayer up` / Docker-based full localnet run.** This machine
   has no Docker installed; `gltest` direct-mode was used instead. See
   `docs/localnet.md`'s "Path B" for the commands, for whoever has Docker.

## First things to do when picking this back up

1. **Do the real payable smoke test** -- the one genuinely unexercised
   path. Connect a wallet on https://datum-gamma.vercel.app/app/create
   and create one STAGE event at the smallest legal stake (0.01 GEN +
   0.05 GEN create bond), satisfying MIN_LEAD (2h) and MIN_WINDOW (6h).
   Then `accept_event` from a second account if you have one, and stop --
   do not adjudicate before the window closes. Record the result in
   `docs/STATUS.md`, success or UserError either way.
2. If the contract address stops resolving, Studio Next was reset (it is
   a development preview). Redeploy with the exact command in
   `docs/STATUS.md`'s SOLVED section -- note it needs BOTH a complete
   `--fees` distribution and a JSON-quoted `--args '"0xADDR"'`, or it
   will fail in one of the two documented ways. Then update
   `deploy/deployments.json` and the Vercel env var.
3. Re-run `python scripts/build_bundle.py` after any contract edit --
   never hand-edit `artifacts/Datum.bundled.py`.

## Local recipe (full logic proof, independent of the live deploy)

The contract is live on Studio Next, but the local suite remains the
fastest and most complete proof of the contract's logic -- it exercises
every write method's happy and refusal path, including flows (appeals,
lapses, expiry) that would take hours of real wall-clock time on-chain:

```bash
cd C:\Users\HP\Desktop\datum

# Rebuild the bundle (gltest clears its own artifacts/ dir at session
# start, so this must run fresh before every test invocation):
python scripts/build_bundle.py

# Pure-logic unit tests -- zero genlayer imports, zero toolchain
# dependency, 64 passing (includes 5 "lying leader" comparator-rejection
# tests):
python -m pytest tests/direct/test_datum_lib.py -q

# Real GenVM sandbox execution -- deploy + create/accept/cancel/expire/
# adjudicate/appeal/re_adjudicate/lapse_appeal/reclaim_bonds/claim, 27
# passing, happy path AND refusal covered for every one of the 12 write
# methods:
python -m pytest tests/direct/test_datum_contract.py -q

# Full runtime validation on the bundle (not just static lint):
PYTHONIOENCODING=utf-8 genvm-lint check artifacts/Datum.bundled.py
```

For a fuller local network (real multi-validator Docker simulator,
`genlayer up`) instead of `gltest` direct-mode's single-process sandbox,
see `docs/localnet.md`'s "Path B" -- not attempted on this machine (no
Docker installed), documented there for whoever has it.

## Design decisions a future steward should NOT casually change

- The 1:1 symmetric-wager model -- switching to a pooled multi-party
  market is a real redesign, not a small patch, and touches every payout
  calculation in `datum_lib.py`.
- `claim()` as the only GEN-moving method -- every other write only
  credits the `claimable` ledger. Do not add a second value-transferring
  call anywhere else without re-reading `docs/architecture.md`.
- The Depends hash on line 1 of `contracts/Datum.py` -- confirmed to
  resolve under SDK version `v0.6.0-rc6` on this machine (see
  `docs/localnet.md`); verify with `genvm-lint check` before ever
  changing it.
- `Datum.__init__(self, treasury: str)` only assigning that one scalar
  field -- this SDK's storage generator auto-allocates every declared
  `TreeMap` field at class-definition time; adding a hand-rolled
  `self.field = TreeMap()` back in will break deploy again (see
  CHANGELOG.md's 1.1.2 entry for exactly why).
- Routing treasury through the same `claimable`/`claim()` ledger every
  other party uses, rather than a separate counter -- see CHANGELOG.md's
  1.1.3 entry for why a separate, undrainable counter was a real bug.

## Portal submission notes (draft)

DATUM settles whether an official station observation cleared a locked
threshold. GenLayer validators fetch two locked publishers and must agree
on usable readings (station id, window, unit, product status, converted
value within tolerance). Code compares. Missing or conflicting evidence
refunds both sides. Frontend is live; contract status is in
docs/STATUS.md.
