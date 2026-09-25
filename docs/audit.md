# DATUM -- self-audit

Risk-by-risk review of the failure modes an adversarial steward would
check first, each as risk -> mitigation -> leftover (what remains
imperfect or unverified, stated plainly rather than hidden).

## Trapped funds

**Risk:** an event gets stuck in a non-terminal state (ACTIVE,
VERDICT_PENDING, APPEALED) forever -- an adjudicator never shows up, an
appeal never resolves -- and both parties' stakes are permanently
unreachable. A second, distinct version of this risk: an amount is
credited nowhere at all on the *normal, successful* path, rather than
being stuck in an unresolved event.

**Mitigation:** `recover_refund(event_id)` is a deterministic,
evidence-free fallback. Any event that has not reached a terminal state
within `RECOVER_REFUND_AFTER` (7 days) can have both stakes returned by
anyone calling it, no adjudication or appeal outcome required.
`lapse_appeal` similarly bounds a stalled appeal to 1 hour before
restoring the prior verdict. `claim()` is the only method that ever moves
GEN out of the contract, and it only ever pays the caller's own ledger
balance (`self.claimable[gl.message.sender_address]`), never an address
argument -- so a claim can't be redirected, and funds credited to an
address are always eventually claimable by that same address.

**Confirmed and fixed this session -- four real fund-stranding bugs, none
caught until an actual multi-step gltest lifecycle test was written and
run (unit tests alone never exercise `_settle`/`re_adjudicate` end to
end):**

1. **Treasury had no withdrawal path at all.** `treasury_balance: u256`
   accumulated fee shares and slashed/forfeited bonds in three places but
   no method ever read or drained it -- `reclaim_bonds` (the only
   plausibly-named candidate) is a documented no-op. Fixed by replacing
   the counter with a constructor-immutable `treasury: str` address and
   routing every fee/forfeiture through the same `_credit()`/`claim()`
   ledger every other party already uses, rather than inventing a second,
   parallel payout mechanism.
2. **A successful appeal's bond was never resolved on the normal path.**
   `_settle()` (called from `finalize()`) never read or cleared
   `rec["appeal"]` at all -- only the 7-day `recover_refund` timeout
   fallback touched it. On the expected, working case (appeal ->
   re_adjudicate -> finalize with no further appeal), the appellant's
   bond (min 0.05 GEN, or half a side's stake) was neither refunded nor
   forfeited -- it just sat in the contract's raw balance, untracked by
   any ledger field, unrecoverable once `FINALIZED`. Fixed: `_settle()`
   now resolves it, refunding the appellant if the final verdict differs
   from the verdict that was appealed (they were right to appeal) or
   forfeiting to treasury if it doesn't (same rule `lapse_appeal` already
   used for a stalled appeal).
3. **`CREATE_BOND` was never returned on a normal settle.** It is
   refunded by `cancel_event` and slashed by `expire_event`, but
   `_settle()` -- the path every accepted-and-resolved event actually
   takes -- never touched it at all. Every single successfully-settled
   event permanently stranded the creator's 0.05 GEN create bond, the
   *expected* case, not an edge case. Fixed: `_settle()` now refunds it
   to the creator unless it was already slashed.
4. **`re_adjudicate()` silently discarded the original adjudicator's
   bond.** It resets `rec["adjudicate_bond_payer"]`/`rec["adjudicate_bond"]`
   to `None` before calling `adjudicate()` again (so the new adjudicator's
   bond can be recorded) -- but never credited the *previous* adjudicator
   anything first. Fixed: `re_adjudicate()` now credits the outgoing
   adjudicator's bond back before resetting those fields.

All four are covered by real `gltest` direct-mode tests
(`TestAppealBondResolution` in `test_datum_contract.py`) that deploy,
run a full create -> accept -> adjudicate -> appeal -> re_adjudicate ->
finalize lifecycle with a mocked LLM response, and assert the exact
resulting ledger balances -- not just that the code compiles or that a
unit test of the pure math passes in isolation.

**Leftover:** `claim()`'s last-claimant-absorbs-dust pattern
(`payout_shares` integer division, tested in `TestEconomics`) means the
very last claimant on a winning side receives a few wei more or less than
a perfectly proportional split. Bounded, tested, and economically
immaterial at GEN's 18-decimal scale, but not literally zero.

## Wrong station accepted as evidence

**Risk:** a reading for the wrong station (a different gauge, a different
city) gets accepted as if it were the locked station's own observation.

**Mitigation:** `validate_source_reading` requires each source's
`station_id` to case-insensitively equal the constitution's locked
`expected_station_id` exactly, for every non-QUAKES class; QUAKES (which
has no single station id) instead requires the source's reported
epicenter (`lat`/`lon`) to fall inside the locked bbox. Any mismatch marks
that source `usable=false` with reason `"wrong station_id"` /
`"epicenter outside bbox"` -- never averaged in, never imputed.
`is_official_station_id` additionally refuses a free-text station at
`create_event` time in the first place (class-specific regex: 4-11
alphanumeric chars for weather stations, exactly 8 digits for USGS sites).

**Leftover:** none identified for this specific risk; station-id matching
is exact-string, not fuzzy, by design.

## Preliminary treated as final

**Risk:** a not-yet-finalized (PRELIMINARY) reading gets treated as
authoritative under a policy that was supposed to require FINAL data
only, letting an event settle on data the publisher itself hasn't
finished revising.

**Mitigation:** `validate_source_reading` checks
`product_status_policy == "FINAL_ONLY" and product_status != "FINAL"` and
marks that source unusable with reason `"preliminary blocked by policy"`
before it can be averaged in. `ALLOW_PRELIMINARY` is an explicit,
constitution-locked opt-in a creator must choose at create time --
FINAL_ONLY is the default. The `PRELIMINARY_BLOCKED` outcome code
surfaces this distinctly in `get_record` rather than collapsing it into
a generic `MISSING`.

**Leftover:** DATUM has no mechanism to force a re-read once a
PRELIMINARY reading is later revised to FINAL, other than the `REVISED`
appeal ground (which may live-refresh the reading). An event that settles
`PRELIMINARY_BLOCKED`/`INCONCLUSIVE` and is never appealed simply refunds
both sides, even if the station's data becomes FINAL and decisive the
next day.

## Witness (publisher) mismatch

**Risk:** the leader claims two publishers agree when their underlying
readings actually differ, or claims a verdict that doesn't match what the
sources actually show.

**Mitigation:** this is the contract's central invariant.
`evaluate_envelope` never trusts the leader's own `verdict`/`code`
fields -- it independently re-derives both from the envelope's
`sources` rows (via `aggregate_sources` + `apply_threshold`) and rejects
the whole envelope (`accepted=False`, no funds move) if the leader's
claim doesn't match the independent derivation exactly. This re-derivation
runs identically inside `validator_fn` for every validator, not just
once for the leader -- so a leader misreporting agreement gets caught by
consensus, not just by the contract's own bookkeeping.

**Leftover:** documented in `docs/localnet.md` -- this project's own
`gltest` direct-mode proof does not exercise genuine multi-validator
disagreement (a single-process mock has one leader, not real independent
validators). The re-derivation logic itself is thoroughly unit-tested in
`datum_lib.py`'s `TestEvaluateEnvelope` (agree -> YES/NO, missing ->
INCONCLUSIVE, conflict -> INCONCLUSIVE, station mismatch, preliminary
blocked, quake-outside-bbox, volatile-key neutralization, different raw
JSON converging on the same accepted record), but a live multi-validator
disagreement scenario has not been captured end-to-end on a real network.

## Spam creates

**Risk:** one address opens unbounded events, none of which are ever
accepted, to grief the board or exhaust storage.

**Mitigation:** `MAX_OPEN_PER_CREATOR` (8) hard-caps how many OPEN events
one address can have simultaneously, checked at `create_event` time.
Every create also costs a real, non-refundable-on-neglect `CREATE_BOND`
(0.05 GEN) that is slashed to treasury via `expire_event` if the window
opens with no acceptor -- spamming opens is not free.

**Leftover:** 8 concurrent opens times a real stake is still a real
amount of capital an attacker could tie up per address, though the bond
slash means it costs them GEN, not just gas, to do so repeatedly.

## Integer overflow / underflow

**Risk:** a payout, fee split, or bond calculation over/underflows,
producing a wrong or exploitable amount.

**Mitigation:** every GEN amount is a plain Python arbitrary-precision
`int` until the moment it's written into a `u256` storage field --
Python ints do not silently wrap, so intermediate arithmetic (fee splits,
pro-rata payouts, bond floors) cannot silently overflow before that final
cast. `payout_shares` uses integer floor division (never float), and
`TestEconomics` in `test_datum_lib.py` specifically tests the
dust-absorption behavior at the boundary. `MAX_BET` (1000 GEN) bounds the
largest single stake, keeping totals well inside `u256`'s range regardless.

**Leftover:** no fuzzing/property-based test sweep of the payout math
across the full input space was run in this session -- coverage is
example-based (specific boundary cases), not exhaustive.

## Side-switch / role confusion

**Risk:** an address that already holds a position on one side of an
event manages to also take the opposite side, or a stranger accepts on
behalf of someone else.

**Mitigation:** `accept_event` requires `side` to be the exact opposite
of `rec["creator_side"]` and refuses if the event is not `OPEN` or
already has a non-null `acceptor` -- exactly one acceptor per event,
ever. There is no "accept on behalf of" parameter anywhere in the write
API; `_sender()` (`gl.message.sender_address`) is always the party
recorded, never an address argument a caller could substitute. Nothing
stops the same address technically being both `creator` and `acceptor`
of the same event at the contract level (self-play), but doing so has no
economic upside -- it just moves GEN from one of the address's own
positions to the other, minus the fee on a decisive outcome.

**Leftover, found in this session, documented rather than fixed**: a
second `accept_event` call on an already-ACTIVE event surfaces the
generic `"not open"` UserError rather than the more specific
`"already accepted"` string, because `accept_event`'s `state != OPEN`
check runs before its `acceptor is not None` check -- the latter is
dead code, unreachable in practice, since state always flips to ACTIVE
atomically with acceptor being set. Both refuse the second accept
correctly; only the diagnostic message differs. See
`tests/direct/test_datum_contract.py`'s `test_second_accept_rejected`.

## Portal rejection patterns checked

| Pattern | Status | Note |
|---|---|---|
| Provider binding / ephemeral read accounts | Avoided | No inline provider key material anywhere; `scripts/deploy.mjs` reads a local keystore path+password from env, never a hardcoded key. |
| Checksum bugs (TreeMap keyed by checksummed hex, looked up raw) | Avoided | All TreeMap keys are plain decimal event ids or `"<event_id>:<address>"` strings, never raw vs. checksummed address ambiguity; addresses are always `str(gl.message.sender_address)`. |
| Validator independence | Addressed | `evaluate_envelope` is called identically inside `validator_fn` and again on the accepted result -- no code path trusts `leader_result`'s own verdict/code without independent re-derivation. |
| Nested nondet | Avoided | Exactly one `gl.vm.run_nondet` call per `adjudicate()` invocation; `leader_fn`/`validator_fn` make no further nondet calls of their own. |
| Finality gating | Addressed | `adjudicate()` refuses (`"window not closed"`) until chain time has passed the locked window end; `finalize()` gates on the appeal window having elapsed. |
| Unsourced evidence | Addressed | Every accepted source reading is validated against the class's own hardcoded publisher registry; unknown publishers are refused at `create_event` time (`"unknown publisher"`), never accepted ad hoc from the model. |
| No escape hatch | Addressed | `recover_refund` is a deterministic, evidence-free fallback after `RECOVER_REFUND_AFTER` (7 days) for any event stuck in ACTIVE/VERDICT_PENDING/APPEALED. |
| Single-candidate-verdict immunity | Addressed | `evaluate_envelope` requires >= 2 usable sources to reach `CLEAR`; a single usable source is `MISSING` (`INCONCLUSIVE`), never treated as sufficient. |
| Unauthenticated action | Addressed | `cancel_event` checks `sender == creator`; `appeal` checks the sender is a bonded party; `claim`/`reclaim_bonds` only ever pay `gl.message.sender_address`'s own ledger balance, never an address argument. |

## Hard-ban compliance

- No other hackathon project or submission is named or linked anywhere in this repository's code, docs, or commit messages.
- No mock/demo markets, no fake events, no synthetic GEN anywhere in `frontend/` -- every read path fails closed to empty/zero when the contract has no code at the configured address (verified live in-browser, see docs/STATUS.md).
- No user-supplied source URLs are ever accepted; publisher hosts are a hardcoded per-class allowlist (`PUBLISHER_REGISTRY` in `contracts/datum_lib.py`).
- The model's own YES/NO/verdict is never trusted as ground truth -- see `evaluate_envelope`.
- No 10-minute rain windows (`STATION_PRECIP` minimum is 6h, enforced by `CLASS_MIN_WINDOW`).
- No reanalysis product sold as a gauge reading (`looks_like_forecast_or_reanalysis` refuses `era5`/`reanalysis`/`merra`/`cfsr`/`narr` markers at create time).
- No admin seize function exists anywhere in `contracts/Datum.py`.
- No private key is committed anywhere in this repository (verified before every commit).

## Known, honestly-documented gaps (not hidden)

1. **Studio Dev hosted deploy is currently blocked**, infra-side
   (`FeeValueMustBeNonZero`), confirmed via two real attempts across
   three fee-parameter configurations. Not a contract bug -- see
   `docs/STATUS.md`.
2. **`re_adjudicate` on an appeal ground of VALUE/STATION/WINDOW/STATUS**
   re-runs the *same* `adjudicate()` non-deterministic path rather than a
   literally separate "replay stored bytes only" code path -- the
   constitution's locked fields are never mutated by an appeal, so
   re-running adjudication against those same locked fields is
   equivalent to "re-reading stored bytes" in effect, but is not a
   separate code path. Documented rather than silently assumed correct.
3. **No genuine multi-validator disagreement has been exercised live**
   -- see "Witness mismatch" above and `docs/localnet.md`.
4. **QUAKES depth is advisory, not code-enforced.** The constitution's
   optional `depth` field is now correctly surfaced in the adjudication
   prompt (fixed this session -- see CHANGELOG.md 1.1.1), and the model
   is instructed to mark a reading outside the locked depth as unusable,
   but `datum_lib.validate_source_reading` does not independently verify
   depth the way it verifies bbox membership for lat/lon. A leader that
   ignores the depth instruction would not be caught by code the way a
   wrong-station or out-of-bbox reading would be. Bbox/lat-lon
   enforcement (the primary QUAKES safety property) is code-enforced;
   depth is not. Worth closing in a follow-up if QUAKES events with a
   non-default depth see real use.
