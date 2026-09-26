# Deployment

## Current deployment

| | |
|---|---|
| Network | Studio Next (chain 61997) |
| Contract | `0xAafb496351df0EEa478c26d7E2f19A3B71d6cE9A` |
| Deploy tx | `0xa2fec0feab81b75789ce9ca422724c3c85433077389aed0c2552cc91fba4cce9` |
| Explorer | https://explorer-studio-dev.genlayer.com/address/0xAafb496351df0EEa478c26d7E2f19A3B71d6cE9A |
| Treasury | `0xC6E6d3b2acCaECeCeB40Ad4bD3dF123DDCB4e537` |

Machine-readable record: [`deploy/deployments.json`](../deploy/deployments.json). Its `bundleSha256` matches `sha256(artifacts/Datum.bundled.py)`.

Studio Next is a development preview and resets periodically. If the contract address stops resolving, it was reset — redeploy with the command below and update `deploy/deployments.json` and the `NEXT_PUBLIC_DATUM_CONTRACT_ADDRESS` environment variable.

This deployment supersedes `0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3`, which is now abandoned — it never held any events, and predates both the checksum-normalization fix and the steward-requested adjudication binding fix (see `docs/audit.md`).

## Deploy arguments must not be JSON-quoted

Three consecutive redeploy attempts of the fixed contract failed with `FINISHED_WITH_ERROR` (transaction `ACCEPTED`, constructor execution reverted) — even a minimal 20-line isolation contract whose entire constructor was `self.treasury = Address(treasury).as_hex` and nothing else failed identically. At the time this looked like a hosted-runtime issue: the exact same bundle and treasury argument deployed and ran correctly in a local `gltest` reproduction, and the real SDK's `Address`/`Keccak256` implementation is pure Python with no native dependencies, so a genuine local/hosted behavior split seemed implausible but unproven.

**It was never a hosted-runtime bug.** A fourth isolation contract — same plain constructor, but with an added view method that calls `Address(raw).as_hex` on an argument supplied at call time rather than at deploy time — deployed fine, and calling that view method through `genlayer call ... --args "0x..."` (the JSON-quoted form used everywhere in this project's own docs and scripts up to this point) failed with `binascii.Error: Only base64 data is allowed`. Decoding the actual calldata sent showed why: the literal double-quote characters were embedded inside the string value itself (`"0xc6e6d3b2...537"`, quotes included, 44 characters instead of 42), so `Address(...)`'s own `val.startswith('0x')` check was false — the value didn't start with `0x`, it started with `"`. Calling the same view method with the address passed **bare, with no surrounding quotes**, worked immediately and returned the correct checksummed form.

Every prior deploy attempt used the quoted form (`--args '"0xADDR"'`), which is why every one of them — regardless of fee configuration, bundle size, or how minimal the isolation contract was — failed identically inside any code path that called `Address(...)` on the constructor argument: the string it received always had two extra literal quote characters glued onto it by the CLI's own argument handling. A constructor that just does `self.treasury = treasury` (no `Address()` call) never notices, since any string is valid there — which is exactly why the *original* pre-fix deployment, which never called `Address()` on its constructor argument, always worked. The two facts only looked contradictory before this was isolated.

**Correct deploy argument syntax:** pass an address as a bare token — `--args 0xADDR`, no quotes — not `--args '"0xADDR"'`. The earlier finding that a JSON *array* form (`--args '["0xADDR"]'`) gets parsed as a single list-valued argument is still accurate and still avoided by not using brackets; quoting a single address as a JSON string turned out to introduce its own, different bug rather than being the fix it looked like at the time.

## Verifying a deployment is live

`eth_getCode` is not a valid liveness check for a GenLayer contract — it always returns `0x`, since GenLayer contracts are not EVM bytecode. Use the network's own JSON-RPC method instead:

```bash
curl -s https://studio-dev.genlayer.com/api \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"gen_getContractSchema","params":["0xAafb496351df0EEa478c26d7E2f19A3B71d6cE9A"]}'
```

A live contract returns its method schema. A nonexistent one returns JSON-RPC error `-32001`. The frontend's `probeContract()` (`frontend/src/lib/datum/network.ts`) uses this method.

A read call is a simpler check:

```bash
genlayer call 0xAafb496351df0EEa478c26d7E2f19A3B71d6cE9A get_config
```

## Deploying

```bash
python scripts/build_bundle.py
genlayer deploy --contract artifacts/Datum.bundled.py \
  --args 0xYOUR_TREASURY_ADDRESS \
  --fees '{"distribution":{"rotations":[0],"appealRounds":0,"totalMessageFees":0,"executionConsumed":0,"receiptFeeMaxGasPrice":"300000000","storageFeeMaxGasPrice":"300000000","maxPriceGenPerTimeUnit":"2","executionBudgetPerRound":"94643100000000","leaderTimeunitsAllocation":"100","validatorTimeunitsAllocation":"200"}}' \
  --fee-value 94643100002588
```

Two details matter here:

- **`--args` must be a bare token** (`0xADDR`), never wrapped in quotes (`'"0xADDR"'` embeds literal quote characters into the string) and never a JSON array (`'["0xADDR"]'` gets parsed as a single list-valued argument instead of a string). See "Deploy arguments must not be JSON-quoted" above.
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
- The checksum-normalization fix, confirmed live: `get_claimable` returns the same checksummed address whether queried with a lowercase or checksummed input.

Payable methods have not yet been called against this specific deployment (they were proven on the prior, now-abandoned address — see git history — but not yet re-run here). Local test coverage for every write method, including payable ones, is documented in [testing.md](testing.md).
