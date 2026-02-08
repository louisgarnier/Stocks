"""
Database connection and initialization.

⚠️ Before making changes, read: ../../docs/workflow/BEST_PRACTICES.md
Always check with the user before modifying this file.
"""

import sqlite3
from pathlib import Path
from typing import Optional

# Database path
DB_DIR = Path(__file__).parent
DB_FILE = DB_DIR / "app.db"


def get_db_connection():
    """
    Get a database connection.
    
    Returns:
        sqlite3.Connection: Database connection
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn


def init_database():
    """
    Initialize the database.
    Creates the database file and tables if they don't exist.
    """
    # Ensure database directory exists
    DB_DIR.mkdir(parents=True, exist_ok=True)
    
    # Read and execute schema
    schema_file = DB_DIR / "schema.sql"
    if schema_file.exists():
        conn = get_db_connection()
        cursor = conn.cursor()
        
        with open(schema_file, 'r') as f:
            schema = f.read()
            cursor.executescript(schema)
        
        conn.commit()
        conn.close()
    else:
        # Create a basic example table if schema.sql doesn't exist
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Example table - customize for your needs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()




