# DATUM

DATUM settles one question on-chain: did a named instrument at a named official station, over a locked window, clear a locked threshold?

**Live app:** https://datum-gamma.vercel.app — reading the live contract (LIVE banner with the deployed address; board is empty because no events exist yet, never placeholder rows).

**Contract:** [`0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3`](https://explorer-studio-dev.genlayer.com/address/0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3) — Studio Next, chain 61997. Deploy tx [`0x84b5319b1ca744c47a0c3c36894e69cf3466c0cc3c876f4fcecf8315c440ae03`](https://explorer-studio-dev.genlayer.com/tx/0x84b5319b1ca744c47a0c3c36894e69cf3466c0cc3c876f4fcecf8315c440ae03), ACCEPTED.

**Create tx:** payable `create_event` has not yet landed on-chain. `genlayer write` (the CLI) cannot attach GEN to any payable method — confirmed by reading its source. `scripts/create_event.mjs` builds a real constitution from the contract's own live registry and config and calls `create_event` with the correct value attached; it needs the deployer keystore's password to run, which is never stored or guessed. Exact command and full detail in [docs/deployment.md](docs/deployment.md).

> "Official station observation at locked publishers for this window."

## The decision GenLayer owns

Not the inequality -- code does that, in plain integer arithmetic, and anyone can re-run it. GenLayer's validator set settles the part that actually requires judgment: which official station id reported (never a free-text nickname), whether what it reported is a completed observation (never a forecast), whether its product status is FINAL or PRELIMINARY under this event's own locked policy, whether its timestamp falls inside the locked window, what unit it was reported in, and whether two independently-read publishers agree within a locked tolerance.

The leader returns a structured JSON envelope: per-publisher source rows, plus a *proposed* verdict and code. That proposed verdict is never trusted. `contracts/datum_lib.py`'s `evaluate_envelope()` independently re-derives the verdict and code from the structured rows in integer arithmetic and only accepts the envelope when the leader's own claim matches the independent derivation exactly. Any mismatch, or any malformed field, is rejected outright and moves no funds. `adjudicate()`'s validator additionally re-fetches independently (a second `gl.nondet.exec_prompt` call) rather than only checking the leader's own claim for internal consistency -- see point 13 below for what's proven where.

## Who profits from a false "usable" reading

Whichever side of the wager that false reading favors. This is exactly why acceptance is never delegated to the model's own verdict field: a leader that could get its own proposed YES/NO trusted blindly would have a direct financial incentive -- its own stake, or a briber's -- to misreport a source as usable when it should have been unusable, or to claim agreement between two publishers that actually conflict. Independent code-side re-derivation from the structured per-source rows, cross-checked by every validator through `gl.vm.run_nondet`'s validator function, removes that single point of leverage. There is no admin key that can force a verdict or move a pot either.

## Instrument classes (V1 -- never mixed in one constitution)

| Class | Instrument | Official id | Unit | Min window | Min lead | Publishers |
|---|---|---|---|---|---|---|
| STATION_PRECIP | Accumulated precipitation | NWS/ASOS/GHCN station id | mm | 6h | 2h | NWS_OBS + GHCN_DAILY |
| STATION_TEMP | Max or min temperature in window | Same station-id family | &deg;C | 24h | 2h | NWS_OBS + GHCN_DAILY |
| STAGE | River stage | USGS 8-digit site number | m | 6h | 2h | USGS_WATER + NOAA_NWPS |
| QUAKES | Max moment magnitude in a bbox | Bounding box (+ optional depth) | Mw | 1h | 30m | USGS_QUAKE + EMSC |

## Must agree vs. may differ vs. unusable

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

22 public methods (10 view, 12 write) -- independently confirmed live via `gen_getContractSchema` against the deployed contract, and via `genvm-lint schema` against the bundle. See [docs/deployment.md](docs/deployment.md).

**Writes:** `create_event`, `accept_event`, `adjudicate`, `finalize`, `appeal`, `re_adjudicate`, `lapse_appeal`, `cancel_event`, `expire_event`, `claim`, `recover_refund`, `reclaim_bonds`.

**Views:** `get_constitution`, `get_config`, `get_registry`, `get_event`, `get_board`, `get_record`, `get_position`, `get_positions`, `get_claimable`, `get_activity`.

Full typed signatures in `contracts/Datum.py`.

## Tests + lint

```bash
# Primary, verified coverage -- zero genlayer imports, plain pytest.
# Includes 5 dedicated "lying leader" tests: reproduces adjudicate()'s
# real validator comparison and proves a leader whose independent
# re-fetch would disagree (on usability, station id, tolerance, or
# window) is rejected.
python -m pytest tests/direct/test_datum_lib.py -q
# 64 passed

# Rebuild the deployable bundle + size check:
python scripts/build_bundle.py
# 41489 bytes, well under the 52224-byte Studio ceiling -- sha256 matches
# the deployed contract exactly, see deploy/deployments.json

# AST-based safety lint + full runtime validation, both on the bundle:
PYTHONIOENCODING=utf-8 genvm-lint check artifacts/Datum.bundled.py
# Lint passed (3 checks); Validation passed; 22 methods (10 view, 12 write)

# gltest direct-mode: real deploy + happy path AND refusal path for
# EVERY one of the 12 write methods, against a live GenVM sandbox:
python -m pytest tests/direct/test_datum_contract.py -q
# 27 passed
```

## Network

| | |
|---|---|
| Network | Studio Next (Studio Dev) |
| Chain id | 61997 |
| RPC | https://studio-dev.genlayer.com/api |
| Studio UI | https://studio-dev.genlayer.com |
| Explorer | https://explorer-studio-dev.genlayer.com |
| Currency | GEN, 18 decimals |

**Studio Next state may reset at any time.** Do not treat the contract address, any event id, or any balance on this network as durable. If the address stops resolving, it was reset -- see [docs/deployment.md](docs/deployment.md) for the redeploy command.

## Proven on-chain vs. proven only in `gltest`

Stated explicitly rather than left to be inferred from where a claim appears:

**Proven on real Studio Next execution:**
- Deploy itself (constructor, storage allocation, all 22 methods registered) -- `gen_getContractSchema` against the live address.
- A real read (`get_config`) returning real on-chain state.
- A real non-payable write (`expire_event` on a nonexistent id) returning the contract's own `event not found` UserError from a real consensus round -- proves write dispatch and error handling execute on-chain, not just in a mock.

**Proven only in `gltest` direct-mode (a real GenVM sandbox, but a single in-process leader, not real multi-validator consensus), not yet on-chain:**
- Every payable method: `create_event`, `accept_event`, `adjudicate`, `appeal`, `re_adjudicate`. No GEN has moved through this contract on any live network yet.
- The lying-leader rejection (`adjudicate()`'s validator independently re-fetching and rejecting a leader whose result disagrees) -- proven at the `datum_lib` comparator level and via `gltest`'s single-leader execution, but never against two genuinely independent GenVM nodes actually disagreeing, which `gltest` cannot simulate.
- `claim()`'s actual payout -- proven at the internal ledger-accounting level (`claimable` zeroes, the right amount is returned) in `gltest`, not as a real GEN balance delta on a live account, since no real stake has moved yet to claim.
- The other six write methods with frontend UI entry points (`appeal`, `re_adjudicate`, `lapse_appeal`, `cancel_event`, `expire_event`, `reclaim_bonds`) -- type-checked, never clicked through a live wallet.

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

## How to deploy (already done once; here for redeploy after a reset)

```bash
python scripts/build_bundle.py
genlayer deploy --contract artifacts/Datum.bundled.py \
  --args '"0xYOUR_TREASURY_ADDRESS"' \
  --fees '{"distribution":{"rotations":[0],"appealRounds":0,"totalMessageFees":0,"executionConsumed":0,"receiptFeeMaxGasPrice":"300000000","storageFeeMaxGasPrice":"300000000","maxPriceGenPerTimeUnit":"2","executionBudgetPerRound":"94643100000000","leaderTimeunitsAllocation":"100","validatorTimeunitsAllocation":"200"}}' \
  --fee-value 94643100002588
```

Needs BOTH a complete fee distribution (not just `--fee-value`) and a
JSON-quoted string argument (`--args '"0x..."'`, not `'["0x..."]'`) --
full diagnosis of why the naive form fails in [docs/deployment.md](docs/deployment.md).
