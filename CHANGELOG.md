# Changelog

All notable changes to this project are documented in this file.

## [1.0.0] - 2026-09-24 - Initial build

- `contracts/datum_lib.py` -- pure-Python core logic (constitution
  validation, publisher registry, unit conversion, volatile-key stripping,
  aggregation/equivalence acceptance, economics, pagination). 55 passing
  plain-pytest unit tests.
- `contracts/Datum.py` -- full GenLayer Intelligent Contract API
  (`create_event`, `accept_event`, `adjudicate`, `finalize`, `appeal`,
  `re_adjudicate`, `lapse_appeal`, `cancel_event`, `expire_event`,
  `claim`, `recover_refund`, `reclaim_bonds`, plus 9 views).
- `scripts/build_bundle.py` -- single-file bundler producing
  `artifacts/Datum.bundled.py` (40190 bytes, under the 52224-byte Studio
  ceiling).
- `frontend/` -- minimal fail-closed Next.js shell (`/`, `/board`,
  `/e/:id`) with a typed SDK locked to Studio Dev (chain 61997).
- `docs/` -- architecture, self-audit, steward notes, and an honest
  toolchain-status writeup with real captured error output.
- No deploy, no GitHub push, no Vercel deploy performed in this build
  session (by design -- see docs/STATUS.md).
