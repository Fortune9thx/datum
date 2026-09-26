# Changelog

All notable changes to this project are documented in this file.

## [1.4.0] - 2026-09-26

### Fixed

- `evaluate_envelope` never checked the leader's claimed `event_id` against the event actually being adjudicated, and never checked that `sources` keys were among the event's own locked publishers -- a stale, hallucinated, or wrongly-keyed envelope could be accepted as long as its self-consistency checks passed. Both are now checked before anything else, and either mismatch refuses the whole envelope.
- Adjudication accepted a source reading with no citation of where it came from. Every usable source must now carry a verbatim `raw` field; a `stable_digest` of it is computed and retained. A usable source with no raw citation is refused.
- `accepted_record` only stored `{usable, reason, converted}` per source, discarding `station_id`/`t`/`value_native`/`unit`/`product_status`/`digest` -- fields the frontend's evidence view already expected and was reading from a `.sources` key that didn't exist in the stored shape at all, so the evidence pane silently rendered nothing regardless of what adjudication actually did. The full row is now retained under `accepted_record.sources`, matching the frontend exactly.
- `get_position`/`get_positions`/`get_claimable`/`get_activity` used a caller-supplied address string directly as a lookup key or comparison value, while every write path stores addresses via `Address(...).as_hex`. A differently-cased query (e.g. non-checksummed) would silently read back empty/zero. The constructor's `treasury` argument had the same gap. All five now normalize through `Address(...).as_hex`.

### Added

- Tests covering event-id binding, publisher-key binding, and the full provenance schema, at both the `datum_lib` and gltest-integration level: `contracts/ProbeTreasury.py` is unrelated to this entry (a deploy-diagnostic contract, see docs/deployment.md); the new coverage here is `TestEvaluateEnvelope`'s binding/provenance tests and `TestAdjudicationSourceBindingAndProvenance` in `test_datum_contract.py`.

## [1.3.0] - 2026-09-25

### Added

- Live deployment to Studio Next: `0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3`.
- `deploy/deployments.json`, a machine-readable deployment record.
- `scripts/create_event.mjs`, a `genlayer-js` script for calling payable methods, since `genlayer write` cannot attach value to a transaction.
- UI entry points for the remaining six write methods (`appeal`, `re_adjudicate`, `lapse_appeal`, `cancel_event`, `expire_event`, `reclaim_bonds`) on the event ticket page, state- and identity-gated.
- `docs/deployment.md` and `docs/testing.md`.

### Fixed

- The frontend's liveness probe used `eth_getCode`, which always returns `0x` for a GenLayer contract (GenLayer contracts are not EVM bytecode). Replaced with `gen_getContractSchema`.
- Two payable UI actions (Accept, Adjudicate) attached zero value instead of the required stake/bond amount; the `re_adjudicate` SDK method was missing its value parameter entirely.

## [1.2.0] - 2026-09-25

### Fixed

- `adjudicate()`'s validator previously re-derived a verdict only from the leader's own claimed data. It now independently re-fetches (a second, separate `gl.nondet.exec_prompt` call) and accepts only when both independent derivations agree.
- `claim()` — the only method that moves GEN out of the contract — called an SDK function that does not exist in the current `genlayer` package, and would have reverted on every call. Fixed the call path and added direct test coverage that actually exercises payout.
- Four fund-accounting gaps found by writing a full lifecycle test rather than relying on unit tests alone: the treasury accumulator had no withdrawal path; a resolved appeal's bond was never credited or forfeited on the normal settlement path; the create bond was never refunded on a normal settlement; `re_adjudicate` discarded the outgoing adjudicator's bond without crediting it. All four now route through the same `claimable` ledger every other party uses.
- Removed unused `positions` storage field and its accessor methods.

### Added

- Direct test coverage (happy path and refusal) for all twelve write methods.
- Five dedicated tests proving the adjudication comparator rejects a leader whose independent re-fetch disagrees on usability, station id, tolerance, or window.

## [1.1.0] - 2026-09-24

### Added

- Public GitHub repository and Vercel deployment.
- Full web application: marketing page, board, ticket, create, stations, portfolio, activity, and constitution views.
- Real `gltest` execution coverage against a GenVM sandbox.

### Fixed

- Stale pre-v0.3.0 GenLayer API usage (`gl.Contract`, `gl.Event`, `gl.vm.run_nondet_unsafe`) replaced with the current API.
- Contract `__init__` no longer hand-instantiates storage fields; the storage generator auto-allocates them.
- A dead branch in the QUAKES adjudication prompt meant the locked depth value never reached the model, and the prompt never requested the epicenter coordinates that source validation requires.
- `tsconfig.json` target raised to support BigInt literals; SDK argument types corrected to match `genlayer-js`.

## [1.0.0] - 2026-09-24

Initial build.

- `contracts/datum_lib.py` — constitution validation, publisher registry, unit conversion, equivalence logic, economics, pagination. Zero GenLayer imports.
- `contracts/Datum.py` — the full contract API: 12 write methods, 10 view methods.
- `scripts/build_bundle.py` — single-file bundler for deployment.
- Initial Next.js frontend shell.
- `docs/architecture.md`, `docs/audit.md`.
