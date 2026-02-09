# Test Transactions - Backend vs Frontend

## Backend Test

Run this command to test the backend:

```bash
python3 backend/tests/test_transactions_count.py
```

**Expected output:**
- Database COUNT(*): 5
- Database SELECT all: 5
- API query simulation: 5
- All should match!

## Frontend Test

Open browser console (F12) and run:

```javascript
// Test 1: Health endpoint
fetch('/api/proxy/health')
  .then(r => r.json())
  .then(data => console.log('Health:', data.transactions, 'transactions'));

// Test 2: List transactions endpoint
fetch('/api/proxy/api/transactions?page=1&limit=25')
  .then(r => r.json())
  .then(data => {
    console.log('List endpoint:');
    console.log('  Total:', data.total);
    console.log('  Data length:', data.data?.length);
    console.log('  First transaction:', data.data?.[0]);
  });
```

**Expected:**
- Health: 5 transactions
- List endpoint total: 5
- List endpoint data length: 5
- First transaction should have id, symbol, etc.

## What to Check

1. **Backend is running**: Check terminal running `uvicorn backend.api.main:app`
2. **No API errors**: Check browser console for errors
3. **Network tab**: Check if `/api/proxy/api/transactions` returns 200 OK
4. **React state**: Use React DevTools to check `transactions` state

## Common Issues

- **Backend not running**: Start with `uvicorn backend.api.main:app --reload`
- **CORS errors**: Check backend CORS settings
- **404 errors**: Check API proxy route
- **Empty data**: Check if SQL query is correct
- **State not updating**: Check useEffect dependencies
