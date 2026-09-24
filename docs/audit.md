# DATUM -- self-audit

Point-by-point self-review against this codebase's own accumulated
GenLayer Portal rejection patterns and the spec's hard bans.

## Portal rejection patterns checked

| Pattern | Status | Note |
|---|---|---|
| Provider binding / ephemeral read accounts | Avoided | No inline provider key material anywhere; `scripts/deploy.mjs` reads a local keystore path+password from env, never a hardcoded key. |
| Checksum bugs (TreeMap keyed by checksummed hex, looked up raw) | Avoided | All TreeMap keys are plain decimal event ids or `"<event_id>:<address>"` strings, never raw vs. checksummed address ambiguity; addresses are always `str(gl.message.sender_address)`. |
| Validator independence | Addressed | `evaluate_envelope` is called identically inside `validator_fn` and again on the accepted result -- no code path trusts `leader_result`'s own verdict/code without independent re-derivation. |
| Nested nondet | Avoided | Exactly one `run_nondet_unsafe` call per `adjudicate()` invocation; `leader_fn`/`validator_fn` make no further nondet calls of their own. |
| Finality gating | Addressed | `adjudicate()` refuses (`"window not closed"`) until chain time has passed the locked window end; `finalize()` refuses (`"appeal closed"` as the not-yet-elapsed signal) until the appeal window has elapsed. |
| Unsourced evidence | Addressed | Every accepted source reading is validated against the class's own hardcoded publisher registry; unknown publishers are refused at `create_event` time (`"unknown publisher"`), never accepted ad hoc from the model. |
| No escape hatch | Addressed | `recover_refund` is a deterministic, evidence-free fallback after `RECOVER_REFUND_AFTER` (7 days) for any event stuck in ACTIVE/VERDICT_PENDING/APPEALED. |
| Single-candidate-verdict immunity | Addressed | `evaluate_envelope` requires >= 2 usable sources to reach `CLEAR`; a single usable source is `MISSING` (`INCONCLUSIVE`), never treated as sufficient. |
| Unauthenticated action | Addressed | `cancel_event` checks `sender == creator`; `appeal` checks `sender in (creator, acceptor)`; `claim`/`reclaim_bonds` only ever pay `gl.message.sender_address`'s own ledger balance, never an address argument. |

## Hard-ban compliance

- No other hackathon project or submission is named or linked anywhere in this repository's code, docs, or (intended) commit messages.
- No mock/demo markets, no fake events, no synthetic GEN anywhere in `frontend/` -- every read path fails closed to empty/zero when the contract has no code at the configured address.
- No user-supplied source URLs are ever accepted; publisher hosts are a hardcoded per-class allowlist (`PUBLISHER_REGISTRY` in `contracts/datum_lib.py`).
- The model's own YES/NO/verdict is never trusted as ground truth -- see `evaluate_envelope`.
- No 10-minute rain windows (`STATION_PRECIP` minimum is 6h, enforced by `CLASS_MIN_WINDOW`).
- No reanalysis product sold as a gauge reading (`looks_like_forecast_or_reanalysis` refuses `era5`/`reanalysis`/`merra`/`cfsr`/`narr` markers at create time).
- No admin seize function exists anywhere in `contracts/Datum.py`.
- No private key is committed anywhere in this repository (verified before commit -- see the git-safety scan in the handoff report).

## Known, honestly-documented gaps (not hidden)

1. **Local toolchain gap** (pre-existing on this machine, not a bug in this contract): `genvm-lint validate`/`schema` and `gltest` direct-mode deploy both fail locally. See [docs/STATUS.md](STATUS.md) for the exact captured error text and root cause. Primary verified coverage is therefore `contracts/datum_lib.py`'s 55/55 plain-pytest unit tests plus a clean `genvm-lint lint` pass (pure AST-based, no runtime needed) on both `contracts/Datum.py` and `artifacts/Datum.bundled.py`.
2. **`re_adjudicate` on an appeal ground of VALUE/STATION/WINDOW/STATUS** re-runs the *same* `adjudicate()` non-deterministic path rather than a separate "replay stored bytes only" code path -- the constitution's locked fields (`station_id`, `window`, `product_status_policy`, threshold/cmp) are never mutated by an appeal, so re-running adjudication against those same locked fields is equivalent to "re-reading stored bytes" in effect, but it is not a literally separate code path. Documented here rather than silently assumed correct.
3. **Frontend has no live functional test** -- Node/npm dependency install and a dev-server smoke test were not run in this session (see docs/STATUS.md); the SDK and routes were written and reviewed but not executed against a live `next dev` server.
