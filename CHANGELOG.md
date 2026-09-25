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

## [1.1.3] - 2026-09-25 - Four real fund-stranding bugs, found by a real lifecycle test

A background audit against this account's accumulated GenLayer steward-
rejection checklist flagged two suspicious areas; writing a real gltest
direct-mode test of the full appeal lifecycle (not just unit tests of the
pure math) to check them surfaced two more. All four are genuine bugs
that would have stranded real GEN on the normal, expected-to-work path,
not an edge case:

- **Treasury had no withdrawal path.** `treasury_balance: u256` accumulated
  fee shares and slashed/forfeited bonds in three separate places with no
  method to ever drain it -- `reclaim_bonds` (the only plausibly-named
  candidate) is a documented no-op. Replaced the counter with a
  constructor-immutable `treasury: str` address; `Datum.__init__` now
  takes `treasury: str` as a required arg. Every fee/forfeiture routes
  through the same `_credit()`/`claim()` ledger every other party already
  uses. `scripts/deploy.mjs` updated to pass the deployer's own address as
  treasury (this project's documented convention when no separate
  treasury account exists).
- **A successful appeal's bond was never resolved on the normal path.**
  `_settle()` never read or cleared `rec["appeal"]` -- only the 7-day
  `recover_refund` timeout fallback did. On the expected case (appeal ->
  re_adjudicate -> finalize, no further appeal), the appellant's bond was
  neither refunded nor forfeited; it sat in the contract's raw balance
  with no ledger entry, unrecoverable once FINALIZED. Fixed: `_settle()`
  now refunds the appellant if the final verdict differs from what was
  appealed, or forfeits to treasury if it doesn't (matching
  `lapse_appeal`'s existing rule for a stalled appeal).
- **`CREATE_BOND` was never returned on a normal settle.** Refunded by
  `cancel_event`, slashed by `expire_event`, but `_settle()` -- the path
  every accepted-and-resolved event actually takes -- never touched it.
  Every successfully-settled event permanently stranded the creator's
  0.05 GEN bond. Fixed: `_settle()` now refunds it unless already slashed.
- **`re_adjudicate()` silently discarded the original adjudicator's
  bond** when resetting `adjudicate_bond_payer`/`adjudicate_bond` to
  `None` before the next `adjudicate()` call overwrites them. Fixed: the
  outgoing adjudicator is credited their bond back first.

Also removed genuinely dead code found in passing: the `positions`
storage field and its `_load_position`/`_save_position`/`_position_key`
helpers were declared and defined but never called from any write method
(`get_position`/`get_positions` read straight from the event record).

All four fixes are covered by two new real `gltest` direct-mode tests
(`TestAppealBondResolution`) that deploy, run a full create -> accept ->
adjudicate -> appeal -> re_adjudicate -> finalize lifecycle with a mocked
LLM response, and assert the exact resulting `claimable` balances --
11/11 direct-mode tests pass, 59/59 pure-logic unit tests pass, bundle
40784 bytes (well under the 52224-byte ceiling), `genvm-lint check`
passes clean.

Two test-harness gotchas hit and worked around while writing these tests,
documented in `tests/direct/conftest.py` and project memory rather than
silently patched away: gltest's `mock_llm()` auto-`json.loads()`s any
JSON-shaped response for `exec_prompt(response_format="json")` semantics,
which breaks a contract (like this one) calling plain `exec_prompt(prompt)`
and parsing the text itself -- worked around with a `conftest.py` patch
that keeps the literal string. Separately, `mock_llm()` matches in
registration order and returns the FIRST match for a repeated pattern,
not the most recent -- `direct_vm.clear_mocks()` before re-registering
for a second scenario is required (a previously-documented gotcha on this
machine, re-confirmed here).

## [1.1.4] - 2026-09-25 - claim() was completely broken; network re-investigation

- **Critical fix: `claim()` -- the ONLY method that ever moves GEN out of
  the contract -- called `gl.get_contract_at(...)`, a stale pre-v0.3.0
  name that does not exist on the current SDK at all.** Confirmed via a
  new real `gltest` test that actually calls `claim()` (no prior test
  ever had): `AttributeError: module 'genlayer' has no attribute
  'get_contract_at'`, on every single call. Fixed to `gl.contract.get_at(...)`,
  cross-checked against the official migration guide
  (sdk.genlayer.com/main/executors/v0.3/python-sdk/migration-guide.html),
  which also independently confirmed every other API rename made in this
  project's earlier 1.1.2 fix (`gl.contract.Contract`, `gl.chain.Event`,
  `gl.vm.run_nondet`, the import pattern) was correct. Added
  `TestClaimActuallyPaysOut` (2 tests) -- 13/13 direct-mode tests now
  pass, and `claim()` specifically is exercised for the first time.
- Independently confirmed the pinned `Depends` hash
  (`5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng`) is a real,
  current, documented runner
  (sdk.genlayer.com/main/executors/v0.3/python-sdk/available-runners.html,
  "GenVM Executor v0.3.0-rc9") -- not stale.
- **Re-investigated the Studio Dev deploy blocker at a steward's request
  to check the explorer.** The 2026-09-24 writeup's conclusion ("hosted
  deploy path is not currently usable") was too broad. The network is
  healthy -- other accounts' transactions, including a deploy of the
  identical official example contract with this project's own Depends
  hash, are FINALIZING right now. This project's own "reverted"
  transaction hashes were never found on-chain at all
  (`{"detail":"Transaction not found"}` on the explorer for every one) --
  the CLI's "Transaction reverted" message describes a client-side
  failure, not a real on-chain revert. Narrowed to: this is a real,
  reproducible bug in the `genlayer` CLI's `deploy` command specifically
  (v0.40.0-rc.3, the only released version supporting Studio Next at all
  -- the stable 0.39.2 channel doesn't know the network exists), failing
  identically across contract size, `--args`, and `--fee-value`
  magnitude. Full evidence trail and untried next steps (Studio UI, a
  raw `genlayer-js` script bypassing the CLI) in `docs/STATUS.md`.

## [1.1.5] - 2026-09-25 - Validator independence and frontend value-attachment bugs

Per-user request: stored this session's major findings as new items
(181-184) in this account's master GenLayer audit checklist, then ran a
strict, assumption-free re-audit of the current codebase against the full
184-item list.

- **Confirmed steward-rejection-pattern bug, now fixed: `adjudicate()`'s
  `validator_fn` only checked the leader's own claimed envelope for
  internal self-consistency, never independently re-acquiring the
  underlying publisher data itself.** This is exactly the pattern behind
  multiple real, confirmed GenLayer steward rejections recorded in
  project memory (checklist items 4/60/65 -- "a validator function that
  only checks the leader's output is well-formed... without independently
  re-deriving its own answer... will be rejected"). A leader that
  fabricated a self-consistent-but-fictional envelope would have passed
  the original check outright. Fixed: `validator_fn` now calls
  `leader_fn()` again itself (a fresh, independent
  `gl.nondet.exec_prompt` call) and only accepts when its own
  independently-derived (verdict, code, agreed_value) matches the
  leader's. Verified via the existing 13 gltest direct-mode tests, all
  still passing unchanged. See docs/architecture.md and docs/audit.md's
  "Witness mismatch" section for the full writeup.
- **Two real frontend/SDK value-attachment bugs, found by checking every
  wired write call site against its contract-side requirement:**
  `app/app/e/[id]/page.tsx`'s Accept YES/NO and Adjudicate buttons all
  hardcoded `0n` for attached value (should be the event's `creator_stake`
  and `ADJUDICATE_BOND` respectively) -- every real click would have
  reverted with `stake mismatch`. `sdk.ts`'s `write.reAdjudicate` had no
  `value` parameter at all, despite `re_adjudicate()` internally
  requiring `ADJUDICATE_BOND` (it calls `adjudicate()` in the same call
  frame). Both fixed; `next build` passes clean.
- Documented, not fixed (real but out of scope for a bug-fix pass): six
  of twelve write methods (`appeal`, `re_adjudicate`, `lapse_appeal`,
  `cancel_event`, `expire_event`, `reclaim_bonds`) have no frontend UI
  entry point at all yet, independent of the contract-deploy blocker.
- A background agent's claim that "zero write methods are called anywhere
  in the frontend" was checked and found FALSE (a bad grep path) before
  being acted on -- six of twelve genuinely are wired, which is how the
  two real bugs above were actually found (by reading the wired ones, not
  by trusting the agent's blanket claim). Recorded as a reminder to
  verify agent-reported findings against the real codebase before fixing
  or documenting them as fact.

## [1.1.6] - 2026-09-25 - Wired the remaining six write methods into the UI

- `app/app/e/[id]/page.tsx` now has buttons for all twelve contract
  writes, not six: `cancel_event` (creator-only, OPEN state), `expire_event`
  (OPEN state, anyone), `appeal` (VERDICT_PENDING, a bonded party, within
  the appeal window, with a ground selector and the correct per-event
  bond via a new `appealBondWei()` helper mirroring `datum_lib`'s
  `appeal_bond_amount`), `re_adjudicate` and `lapse_appeal` (APPEALED
  state), and `reclaim_bonds` (FINALIZED/CANCELED/EXPIRED). An open
  appeal's details (appellant, ground, bond, prior verdict) are now
  displayed on the ticket when present.
- Extended `DatumEvent`/added `AppealInfo` in `types.ts` with the fields
  this needed (`depth`, `appeal_window`, `create_bond`,
  `create_bond_slashed`, `adjudicate_bond_payer`, `adjudicate_bond`,
  `finalized_at`, `appeal`, `last_state_change_at`) -- confirmed against
  the real contract's event record shape rather than guessed.
- All conditional rendering is best-effort client-side convenience (state
  + wallet-identity checks) -- the contract's own guards remain
  authoritative regardless of what the UI shows or hides.
- Verified via a clean `next build` and a live render check (no console
  errors, correct fail-closed empty state). Deployed to
  https://datum-gamma.vercel.app.

## [1.1.7] - 2026-09-25 - Close proof gaps: comparator tests, six-write coverage, one more A/B, a real doc regression found and fixed

Per explicit instruction ("close proof gaps, do not claim Portal-ready"):

- Added `TestLyingLeaderDetection` (5 tests) to `test_datum_lib.py`,
  reproducing `adjudicate()`'s real validator comparison logic exactly
  (two independently-evaluated envelopes compared field-by-field) and
  proving a leader whose independent re-fetch would disagree -- on
  usable/unusable status, station id, tolerance, or window -- is
  rejected, while two genuinely independent but differently-formatted
  envelopes with the same underlying readings still agree. `gltest`
  cannot inject two different LLM response bodies for one mocked prompt
  pattern (documented, pre-existing limitation), so this is tested at
  the `datum_lib` level, exactly as instructed -- does not prove genuine
  network-level multi-validator disagreement, and `docs/audit.md`/
  `docs/STATUS.md` both say so explicitly rather than implying otherwise.
- Added direct happy-path AND refusal-path `gltest` tests for all six
  previously under-tested writes: `cancel_event` (refusal after accept,
  on top of the existing creator/stranger coverage), `expire_event`
  (slash on window-start, refused before window start and after accept),
  `appeal` (stranger refused, post-window refused, pre-VERDICT_PENDING
  refused), `re_adjudicate` (refused on non-APPEALED state), `lapse_appeal`
  (refused before the 1h stall, restores prior verdict + forfeits the
  bond after it, refused on non-APPEALED state), `reclaim_bonds`
  (succeeds as a no-op for a bonded party on a terminal event, refuses a
  stranger and a non-terminal state). `claim()` drain/non-owner-refuse
  was already locked from the prior session, left as-is. Total suite:
  91 passing (64 unit + 27 gltest direct-mode), every one of the 12
  write methods now has both a happy-path and a refusal test.
- One more hosted A/B pass, as instructed, before declaring hosted dead
  a second time: both attempts (Hello, DATUM bundle) reverted identically
  with `FeeValueMustBeNonZero`, both confirmed never reaching the chain
  via the explorer, zero GEN spent. Per this project's own rule: stopped
  spending GEN. Added a concrete, copy-pasteable local recipe (not just a
  pointer) to `docs/STEWARD.md`.
- **Found and fixed a real content-loss regression**: an earlier `Write`
  tool call to `docs/STATUS.md` had silently truncated the file from 262
  lines to 138, losing the entire "Local toolchain" evidence section,
  the "Frontend" section, the "what to run" section, and the "open
  questions" section -- unnoticed until this pass's own line-count check
  across git history. Restored and updated with current, accurate
  figures (91 tests, 12/12 write methods covered, current bundle size).
  Flagged plainly in the restored document itself rather than silently
  fixed, and checked every other doc file's line-count history for the
  same failure mode (none found).
- README's first screen (decision, adversary, must-agree/may-differ,
  failure policy, live URL, contract status) was already in that order;
  updated its contract-address line and test-count/deploy sections to
  the current, accurate figures and the corrected (CLI-specific, not
  infra-side) deploy-blocker framing.
- Confirmed: no "100% ready" or "Portal-ready" claim exists anywhere in
  this repository.
