# Security review

Risk-by-risk review of DATUM's fund-handling and adjudication logic. Each entry is risk → mitigation → residual limitation.

## Trapped funds

**Risk:** an event stuck in a non-terminal state (`ACTIVE`, `VERDICT_PENDING`, `APPEALED`) permanently locks both parties' stakes.

**Mitigation:** `recover_refund(event_id)` is a deterministic, evidence-free fallback. Any event that has not reached a terminal state within `RECOVER_REFUND_AFTER` (7 days) can have both stakes returned by anyone calling it. `lapse_appeal` bounds a stalled appeal to 1 hour before restoring the prior verdict. `claim()` is the only method that moves GEN out of the contract, and it only ever pays the caller's own credited balance (`self.claimable[gl.message.sender_address]`) — never an address argument, so a claim cannot be redirected.

Every value credited during settlement — the create bond, the adjudicate bond, the appeal bond, and the decisive-pot fee split — is routed through this same `claimable` ledger and drained only by `claim()`. There is no separate accounting path for any of these, which removes an entire class of "credited somewhere untracked" bugs.

**Residual:** `claim()`'s payout math (`payout_shares`, integer floor division) means the last claimant on a winning side can receive a few wei more or less than a perfectly proportional split. Bounded, tested, and economically immaterial at GEN's 18-decimal scale.

## Wrong station accepted as evidence

**Risk:** a reading for the wrong station is accepted as the locked station's own observation.

**Mitigation:** `validate_source_reading` requires each source's `station_id` to case-insensitively match the constitution's locked `expected_station_id` exactly, for every class except QUAKES. QUAKES has no single station id, so it instead requires the source's reported epicenter (`lat`/`lon`) to fall inside the locked bounding box. Any mismatch marks that source `usable=false` — never averaged in, never imputed. `is_official_station_id` additionally refuses a free-text station at `create_event` time, before any adjudication is possible.

**Residual:** none identified. Station-id matching is exact-string by design, not fuzzy.

## Preliminary data treated as final

**Risk:** a not-yet-finalized reading is treated as authoritative under a policy requiring final data only.

**Mitigation:** `validate_source_reading` marks a source unusable if its `product_status` is `PRELIMINARY` under a `FINAL_ONLY` policy. `FINAL_ONLY` is the default; `ALLOW_PRELIMINARY` is an explicit, constitution-locked opt-in at create time. The `PRELIMINARY_BLOCKED` outcome code surfaces this distinctly in `get_record`.

**Residual:** DATUM has no mechanism to force a re-read once a preliminary reading is later revised to final, other than the `REVISED` appeal ground. An event that settles inconclusive and is never appealed refunds both sides even if the underlying data later becomes final and decisive.

## Witness (publisher) mismatch

**Risk:** the leader claims two publishers agree when they don't, or fabricates readings outright.

**Mitigation:** `evaluate_envelope` never trusts a leader's claimed `verdict`/`code` — it independently re-derives both from the envelope's `sources` rows. `adjudicate()`'s `validator_fn` goes further: it calls `leader_fn()` a second time, independently, and only accepts when the two independently-derived outcomes (verdict, code, agreed value) agree. A leader that fabricates an internally-consistent but fictional envelope cannot pass unless a second, independent fetch produces the same result. See [architecture.md](architecture.md) for the full call flow.

**Residual:** `gltest`'s single-process sandbox cannot simulate genuine multi-validator disagreement over a real network — see [testing.md](testing.md). The comparator logic itself is proven directly (`TestLyingLeaderDetection` in `test_datum_lib.py`) and exercised through the real adjudication path in `gltest`, but a live network-level disagreement has not been captured end-to-end.

## Spam creates

**Risk:** one address opens unbounded events to grief the board or exhaust storage.

**Mitigation:** `MAX_OPEN_PER_CREATOR` (8) caps concurrent open events per address. Every create costs a non-trivial `CREATE_BOND` (0.05 GEN), slashed to treasury if the window opens with no acceptor.

**Residual:** 8 concurrent opens at a real stake is still real capital an attacker could tie up per address, though the bond slash makes repeated abuse costly rather than free.

## Integer overflow / underflow

**Risk:** a payout, fee split, or bond calculation over- or underflows.

**Mitigation:** every GEN amount is a plain Python arbitrary-precision `int` until the moment it is written into a `u256` storage field, so intermediate arithmetic cannot silently wrap. `payout_shares` uses integer floor division, never float. `MAX_BET` (1000 GEN) bounds the largest single stake well inside `u256`'s range.

**Residual:** coverage is example-based (specific boundary cases in `TestEconomics`), not an exhaustive property-based sweep of the input space.

## Side-switch / role confusion

**Risk:** an address takes both sides of an event, or a stranger accepts on someone else's behalf.

**Mitigation:** `accept_event` requires `side` to be the exact opposite of the creator's side, and refuses once an event has already been accepted. There is no "accept on behalf of" parameter anywhere in the write API — the caller's own sender address is always the party recorded. Nothing prevents the same address from being both creator and acceptor of the same event, but doing so has no economic upside: it only moves GEN between that address's own positions, minus the decisive-outcome fee.

**Residual:** a second `accept_event` call on an already-active event surfaces the generic `"not open"` error rather than the more specific `"already accepted"` string, since the state check runs first. Both correctly refuse the second accept; only the diagnostic message differs.

## Portal rejection patterns checked

| Pattern | Status | Note |
|---|---|---|
| Provider binding / ephemeral read accounts | Avoided | No inline provider key material anywhere; deploy/write scripts read a local keystore path and password from environment variables, never a hardcoded key. |
| Checksum ambiguity (map keyed by checksummed hex, looked up raw) | Avoided | All map keys are plain decimal event ids or `"<event_id>:<address>"` strings; addresses are always `str(gl.message.sender_address)`. |
| Validator independence | Addressed | `validator_fn` independently re-fetches and re-derives rather than checking only the leader's own claimed output. |
| Nested non-determinism | Avoided | Exactly one `gl.vm.run_nondet` call per `adjudicate()` invocation. |
| Finality gating | Addressed | `adjudicate()` refuses until the locked window has closed; `finalize()` gates on the appeal window having elapsed. |
| Unsourced evidence | Addressed | Every accepted source is validated against a hardcoded, per-class publisher allowlist; unknown publishers are refused at create time. |
| No escape hatch | Addressed | `recover_refund` is a deterministic, evidence-free fallback for any event stuck in a non-terminal state past `RECOVER_REFUND_AFTER`. |
| Single-source verdict | Addressed | `evaluate_envelope` requires at least two usable sources to reach a decisive outcome. |
| Unauthenticated action | Addressed | `cancel_event` requires the sender be the creator; `appeal` requires a bonded party; `claim`/`reclaim_bonds` only ever pay the caller's own credited balance. |

## Hard constraints

- No other project is named or referenced anywhere in this repository.
- No mock or demo data anywhere in `frontend/` — every read path fails closed to an honest empty/zero state when the contract is unreachable or not yet deployed.
- No user-supplied source URL is ever accepted; publisher hosts are a hardcoded per-class allowlist.
- No admin function can seize funds or force a verdict.
- No private key, keystore, mnemonic, or `.env` file is committed to this repository.

## Known limitations

1. **`re_adjudicate` on grounds VALUE/STATION/WINDOW/STATUS** re-runs the same non-deterministic `adjudicate()` path rather than a literally separate "replay stored bytes only" code path. Since the constitution's locked fields are never mutated by an appeal, re-running adjudication against those same locked fields is equivalent in effect, but not a distinct code path.
2. **No genuine multi-validator disagreement has been exercised live** — see "Witness mismatch" above and [testing.md](testing.md).
3. **QUAKES `depth` is advisory, not code-enforced.** The locked depth is surfaced in the adjudication prompt and the model is instructed to treat an out-of-range reading as unusable, but `validate_source_reading` does not independently verify depth the way it verifies bbox membership. Bbox/lat-lon enforcement (the primary QUAKES safety property) is code-enforced; depth is not.
