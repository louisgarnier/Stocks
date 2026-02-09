/**
 * Frontend Test - Transactions Count and Display
 * 
 * Run this in the browser console (F12) to test the frontend API calls
 * and verify transaction counts match between frontend and backend.
 */

console.log('\n' + '='.repeat(70));
console.log('🧪 FRONTEND TRANSACTIONS TEST');
console.log('='.repeat(70));

// Test 1: Health endpoint
console.log('\n🔍 TEST 1: Health Endpoint');
fetch('/api/proxy/health')
  .then(r => r.json())
  .then(data => {
    console.log('✅ Health response:', data);
    console.log(`   Transactions count: ${data.transactions}`);
    console.log(`   Database status: ${data.database}`);
    return data.transactions;
  })
  .catch(err => {
    console.error('❌ Health endpoint error:', err);
    return null;
  })
  .then(healthCount => {
    // Test 2: List transactions endpoint
    console.log('\n🔍 TEST 2: List Transactions Endpoint');
    return fetch('/api/proxy/api/transactions?page=1&limit=25')
      .then(r => r.json())
      .then(data => {
        console.log('✅ List response:', data);
        console.log(`   Total: ${data.total}`);
        console.log(`   Data array length: ${data.data?.length || 0}`);
        console.log(`   Page: ${data.page}`);
        console.log(`   Pages: ${data.pages}`);
        
        if (data.data && data.data.length > 0) {
          console.log(`\n📋 First ${Math.min(5, data.data.length)} transactions:`);
          data.data.slice(0, 5).forEach((tx, i) => {
            console.log(`   ${i + 1}. ID:${tx.id} | ${tx.transaction_id} | ${tx.symbol} | ${tx.trade_date}`);
          });
        } else {
          console.log('   ⚠️  No transactions in data array!');
        }
        
        return { healthCount, listTotal: data.total, listDataLength: data.data?.length || 0 };
      })
      .catch(err => {
        console.error('❌ List endpoint error:', err);
        return { healthCount, listTotal: null, listDataLength: null };
      });
  })
  .then(results => {
    // Summary
    console.log('\n' + '='.repeat(70));
    console.log('📊 SUMMARY');
    console.log('='.repeat(70));
    console.log(`Health endpoint:        ${results.healthCount}`);
    console.log(`List endpoint total:   ${results.listTotal}`);
    console.log(`List endpoint data:    ${results.listDataLength}`);
    
    // Consistency check
    console.log('\n' + '='.repeat(70));
    console.log('✅ CONSISTENCY CHECK');
    console.log('='.repeat(70));
    
    let allMatch = true;
    if (results.healthCount !== results.listTotal) {
      console.log(`❌ Health vs List total: ${results.healthCount} != ${results.listTotal}`);
      allMatch = false;
    } else {
      console.log(`✅ Health = List total: ${results.healthCount}`);
    }
    
    if (results.listDataLength !== results.listTotal) {
      console.log(`❌ List data length vs total: ${results.listDataLength} != ${results.listTotal}`);
      allMatch = false;
    } else {
      console.log(`✅ List data length = total: ${results.listDataLength}`);
    }
    
    if (allMatch) {
      console.log('\n✅ ALL TESTS PASSED - Frontend API calls are consistent!');
      console.log('\n💡 If UI shows different count, check:');
      console.log('   1. React component state (use React DevTools)');
      console.log('   2. Component re-renders after API calls');
      console.log('   3. useEffect dependencies');
    } else {
      console.log('\n❌ INCONSISTENCIES FOUND - Frontend API calls have issues!');
    }
    
    console.log('\n' + '='.repeat(70));
  })
  .catch(err => {
    console.error('❌ Test failed:', err);
  });
