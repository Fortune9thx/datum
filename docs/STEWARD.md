# DATUM -- steward notes

This document is for whoever picks this project up next (including a
future version of the original author).

## 30-second walkthrough

1. Open https://datum-gamma.vercel.app -- a paper/ink long-scroll
   explaining what DATUM settles and how, then `/app` for the live board.
2. The board, ticket, portfolio, and activity pages are all currently
   empty, with an honest orange banner: **"Contract not deployed on
   Studio Next (61997)."** That is correct, not broken -- see below.
3. Read `/app/docs` in the app (or `README.md` in this repo) for the
   constitution, the equivalence rules, and the economics.
4. For proof the contract itself works, despite not being deployed: run
   `python -m pytest tests/direct/test_datum_contract.py -q` -- 9/9
   passing, a real deploy + create/accept/cancel/adjudicate-guard flow
   against a live GenVM sandbox. Full detail in `docs/localnet.md`.

## Evidence URLs

- Repo: https://github.com/Fortune9thx/datum
- Live app: https://datum-gamma.vercel.app
- Contract address: none yet -- see `docs/STATUS.md` for two real,
  documented Studio Dev deploy attempts (both blocked by an infra-side
  FeeManager revert) and `docs/localnet.md` for the local proof instead.
- Test commands: `python -m pytest tests/direct/ -q` (68 tests total: 59
  in `test_datum_lib.py`, 9 in `test_datum_contract.py`), `PYTHONIOENCODING=utf-8
  genvm-lint check artifacts/Datum.bundled.py` for the full-runtime lint.

## What is genuinely done

- `contracts/datum_lib.py` -- the full rule set (constitution validation,
  publisher registry, unit conversion, volatile-key stripping, aggregation
  + equivalence acceptance, economics math, pagination, the adjudication
  prompt builder) with 59 passing plain-pytest unit tests. Zero genlayer
  imports, zero toolchain dependency -- the most trustworthy part of the
  repo.
- `contracts/Datum.py` -- the full write/view API from the spec (22
  methods: 10 view, 12 write), wired to `datum_lib`'s logic via the
  bundler. `genvm-lint check` (full runtime validation, not just static
  lint) passes cleanly on the bundle.
- `scripts/build_bundle.py` -- regenerates `artifacts/Datum.bundled.py`
  (~40.7KB, well under the 52224-byte Studio ceiling) any time either
  source file changes. **Run it after every edit to `contracts/*.py` --
  the bundle is what actually gets deployed and tested, and it is not
  auto-regenerated on save.**
- `tests/direct/test_datum_contract.py` -- a real `gltest` direct-mode
  execution proof, 9/9 passing (deploy, create with real GEN attached,
  accept from a second account, three create-time refusals, cancel
  restricted to the creator, adjudicate refusing before window close).
- `frontend/` -- the Next.js web app, live at
  https://datum-gamma.vercel.app. A marketing long-scroll at `/`, and the
  app under `/app` (board), `/app/e/:id` (ticket), `/app/create`,
  `/app/stations`, `/app/portfolio`, `/app/activity`, `/app/docs`.
  `/board` and `/e/:id` redirect to their `/app` equivalents. Verified
  live in-browser (desktop + 375px mobile, zero console errors).

  It fails closed in four distinct, separately-worded states, via
  `probeContract()` in `src/lib/datum/network.ts`: no address configured,
  address set but no code (Studio Next was reset), RPC unreachable, and
  live. An unreachable RPC is never rendered as "no events" -- each state
  states what is actually true, and no view ever substitutes placeholder
  or demo rows for a live contract.
- GitHub push and Vercel production deploy are both live (see Evidence
  URLs above).

## What is NOT done yet, and why

1. **No contract is deployed to Studio Dev.** Two real attempts (a
   trivial Hello contract and the full DATUM bundle, via `genlayer
   deploy`) both reverted identically with `FeeValueMustBeNonZero` --
   confirmed infra-side (Studio Dev's FeeManager), not a bug in this
   repo. Full proof and exact retry commands: `docs/STATUS.md`.
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

1. Check whether Studio Dev's `FeeValueMustBeNonZero` issue has cleared:
   `genlayer deploy --contract artifacts/Datum.bundled.py --args []`. If
   it still reverts with that exact error, the platform-side issue in
   `docs/STATUS.md` is still open -- don't re-experiment with fee
   parameters, three different configurations already failed identically.
2. Once a deploy succeeds: set `NEXT_PUBLIC_DATUM_CONTRACT_ADDRESS` in
   Vercel (production + preview), redeploy, confirm `eth_getCode` is
   non-empty and the live banner shows the address.
3. Then do one real smoke transaction with real GEN, smallest legal
   amounts: `create_event` (STAGE or QUAKES, satisfying MIN_LEAD/MIN_WINDOW),
   `accept_event` from a second account, and stop -- do not adjudicate
   before the window closes. Document the result in `docs/STATUS.md`,
   success or UserError either way.
4. Re-run `python scripts/build_bundle.py` after any contract edit --
   never hand-edit `artifacts/Datum.bundled.py`.

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
- `Datum.__init__` staying empty -- this SDK's storage generator
  auto-allocates every declared field at class-definition time; adding a
  hand-rolled `self.field = TreeMap()` back in will break deploy again
  (see CHANGELOG.md's 1.1.2 entry for exactly why).

## Portal submission notes (draft)

DATUM settles whether an official station observation cleared a locked
threshold. GenLayer validators fetch two locked publishers and must agree
on usable readings (station id, window, unit, product status, converted
value within tolerance). Code compares. Missing or conflicting evidence
refunds both sides. Frontend is live; contract status is in
docs/STATUS.md.
