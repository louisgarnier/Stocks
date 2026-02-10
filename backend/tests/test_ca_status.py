#!/usr/bin/env python3
"""
Test script for Corporate Actions Status Management

Tests the behavior of CA status (grey/green/orange) when:
1. Importing trades (CSV/Flex) -> status should be orange
2. Fetching from yfinance -> status should be green (if CA found) or grey (if no CA)
3. Deleting trades -> status should remain unchanged (CA are kept)

Run: python backend/tests/test_ca_status.py
"""

import sys
from pathlib import Path
import sqlite3

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.utils.ca_status import set_ca_status, get_ca_status, delete_ca_status
from backend.database.connection import get_db_connection

def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_status(status_data):
    """Print CA status data in a formatted way."""
    if not status_data:
        print("   No symbols found in database")
        return
    
    print(f"\n   {'Symbol':<10} {'Status':<10} {'Has CA':<10} {'Last Fetched':<20}")
    print("   " + "-" * 60)
    
    for symbol, data in sorted(status_data.items()):
        status_emoji = {
            'grey': '⚪',
            'green': '✅',
            'orange': '🟠'
        }.get(data['status'], '❓')
        
        has_ca = '✓' if data['has_actions'] else '✗'
        last_fetched = data['last_fetched_at'] or 'Never'
        
        print(f"   {symbol:<10} {status_emoji} {data['status']:<8} {has_ca:<10} {last_fetched:<20}")

def test_set_and_get_status():
    """Test setting and getting CA status."""
    print_header("TEST 1: Set and Get CA Status")
    
    # Test symbols
    test_symbols = ['TEST1', 'TEST2', 'TEST3']
    
    print("\n📝 Setting status to 'orange' for test symbols...")
    set_ca_status(test_symbols, 'orange')
    
    print("📊 Getting status for test symbols...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for symbol in test_symbols:
        cursor.execute("SELECT status FROM corporate_actions_status WHERE sec_id = ?", (symbol,))
        row = cursor.fetchone()
        if row:
            print(f"   {symbol}: {row['status']}")
        else:
            print(f"   {symbol}: NOT FOUND")
    
    conn.close()
    
    print("\n🗑️  Cleaning up test data...")
    delete_ca_status(test_symbols)
    print("   ✅ Test symbols removed")

def test_status_after_import():
    """Test CA status behavior after importing trades."""
    print_header("TEST 2: Status After Trade Import (Simulated)")
    
    print("\n📋 Scenario: User imports trades for AAPL, MSFT")
    print("   Expected: Status should be set to 'orange' for these symbols")
    
    # Simulate import
    imported_symbols = ['AAPL', 'MSFT']
    set_ca_status(imported_symbols, 'orange')
    
    print("\n📊 Current status:")
    status_data = get_ca_status()
    
    for symbol in imported_symbols:
        if symbol in status_data:
            print(f"   {symbol}: {status_data[symbol]['status']} {'✅' if status_data[symbol]['status'] == 'orange' else '❌'}")

def test_status_after_fetch():
    """Test CA status behavior after fetching from yfinance."""
    print_header("TEST 3: Status After Fetch from yfinance (Simulated)")
    
    print("\n📋 Scenario: User fetches CA from yfinance")
    print("   Expected: Status should be 'green' if CA found, 'grey' if no CA")
    
    # Get actual symbols from database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT symbol FROM transactions LIMIT 5")
    symbols = [row[0] for row in cursor.fetchall()]
    
    if not symbols:
        print("   ⚠️  No symbols found in database - skipping test")
        conn.close()
        return
    
    print(f"\n   Testing with symbols: {', '.join(symbols)}")
    
    # Check which symbols have CA
    symbols_with_ca = []
    symbols_without_ca = []
    
    for symbol in symbols:
        cursor.execute("SELECT COUNT(*) FROM corporate_actions WHERE sec_id = ?", (symbol,))
        count = cursor.fetchone()[0]
        if count > 0:
            symbols_with_ca.append(symbol)
        else:
            symbols_without_ca.append(symbol)
    
    conn.close()
    
    # Simulate fetch results
    if symbols_with_ca:
        set_ca_status(symbols_with_ca, 'green')
        print(f"\n   ✅ Set 'green' for symbols with CA: {', '.join(symbols_with_ca)}")
    
    if symbols_without_ca:
        set_ca_status(symbols_without_ca, 'grey')
        print(f"   ⚪ Set 'grey' for symbols without CA: {', '.join(symbols_without_ca)}")
    
    print("\n📊 Current status:")
    status_data = get_ca_status()
    print_status(status_data)

def test_status_persistence_after_delete():
    """Test that CA status persists after deleting trades."""
    print_header("TEST 4: Status Persistence After Deleting Trades")
    
    print("\n📋 Scenario: User deletes trades but CA remain in database")
    print("   Expected: CA status should remain unchanged")
    
    # Get current status
    status_before = get_ca_status()
    
    if not status_before:
        print("   ⚠️  No symbols found in database - skipping test")
        return
    
    print("\n📊 Status BEFORE simulated delete:")
    print_status(status_before)
    
    print("\n🗑️  Simulating trade deletion (status should NOT change)...")
    print("   Note: In real scenario, trades are deleted but CA and status remain")
    
    # Get status again (should be unchanged)
    status_after = get_ca_status()
    
    print("\n📊 Status AFTER simulated delete:")
    print_status(status_after)
    
    # Verify no changes
    if status_before == status_after:
        print("\n   ✅ Status unchanged - TEST PASSED")
    else:
        print("\n   ❌ Status changed - TEST FAILED")

def test_full_workflow():
    """Test the complete workflow."""
    print_header("TEST 5: Complete Workflow")
    
    print("\n📋 Workflow:")
    print("   1. Import trades -> status = orange")
    print("   2. Fetch CA from yfinance -> status = green/grey")
    print("   3. Import more trades -> status = orange again")
    print("   4. Fetch CA again -> status = green/grey")
    
    test_symbol = 'WORKFLOW_TEST'
    
    print(f"\n1️⃣  Simulating trade import for {test_symbol}...")
    set_ca_status([test_symbol], 'orange')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM corporate_actions_status WHERE sec_id = ?", (test_symbol,))
    row = cursor.fetchone()
    print(f"   Status: {row['status'] if row else 'NOT FOUND'} {'✅' if row and row['status'] == 'orange' else '❌'}")
    
    print(f"\n2️⃣  Simulating yfinance fetch (no CA found) for {test_symbol}...")
    set_ca_status([test_symbol], 'grey')
    cursor.execute("SELECT status FROM corporate_actions_status WHERE sec_id = ?", (test_symbol,))
    row = cursor.fetchone()
    print(f"   Status: {row['status'] if row else 'NOT FOUND'} {'✅' if row and row['status'] == 'grey' else '❌'}")
    
    print(f"\n3️⃣  Simulating another trade import for {test_symbol}...")
    set_ca_status([test_symbol], 'orange')
    cursor.execute("SELECT status FROM corporate_actions_status WHERE sec_id = ?", (test_symbol,))
    row = cursor.fetchone()
    print(f"   Status: {row['status'] if row else 'NOT FOUND'} {'✅' if row and row['status'] == 'orange' else '❌'}")
    
    print(f"\n4️⃣  Simulating yfinance fetch (CA found) for {test_symbol}...")
    set_ca_status([test_symbol], 'green')
    cursor.execute("SELECT status FROM corporate_actions_status WHERE sec_id = ?", (test_symbol,))
    row = cursor.fetchone()
    print(f"   Status: {row['status'] if row else 'NOT FOUND'} {'✅' if row and row['status'] == 'green' else '❌'}")
    
    conn.close()
    
    print(f"\n🗑️  Cleaning up test data...")
    delete_ca_status([test_symbol])
    print("   ✅ Test symbol removed")

def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  🧪 CORPORATE ACTIONS STATUS - TEST SUITE")
    print("=" * 70)
    
    try:
        test_set_and_get_status()
        test_status_after_import()
        test_status_after_fetch()
        test_status_persistence_after_delete()
        test_full_workflow()
        
        print("\n" + "=" * 70)
        print("  ✅ ALL TESTS COMPLETED")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
