# Deployment

## Current deployment

| | |
|---|---|
| Network | Studio Next (chain 61997) |
| Contract | `0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3` |
| Deploy tx | `0x84b5319b1ca744c47a0c3c36894e69cf3466c0cc3c876f4fcecf8315c440ae03` |
| Explorer | https://explorer-studio-dev.genlayer.com/address/0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3 |
| Treasury | `0xC6E6d3b2acCaECeCeB40Ad4bD3dF123DDCB4e537` |

Machine-readable record: [`deploy/deployments.json`](../deploy/deployments.json). Its `bundleSha256` must match `sha256(artifacts/Datum.bundled.py)` — as of the redeploy blocker below, it currently does **not**; see that section before assuming the two are in sync.

Studio Next is a development preview and resets periodically. If the contract address stops resolving, it was reset — redeploy with the command below and update `deploy/deployments.json` and the `NEXT_PUBLIC_DATUM_CONTRACT_ADDRESS` environment variable.

## Known issue: redeploy currently blocked (hosted `__init__` execution)

A source change added `Address(treasury).as_hex` normalization to the constructor (closing a checksum-case bug in `get_position`/`get_positions`/`get_claimable`/`get_activity` — see `docs/audit.md`). That change is committed and passes every local check, but it has not been possible to ship it to a live contract: three consecutive deploy attempts on Studio Next failed with `FINISHED_WITH_ERROR` (transaction `ACCEPTED`, constructor execution reverted):

- `0x98bcbc8c455f66792ffbbfd7093932e990b3b93c84845a2626aa951450b8cc19` — full DATUM bundle, explicit `--fee-value`.
- `0xd1801f67d2db6653574c4df6f1be00237eaec9f442fb1d8ae8a4e9c5fd8de146` — full DATUM bundle, `--fee-value` omitted (CLI auto-derived).
- `0x7d39c9105005dd7d00f6ff87e9328054987f3bedd4b58eb005293dde2b0829b3` — a minimal 20-line isolation contract (`contracts/ProbeTreasury.py`), same pinned dependency hash, whose entire constructor is `self.treasury = Address(treasury).as_hex` and nothing else.

The third result is the important one: it rules out anything specific to DATUM's size or structure. Ruled out directly:

- **Fee/gas budget** — identical failure with and without an explicit `--fee-value`.
- **A logic bug in the change itself** — the exact same bundle, treasury argument, and pinned SDK version (`v0.6.0-rc6`) deploy and execute correctly in a local `gltest` reproduction (`__init__`, `get_config()`, and `get_claimable()` all succeed).
- **A WASM-sandbox portability gap** — the real SDK's `Address.as_hex`/`Keccak256` implementation is pure Python with no native dependencies, so there's no reason it would behave differently in the hosted sandbox than locally.

Studio Next's debug-trace RPC (`gen_dbg_traceTransaction`) returns `Method not found` on the hosted API, so no traceback is retrievable for any of the three failures. The working conclusion — not a proven root cause, the best-supported explanation after ruling out the above — is that the hosted runner for this pinned dependency hash currently behaves differently from the local cached SDK build for at least this constructor pattern. `genlayer-studio`'s GitHub issues have several other open, unrelated infrastructure-correctness reports filed in the same window (e.g. #1757, #1761, #1767–#1769), consistent with broader instability rather than a DATUM-specific regression, though none matches this exact symptom.

**Decision:** stop spending GEN on further blind retries. The live contract at `0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3` (see above) is unaffected and keeps running the pre-fix code — the frontend continues pointing at it. The checksum fix stays committed in source (`contracts/Datum.py`, `artifacts/Datum.bundled.py`) and will ship on the next redeploy attempt, once this clears. If retrying: try again after a delay (this network's infra issues have historically been transient), and if it fails identically again, file a `genlayer-studio` issue with this exact reproduction — the existing open issues don't cover it.

## Verifying a deployment is live

`eth_getCode` is not a valid liveness check for a GenLayer contract — it always returns `0x`, since GenLayer contracts are not EVM bytecode. Use the network's own JSON-RPC method instead:

```bash
curl -s https://studio-dev.genlayer.com/api \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"gen_getContractSchema","params":["0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3"]}'
```

A live contract returns its method schema. A nonexistent one returns JSON-RPC error `-32001`. The frontend's `probeContract()` (`frontend/src/lib/datum/network.ts`) uses this method.

A read call is a simpler check:

```bash
genlayer call 0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3 get_config
```

## Deploying

```bash
python scripts/build_bundle.py
genlayer deploy --contract artifacts/Datum.bundled.py \
  --args '"0xYOUR_TREASURY_ADDRESS"' \
  --fees '{"distribution":{"rotations":[0],"appealRounds":0,"totalMessageFees":0,"executionConsumed":0,"receiptFeeMaxGasPrice":"300000000","storageFeeMaxGasPrice":"300000000","maxPriceGenPerTimeUnit":"2","executionBudgetPerRound":"94643100000000","leaderTimeunitsAllocation":"100","validatorTimeunitsAllocation":"200"}}' \
  --fee-value 94643100002588
```

Two details matter here:

- **`--args` must be a JSON-quoted string** (`'"0x..."'`), not a JSON array (`'["0x..."]'`). The constructor takes a single `treasury: str` argument; passing an array causes the CLI to hand the contract a list instead of a string.
- **`--fees` needs a complete distribution object**, not just `--fee-value`. An incomplete distribution is rejected by the network before the transaction is broadcast. The values above were taken from a confirmed successful deployment on this network and are safe defaults to reuse.

After a successful deploy, set the contract address in Vercel and redeploy the frontend:

```bash
cd frontend
vercel env add NEXT_PUBLIC_DATUM_CONTRACT_ADDRESS production
vercel env add NEXT_PUBLIC_DATUM_CONTRACT_ADDRESS preview
vercel --prod --yes
```

## Sending a write transaction

`genlayer write` cannot attach GEN to a payable method call — it always sends zero value. For any payable method (`create_event`, `accept_event`, `adjudicate`, `appeal`, `re_adjudicate`), use either:

- the frontend, connected to an injected wallet, or
- `genlayer-js` directly. `scripts/create_event.mjs` is a working example: it decrypts a local keystore, builds a constitution from the contract's own live `get_registry()`/`get_config()` output, and calls `create_event` with the correct `MIN_BET + CREATE_BOND` value attached.

```bash
DATUM_KEYSTORE_PATH=/path/to/keystore.json DATUM_KEYSTORE_PASSWORD=... node scripts/create_event.mjs
```

Non-payable writes (`finalize`, `cancel_event`, `expire_event`, `lapse_appeal`, `claim`, `recover_refund`, `reclaim_bonds`) work fine through `genlayer write`.

## What has been exercised on this deployment

- Deploy, storage allocation, and method registration — confirmed via `gen_getContractSchema`.
- A live read (`get_config`).
- A live non-payable write (`expire_event` on a nonexistent id) returning the contract's own `event not found` error from a real consensus round: [`0x01809ec4ac941cb0b6feba525599153dfc0c1cc13e87cd2da295714fac31fe71`](https://explorer-studio-dev.genlayer.com/tx/0x01809ec4ac941cb0b6feba525599153dfc0c1cc13e87cd2da295714fac31fe71).

Payable methods have not yet been called against this deployment. Local test coverage for every write method, including payable ones, is documented in [testing.md](testing.md).
