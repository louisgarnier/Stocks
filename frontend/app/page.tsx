/**
 * IBKR Portfolio Tracker - Dashboard
 * 
 * ⚠️ Before making changes, read: ../../docs/workflow/BEST_PRACTICES.md
 * Always check with the user before modifying this file.
 */

'use client';

import { useEffect, useState } from 'react';

interface HealthResponse {
  status: string;
  database: string;
  transactions: number;
  positions: number;
}

interface FlexStatus {
  last_fetch_at: string | null;
  last_fetch_status: string;
  last_fetch_message: string | null;
  records_fetched: number;
}

interface Transaction {
  id: number;
  transaction_id: string;
  symbol: string;
  trade_date: string;
  quantity: number;
  t_price: number | null;
  proceeds: number | null;
  comm_fee: number | null;
  updated_quantity: number | null;
  updated_t_price: number | null;
  stock_splits_applied: string | null;
}

interface TransactionsResponse {
  data: Transaction[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export default function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [flexStatus, setFlexStatus] = useState<FlexStatus | null>(null);
  const [transactions, setTransactions] = useState<TransactionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [sortBy, setSortBy] = useState('trade_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [symbolFilter, setSymbolFilter] = useState<string>('');
  const [symbols, setSymbols] = useState<{symbol: string, count: number}[]>([]);

  const fetchHealth = async () => {
    try {
      const response = await fetch('/api/proxy/health');
      if (!response.ok) throw new Error('API not reachable');
      const data = await response.json();
      setHealth(data);
      setError(null);
    } catch (err) {
      setError('Cannot connect to API');
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  const fetchFlexStatus = async () => {
    try {
      const response = await fetch('/api/proxy/api/flex/status');
      if (response.ok) {
        const data = await response.json();
        setFlexStatus(data);
      }
    } catch (err) {
      console.error('Failed to fetch flex status:', err);
    }
  };

  const fetchTransactions = async (
    page: number = 1, 
    limit: number = pageSize,
    sort: string = sortBy,
    order: string = sortOrder,
    symbol: string = symbolFilter
  ) => {
    try {
      let url = `/api/proxy/api/transactions?page=${page}&limit=${limit}&sort_by=${sort}&sort_order=${order}`;
      if (symbol) url += `&symbol=${symbol}`;
      
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        setTransactions(data);
        setCurrentPage(page);
      }
    } catch (err) {
      console.error('Failed to fetch transactions:', err);
    }
  };

  const fetchSymbols = async () => {
    try {
      const response = await fetch('/api/proxy/api/transactions/symbols');
      if (response.ok) {
        const data = await response.json();
        setSymbols(data.symbols || []);
      }
    } catch (err) {
      console.error('Failed to fetch symbols:', err);
    }
  };

  const handleSort = (column: string) => {
    const newOrder = sortBy === column && sortOrder === 'desc' ? 'asc' : 'desc';
    setSortBy(column);
    setSortOrder(newOrder);
    fetchTransactions(1, pageSize, column, newOrder, symbolFilter);
  };

  const handleSymbolFilter = (symbol: string) => {
    setSymbolFilter(symbol);
    setCurrentPage(1);
    fetchTransactions(1, pageSize, sortBy, sortOrder, symbol);
  };

  const handleFetchFromIBKR = async () => {
    setFetching(true);
    try {
      const response = await fetch('/api/proxy/api/flex/fetch', { method: 'POST' });
      if (response.ok) {
        // Poll for status updates
        const pollStatus = async () => {
          const statusRes = await fetch('/api/proxy/api/flex/status');
          const status = await statusRes.json();
          setFlexStatus(status);
          
          if (status?.last_fetch_status === 'fetching') {
            setTimeout(pollStatus, 2000);
          } else {
            setFetching(false);
            await fetchHealth();
            await fetchTransactions(1, pageSize);
          }
        };
        setTimeout(pollStatus, 2000);
      }
    } catch (err) {
      console.error('Failed to trigger fetch:', err);
      setFetching(false);
    }
  };

  const handlePageSizeChange = (newSize: number) => {
    setPageSize(newSize);
    setCurrentPage(1);
    fetchTransactions(1, newSize);
  };

  useEffect(() => {
    fetchHealth();
    fetchFlexStatus();
    fetchTransactions();
    fetchSymbols();
    
    const interval = setInterval(() => {
      fetchHealth();
      fetchFlexStatus();
    }, 10000);
    
    return () => clearInterval(interval);
  }, []);

  const isConnected = health?.database === 'connected';

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f9fafb' }}>
        <div style={{ textAlign: 'center' }}>
          <p style={{ color: '#6b7280' }}>Chargement...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f9fafb' }}>
        <div style={{ textAlign: 'center', color: '#dc2626', maxWidth: '600px', padding: '20px' }}>
          <h2 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '16px' }}>Erreur de connexion</h2>
          <p style={{ marginBottom: '16px' }}>{error}</p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '12px 24px',
              backgroundColor: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontSize: '16px',
              cursor: 'pointer',
              fontWeight: '500',
            }}
          >
            Recharger la page
          </button>
          <p style={{ marginTop: '16px', fontSize: '14px', color: '#6b7280' }}>
            Vérifiez que le serveur backend est démarré sur http://localhost:8000
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f9fafb' }}>
      {/* Header */}
      <header style={{ backgroundColor: 'white', borderBottom: '1px solid #e5e7eb', padding: '16px 20px' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: '#1f2937' }}>
            IBKR Portfolio Tracker
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '6px 12px',
                borderRadius: '9999px',
                fontSize: '14px',
                fontWeight: '500',
                backgroundColor: isConnected ? '#dcfce7' : '#fef2f2',
                color: isConnected ? '#166534' : '#dc2626',
              }}
            >
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  marginRight: '8px',
                  backgroundColor: isConnected ? '#22c55e' : '#ef4444',
                }}
              />
              {isConnected ? 'Connecté' : 'Déconnecté'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '32px 20px' }}>
        {/* Stats Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px', marginBottom: '32px' }}>
          <div
            style={{
              backgroundColor: 'white',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              padding: '24px',
              boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
            }}
          >
            <h3 style={{ fontSize: '14px', fontWeight: '500', color: '#6b7280', marginBottom: '8px' }}>
              Base de données
            </h3>
            <p style={{ fontSize: '28px', fontWeight: '600', color: '#1f2937' }}>
              {health?.database === 'connected' ? '✅ Connectée' : '❌ Erreur'}
            </p>
          </div>

          <div
            style={{
              backgroundColor: 'white',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              padding: '24px',
              boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
            }}
          >
            <h3 style={{ fontSize: '14px', fontWeight: '500', color: '#6b7280', marginBottom: '8px' }}>
              Transactions
            </h3>
            <p style={{ fontSize: '28px', fontWeight: '600', color: '#1f2937' }}>
              {health?.transactions ?? 0}
            </p>
          </div>

          <div
            style={{
              backgroundColor: 'white',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              padding: '24px',
              boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
            }}
          >
            <h3 style={{ fontSize: '14px', fontWeight: '500', color: '#6b7280', marginBottom: '8px' }}>
              Positions
            </h3>
            <p style={{ fontSize: '28px', fontWeight: '600', color: '#1f2937' }}>
              {health?.positions ?? 0}
            </p>
          </div>
        </div>

        {/* Sync Status */}
        {flexStatus && (
          <div
            style={{
              backgroundColor: 'white',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              padding: '16px 24px',
              marginBottom: '20px',
              boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <span style={{ fontSize: '14px', color: '#6b7280' }}>Dernière synchronisation: </span>
              <span style={{ fontSize: '14px', fontWeight: '500', color: '#1f2937' }}>
                {flexStatus.last_fetch_at 
                  ? new Date(flexStatus.last_fetch_at).toLocaleString('fr-FR')
                  : 'Jamais'}
              </span>
              {flexStatus.last_fetch_status === 'success' && (
                <span style={{ marginLeft: '12px', color: '#16a34a', fontSize: '14px' }}>
                  ✅ {flexStatus.records_fetched} enregistrements
                </span>
              )}
              {flexStatus.last_fetch_status === 'error' && (
                <span style={{ marginLeft: '12px', color: '#dc2626', fontSize: '14px' }}>
                  ❌ {flexStatus.last_fetch_message}
                </span>
              )}
              {flexStatus.last_fetch_status === 'fetching' && (
                <span style={{ marginLeft: '12px', color: '#f59e0b', fontSize: '14px' }}>
                  ⏳ Récupération en cours...
                </span>
              )}
            </div>
            <button
              onClick={handleFetchFromIBKR}
              disabled={fetching || flexStatus.last_fetch_status === 'fetching'}
              style={{
                backgroundColor: fetching ? '#9ca3af' : '#3b82f6',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                padding: '10px 20px',
                fontSize: '14px',
                fontWeight: '500',
                cursor: fetching ? 'not-allowed' : 'pointer',
              }}
            >
              {fetching ? '⏳ Récupération...' : '🔄 Sync from IBKR'}
            </button>
          </div>
        )}

        {/* Transactions Section */}
        <div
          style={{
            backgroundColor: 'white',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
          }}
        >
          <div style={{ padding: '20px 24px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937' }}>
              Transactions
            </h2>
            {transactions && transactions.total > 0 && (
              <span style={{ fontSize: '14px', color: '#6b7280' }}>
                {transactions.total} transaction{transactions.total > 1 ? 's' : ''}
              </span>
            )}
          </div>
          <div style={{ padding: transactions?.data?.length ? '0' : '48px 24px' }}>
            {!transactions?.data?.length ? (
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '48px', marginBottom: '16px' }}>📄</div>
                <h3 style={{ fontSize: '18px', fontWeight: '500', color: '#1f2937', marginBottom: '8px' }}>
                  Aucune transaction
                </h3>
                <p style={{ fontSize: '14px', color: '#6b7280', marginBottom: '24px' }}>
                  Récupérez vos transactions depuis IBKR pour commencer.
                </p>
              </div>
            ) : (
              <>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ backgroundColor: '#f9fafb' }}>
                      <th 
                        onClick={() => handleSort('trade_date')}
                        style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer', userSelect: 'none' }}
                      >
                        Date {sortBy === 'trade_date' && (sortOrder === 'desc' ? '↓' : '↑')}
                      </th>
                      <th 
                        onClick={() => handleSort('symbol')}
                        style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer', userSelect: 'none' }}
                      >
                        Symbol {sortBy === 'symbol' && (sortOrder === 'desc' ? '↓' : '↑')}
                      </th>
                      <th 
                        onClick={() => handleSort('quantity')}
                        style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer', userSelect: 'none' }}
                      >
                        Quantité {sortBy === 'quantity' && (sortOrder === 'desc' ? '↓' : '↑')}
                      </th>
                      <th 
                        onClick={() => handleSort('t_price')}
                        style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer', userSelect: 'none' }}
                      >
                        Prix {sortBy === 't_price' && (sortOrder === 'desc' ? '↓' : '↑')}
                      </th>
                      <th 
                        onClick={() => handleSort('proceeds')}
                        style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer', userSelect: 'none' }}
                      >
                        Montant {sortBy === 'proceeds' && (sortOrder === 'desc' ? '↓' : '↑')}
                      </th>
                      <th 
                        onClick={() => handleSort('comm_fee')}
                        style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer', userSelect: 'none' }}
                      >
                        Frais {sortBy === 'comm_fee' && (sortOrder === 'desc' ? '↓' : '↑')}
                      </th>
                    </tr>
                    {/* Filter Row */}
                    <tr style={{ backgroundColor: '#f3f4f6' }}>
                      <th style={{ padding: '8px 16px' }}>
                        <input
                          type="text"
                          placeholder="Filtrer..."
                          style={{ width: '100%', padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '12px' }}
                        />
                      </th>
                      <th style={{ padding: '8px 16px' }}>
                        <input
                          type="text"
                          placeholder="Filtrer..."
                          value={symbolFilter}
                          onChange={(e) => handleSymbolFilter(e.target.value.toUpperCase())}
                          style={{ width: '100%', padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '12px' }}
                        />
                      </th>
                      <th style={{ padding: '8px 16px' }}></th>
                      <th style={{ padding: '8px 16px' }}></th>
                      <th style={{ padding: '8px 16px' }}></th>
                      <th style={{ padding: '8px 16px' }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.data.map((tx) => (
                      <tr key={tx.id} style={{ borderTop: '1px solid #e5e7eb' }}>
                        <td style={{ padding: '12px 16px', fontSize: '14px', color: '#1f2937' }}>{tx.trade_date}</td>
                        <td style={{ padding: '12px 16px', fontSize: '14px', fontWeight: '500', color: '#1f2937' }}>{tx.symbol}</td>
                        <td style={{ padding: '12px 16px', fontSize: '14px', color: tx.quantity >= 0 ? '#16a34a' : '#dc2626', textAlign: 'right' }}>
                          {tx.quantity >= 0 ? '+' : ''}{tx.quantity.toFixed(2)}
                        </td>
                        <td style={{ padding: '12px 16px', fontSize: '14px', color: '#1f2937', textAlign: 'right' }}>
                          {tx.t_price ? `$${tx.t_price.toFixed(2)}` : '-'}
                        </td>
                        <td style={{ padding: '12px 16px', fontSize: '14px', color: '#1f2937', textAlign: 'right' }}>
                          {tx.proceeds ? `$${tx.proceeds.toFixed(2)}` : '-'}
                        </td>
                        <td style={{ padding: '12px 16px', fontSize: '14px', color: '#6b7280', textAlign: 'right' }}>
                          {tx.comm_fee ? `$${Math.abs(tx.comm_fee).toFixed(2)}` : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                
                {/* Pagination */}
                <div style={{ padding: '16px 24px', borderTop: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  {/* Page size selector */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '14px', color: '#6b7280' }}>Afficher:</span>
                    {[25, 50, 100, 200].map((size) => (
                      <button
                        key={size}
                        onClick={() => handlePageSizeChange(size)}
                        style={{
                          padding: '6px 12px',
                          border: '1px solid #d1d5db',
                          borderRadius: '6px',
                          backgroundColor: pageSize === size ? '#3b82f6' : 'white',
                          color: pageSize === size ? 'white' : '#374151',
                          cursor: 'pointer',
                          fontSize: '14px',
                        }}
                      >
                        {size}
                      </button>
                    ))}
                  </div>
                  
                  {/* Page navigation */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <button
                      onClick={() => fetchTransactions(currentPage - 1, pageSize)}
                      disabled={currentPage === 1}
                      style={{
                        padding: '8px 16px',
                        border: '1px solid #d1d5db',
                        borderRadius: '6px',
                        backgroundColor: currentPage === 1 ? '#f3f4f6' : 'white',
                        color: currentPage === 1 ? '#9ca3af' : '#374151',
                        cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                        fontSize: '14px',
                      }}
                    >
                      ← Précédent
                    </button>
                    <span style={{ padding: '8px 16px', fontSize: '14px', color: '#6b7280' }}>
                      Page {currentPage} / {transactions.pages}
                    </span>
                    <button
                      onClick={() => fetchTransactions(currentPage + 1, pageSize)}
                      disabled={currentPage === transactions.pages}
                      style={{
                        padding: '8px 16px',
                        border: '1px solid #d1d5db',
                        borderRadius: '6px',
                        backgroundColor: currentPage === transactions.pages ? '#f3f4f6' : 'white',
                        color: currentPage === transactions.pages ? '#9ca3af' : '#374151',
                        cursor: currentPage === transactions.pages ? 'not-allowed' : 'pointer',
                        fontSize: '14px',
                      }}
                    >
                      Suivant →
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}




