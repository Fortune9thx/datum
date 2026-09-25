# DATUM -- status

Last updated: 2026-09-25. GitHub and Vercel are both live. Studio Dev
contract deploy is blocked -- but as of 2026-09-25, this is now confirmed
to be a client-side issue specific to the `genlayer` CLI's deploy path on
this machine, not a broken network. See "Hosted deploy proof" below for
the full evidence trail.

## Deploy status

| Target | Status |
|---|---|
| GitHub push | **Live.** https://github.com/Fortune9thx/datum, public, `main`. |
| Vercel deploy | **Live.** https://datum-gamma.vercel.app, fails closed everywhere (see below). |
| Studio Dev (chain 61997) contract deploy | **Blocked, client-side, CLI-specific.** The network itself is healthy -- see below. |

No contract address exists for this project yet. `NEXT_PUBLIC_DATUM_CONTRACT_ADDRESS`
is unset in Vercel; the frontend's `probeContract()` correctly reports
`no-address` and shows nothing but zeros and an honest banner.

## Hosted deploy proof

Deployer: `bradbury-deploy` (`0xc6e6d3b2accaececeb40ad4bd3df123ddcb4e537`),
already unlocked in the `genlayer` CLI's own session on this machine --
balance 60.10303647329982136 GEN unchanged across every attempt below (all
reverts were free; no GEN was actually spent). Network: `studio-dev`,
chain 61997, confirmed via `genlayer config get`.

### 2026-09-24: initial attempts, wrongly concluded "network broken"

Three deploy attempts (a 295-byte zero-arg Hello contract, twice with
different fee configs, and the DATUM bundle once) all reverted identically
with `FeeValueMustBeNonZero`. At the time this was written up as "Studio
Dev's hosted deploy path is not currently usable" -- **that conclusion was
wrong**, corrected below.

### 2026-09-25: re-investigation, prompted by a direct steward request to check the explorer

**The network is healthy.** `curl https://explorer-studio-dev.genlayer.com/api/transactions?limit=15`
shows a steady stream of real `FINALIZED`/`ACCEPTED` transactions from
other accounts, including deploys, right up to the current time --
several with the identical `fee_value` this project's own CLI had
attempted (`100000000000010352`), successfully FINALIZED. One deploy in
particular (`0x7654c63882e5cd6264142b93aa3b2d847de431ce8f27ad47b8bf2e458868ac88`,
`FINALIZED`) used the exact same official Storage boilerplate example and
the exact same `Depends` hash this project is pinned to
(`5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng`).

**None of this project's own "reverted" transaction hashes exist on-chain
at all.** `curl https://explorer-studio-dev.genlayer.com/api/transactions/<hash>`
for every hash recorded in the 2026-09-24 attempts (and every hash from
the fresh attempts below) returns `{"detail":"Transaction not found"}`.
The `genlayer` CLI's own reported "Transaction reverted: ... EVM tx
0x..." is therefore **not describing a real, mined, reverted on-chain
transaction** -- it is a client-side failure (a local simulation or
pre-flight check inside the CLI/SDK) that happens before anything is
actually broadcast. The CLI's own error message is misleading about this.

**Re-attempted with several different configurations, all failing
identically, all client-side (no tx ever found on-chain):**

```
$ genlayer deploy --contract artifacts/Datum.bundled.py --args '["0xC6E6...4537"]' --fee-value 100000000000010352
Error: Transaction reverted: EVM tx 0x92fb53e9...bf8ce8. FeeValueMustBeNonZero(1)

$ genlayer deploy --contract artifacts/Datum.bundled.py --args '["0xC6E6...4537"]' \
    --fees '{"distribution":{"leaderTimeunitsAllocation":"100","validatorTimeunitsAllocation":"200","rotations":[0]}}' \
    --fee-value 100000000000010352
Error: Transaction reverted: EVM tx 0xce32d7ad...9e5e9c56. FeeValueMustBeNonZero(3)

$ genlayer deploy --contract artifacts/Datum.bundled.py --args '["0xC6E6...4537"]' --fee-value 500000000000000
Error: Transaction reverted: EVM tx 0x4758300f...d76fd80d4. FeeValueMustBeNonZero(1)

$ genlayer deploy --contract artifacts/smoke/Hello.py --args [] --fee-value 200000000000000
Error: Transaction reverted: EVM tx 0x88ed5648...0855a7dd6. FeeValueMustBeNonZero(1)
```

Notably, the successful on-chain deploy's actual `fee_value` was
`94643100002588` (~9.5e13 wei, ~0.0000946 GEN) -- roughly **1000x smaller**
than what this CLI's own `genlayer estimate-fees` returns
(`100000000000010352`, ~1e17 wei, ~0.1 GEN) for the same network. Explicitly
passing a `--fee-value` in that smaller order of magnitude was tried too
(see the third command above) and still failed identically -- so the bug
is not simply "the estimate is 1000x too high"; something about how this
CLI version constructs/validates the fee message allocation locally is
broken, independent of the number passed.

**Version check, to rule out a stale local CLI:** `npm view genlayer
dist-tags` shows `rc: '0.40.0-rc.3'` (published 2026-09-03) as the newest
available `genlayer` CLI release -- already installed, confirmed via
`genlayer --version`. The stable channel (`latest: '0.39.2'`) does not
know the `studio-dev` network at all (`Unknown network: studio-dev`), so
it cannot be used as a fallback for this network. **`0.40.0-rc.3` is the
only released CLI version that supports Studio Next, and it is the
version failing.** Whatever tool produced the successful transactions
above (Studio UI, a different `genlayer-js` build, or an internal script)
is evidently not hitting the same client-side bug this CLI's `deploy`
command has.

### Conclusion

**The network is not broken. This is a real, reproducible bug in the
`genlayer` CLI (v0.40.0-rc.3) deploy path on this machine** -- every
attempt fails identically regardless of contract size/content, `--args`,
or `--fee-value` magnitude, and none of them ever reach the chain at all
(confirmed via the explorer, not assumed). This supersedes the 2026-09-24
writeup's "hosted deploy path is not currently usable" conclusion, which
was reasonable given the evidence available at the time but is now known
to be too broad.

**Never claim "contracts may only be 300 bytes"** -- that was never what
either failure was. The GenVM size ceiling remains ~52,224 bytes, and
DATUM's bundle (40,784 bytes) is well inside it, independently confirmed
by `genvm-lint lint` and the bundler's own size check below.

### What to try next (not yet attempted this session)

1. **Studio UI** (https://studio-dev.genlayer.com) -- browser + wallet
   deploy, not exercised in this non-interactive session. Given the CLI's
   failure is now confirmed client-side and CLI-specific, the UI (a
   different client) may well work where the CLI does not.
2. **Raw `genlayer-js` SDK script**, bypassing the CLI's `deploy` command
   entirely (the pattern `scripts/deploy.mjs` already uses, matching
   `precedence-settler`'s proven-working approach on this same network) --
   worth trying with a real keystore password, since the CLI wrapper
   itself, not the underlying SDK/network, is the suspect.
3. If either works, please file the CLI bug upstream
   (`genlayerlabs/genlayer` or wherever `npm genlayer` is tracked) with
   the repro above -- a deploy that never reaches the chain but reports a
   misleading "Transaction reverted" is a real, currently-unfixed bug
   independent of this project.

## Local toolchain: what actually happened (real captured output)

This machine has a long-documented, cross-project history of
`genvm-lint`'s runtime-dependent commands and `gltest`'s direct-mode
deploy failing with `name 'gl' is not defined`, assumed to be a
persistent local gap. **On this project, that assumption turned out to
