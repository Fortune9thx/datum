# DATUM

DATUM settles one question on-chain: did a named instrument at a named official station, over a locked window, clear a locked threshold?

**Live app:** https://datum-gamma.vercel.app (marketing site + board/create/stations/portfolio/activity/docs -- fails closed everywhere below, since nothing is deployed yet).

**Contract address:** not deployed -- see [docs/STATUS.md](docs/STATUS.md) for two real, documented Studio Dev deploy attempts (both blocked by an infra-side FeeManager revert, unrelated to this repo's code) and [docs/localnet.md](docs/localnet.md) for a real, passing local execution proof instead.

> "Official station observation at locked publishers for this window."

## The decision GenLayer owns

Not the inequality -- code does that, in plain integer arithmetic, and anyone can re-run it. GenLayer's validator set settles the part that actually requires judgment: which official station id reported (never a free-text nickname), whether what it reported is a completed observation (never a forecast), whether its product status is FINAL or PRELIMINARY under this event's own locked policy, whether its timestamp falls inside the locked window, what unit it was reported in, and whether two independently-read publishers agree within a locked tolerance.

The leader returns a structured JSON envelope: per-publisher source rows, plus a *proposed* verdict and code. That proposed verdict is never trusted. `contracts/datum_lib.py`'s `evaluate_envelope()` independently re-derives the verdict and code from the structured rows in integer arithmetic and only accepts the envelope when the leader's own claim matches the independent derivation exactly. Any mismatch, or any malformed field, is rejected outright and moves no funds.

## Who profits from a false "usable" reading

Whichever side of the wager that false reading favors. This is exactly why acceptance is never delegated to the model's own verdict field: a leader that could get its own proposed YES/NO trusted blindly would have a direct financial incentive -- its own stake, or a briber's -- to misreport a source as usable when it should have been unusable, or to claim agreement between two publishers that actually conflict. Independent code-side re-derivation from the structured per-source rows, cross-checked by every validator through `gl.vm.run_nondet`'s validator function, removes that single point of leverage. There is no admin key that can force a verdict or move a pot either.

## Instrument classes (V1 -- never mixed in one constitution)

| Class | Instrument | Official id | Unit | Min window | Min lead | Publishers |
|---|---|---|---|---|---|---|
| STATION_PRECIP | Accumulated precipitation | NWS/ASOS/GHCN station id | mm | 6h | 2h | NWS_OBS + GHCN_DAILY |
| STATION_TEMP | Max or min temperature in window | Same station-id family | &deg;C | 24h | 2h | NWS_OBS + GHCN_DAILY |
| STAGE | River stage | USGS 8-digit site number | m | 6h | 2h | USGS_WATER + NOAA_NWPS |
| QUAKES | Max moment magnitude in a bbox | Bounding box (+ optional depth) | Mw | 1h | 30m | USGS_QUAKE + EMSC |

## Equivalence: must agree vs. may differ vs. unusable

**Must agree**, per usable source, within the constitution's locked tolerance: the converted reading value, the station id (or, for QUAKES, an epicenter inside the locked bbox), the product status, and that the timestamp falls inside the locked window.

**May differ**: raw JSON formatting, key order, and volatile fields (`generationtime_ms`, `requestId`, `requestDT`, `generated`, and similar) -- these are stripped before any stability digest is taken, so two publishers' differently-formatted-but-equivalent raw responses still converge on the same accepted record.

**Unusable, never averaged in, never imputed as zero**: an unreachable or non-200 source, a wrong or malformed station id, a timestamp outside the window, a forecast-marked or reanalysis-marked product, a PRELIMINARY reading under a `FINAL_ONLY` policy, or (QUAKES only) an epicenter outside the locked bbox.

## Failure policy

| Code | Verdict | Cause | Money |
|---|---|---|---|
| `CLEAR` | YES / NO | Two-plus usable readings agreed within tolerance; threshold compared | Decisive -- 2% fee on the pot |
| `MISSING` | INCONCLUSIVE | Fewer than two usable readings | Both stakes returned, no fee |
| `CONFLICT` | INCONCLUSIVE | Usable readings disagreed beyond tolerance | Both stakes returned, no fee |
| `PRELIMINARY_BLOCKED` | INCONCLUSIVE | Readings existed but were PRELIMINARY under `FINAL_ONLY` | Both stakes returned, no fee |

If an event never reaches a terminal state at all, `recover_refund()` returns both stakes deterministically after 7 days -- no evidence required, no fee. Liveness failure never strands funds.

## Economics (immutable after deploy)

| | |
|---|---|
| `MIN_BET` | 0.01 GEN |
| `MAX_BET` | 1000 GEN |
| `CREATE_BOND` | 0.05 GEN -- slashed to treasury if the window opens with no acceptor |
| `ADJUDICATE_BOND` | 0.02 GEN -- returned + fee share on a decisive verdict |
| `FEE_BPS` | 200 (2%) of a decisive pot only -- 50% adjudicator / 50% treasury; 0% on any refund |
| `APPEAL_BOND` | 50% of one side's stake, floor 0.05 GEN |
| `APPEAL_WINDOW` | chosen at create, 5 minutes to 7 days |
| `LAPSE_APPEAL_STALL` | 1 hour -- an unfollowed appeal restores the prior verdict |
| `RECOVER_REFUND_AFTER` | 7 days -- deterministic no-fee refund if never terminal |
| `MAX_OPEN_PER_CREATOR` | 8 |

## Methods

22 public methods (10 view, 12 write) -- independently confirmed via `genvm-lint schema` against the deployable bundle, see `docs/STATUS.md`.

**Writes:** `create_event`, `accept_event`, `adjudicate`, `finalize`, `appeal`, `re_adjudicate`, `lapse_appeal`, `cancel_event`, `expire_event`, `claim`, `recover_refund`, `reclaim_bonds`.

**Views:** `get_constitution`, `get_config`, `get_registry`, `get_event`, `get_board`, `get_record`, `get_position`, `get_positions`, `get_claimable`, `get_activity`.

Full typed signatures in `contracts/Datum.py`.

## How to test

```bash
# Primary, verified coverage -- zero genlayer imports, plain pytest:
python -m pytest tests/direct/test_datum_lib.py -q
# 59 passed

# Rebuild the deployable bundle + size check:
python scripts/build_bundle.py
# 40758 bytes, well under the 52224-byte Studio ceiling

# AST-based safety lint + full runtime validation, both on the bundle:
PYTHONIOENCODING=utf-8 genvm-lint check artifacts/Datum.bundled.py
# Lint passed (3 checks); Validation passed; 22 methods (10 view, 12 write)

# gltest direct-mode: real deploy + create/accept/cancel/adjudicate-guard
# flow against a live GenVM sandbox (see docs/localnet.md for what this
# does and doesn't prove):
python -m pytest tests/direct/test_datum_contract.py -q
# 9 passed
```

## How to deploy

Not currently possible on Studio Dev -- two real, documented attempts (a
trivial Hello contract and the full DATUM bundle, both via `genlayer
deploy`) reverted identically with `FeeValueMustBeNonZero`, an infra-side
FeeManager issue, not a contract or repo problem. Full proof, exact
commands, and what to try once it clears: [docs/STATUS.md](docs/STATUS.md).
A real local execution proof exists in the meantime:
[docs/localnet.md](docs/localnet.md).

## What we refused (by design, at `create_event` time)

- Reanalysis products (ERA5, MERRA, CFSR, NARR, ...) labeled as a station reading
- Free-text station "nicknames" with no official-id shape
- Forecast endpoints presented as completed observations
- Publishers from two different instrument classes mixed into one constitution
- A single publisher (two independent publishers are the floor)
- A window shorter than the class minimum, or starting before `now + MIN_LEAD`
- A caller-supplied source URL (publishers are a hardcoded per-class allowlist)
- A model's own YES/NO/verdict trusted without code independently re-deriving and matching it
- An admin key that can seize funds or force a verdict

## Network

| | |
|---|---|
| Network | Studio Next (Studio Dev) only |
| Chain id | 61997 |
| RPC | https://studio-dev.genlayer.com/api |
| Studio UI | https://studio-dev.genlayer.com |
| Explorer | https://explorer-studio-dev.genlayer.com |
| Currency | GEN, 18 decimals |

**Studio Dev state may reset at any time.** Do not treat any address, event id, or balance on this network as durable.
