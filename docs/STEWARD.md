# DATUM -- steward notes

This document is for whoever picks this project up next (including a
future version of the original author).

## What is genuinely done

- `contracts/datum_lib.py` -- the full rule set (constitution validation,
  publisher registry, unit conversion, volatile-key stripping, aggregation
  + equivalence acceptance, economics math, pagination) with 55 passing
  plain-pytest unit tests (`tests/direct/test_datum_lib.py`). This is the
  most trustworthy part of the repo -- it has zero genlayer imports and
  zero toolchain dependency.
- `contracts/Datum.py` -- the full write/view API from the spec, wired to
  `datum_lib`'s logic via the bundler. `genvm-lint lint` (AST-based safety
  checks) passes cleanly.
- `scripts/build_bundle.py` -- regenerates `artifacts/Datum.bundled.py`
  (currently ~40KB, well under the 52224-byte Studio ceiling) any time
  either source file changes. Run it after every edit.
- `frontend/` -- a minimal, intentionally unstyled Next.js shell (`/`,
  `/board`, `/e/:id`) that fails closed to empty/zero state whenever
  `NEXT_PUBLIC_DATUM_CONTRACT_ADDRESS` is unset or has no code on-chain.

## What is NOT done yet (by explicit instruction, not oversight)

1. **No deploy has been attempted.** Neither to Studio Dev nor anywhere
   else. See docs/STATUS.md for the exact commands to run.
2. **No `git push` / GitHub repo was created.** The repo is `git init`'d
   locally with a clean history on `main`.
3. **No `vercel --prod` / any Vercel deploy.**
4. **`gltest` direct-mode and `genvm-lint validate/schema` were not made
   to pass** -- they fail locally due to a pre-existing, machine-level
   toolchain gap (GenVM runner bundle download failures / rate limiting),
   documented with real captured error text in docs/STATUS.md. This is
   not specific to DATUM; every prior GenLayer project on this machine
   hits the same wall.
5. **The frontend was never run.** `npm install && npm run dev` inside
   `frontend/` was not executed in this session -- do that first before
   trusting the shell renders correctly.

## First things to do when picking this back up

1. `cd frontend && npm install && npm run dev` -- confirm the shell
   actually renders and fails closed with no contract address configured.
2. Try the Hello-world smoke-test deploy suggested in docs/STATUS.md
   before attempting DATUM's own deploy, to isolate whether
   genlayer-studio#1757 is still blocking Studio Dev.
3. Once genvm-lint/gltest's runner-download issue is resolved locally (or
   run from a machine/network without the GitHub rate-limit problem),
   re-run `gltest tests/direct/test_datum_contract.py` -- it is written
   and ready, just currently blocked at the fixture/deploy step.
4. Re-run `python scripts/build_bundle.py` after any contract edit --
   never hand-edit `artifacts/Datum.bundled.py`.

## Design decisions a future steward should NOT casually change

- The 1:1 symmetric-wager model (see docs/architecture.md) -- switching to
  a pooled multi-party market is a real redesign, not a small patch, and
  touches `_settle`'s payout math.
- `claim()` as the only GEN-moving method -- every other write only
  credits the `claimable` ledger. Do not add a second `emit_transfer` call
  anywhere else without re-reading the Studio-safety rationale in
  docs/architecture.md.
- The Depends hash on line 1 of `contracts/Datum.py` -- verify it still
  lints clean with `genvm-lint lint` before ever changing it; it is reused
  from a confirmed-working prior project on this exact machine.
