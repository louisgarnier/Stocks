"""
Database tests.

⚠️ Before making changes, read: ../../docs/workflow/BEST_PRACTICES.md
"""

import pytest
import os
import tempfile
from pathlib import Path
from backend.database.connection import get_db_connection, init_database, DB_FILE


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    # Save original DB file path
    original_db = DB_FILE
    
    # Create temporary database
    temp_dir = tempfile.mkdtemp()
    temp_db_path = Path(temp_dir) / "test.db"
    
    # Temporarily change DB_FILE
    import backend.database.connection as db_module
    db_module.DB_FILE = temp_db_path
    
    # Initialize database
    init_database()
    
    yield temp_db_path
    
    # Cleanup
    if temp_db_path.exists():
        temp_db_path.unlink()
    db_module.DB_FILE = original_db


def test_database_initialization(temp_db):
    """Test database initialization creates tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check core tables from the current schema exist
    for table in ("transactions", "tracked_universe", "market_data", "indicators"):
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        )
        assert cursor.fetchone() is not None, f"missing table: {table}"
    conn.close()


def test_database_connection(temp_db):
    """Test database connection works."""
    conn = get_db_connection()
    assert conn is not None
    
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    result = cursor.fetchone()
    
    assert result[0] == 1
    conn.close()




