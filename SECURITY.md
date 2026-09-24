# Security

DATUM is a hackathon-stage GenLayer Intelligent Contract deployed only on
Studio Dev (chain id 61997), a devnet whose state may reset at any time.
Do not send real value to any DATUM contract address, and do not treat any
address, balance, or event id on Studio Dev as durable.

## Reporting a vulnerability

Open an issue in this repository (or, once published, use the repository's
private security advisory feature) describing the issue. Please avoid
publicly disclosing a fund-affecting bug before the maintainer has had a
chance to respond.

## Scope notes

- No admin seize function exists anywhere in `contracts/Datum.py`.
- The only method that moves GEN out of the contract is `claim()`, and it
  only ever pays `gl.message.sender_address`'s own credited balance --
  never an address supplied as an argument.
- The model's proposed verdict/code is never trusted directly; see
  `contracts/datum_lib.py`'s `evaluate_envelope()` and
  `docs/architecture.md` for the independent re-derivation this contract
  performs before any pool moves.
- Publisher hosts are a hardcoded per-class allowlist
  (`PUBLISHER_REGISTRY`); no user-supplied source URL is ever fetched.
- No private key, keystore, mnemonic, or `.env` file is committed to this
  repository -- verify with `git status` / `git log --all --full-history`
  before any push if you are unsure.
