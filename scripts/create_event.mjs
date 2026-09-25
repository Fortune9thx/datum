// DATUM create_event -- Studio Next (chain 61997) only.
//
// The `genlayer` CLI's `write` command cannot attach GEN to a payable
// call (its WriteAction hardcodes value: 0n), so payable methods must go
// through genlayer-js directly, as this script does.
//
// The constitution below uses a QUAKES event (the shortest MIN_WINDOW
// and MIN_LEAD of the four classes), the two publishers the registry
// allows for that class, a real bounding box, and MIN_BET + CREATE_BOND
// attached exactly as create_event requires. See docs/deployment.md.
//
// Usage:
//   DATUM_KEYSTORE_PATH=... DATUM_KEYSTORE_PASSWORD=... node scripts/create_event.mjs
import fs from "node:fs";
import { ethers } from "ethers";
import { createClient, createAccount } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";

const KEYSTORE_PATH = process.env.DATUM_KEYSTORE_PATH;
const KEYSTORE_PASSWORD = process.env.DATUM_KEYSTORE_PASSWORD;
const CONTRACT_ADDRESS = "0x3eb7D9044665De3FC78d12bBC8E78d9352EAAdC3";

if (!KEYSTORE_PATH || !KEYSTORE_PASSWORD) {
  console.error("Set DATUM_KEYSTORE_PATH and DATUM_KEYSTORE_PASSWORD");
  process.exit(1);
}

const keystoreJson = fs.readFileSync(KEYSTORE_PATH, "utf-8");
const wallet = await ethers.Wallet.fromEncryptedJson(keystoreJson, KEYSTORE_PASSWORD);
const privateKey = wallet.privateKey;

if (!/^0x[0-9a-fA-F]{64}$/.test(privateKey)) {
  console.error("Decrypted key has unexpected length/format, aborting.");
  process.exit(1);
}

const account = createAccount(privateKey);
if (account.address.toLowerCase() !== wallet.address.toLowerCase()) {
  console.error("Derived address mismatch, aborting.");
  process.exit(1);
}
console.log("Sender address:", account.address);

const client = createClient({ chain: studioDevnet, account });

const balance = await client.getBalance({ address: account.address });
console.log("Balance (wei):", balance.toString());

// VALUE_SCALE = 100 (see contracts/datum_lib.py). 1.00 Mw threshold.
const NOW = Math.floor(Date.now() / 1000);
const MIN_LEAD_QUAKES = 30 * 60; // 1800s
const MIN_WINDOW_QUAKES = 60 * 60; // 3600s
const start = NOW + MIN_LEAD_QUAKES + 120;
const end = start + MIN_WINDOW_QUAKES;

const constitution = {
  class: "QUAKES",
  bbox: [-122.6, 37.2, -121.7, 38.0], // Northern California, real coords
  metric: "mw_max",
  threshold: 100, // 1.00 Mw scaled by VALUE_SCALE=100
  cmp: "gte",
  window: [start, end],
  publishers: ["USGS_QUAKE", "EMSC"],
  product_status_policy: "FINAL_ONLY",
};
console.log("Constitution:", JSON.stringify(constitution));

const MIN_BET = 10n ** 16n; // 0.01 GEN
const CREATE_BOND = 5n * 10n ** 16n; // 0.05 GEN, must match datum_lib.CREATE_BOND
const attachedValue = MIN_BET + CREATE_BOND;

const fees = await client.estimateTransactionFeesForWrite({
  address: CONTRACT_ADDRESS,
  functionName: "create_event",
  args: [JSON.stringify(constitution), "YES", MIN_BET.toString()],
  value: attachedValue,
});
console.log("Estimated fees:", { feeValue: fees.feeValue?.toString(), distribution: fees.distribution });

const txHash = await client.writeContract({
  address: CONTRACT_ADDRESS,
  functionName: "create_event",
  args: [JSON.stringify(constitution), "YES", MIN_BET.toString()],
  value: attachedValue,
  fees,
});
console.log("create_event tx hash:", txHash);

const receipt = await client.waitForTransactionReceipt({
  hash: txHash,
  waitUntil: "decided",
  retries: 60,
  interval: 5000,
});
console.log("Status:", receipt.statusName);
console.log("Execution result:", receipt.txExecutionResultName);
console.log("Full receipt:", JSON.stringify(receipt, (_k, v) => (typeof v === "bigint" ? v.toString() : v), 2));

if (receipt.txExecutionResultName === "FINISHED_WITH_RETURN") {
  const eventId = receipt.txDataDecoded?.returnValue ?? null;
  console.log("Event id:", eventId);

  const eventJson = await client.readContract({
    address: CONTRACT_ADDRESS,
    functionName: "get_event",
    args: [eventId],
  });
  console.log("get_event(id) from chain:", eventJson);

  fs.writeFileSync(
    "scripts/create_event_result.json",
    JSON.stringify(
      {
        contractAddress: CONTRACT_ADDRESS,
        createEventTxHash: txHash,
        eventId,
        statusName: receipt.statusName,
        txExecutionResultName: receipt.txExecutionResultName,
        creatorAddress: account.address,
        constitution,
        attachedValueWei: attachedValue.toString(),
        eventOnChain: JSON.parse(String(eventJson)),
        createdAt: new Date().toISOString(),
      },
      null,
      2
    )
  );
  console.log("Wrote scripts/create_event_result.json");
} else {
  console.error("create_event did not finish with a return value -- see Execution result above.");
  process.exit(1);
}
