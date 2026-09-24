# DATUM

DATUM settles one question on-chain: did a named instrument at a named official station, over a locked window, clear a locked threshold?

**Live URL:** https://datum-gamma.vercel.app (frontend shell only -- contract not yet deployed, so it fails closed).
**Contract address:** not yet deployed (Studio Dev, chain id 61997) -- see [docs/STATUS.md](docs/STATUS.md) for exact readiness state and blockers.

> "Official station observation at locked publishers for this window."

## What GenLayer decides, what code decides

GenLayer's validator set settles the contested, judgment-shaped part of the question: which official station id actually reported (never a free-text nickname), whether the reading is a completed observation (never a forecast), whether its product status is FINAL or PRELIMINARY under this event's own locked policy, whether its timestamp actually falls inside the locked window, what unit it was reported in, and whether two independently-read publishers agree within a locked tolerance.

Code owns the comparison. The model returns a structured JSON envelope containing per-publisher source data and a *proposed* verdict/code -- that proposed verdict is never trusted blindly. `contracts/datum_lib.py`'s `evaluate_envelope()` independently re-derives the verdict and code from the structured source rows and only accepts the envelope when the leader's own claim matches the independently-derived one exactly. A mismatch, or any malformed field, is rejected outright and moves no funds.

## Who profits from a false "usable" reading

Whichever side of the wager a falsely-accepted reading favors. This is exactly why acceptance is never delegated to the model's own verdict field: a leader node that could get its own proposed YES/NO trusted blindly would have a direct financial incentive (its own stake, or a briber's) to misreport a source as usable when it should have been marked unusable, or to fabricate agreement between two publishers that actually conflict. Independent code-side re-derivation from the structured per-source rows, cross-checked by every validator via `gl.vm.run_nondet_unsafe`'s validator_fn, removes that single point of leverage.

## Instrument classes (V1 -- never mixed in one constitution)

| Class | Instrument | Official id | Unit | Min window | Publishers |
|---|---|---|---|---|---|
| STATION_PRECIP | Accumulated precipitation | NWS/ASOS/GHCN station id | mm | 6h | Two locked precipitation hosts |
| STATION_TEMP | Max or min temperature in window | Same station-id family | &deg;C | 24h | Two locked temperature hosts |
| STAGE | River stage | USGS 8-digit site number | m | 6h | USGS Water Services + NOAA NWPS |
| QUAKES | Max moment magnitude in a bbox | Bounding box (+ optional depth) | Mw | 1h | USGS earthquake catalog + EMSC |

## Constitution (frozen fields, sha256-committed before acceptance)

`class`, `station_id` (or `bbox` for QUAKES), `metric`, `threshold` (scaled integer, `VALUE_SCALE=100`), `cmp` (`gt`\|`gte`\|`lt`\|`lte`), `window` (`[start, end)` Unix chain time only), `publishers` (2-3, from the class's own registry), `product_status_policy` (`FINAL_ONLY` default, or `ALLOW_PRELIMINARY`), `tolerance` (class default if omitted). A missing reading never counts as zero; a conflict beyond tolerance and a missing reading both resolve to `INCONCLUSIVE`, never a forced YES/NO.

## Equivalence: what must agree vs. what may differ

**Must agree** (within tolerance / exactly, per field): converted reading value (within the class's locked tolerance), station id, product status, and that the timestamp falls inside the locked window. **May differ**: raw JSON formatting, key order, and volatile fields (`generationtime_ms`, `requestId`, `requestDT`, `generated`, and similar) -- these are stripped before any stability digest is taken, so two publishers' differently-formatted-but-equivalent raw responses still converge on the same accepted record.

## Economics (immutable after deploy)

- `MIN_BET` = 0.01 GEN, `MAX_BET` = 1000 GEN
- `CREATE_BOND` = 0.05 GEN (slashed to treasury if the window starts with no acceptor)
- `ADJUDICATE_BOND` = 0.02 GEN (returned + fee share on a decisive YES/NO)
- `FEE_BPS` = 200 (2%) of a **decisive** pot only, split 50/50 adjudicator/treasury; 0% on any refund
- `APPEAL_BOND` = 50% of one side's stake, floor 0.05 GEN
- `APPEAL_WINDOW` chosen at create time, 5 minutes to 7 days
- `LAPSE_APPEAL_STALL` = 1 hour (an unfollowed appeal restores the prior verdict)
- `RECOVER_REFUND_AFTER` = 7 days (deterministic no-fee refund if an event never reaches FINALIZED)
- `MAX_OPEN_PER_CREATOR` = 8

## Methods

See `contracts/Datum.py` for the full typed API. Views: `get_constitution`, `get_config`, `get_registry`, `get_event`, `get_board`, `get_record`, `get_position`, `get_positions`, `get_claimable`, `get_activity`. Writes: `create_event`, `accept_event`, `adjudicate`, `finalize`, `appeal`, `re_adjudicate`, `lapse_appeal`, `cancel_event`, `expire_event`, `claim`, `recover_refund`, `reclaim_bonds`.

## How to test

```bash
# Primary, verified coverage -- zero genlayer imports, plain pytest:
python -m pytest tests/direct/test_datum_lib.py -q

# Bundle + size check:
python scripts/build_bundle.py

# AST-based safety lint (works locally):
PYTHONIOENCODING=utf-8 genvm-lint lint artifacts/Datum.bundled.py

# Full-runtime validation / gltest direct-mode (currently blocked locally --
# see docs/STATUS.md for the exact captured errors and why):
gltest tests/direct/test_datum_contract.py
```

## How to deploy

Not attempted in this build session by design (see [docs/STATUS.md](docs/STATUS.md) for the exact commands to run yourself, and the known Studio Dev hosted-deploy risk, genlayer-studio#1757).

## What we refused (by design, at `create_event` time)

- Reanalysis products (ERA5, MERRA, CFSR, NARR, ...) labeled as a station reading
- Free-text station "nicknames" with no official-id shape
- Forecast endpoints presented as completed observations
- Publishers from two different instrument classes mixed into one constitution
- A single publisher (two independent publishers are the floor)
- A window shorter than the class minimum, or starting before `now + MIN_LEAD`
- A model's own YES/NO/verdict trusted without code independently re-deriving and matching it

## Network

| | |
|---|---|
| Network | Studio Dev only |
| Chain id | 61997 |
| RPC | https://studio-dev.genlayer.com/api |
| Studio UI | https://studio-dev.genlayer.com |
| Explorer | https://explorer-studio-dev.genlayer.com |
| Currency | GEN, 18 decimals |

**Studio Dev state may reset at any time.** Do not treat any address, event id, or balance on this network as durable.
