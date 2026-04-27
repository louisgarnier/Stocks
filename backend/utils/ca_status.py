"""
Corporate Actions Status Management

Helper functions to manage the status (grey/green/orange) of corporate actions per symbol.
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional

from backend.database.connection import get_db_connection


def set_ca_status(symbols: List[str], status: str, conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Set the corporate actions status for one or more symbols.
    
    Args:
        symbols: List of symbol strings
        status: 'grey', 'green', or 'orange'
        conn: Optional database connection (creates new one if None)
    """
    if not symbols:
        return
    
    if status not in ('grey', 'green', 'orange'):
        raise ValueError(f"Invalid status: {status}. Must be 'grey', 'green', or 'orange'")
    
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True
    
    try:
        cursor = conn.cursor()
        now = datetime.now().astimezone().isoformat()
        
        for symbol in symbols:
            # Check if status exists
            cursor.execute("SELECT sec_id FROM corporate_actions_status WHERE sec_id = ?", (symbol,))
            exists = cursor.fetchone()
            
            if exists:
                # Update existing status
                cursor.execute("""
                    UPDATE corporate_actions_status
                    SET status = ?, updated_at = ?, last_fetched_at = ?
                    WHERE sec_id = ?
                """, (status, now, now if status in ('green', 'grey') else None, symbol))
            else:
                # Insert new status
                cursor.execute("""
                    INSERT INTO corporate_actions_status (sec_id, status, last_fetched_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (symbol, status, now if status in ('green', 'grey') else None, now, now))
        
        conn.commit()
    finally:
        if close_conn:
            conn.close()


def get_ca_status(symbol: Optional[str] = None, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Dict]:
    """
    Get corporate actions status for a symbol or all symbols.
    
    Args:
        symbol: Optional symbol to filter by (returns all if None)
        conn: Optional database connection (creates new one if None)
        
    Returns:
        Dict mapping symbol -> {status, last_fetched_at, has_actions}
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        close_conn = True
    
    try:
        cursor = conn.cursor()
        
        # Get all symbols from transactions
        if symbol:
            cursor.execute("SELECT DISTINCT symbol FROM transactions WHERE symbol = ?", (symbol,))
        else:
            cursor.execute("SELECT DISTINCT symbol FROM transactions")
        
        all_symbols = [row[0] for row in cursor.fetchall()]
        
        # Get status for each symbol
        result = {}
        for sym in all_symbols:
            # Get status from corporate_actions_status
            cursor.execute("""
                SELECT status, last_fetched_at
                FROM corporate_actions_status
                WHERE sec_id = ?
            """, (sym,))
            status_row = cursor.fetchone()
            
            # Check if symbol has any corporate actions
            cursor.execute("""
                SELECT COUNT(*) FROM corporate_actions WHERE sec_id = ?
            """, (sym,))
            has_actions = cursor.fetchone()[0] > 0
            
            if status_row:
                result[sym] = {
                    "status": status_row["status"],
                    "last_fetched_at": status_row["last_fetched_at"],
                    "has_actions": has_actions
                }
            else:
                # No status record - determine based on has_actions
                result[sym] = {
                    "status": "green" if has_actions else "grey",
                    "last_fetched_at": None,
                    "has_actions": has_actions
                }
        
        return result
    finally:
        if close_conn:
            conn.close()


def delete_ca_status(symbols: List[str], conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Delete corporate actions status for one or more symbols.
    
    Args:
        symbols: List of symbol strings
        conn: Optional database connection (creates new one if None)
    """
    if not symbols:
        return
    
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True
    
    try:
        cursor = conn.cursor()
        placeholders = ','.join(['?'] * len(symbols))
        cursor.execute(f"DELETE FROM corporate_actions_status WHERE sec_id IN ({placeholders})", symbols)
        conn.commit()
    finally:
        if close_conn:
            conn.close()
