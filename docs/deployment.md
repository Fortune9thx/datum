# Deployment

## Current deployment

| | |
|---|---|
| Network | Studio Next (chain 61997) |
| Contract | `0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3` |
| Deploy tx | `0x84b5319b1ca744c47a0c3c36894e69cf3466c0cc3c876f4fcecf8315c440ae03` |
| Explorer | https://explorer-studio-dev.genlayer.com/address/0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3 |
| Treasury | `0xC6E6d3b2acCaECeCeB40Ad4bD3dF123DDCB4e537` |

Machine-readable record: [`deploy/deployments.json`](../deploy/deployments.json). Its `bundleSha256` must match `sha256(artifacts/Datum.bundled.py)`.

Studio Next is a development preview and resets periodically. If the contract address stops resolving, it was reset — redeploy with the command below and update `deploy/deployments.json` and the `NEXT_PUBLIC_DATUM_CONTRACT_ADDRESS` environment variable.

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
