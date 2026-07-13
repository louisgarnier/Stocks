from datetime import datetime, date, timezone

from backend.api.utils.trading_days import (
    last_completed_trading_day, close_of, freshness_level,
)


def _utc(y, m, d, h=12, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


# --- last_completed_trading_day -----------------------------------------
# 2026-07-13 is a Monday; 2026-07-10 the preceding Friday.

def test_monday_before_close_returns_friday():
    assert last_completed_trading_day(_utc(2026, 7, 13, 12)) == date(2026, 7, 10)

def test_monday_after_close_returns_monday():
    assert last_completed_trading_day(_utc(2026, 7, 13, 22, 30)) == date(2026, 7, 13)

def test_saturday_returns_friday():
    assert last_completed_trading_day(_utc(2026, 7, 11, 9)) == date(2026, 7, 10)

def test_sunday_returns_friday():
    assert last_completed_trading_day(_utc(2026, 7, 12, 23)) == date(2026, 7, 10)

def test_midweek_after_close_returns_same_day():
    # Wednesday 2026-07-08 at 23:00 UTC
    assert last_completed_trading_day(_utc(2026, 7, 8, 23)) == date(2026, 7, 8)

def test_midweek_before_close_returns_previous_day():
    assert last_completed_trading_day(_utc(2026, 7, 8, 9)) == date(2026, 7, 7)


# --- close_of -------------------------------------------------------------

def test_close_of_is_22_utc():
    c = close_of(date(2026, 7, 10))
    assert c == datetime(2026, 7, 10, 22, 0, tzinfo=timezone.utc)


# --- freshness_level: prices/signals (trading-day aware) -------------------
NOW_MONDAY = _utc(2026, 7, 13, 12, 50)          # lctd = Fri 07-10

def test_prices_fresh_when_bar_is_lctd_and_checked_after_close():
    # Checked Monday morning, well after Friday 22:00 UTC close.
    assert freshness_level("prices", "2026-07-10",
                           "2026-07-13T11:12:37+02:00", NOW_MONDAY) == "fresh"

def test_prices_stale_when_bar_missing_for_lctd():
    assert freshness_level("prices", "2026-07-09",
                           "2026-07-13T11:12:37+02:00", NOW_MONDAY) == "stale"

def test_prices_stale_when_not_checked_since_close():
    # Bar is Friday's but last sync ran Friday 12:00 UTC (before Friday close).
    assert freshness_level("prices", "2026-07-10",
                           "2026-07-10T12:00:00+00:00", NOW_MONDAY) == "stale"

def test_prices_unknown_without_data():
    assert freshness_level("prices", None, None, NOW_MONDAY) == "unknown"

def test_prices_stale_when_never_checked():
    assert freshness_level("prices", "2026-07-10", None, NOW_MONDAY) == "stale"


# --- freshness_level: fundamentals (7-day window) ---------------------------

def test_fundamentals_fresh_within_7_days():
    assert freshness_level("fundamentals", "2026-07-08T09:00:00+00:00",
                           None, NOW_MONDAY) == "fresh"

def test_fundamentals_stale_after_7_days():
    assert freshness_level("fundamentals", "2026-07-01T09:00:00+00:00",
                           None, NOW_MONDAY) == "stale"


# --- freshness_level: ibkr (checked since lctd close) ------------------------

def test_ibkr_fresh_when_synced_after_friday_close():
    assert freshness_level("ibkr", "2026-07-11T09:12:00+02:00",
                           "2026-07-11T09:12:00+02:00", NOW_MONDAY) == "fresh"

def test_ibkr_stale_when_synced_before_friday_close():
    assert freshness_level("ibkr", "2026-07-10T08:00:00+02:00",
                           "2026-07-10T08:00:00+02:00", NOW_MONDAY) == "stale"
