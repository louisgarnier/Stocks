"""
Database connection and initialization - IBKR Portfolio Tracker

⚠️ Before making changes, read: ../../docs/workflow/BEST_PRACTICES.md
Always check with the user before modifying this file.
"""

import sqlite3
from pathlib import Path
from typing import Optional

# Database path - use output/database/ directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_DIR = PROJECT_ROOT / "output" / "database"
DB_FILE = DB_DIR / "finance.db"
SCHEMA_FILE = Path(__file__).parent / "schema.sql"


def get_db_connection():
    """
    Get a database connection.

    WAL mode lets readers see the last committed snapshot while a writer holds
    an open transaction (a long analytics sync no longer blocks the dashboard
    read); the busy-timeout waits on brief lock contention instead of raising
    'database is locked'.

    Returns:
        sqlite3.Connection: Database connection
    """
    # Ensure database directory exists
    DB_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    conn.execute("PRAGMA journal_mode=WAL")  # concurrent read-during-write
    conn.execute("PRAGMA busy_timeout=30000")  # wait up to 30s, don't error
    conn.execute("PRAGMA foreign_keys = ON")  # Enable CASCADE delete
    return conn


def init_database():
    """
    Initialize the database.
    Creates the database file and tables if they don't exist.
    """
    # Ensure database directory exists
    DB_DIR.mkdir(parents=True, exist_ok=True)
    
    # Read and execute schema
    if SCHEMA_FILE.exists():
        conn = get_db_connection()
        cursor = conn.cursor()
        
        with open(SCHEMA_FILE, 'r') as f:
            schema = f.read()
            cursor.executescript(schema)
        
        conn.commit()
        conn.close()
        print(f"✅ Database initialized at {DB_FILE}")
    else:
        print(f"❌ Schema file not found: {SCHEMA_FILE}")


def get_db_path():
    """Return the database file path."""
    return DB_FILE




