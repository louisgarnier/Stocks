# Epic A — Sync Pipeline Restructure

**Status:** [x] Done
**Commits:** `c6386de..3d8b6a8` (`[SYNC-1..14]`)

## Goal

Replace the monolithic `/api/transactions/flex-import` route with a decoupled 4-step pipeline at `/api/sync/*` plus an orchestrator. Drop the reconciliation feature (positions and transactions both come from the same Flex Query response, so they're inherently consistent).

## Stories shipped

| ID | Description |
|---|---|
| **A-1** | Shared test fixtures (`temp_db`, minimal Flex XML) |
| **A-2** | Drop reconciliation: simplify `/api/positions`, drop frontend recon UI |
| **A-3** | Drop `positions_calculated` table + recalc script + duplicate empty DB |
| **A-4** | Add `fetch_flex_response()` helper with env-var fallback for query IDs |
| **A-5..8** | All four `/api/sync/*` step endpoints + `/api/sync/full` orchestrator |
| **A-9** | Wire frontend Sync IBKR header button to `/api/sync/full` |
| **A-10** | Delete deprecated `/api/transactions/flex-import` route |
| **A-11** | End-to-end smoke test against real IBKR |
| **A-12** | Restore `import_logs` writes from new sync pipeline |
| **A-13** | Tag DB timestamps with local timezone offset (positions) |
| **A-14** | Tag `import_logs.import_date` with local timezone offset |

## Outcomes

- 4-step pipeline: positions → transactions → corporate-actions → splits
- Steps 1+2 share a single Flex pull in the orchestrator
- Failures stop the chain at the failing step; earlier successful steps remain committed
- 9 backend integration tests
- Frontend Sync IBKR button calls `/api/sync/full` and renders per-step ✅/❌ pills

## Reference

Plan that drove this work (kept for archive): inspectable via `git log --grep '\[SYNC-' --reverse`.
