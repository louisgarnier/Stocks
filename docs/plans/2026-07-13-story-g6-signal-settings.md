# G-6 Signal Settings + G-7 E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Settings tab gets a "Sell Signals" card (approved mockup): 11 signal toggles in 3 groups, editable %-thresholds for trailing_drawdown/stop_loss, immediate save, "Recompute signals now" button. Then the G-7 end-to-end smoke.

**Architecture:** Backend is complete (`GET/POST /api/holding-signals/settings`, `POST /api/sync/holding-signals`). Everything is frontend: extend `lib/holding-signals.ts` with settings API + group metadata, new `SignalSettingsCard` component wired into page.tsx's configuration tab, jest tests, then a Playwright E2E smoke.

**Tech Stack:** Next.js + shadcn (Card/Switch/Input/Badge), Jest/RTL, Playwright (e2e/).

## Global Constraints

- Approved mockup: 3 groups (Trend breaks / Volume & momentum / Risk), Switch per signal, threshold inputs show **percent** (DB stores fractions: 0.10 ↔ "10"), validation 1–95 %, immediate PUT per change + "✓ Saved" hint, note "takes effect on next signals sync".
- "Recompute signals now" calls `POST /api/proxy/api/sync/holding-signals` directly (holdings-only compute, NOT the screen/research sync) with a local loading state.
- All fetches go through `/api/proxy/api/...` like the rest of the app.
- Commit format: `[STORY-G-6] type: ...` / `[STORY-G-7] type: ...` + Claude co-author line.

---

### Task 1: Settings API + metadata in `lib/holding-signals.ts`

**Files:**
- Modify: `frontend/lib/holding-signals.ts`
- Test: `frontend/__tests__/signal-settings-lib.test.ts`

**Interfaces (produced):**
```ts
export interface SignalSetting { signal_type: string; enabled: boolean; threshold: number | null }
export interface SignalGroupDef { title: string; signals: { type: string; trigger: string; thresholdUnit?: string }[] }
export const SIGNAL_GROUPS: SignalGroupDef[]   // 3 groups, 11 signals, mockup trigger texts
export async function fetchSignalSettings(): Promise<SignalSetting[]>
export async function updateSignalSetting(s: SignalSetting): Promise<void>  // POST, throws on !ok
```
`SIGNAL_GROUPS`: Trend breaks = ma50_break/ma100_break/ma150_break/ma200_break/death_cross; Volume & momentum = volume_dryup/distribution_day/rsi_weakness/mrsi_flip; Risk = trailing_drawdown (`thresholdUnit: '% from 30-day high'`), stop_loss (`thresholdUnit: '% below cost basis'`).

Steps: failing test (fetch mock: GET returns items, POST called with JSON body; SIGNAL_GROUPS covers exactly the 11 types) → implement → test green → commit `[STORY-G-6] feat: signal-settings client API + group metadata`.

### Task 2: `SignalSettingsCard` + wire into Settings tab

**Files:**
- Create: `frontend/components/settings/SignalSettingsCard.tsx`
- Modify: `frontend/app/page.tsx` (configuration tab, after the Tracked Universe card's closing `</Card>`)
- Test: `frontend/__tests__/signal-settings-card.test.tsx`

**Behavior:**
- Loads settings on mount; header badge "N / 11 enabled"; rows per SIGNAL_GROUPS (Switch + label via `signalLabel()` + trigger text; disabled rows at 55 % opacity).
- Threshold Input only where `thresholdUnit` (value = `Math.round(threshold*100)`); onBlur/Enter → clamp 1–95, PUT `threshold/100`.
- Any successful PUT → "✓ Saved · takes effect on next signals sync" hint (fades state, no timer needed for v1); failed PUT → revert optimistic state + inline error text.
- "↻ Recompute signals now" → `POST /api/proxy/api/sync/holding-signals`, local spinner, then re-fetch settings-independent (no-op) — just show "✓ Signals recomputed".

Jest: renders 11 switches from mocked GET; toggling one POSTs `{signal_type, enabled:false, threshold}`; threshold input converts % ↔ fraction; recompute button POSTs the sync endpoint.

Steps: failing tests → component → wire into page.tsx → `npx jest` all green + `tsc --noEmit` → commit `[STORY-G-6] feat: Sell Signals settings card in Settings tab`.

### Task 3 (G-7): E2E smoke

**Files:**
- Create: `frontend/e2e/signals_smoke.py` (pattern: `frontend/e2e/dashboard_smoke.py`, live :3010/:8010)

Assertions:
1. Settings tab shows "Sell Signals" card with 11 switches, badge count matches enabled count from API.
2. Toggle ma150_break off → API GET reflects enabled=false → toggle back on (leave state as found).
3. Set trailing_drawdown to 12 → API shows 0.12 → restore 10 → API shows 0.10.
4. "Recompute signals now" → button disables then re-enables; `/api/holding-signals` last_evaluated_at advances.
5. Positions tab: signal pills render (green/yellow/red), expanding a row shows fired signals. 0 console errors.

Steps: write script → run vs live app → paste output → commit `[STORY-G-7] test: signals E2E smoke`. Close ritual: build-log + codebase.md + ACTIVE.md (G complete), ROADMAP → G shipped.
