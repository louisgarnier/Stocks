"""
Direct API Test - Check if /api/transactions endpoint works

Run this while the backend is running to test the endpoint directly.
"""

import requests
import json

def test_api():
    print("\n" + "="*70)
    print("🧪 DIRECT API TEST")
    print("="*70)
    
    base_url = "http://localhost:8000"
    
    # Test 1: Health endpoint
    print("\n🔍 TEST 1: Health Endpoint")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health: {data['transactions']} transactions")
        else:
            print(f"❌ Health failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Health error: {e}")
        return
    
    # Test 2: List transactions endpoint
    print("\n🔍 TEST 2: List Transactions Endpoint")
    try:
        response = requests.get(f"{base_url}/api/transactions?page=1&limit=25")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ List endpoint:")
            print(f"   Total: {data.get('total', 'N/A')}")
            print(f"   Data length: {len(data.get('data', []))}")
            print(f"   Page: {data.get('page', 'N/A')}")
            print(f"   Pages: {data.get('pages', 'N/A')}")
            
            if data.get('data'):
                print(f"\n📋 First transaction:")
                tx = data['data'][0]
                print(f"   ID: {tx.get('id')}")
                print(f"   transaction_id: {tx.get('transaction_id')}")
                print(f"   symbol: {tx.get('symbol')}")
                print(f"   trade_date: {tx.get('trade_date')}")
            else:
                print("   ⚠️  No transactions in data array!")
        else:
            print(f"❌ List endpoint failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ List endpoint error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)
    print("💡 If backend returns 5 but frontend shows 0:")
    print("   1. Check browser console for API errors")
    print("   2. Check Network tab - is /api/proxy/api/transactions called?")
    print("   3. Check if backend was restarted after code changes")
    print("="*70)

if __name__ == "__main__":
    test_api()
