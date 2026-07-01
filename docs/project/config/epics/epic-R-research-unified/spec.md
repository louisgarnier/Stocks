# Epic R — Research Unified View

> **Type:** Correction / consolidation (do now, before resuming G → E → F).
> **Status:** [→] In Progress
> **Full design spec:** [`docs/superpowers/specs/2026-07-01-research-unified-view-design.md`](../../../../superpowers/specs/2026-07-01-research-unified-view-design.md)
> **Depends on:** Epic S (Screener, Phase 1 built), Epic D (Indicators), Epic H (Security Detail Sheet).

## Why now (the correction)

The Screener (Epic S) and Browse Universe (Epic H surface) grew into **two divergent per-stock pipelines**: indicators (Epic D) live in one, screener signals + fundamentals in the other. Neither shows the whole picture, the detail popup has no fundamentals, and the consolidation compute silently under-produces (`consolidation_patterns` = 1 row / 561). This must be corrected before layering more features on top of a split, unreliable data model.

This epic **merges** the two into one clean, reliable, configurable Research view backed by a single per-symbol dataset. It does **not** drop later work — G (sell-signals frontend), E-remaining (drill-down chart), F (options S/R), Screener Phase-2 calibration, and all parked items stay queued.

## Stories

| ID | Story | AC (summary) |
|---|---|---|
| **R-1** | Unified data view + CSV | `research_overview` view = universe ⨝ **latest indicators** ⨝ signals ⨝ consolidation ⨝ breakout ⨝ fundamentals ⨝ latest score. `GET /api/research/overview?format=json\|csv`; `/api/screener/overview` kept as alias. Unit tests for indicator join + json/csv parity. |
| **R-2** | Consolidation reliability fix | Debugging spike (systematic-debugging): why `consolidation_patterns` writes 1/561. Test hypotheses: seed-drift params, ZigZag port I/O bug, retention prune. DoD: patterns + S/R populate for a meaningful fraction; regression test asserts >1 symbol. |
| **R-3** | Merged Research UI | Move Screener grid into Browse Universe window; retire standalone `screener` tab. Top toolbar = **3 sync buttons (Fundamentals w/ auto-rescore · Technical · Compute) + Run all** (chains Technical → Fundamentals → Compute), each with last-run/stale badge. Column show/hide menu; default = union of current Screener + Browse Universe columns; persisted to localStorage. Preserve sort/filter/CSV. |
| **R-4** | Detail popup — Fundamentals card | Extend `GET /api/security/{sym}/detail` with a `fundamentals` block; `SecurityDetailSheet` renders a Fundamentals card (margins, ROE, ROIC, FCF margin, interest cover, EPS 5y growth, gates x/7, market cap, P/E) alongside existing cards. |

## Build order

R-1 → R-2 → R-3 → R-4 (each shippable). R-2 can run in parallel with R-1 if needed (independent code paths).

## Out of scope (stays in later epics / parked)

- Score-weight calibration → **Epic S Phase 2**.
- Per-symbol drill-down chart `/tech-analysis/{symbol}` (lightweight-charts) → **Epic E remaining**.
- Sell-signals column/settings frontend → **Epic G**.
- Options max-pain / walls → **Epic F**.
- FIFO, Watchlist, Auto-scheduling, historical snapshots → parked (unchanged).

## Commit prefix

`[STORY-R-<N>]`.
