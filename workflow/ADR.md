# ADR.md — architectural decision records

## 2026-07-10 — ADR-1: Pipeline freshness contract (indicators → screen signals)

**Context:** market_data, indicators, and screen_signals are synced by independent endpoints/buttons. Signals computed on 2026-07-01 joined fresh prices with ~7-week-stale MAs and were never invalidated, poisoning research_overview (see ERRORS.md stale-join entry).

**Decision:**
1. **Read-time guard** — `screen_signals_compute` only accepts an indicators row dated within 7 calendar days at-or-before the last market_data bar (`INDICATOR_FRESHNESS_DAYS`). Stale ⇒ MA-derived fields are NULL, never silently wrong.
2. **Write-time chaining** — every endpoint that recomputes indicators (`/api/sync/analytics`, `/api/sync/full`) chains `_step_screen()` (signals → consolidation → breakout → scoring → prune) afterwards. `/api/sync/screen` remains standalone for post-tuning recompute.
3. Long-running sync endpoints are plain `def` (FastAPI threadpool), never `async def`, so the event loop stays responsive (`/analytics`, `/full`, `/screen`, `/fundamentals`).

**Consequence:** `signal_date` can no longer drift from `indicator_date` through normal UI use; a stale join degrades to honest NULLs instead of wrong verdicts.

## 2026-07-10 — ADR-2: Two consolidation detectors coexist, columns labeled by source

**Context:** `breakout_compute.py` embeds its own strict 40-day consolidation detection (verbatim port of `d_breakout_detector_3.py` — contractually not to be refactored), independent of `consolidation_compute.py` (ZigZag quality scoring → `consolidation_patterns`, port of `g_consolidation.py`). research_overview mixed columns from both, so `breakout_detected` rows showed empty consolidation columns — read as data corruption.

**Decision:** keep both detectors (they answer different questions: tradeable-breakout setup vs. consolidation quality screening), but every breakout row now exposes the bounds of the consolidation that produced it as distinct view columns: `breakout_support`, `breakout_resistance`, `breakout_range_pct`, `breakout_duration_days`. The ZigZag detector keeps `consolidation_quality` / `support_level` / `resistance_level`. No algorithm changes.

**Rejected alternative:** making breakout read `consolidation_patterns` — would alter the verbatim-ported detection semantics and couple two deliberately separate signals.

**Follow-up (Phase B wireframe audit):** decide how the UI presents the two sources so they aren't mistaken for one detector.
