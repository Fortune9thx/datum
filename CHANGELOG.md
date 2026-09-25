# Changelog

All notable changes to this project are documented in this file.

## [1.0.0] - 2026-09-24 - Initial build

- `contracts/datum_lib.py` -- pure-Python core logic (constitution
  validation, publisher registry, unit conversion, volatile-key stripping,
  aggregation/equivalence acceptance, economics, pagination). 55 passing
  plain-pytest unit tests.
- `contracts/Datum.py` -- full GenLayer Intelligent Contract API
  (`create_event`, `accept_event`, `adjudicate`, `finalize`, `appeal`,
  `re_adjudicate`, `lapse_appeal`, `cancel_event`, `expire_event`,
  `claim`, `recover_refund`, `reclaim_bonds`, plus 9 views).
- `scripts/build_bundle.py` -- single-file bundler producing
  `artifacts/Datum.bundled.py` (40190 bytes, under the 52224-byte Studio
  ceiling).
- `frontend/` -- fail-closed Next.js shell (`/`, `/board`, `/e/:id`) with
  a typed SDK locked to Studio Dev (chain 61997).
- `docs/` -- architecture, self-audit, steward notes, and an honest
  toolchain-status writeup with real captured error output.
- No deploy, no GitHub push, no Vercel deploy performed in this build
  session (by design -- see docs/STATUS.md).

## [1.1.0] - 2026-09-24 - GitHub, Vercel, and the real web app

- Pushed the repo public to https://github.com/Fortune9thx/datum and
  deployed the frontend to https://datum-gamma.vercel.app.
- Fixed two real build bugs found while shipping: `tsconfig.json` targeted
  ES2017 (too low for BigInt literals used in `format.ts`), and the SDK's
  `readContract`/`writeContract` `args` were typed `unknown[]` instead of
  genlayer-js's `CalldataEncodable[]`.
- Corrected a Vercel project mislink: the first `vercel link` auto-matched
  an unrelated pre-existing project literally named "frontend" under the
  same account; recreated a dedicated `datum` project instead so nothing
  else was overwritten.
- Replaced the placeholder shell with the full app: a marketing
  long-scroll at `/`, and `/app` (board), `/app/e/:id` (ticket),
  `/app/create`, `/app/stations`, `/app/portfolio`, `/app/activity`,
  `/app/docs`. `/board` and `/e/:id` redirect to their `/app` equivalents.
- `probeContract()` now distinguishes four states -- no address, address
  with no code (Studio Next reset), RPC unreachable, and live -- so an
  infra failure is never rendered as "no events".
- SDK extended to cover every contract view and write by its real method
  name; the create form mirrors `datum_lib`'s create-time refusals
  client-side while leaving the contract authoritative.
- Still no contract deployed to Studio Next; the frontend fails closed
  against that fact everywhere.

## [1.1.1] - 2026-09-24 - Fix the dead depth branch and the QUAKES lat/lon gap

- Fixed `contracts/Datum.py`'s adjudication prompt builder: the QUAKES
  depth label was `('any' if not None else 'any')`, an expression that is
  always `True` and always rendered `"any"` regardless of the
  constitution's actual locked `depth`. `depth` was validated and hashed
  into the constitution (`datum_lib.py`) but never reached the prompt or
  the call site in `adjudicate()` at all.
- While fixing it, found a second, more serious bug in the same function:
  the frozen prompt's requested JSON shape never asked the model for
  `lat`/`lon`, yet `validate_source_reading()` requires both for every
  QUAKES source (`"missing epicenter coordinates"` otherwise) to check
  bbox membership. Every QUAKES source would have come back unusable
  regardless of the reading's accuracy. Added `lat`/`lon` to the QUAKES
  JSON shape and an explicit prompt instruction to include them.
- Relocated the prompt builder from `Datum.py` into `datum_lib.py` as
  `_adjudication_prompt` (zero genlayer imports, like everything else in
  that module) so it is directly plain-pytest testable rather than only
  reachable through the genlayer runtime. `scripts/build_bundle.py`
  inlines it into the bundle exactly as before; the bundle's single call
  site in `adjudicate()` is unchanged.
- Added 4 unit tests (`TestAdjudicationPrompt`) covering: a non-default
  depth actually appears in the built prompt, the default (`None`) case
  still renders `"any"`, the QUAKES prompt requests `lat`/`lon`, and a
  non-QUAKES prompt has neither depth nor bbox fields. 59/59 tests pass.
- Rebuilt `artifacts/Datum.bundled.py` (40881 bytes, still well under the
  52224-byte Studio ceiling) and re-verified `genvm-lint lint` passes
  clean on the bundle.

## [1.1.2] - 2026-09-25 - The local toolchain gap was three fixable bugs, not a wall

- Fixed three real, stacked bugs in `contracts/Datum.py` that made `genvm-lint check/validate/
  schema` and `gltest` direct-mode deploy fail with the misleading generic symptom
  `name 'gl' is not defined`, previously assumed to be an unfixable local toolchain gap:
  1. Stale pre-v0.3.0 API names: `from genlayer import *` (never actually binds `gl`) ->
     `import genlayer as gl` + `from genlayer.types import *` + `from genlayer.storage import
     TreeMap`; bare `gl.Contract` -> `gl.contract.Contract`; bare `gl.Event` (used by all 10 event
     classes) -> `gl.chain.Event`; `gl.vm.run_nondet_unsafe` (does not exist in this SDK) ->
     `gl.vm.run_nondet`. Verified against the real installed SDK source and against
     `precedence-settler`'s own contract, which has actually deployed and FINALIZED on this same
     network with this same Depends hash.
  2. `Datum.__init__` hand-instantiated its TreeMap fields (`self.events = TreeMap()`, etc). This
     SDK's storage generator auto-allocates every declared persistent field at class-definition
     time and rejects a freehand `TreeMap()` call in `__init__` outright (`GenerationError:
     generic storage classes can not be instantiated with __init__`). Fixed by leaving `__init__`
     empty -- the auto-allocation already gives every field its correct empty/zero default.
  3. `gltest`'s own `bundles-v2/` SDK cache lacked the tarball for this project's pinned runner
     hash under its expected path (an older, differently-laid-out cache existed alongside it from
     a prior `gltest` version) -- copied into place rather than re-downloaded, avoiding a GitHub
     rate-limit risk.
- `tests/direct/test_datum_contract.py` was rewritten to actually deploy (was previously
  documented as blocked) and now runs a real create/accept/cancel/adjudicate-guard flow against a
  live GenVM sandbox: 9/9 passing, including real GEN attached via `direct_vm.value` and a second
  account via `direct_vm.prank(...)`. `CONTRACT_PATH` now points at `artifacts/Datum.bundled.py`
  (the file that actually has `datum_lib`'s functions inlined) instead of the un-bundled source,
  and the `contract` fixture rebuilds the bundle itself immediately before each deploy, since
  gltest clears its own `artifacts/` directory (name collision with the bundler's output dir) at
  session start.
- In passing, found and left as-is (documented, not fixed, since it's not a functional bug): a
  second `accept_event` on an already-ACTIVE event surfaces `"not open"` rather than the more
  specific `"already accepted"` string, because the state check runs first -- both correctly
  refuse the second accept, only the diagnostic message differs.
- `genvm-lint check`/`validate`/`schema` all now pass cleanly on the bundle (22 methods: 10 view,
  12 write). Full detail in `docs/STATUS.md`; the underlying toolchain finding is recorded in
  project memory (`genlayer-consensus-v06-migration-findings`,
  `genlayer-treemap-explicit-init-safe`) for reuse on future GenLayer projects on this machine.
