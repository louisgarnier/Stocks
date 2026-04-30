"""Regression test for the SYNC-13 timezone bug in incremental CA fetch.

`set_ca_status` writes tz-aware ISO timestamps (datetime.now().astimezone()).
The incremental fetcher used to compare those against a tz-naive
`datetime.now()`, raising "can't subtract offset-naive and offset-aware
datetimes" and breaking the corporate_actions step in /api/sync/full.
"""
import sqlite3

import pandas as pd

from backend.utils.ca_status import set_ca_status


def test_incremental_fetch_handles_tz_aware_status(temp_db, monkeypatch):
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO transactions (transaction_id, symbol, trade_date, "
        "quantity, currency) VALUES ('T1', 'NVDA', '2024-01-01', 10, 'USD')"
    )
    conn.commit()
    conn.close()

    set_ca_status(["NVDA"], "green")

    import backend.scripts.fetch_corporate_actions as fca
    monkeypatch.setattr(fca, "DB_PATH", temp_db)
    monkeypatch.setattr(
        fca,
        "fetch_all_corporate_actions",
        lambda securities: pd.DataFrame(
            columns=["sec_id", "ca_type", "ex_date", "amount", "notes"]
        ),
    )

    result = fca.fetch_and_import_corporate_actions(incremental=True)
    assert result is not None
    assert "errors" in result
