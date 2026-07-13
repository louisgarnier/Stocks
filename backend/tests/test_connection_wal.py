"""WAL + busy-timeout: a read must not block behind a concurrent write."""
import sqlite3
import threading
import time

from backend.database import connection as conn_mod


def _point_db_at(tmp_path, monkeypatch):
    db_dir = tmp_path / "database"
    db_dir.mkdir()
    monkeypatch.setattr(conn_mod, "DB_DIR", db_dir)
    monkeypatch.setattr(conn_mod, "DB_FILE", db_dir / "finance.db")


def test_connection_is_wal_with_busy_timeout(tmp_path, monkeypatch):
    _point_db_at(tmp_path, monkeypatch)
    conn = conn_mod.get_db_connection()
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1  # preserved
    finally:
        conn.close()


def test_read_succeeds_during_open_write_transaction(tmp_path, monkeypatch):
    """With WAL, a reader sees the last committed snapshot while a writer holds
    an open transaction — it must NOT raise 'database is locked'."""
    _point_db_at(tmp_path, monkeypatch)
    setup = conn_mod.get_db_connection()
    setup.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    setup.execute("INSERT INTO t (id, v) VALUES (1, 'committed')")
    setup.commit()
    setup.close()

    writer = conn_mod.get_db_connection()
    writer.execute("BEGIN IMMEDIATE")
    writer.execute("INSERT INTO t (id, v) VALUES (2, 'uncommitted')")  # holds write lock

    reader = conn_mod.get_db_connection()
    try:
        rows = reader.execute("SELECT v FROM t ORDER BY id").fetchall()
        # Reader sees only the committed row, and crucially does not raise.
        assert [r[0] for r in rows] == ["committed"]
    finally:
        reader.close()
        writer.rollback()
        writer.close()
