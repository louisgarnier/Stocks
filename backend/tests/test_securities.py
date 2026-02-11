#!/usr/bin/env python3
"""
Test script for the /api/transactions/securities endpoint.

Run: python backend/tests/test_securities.py
"""

import requests
import sys

API_BASE_URL = "http://localhost:8000"


def test_securities_endpoint():
    """Test the securities endpoint."""
    print("=" * 60)
    print("🧪 Testing /api/transactions/securities endpoint")
    print("=" * 60)
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/transactions/securities")
        
        print(f"\n📡 GET /api/transactions/securities")
        print(f"   Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ Error: {response.text}")
            return False
        
        data = response.json()
        
        print(f"\n✅ Response received:")
        print(f"   Total securities: {data.get('total', 0)}")
        print()
        
        securities = data.get('data', [])
        
        if not securities:
            print("   📭 No securities in database")
            return True
        
        # Display securities in a table format
        print(f"   {'Symbol':<10} {'Position':>12} {'Transactions':>14} {'Currency':>10} {'First Trade':<12} {'Last Trade':<12}")
        print("   " + "-" * 72)
        
        for sec in securities:
            symbol = sec.get('symbol', 'N/A')
            position = sec.get('total_quantity', 0)
            tx_count = sec.get('transaction_count', 0)
            currency = sec.get('currency', 'USD') or 'USD'
            first = sec.get('first_trade', 'N/A')
            last = sec.get('last_trade', 'N/A')
            
            # Color coding for position
            pos_str = f"{position:+.2f}"
            
            print(f"   {symbol:<10} {pos_str:>12} {tx_count:>14} {currency:>10} {first:<12} {last:<12}")
        
        print()
        print(f"📊 Summary:")
        print(f"   - {len(securities)} unique securities")
        
        # Count open vs closed positions
        open_positions = [s for s in securities if abs(s.get('total_quantity', 0)) > 0.01]
        closed_positions = [s for s in securities if abs(s.get('total_quantity', 0)) <= 0.01]
        
        print(f"   - {len(open_positions)} open positions")
        print(f"   - {len(closed_positions)} closed positions (qty ≈ 0)")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Cannot connect to API at {API_BASE_URL}")
        print("   Make sure the backend is running: python -m uvicorn backend.api.main:app --reload --port 8000")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def main():
    """Main entry point."""
    success = test_securities_endpoint()
    
    print()
    print("=" * 60)
    if success:
        print("✅ Test completed successfully")
    else:
        print("❌ Test failed")
    print("=" * 60)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
