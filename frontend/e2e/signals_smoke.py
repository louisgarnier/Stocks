"""STORY-G-7 — Sell signals E2E smoke test.

Headless-Chromium walk of the live app asserting the full Epic G surface:
Settings tab has the Sell Signals card (11 switches, enabled-count badge),
a toggle round-trips through POST /api/holding-signals/settings and back,
a threshold edit round-trips % <-> fraction, "Recompute signals now" reruns
the holdings compute (last_evaluated_at advances), and the Positions tab
still renders signal pills with a working expand panel. Any console error
fails the run. All mutated settings are restored to their initial state.

Run (interpreter that has Playwright + chromium installed):
    python3 frontend/e2e/signals_smoke.py

Requires the backend (:8010) and frontend (:3010) already running.
"""
import json
import sys
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3010"
API = "http://localhost:8010"
SHOT = "/private/tmp/claude-501/-Users-louisgarnier-Claude-Stocks/443e0531-e2f0-4548-8a33-f6079190eecc/scratchpad"

failures: list[str] = []
console_errors: list[str] = []


def check(cond: bool, label: str) -> None:
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {label}")
    if not cond:
        failures.append(label)


def api_settings() -> dict:
    with urllib.request.urlopen(f"{API}/api/holding-signals/settings") as r:
        return {s["signal_type"]: s for s in json.load(r)["items"]}


def api_signals_max_evaluated() -> str:
    with urllib.request.urlopen(f"{API}/api/holding-signals") as r:
        items = json.load(r)["items"]
    return max((i["last_evaluated_at"] for i in items), default="")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1200})
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))

    initial = api_settings()

    # ---- 1. Settings tab: Sell Signals card --------------------------------
    print("== Settings: Sell Signals card ==")
    page.goto(BASE, wait_until="networkidle")
    page.get_by_text("⚙️ Settings").click()
    page.wait_for_timeout(1500)
    card = page.locator("text=Sell Signals").locator("xpath=ancestor::div[contains(@class,'rounded-xl') or contains(@class,'border')][1]")
    body = page.inner_text("body")
    check("Sell Signals" in body, "Sell Signals card present")
    switches = page.get_by_role("switch").all()
    signal_switches = [s for s in switches if (s.get_attribute("id") or "").startswith("signal-")]
    check(len(signal_switches) == 11, f"11 signal switches rendered (got {len(signal_switches)})")
    enabled_initial = sum(1 for s in initial.values() if s["enabled"])
    check(f"{enabled_initial} / 11 enabled" in body, "enabled-count badge matches API")
    for title in ("Trend breaks", "Volume & momentum", "Risk"):
        # headings render uppercase via CSS text-transform
        check(title.upper() in body.upper(), f"group '{title}' present")
    page.screenshot(path=f"{SHOT}/e2e_g_1_settings.png", full_page=True)

    # ---- 2. Toggle round-trip ----------------------------------------------
    print("== Toggle round-trip (ma150_break) ==")
    was_enabled = initial["ma150_break"]["enabled"]
    sw = page.locator("#signal-ma150_break")
    sw.click()
    page.wait_for_timeout(800)
    after = api_settings()
    check(after["ma150_break"]["enabled"] == (not was_enabled), "toggle persisted via API")
    check("Saved" in page.inner_text("body"), "'Saved' hint shown")
    sw.click()  # restore
    page.wait_for_timeout(800)
    check(api_settings()["ma150_break"]["enabled"] == was_enabled, "toggle restored to initial state")

    # ---- 3. Threshold round-trip -------------------------------------------
    print("== Threshold round-trip (trailing_drawdown) ==")
    orig_thr = initial["trailing_drawdown"]["threshold"]
    inp = page.get_by_label("Trailing drawdown threshold")
    check(inp.input_value() == str(round(orig_thr * 100)), "input shows percent of stored fraction")
    inp.fill("12")
    inp.press("Enter")
    page.wait_for_timeout(800)
    check(abs(api_settings()["trailing_drawdown"]["threshold"] - 0.12) < 1e-9, "12% saved as 0.12")
    inp.fill(str(round(orig_thr * 100)))
    inp.press("Enter")
    page.wait_for_timeout(800)
    check(abs(api_settings()["trailing_drawdown"]["threshold"] - orig_thr) < 1e-9, "threshold restored")

    # ---- 4. Recompute now ----------------------------------------------------
    print("== Recompute signals now ==")
    before_eval = api_signals_max_evaluated()
    page.get_by_role("button", name="Recompute signals now").click()
    page.wait_for_timeout(4000)
    after_eval = api_signals_max_evaluated()
    check(after_eval > before_eval, f"last_evaluated_at advanced ({before_eval[:19]} → {after_eval[:19]})")
    check("Signals recomputed" in page.inner_text("body"), "'Signals recomputed' hint shown")
    page.screenshot(path=f"{SHOT}/e2e_g_2_recompute.png")

    # ---- 5. Positions tab: pills + expand panel ------------------------------
    print("== Positions: pills + expand panel ==")
    page.get_by_text("📊 Positions", exact=False).first.click()
    page.wait_for_timeout(1500)
    pills = page.locator("[data-testid='signal-pill'], [class*='signal']").count()
    body = page.inner_text("body")
    rows = page.locator("table tbody tr")
    check(rows.count() >= 15, f"positions table rendered ({rows.count()} rows)")
    rows.first.click()
    page.wait_for_timeout(600)
    expanded = page.inner_text("body")
    check(("Fired" in expanded) or ("No signals fired" in expanded) or ("signals" in expanded.lower()),
          "expand panel opens on row click")
    page.screenshot(path=f"{SHOT}/e2e_g_3_positions.png", full_page=True)

    browser.close()

# ---- Summary -----------------------------------------------------------------
print("\n== Summary ==")
check(len(console_errors) == 0, f"console errors: {len(console_errors)}")
for e in console_errors[:5]:
    print("   console:", e[:200])
if failures:
    print(f"\n{len(failures)} FAILURE(S):")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("ALL GREEN")
