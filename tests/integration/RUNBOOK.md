# Integration test runbook (manual, documented -- not automated)

Live integration tests against a real Studio Dev deployment cannot be run
in this session (no deploy was attempted, and the local `gltest`/
`genvm-lint` runtime toolchain is blocked -- see `docs/STATUS.md`). This
runbook documents the manual steps a future steward should run once a
contract is actually deployed, rather than silently skipping integration
coverage.

## Prerequisites

- A DATUM contract deployed on Studio Dev (chain 61997) -- see
  `docs/STATUS.md` section (c) for the deploy commands.
- Two funded Studio Dev accounts (creator + acceptor).
- `frontend/.env` pointed at the deployed contract address.

## Manual test plan

1. **Create + accept happy path.** From account A, call `create_event`
   with a `STATION_PRECIP` constitution, `side="YES"`, a valid stake.
   Confirm `get_constitution` returns a stable 64-character hex hash.
   From account B, call `accept_event` with `side="NO"` and a matching
   stake. Confirm `get_event` reports `state == "ACTIVE"`.

2. **Adjudicate after window close.** Wait until chain time passes the
   locked window end. Call `adjudicate` from either account with
   `ADJUDICATE_BOND` attached. Confirm the returned verdict is one of
   `YES`/`NO`/`INCONCLUSIVE` and that `get_record` reflects it.

3. **Finalize after appeal window.** Wait past the event's
   `appeal_window`. Call `finalize`. Confirm `get_event` reports
   `state == "FINALIZED"` and that `get_claimable` for the winning
   address reflects a nonzero payout.

4. **Claim.** From the winning address, call `claim`. Confirm the
   on-chain GEN balance increases by the expected amount (pot minus fee)
   and that `get_claimable` afterward returns `0`.

5. **Appeal path.** Repeat steps 1-2 with a second event. Before the
   appeal window elapses, call `appeal` from either bonded party with a
   valid `APPEAL_BOND`. Confirm `get_event` reports `state == "APPEALED"`.
   Call `re_adjudicate`. Confirm the event returns to `VERDICT_PENDING`
   (or is re-finalized on the next `finalize` call).

6. **Lapse appeal.** Repeat the appeal step, then wait past
   `LAPSE_APPEAL_STALL` without calling `re_adjudicate`. Call
   `lapse_appeal` from any address. Confirm the prior verdict is
   restored and the appellant's bond is not returned (forfeit to
   treasury).

7. **Expire unaccepted.** Create an event and let its window start with
   no acceptor. Call `expire_event`. Confirm the creator's stake is
   refunded via `get_claimable` but the `CREATE_BOND` is not (check
   `treasury_balance` growth via `get_config`/a dedicated future view).

8. **Recover refund.** Create + accept an event, then let it sit past
   `RECOVER_REFUND_AFTER` (7 days) without adjudication. Call
   `recover_refund` from any address. Confirm both stakes are refunded
   with zero fee.

Record the actual observed transaction hashes and outcomes in this file
(or a dated copy of it) once run -- do not silently mark this runbook as
"passed" without real transaction evidence.
