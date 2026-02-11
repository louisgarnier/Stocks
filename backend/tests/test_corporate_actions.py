#!/usr/bin/env python3
"""
Test script for Corporate Actions API endpoints.

Run: python backend/tests/test_corporate_actions.py
"""

import requests
import sys

API_BASE_URL = "http://localhost:8000"


def test_list_corporate_actions():
    """Test GET /api/corporate-actions endpoint."""
    print("\n" + "=" * 60)
    print("📋 Testing GET /api/corporate-actions")
    print("=" * 60)
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/corporate-actions?limit=100")
        
        print(f"\n📡 Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Error: {response.text}")
            return False
        
        data = response.json()
        
        print(f"✅ Total corporate actions: {data.get('total', 0)}")
        print(f"   Page: {data.get('page')}/{data.get('pages')}")
        
        actions = data.get('data', [])
        
        if not actions:
            print("\n   📭 No corporate actions in database")
            return True
        
        # Count by type
        by_type = {}
        for ca in actions:
            ca_type = ca.get('ca_type', 'unknown')
            by_type[ca_type] = by_type.get(ca_type, 0) + 1
        
        print("\n   By type:")
        for ca_type, count in sorted(by_type.items()):
            print(f"      {ca_type}: {count}")
        
        # Show first 5 actions
        print("\n   Sample data (first 5):")
        print(f"   {'Symbol':<10} {'Type':<12} {'Ex-Date':<12} {'Amount/Ratio':<15} {'Direction':<10}")
        print("   " + "-" * 60)
        
        for ca in actions[:5]:
            symbol = ca.get('sec_id', 'N/A')
            ca_type = ca.get('ca_type', 'N/A')
            ex_date = ca.get('ex_date', 'N/A')
            
            if ca_type == 'dividend':
                amount = f"${ca.get('amount', 0):.4f}" if ca.get('amount') else 'N/A'
                direction = ''
            elif ca_type == 'split':
                amount = f"{ca.get('split_to')}:{ca.get('split_from')}"
                direction = ca.get('split_direction', '') or ''
            else:
                amount = str(ca.get('amount', 'N/A'))
                direction = ''
            
            print(f"   {symbol:<10} {ca_type:<12} {ex_date:<12} {amount:<15} {direction:<10}")
        
        if len(actions) > 5:
            print(f"   ... and {len(actions) - 5} more")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Cannot connect to API at {API_BASE_URL}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def test_filter_by_type():
    """Test filtering by ca_type."""
    print("\n" + "=" * 60)
    print("🔍 Testing filter by type (dividends only)")
    print("=" * 60)
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/corporate-actions?ca_type=dividend&limit=5")
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            return False
        
        data = response.json()
        dividends = data.get('data', [])
        
        print(f"\n✅ Found {data.get('total', 0)} dividends")
        
        # Verify all are dividends
        non_dividends = [ca for ca in dividends if ca.get('ca_type') != 'dividend']
        if non_dividends:
            print(f"❌ Filter failed: found {len(non_dividends)} non-dividend actions")
            return False
        
        print("   ✅ Filter working correctly")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def test_filter_by_symbol():
    """Test filtering by symbol."""
    print("\n" + "=" * 60)
    print("🔍 Testing filter by symbol (NVDA)")
    print("=" * 60)
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/corporate-actions?symbol=NVDA&limit=20")
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            return False
        
        data = response.json()
        actions = data.get('data', [])
        
        print(f"\n✅ Found {data.get('total', 0)} corporate actions for NVDA")
        
        if actions:
            # Show NVDA actions
            for ca in actions[:10]:
                ca_type = ca.get('ca_type')
                ex_date = ca.get('ex_date')
                if ca_type == 'dividend':
                    detail = f"${ca.get('amount', 0):.4f}"
                elif ca_type == 'split':
                    detail = f"{ca.get('split_to')}:{ca.get('split_from')} ({ca.get('split_direction', 'N/A')})"
                else:
                    detail = str(ca.get('amount', 'N/A'))
                print(f"   {ex_date} - {ca_type}: {detail}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def test_summary():
    """Test GET /api/corporate-actions/summary endpoint."""
    print("\n" + "=" * 60)
    print("📊 Testing GET /api/corporate-actions/summary")
    print("=" * 60)
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/corporate-actions/summary")
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            return False
        
        data = response.json()
        
        print(f"\n✅ Summary:")
        print(f"   Total actions: {data.get('total', 0)}")
        print(f"   Securities with actions: {data.get('securities_with_actions', 0)}")
        print(f"\n   By type:")
        
        by_type = data.get('by_type', {})
        for ca_type, count in by_type.items():
            print(f"      {ca_type}: {count}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def main():
    """Main entry point."""
    print("=" * 60)
    print("🧪 CORPORATE ACTIONS API TEST")
    print("=" * 60)
    print(f"\n🌐 API: {API_BASE_URL}")
    
    results = []
    
    results.append(("List Corporate Actions", test_list_corporate_actions()))
    results.append(("Filter by Type", test_filter_by_type()))
    results.append(("Filter by Symbol", test_filter_by_symbol()))
    results.append(("Summary", test_summary()))
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status} - {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)
    
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
