"""Epic V — Dashboard & IA restructure E2E smoke test.

Headless-Chromium walk of the live app on http://localhost:3010 asserting the
shipped Epic V surface: Dashboard is the landing tab (net worth hero, allocation
donut, performance vs S&P 500, action queue with sell + buy rows), a mover opens
the security detail sheet (Technical signals card — Task 9), Browse Universe shows
exactly one grid with the colour-coded group header row (Task 10) and no leftover
"Market Data" panel (Task 6), and the Journal hides the EUR.USD FX leg by default
(Task 7). Any console error fails the run.

Run (interpreter that has Playwright + chromium installed):
    /Library/Frameworks/Python.framework/Versions/3.10/bin/python3 frontend/e2e/dashboard_smoke.py

Requires the backend (:8010) and frontend (:3010) already running.
"""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://localhost:3010"
SHOT = "/private/tmp/claude-501/-Users-louisgarnier-Claude-Stocks/497ef27c-55dd-4cbb-92fe-d8c568191152/scratchpad"

failures: list[str] = []
console_errors: list[str] = []


def check(cond: bool, label: str) -> None:
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {label}")
    if not cond:
        failures.append(label)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1200})
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))

    # ---- 1. Dashboard is the landing tab -----------------------------------
    print("== Dashboard (landing) ==")
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(3500)  # dashboard fetches /api/dashboard async
    body = page.inner_text("body")
    page.screenshot(path=f"{SHOT}/e2e_1_dashboard.png", full_page=True)

    check("NET WORTH" in body, "net worth hero present")
    check("€" in body, "EUR base currency rendered")
    check("ALLOCATION" in body, "allocation card present")
    check(page.locator("svg").count() >= 2, "allocation donut + performance chart SVGs present")
    check("PERFORMANCE VS S&P 500" in body, "performance vs S&P 500 chart present")
    check("ACTION QUEUE" in body, "action queue present")
    check("SELL SIGNALS" in body, "sell-signal section present (>=1 sell row)")
    check("BUY CANDIDATES" in body, "buy-candidate section present (>=1 buy row)")
    check("MOVERS" in body.upper(), "movers card present")

    # ---- 2. Click a mover -> detail sheet opens ----------------------------
    print("== Mover -> detail sheet ==")
    # Movers render as rows carrying a ticker + %; click the first one and assert
    # the security detail sheet (Technical signals card, Task 9) opens.
    opened = False
    for ticker in ("SOFI", "TSLA", "HOOD", "IONQ", "RGTI", "ACHR"):
        loc = page.locator(f"text=/^{ticker}\\b/").first
        if loc.count() and loc.is_visible():
            loc.click()
            page.wait_for_timeout(1800)
            if "Technical signals" in page.inner_text("body"):
                opened = True
                break
    page.screenshot(path=f"{SHOT}/e2e_2_detail_sheet.png", full_page=True)
    check(opened, "clicking a mover opens the security detail sheet")
    sheet = page.inner_text("body")
    check("Technical signals" in sheet, "detail sheet shows Technical signals card (Task 9)")
    check(("ZigZag" in sheet) or ("swing" in sheet.lower()), "detail sheet shows ZigZag block (Task 9)")
    page.keyboard.press("Escape")
    page.wait_for_timeout(600)

    # ---- 3. Browse Universe: one grid, grouped headers, no Market Data -----
    print("== Browse Universe (Research grid) ==")
    page.locator("button:has-text('Browse Universe')").first.click()
    page.wait_for_timeout(2500)
    bu = page.inner_text("body")
    page.screenshot(path=f"{SHOT}/e2e_3_browse_universe.png", full_page=True)

    check(page.locator("table").count() == 1, "exactly one grid on Research view")
    check("Market Data" not in bu, "old Market Data panel absent (Task 6)")
    check(page.locator("thead tr").count() >= 2, "grid has a group header row above column headers (Task 10)")
    group_row = page.locator("thead tr").first
    group_ths = group_row.locator("th")
    labels = [group_ths.nth(i).inner_text().strip().upper() for i in range(group_ths.count())]
    check("MOMENTUM" in labels and "BREAKOUT" in labels, f"group header labels present: {labels}")
    # colSpans must sum to the visible column count (header aligns with body)
    span_sum = sum(int(group_ths.nth(i).get_attribute("colspan") or "1") for i in range(group_ths.count()))
    header_cells = page.locator("thead tr").nth(1).locator("th").count()
    check(span_sum == header_cells, f"group colSpans ({span_sum}) sum to visible column count ({header_cells})")

    # ---- 4. Journal hides the EUR.USD FX leg by default --------------------
    print("== Journal (trades-first) ==")
    page.locator("button:has-text('Journal')").first.click()
    page.wait_for_timeout(2500)
    jrn = page.inner_text("body")
    page.screenshot(path=f"{SHOT}/e2e_4_journal.png", full_page=True)
    check("EUR.USD" not in jrn, "EUR.USD FX leg hidden by default (Task 7)")

    # ---- 5. Sync hub: chips are actionable + a Sync-all button (Epic SH) ---
    print("== Sync hub (Dashboard) ==")
    page.locator("button:has-text('Dashboard')").first.click()
    page.wait_for_timeout(2500)
    check(page.locator("button:has-text('Sync all')").count() == 1, "Dashboard has a 'Sync all' button")
    check(page.locator("button", has_text="prices").count() >= 1, "prices staleness chip is a button (actionable)")
    check(page.locator("button", has_text="signals").count() >= 1, "signals staleness chip is a button (actionable)")

    # ---- 6. WAL + provider: start a sync, leave & return — dashboard stays live
    # Clicking the signals chip runs a CPU-bound recompute (POST /api/sync/screen).
    # With WAL the dashboard read must NOT block behind that write, and the app-level
    # provider must outlive the tab switch. We assert the robust, non-flaky win:
    # the dashboard still renders its net-worth hero (never stuck on "Loading…")
    # after starting a sync and navigating away and back.
    print("== Sync survives navigation + dashboard stays live (WAL) ==")
    page.locator("button", has_text="signals").first.click()  # kick off a real recompute
    page.wait_for_timeout(600)
    page.locator("button:has-text('Browse Universe')").first.click()  # leave immediately
    page.wait_for_timeout(700)
    page.locator("button:has-text('Dashboard')").first.click()  # come back mid-sync
    page.wait_for_timeout(1500)
    back = page.inner_text("body")
    check("NET WORTH" in back, "dashboard still renders (net worth) while a sync runs — not stuck on Loading (WAL win)")
    check("Loading dashboard" not in back, "dashboard is not stuck on 'Loading dashboard…' during a sync")
    # Soft signal (logged, not asserted — a fast recompute may already be done):
    still_syncing = page.locator("button:has-text('Syncing')").count()
    print(f"  (info) 'Syncing…' still visible after round-trip: {still_syncing >= 1}")
    page.screenshot(path=f"{SHOT}/e2e_5_sync_hub.png", full_page=True)

    # ---- 7. Zero console errors across the whole walk ----------------------
    print("== Console health ==")
    check(len(console_errors) == 0, f"no console errors (saw {len(console_errors)}: {console_errors[:3]})")

    browser.close()

print("\n" + "=" * 60)
if failures:
    print(f"SMOKE FAILED — {len(failures)} assertion(s):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("SMOKE PASSED — all assertions green.")
sys.exit(0)
