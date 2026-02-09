# Frontend Test - Transactions Count and Display

## Test Steps

1. **Open Browser Console** (F12)
2. **Run these commands in the console:**

```javascript
// Test 1: Check health endpoint
fetch('/api/proxy/health')
  .then(r => r.json())
  .then(data => {
    console.log('📊 Health endpoint:', data);
    console.log('   Transactions count:', data.transactions);
  });

// Test 2: Check list transactions endpoint
fetch('/api/proxy/api/transactions?page=1&limit=25')
  .then(r => r.json())
  .then(data => {
    console.log('📊 List endpoint:', data);
    console.log('   Total:', data.total);
    console.log('   Data array length:', data.data?.length);
    console.log('   First transaction:', data.data?.[0]);
  });

// Test 3: Check React state
// In React DevTools, check the component state:
// - health.transactions
// - transactions.total
// - transactions.data.length
```

## Expected Results

- Health endpoint should return the same count as the database
- List endpoint should return transactions in the data array
- Frontend state should match the API responses

## Common Issues

1. **CORS errors**: Check if backend is running on port 8000
2. **404 errors**: Check if API proxy route is correct
3. **Empty data array**: Check if SQL query is correct
4. **State not updating**: Check if useEffect dependencies are correct
