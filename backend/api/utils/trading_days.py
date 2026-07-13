"""Trading-day-aware freshness for the dashboard staleness chips.

A daily bar for day D only exists once all covered markets have closed.
We use a single global cutoff of 22:00 UTC (US close is 20:00/21:00 UTC
depending on DST; Paris closes earlier), so:
  - before 22:00 UTC on a weekday, the last COMPLETED trading day is the
    previous weekday;
  - weekends roll back to Friday.
Market holidays are not modeled (YAGNI): on a holiday the chip shows
amber for one day, which is honest-but-conservative rather than wrong.
"""
from datetime import date, datetime, time, timedelta, timezone

MARKET_CLOSE_UTC = time(22, 0)
FUNDAMENTALS_FRESH_DAYS = 7


def close_of(day: date) -> datetime:
    """Timezone-aware UTC datetime when day's daily bars are complete."""
    return datetime.combine(day, MARKET_CLOSE_UTC, tzinfo=timezone.utc)


def last_completed_trading_day(now: datetime) -> date:
    """Most recent weekday whose 22:00 UTC close is in the past."""
    d = now.astimezone(timezone.utc).date()
    while d.weekday() >= 5 or now < close_of(d):
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
    return d


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(ts)
    except ValueError:
        return None
    if parsed.tzinfo is None:  # bare dates ("2026-07-10") → treat as UTC
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def freshness_level(kind: str, data_date: str | None,
                    checked_at: str | None, now: datetime) -> str:
    """'fresh' | 'stale' | 'unknown' for one staleness chip.

    prices/signals: fresh iff the newest bar is the last completed trading
    day AND a sync verified it after that day's close.
    fundamentals:   fresh iff fetched within FUNDAMENTALS_FRESH_DAYS.
    ibkr:           fresh iff the last sync finished after the last
                    completed trading day's close.
    """
    if data_date is None:
        return "unknown"
    lctd = last_completed_trading_day(now)
    checked = _parse(checked_at)

    if kind == "fundamentals":
        fetched = _parse(data_date)
        if fetched is None:
            return "unknown"
        age_days = (now - fetched).total_seconds() / 86400
        return "fresh" if age_days <= FUNDAMENTALS_FRESH_DAYS else "stale"

    if kind == "ibkr":
        return "fresh" if checked and checked >= close_of(lctd) else "stale"

    # prices / signals
    bar = _parse(data_date)
    if bar is None:
        return "unknown"
    bar_ok = bar.date() >= lctd
    checked_ok = checked is not None and checked >= close_of(lctd)
    return "fresh" if bar_ok and checked_ok else "stale"
