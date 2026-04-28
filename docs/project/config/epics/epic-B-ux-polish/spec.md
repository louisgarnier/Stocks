# Epic B — UX Polish

**Status:** [x] Done
**Commits:** `212f1c6`, `09605e4`, `9fa1d56` (`[STORY-B-1..3]`)

## Goal

Three coordinated UX improvements: collapse 6 flat tabs into 3 with sub-tabs, add a staleness badge in the header, and replace the sync spinner with a per-step progress strip. Plus visible filter toolbars on every Transactions sub-tab.

## Stories shipped

### B-1 — Tab restructure + staleness badge + sync progress strip
- 6 flat tabs → 3 top-level: Positions / Transactions / Configuration
- Transactions has 3 sub-tabs: Original / Split-Adjusted / Corporate Actions
- Default tab = Positions
- Header shows: 🔄 Sync IBKR button → "Last sync: Xh ago" pill (color-coded green<6h, amber<24h, red>24h) → "Connecté" pill
- 4-card progress strip below header during sync (⏳ → ✅/❌ per step), auto-hide 5s after

### B-2 — Visible filter toolbar on Transactions / Original
- Always-rendered toolbar above the table (Symbol / Date from / Date to / Side: All/Buy/Sell)
- Backend `/api/transactions` accepts new params: `date_from`, `date_to`, `side`
- Replaces buried thead filter that disappeared when filter returned 0 rows

### B-3 — Visible filter toolbars on Split-Adjusted + Corporate Actions sub-tabs
- Same toolbar pattern: Symbol / Date from / Date to / CA Type
- Backend `/api/updated-transactions`: add `date_from`, `date_to`, `ca_type`; switch symbol filter to LIKE prefix
- Backend `/api/corporate-actions`: add `date_from`, `date_to` filters on `ex_date`
- "Clear filters ✕" button visible whenever any filter is active

## Outcomes

- Cleaner mental model (2 key tabs + 1 admin tab)
- Stale-data anxiety solved at a glance via the badge
- Sync feels alive instead of just spinning
- Filter "doesn't work" bug (paste returns 0 rows → input vanishes) eliminated everywhere
