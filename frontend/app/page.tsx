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

interface Split {
  id: number;
  symbol: string;
  split_date: string;
  split_ratio: number;
  fetched_at: string | null;
  applied_at: string | null;
}

interface SplitsResponse {
  data: Split[];
  total: number;
}

interface SplitsStatus {
  total_splits: number;
  splits_applied: number;
  last_fetch_at: string | null;
  transactions_adjusted: number;
}

type TabType = 'transactions' | 'splits' | 'adjusted';

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<TabType>('transactions');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [flexStatus, setFlexStatus] = useState<FlexStatus | null>(null);
  const [transactions, setTransactions] = useState<TransactionsResponse | null>(null);
  const [splits, setSplits] = useState<SplitsResponse | null>(null);
  const [splitsStatus, setSplitsStatus] = useState<SplitsStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [fetchingSplits, setFetchingSplits] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [sortBy, setSortBy] = useState('trade_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [symbolFilter, setSymbolFilter] = useState<string>('');

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

  const fetchTransactions = async (page: number = 1, limit: number = pageSize, sort: string = sortBy, order: string = sortOrder, symbol: string = symbolFilter) => {
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

  const fetchSplits = async () => {
    try {
      const response = await fetch('/api/proxy/api/splits');
      if (response.ok) {
        const data = await response.json();
        setSplits(data);
      }
    } catch (err) {
      console.error('Failed to fetch splits:', err);
    }
  };

  const fetchSplitsStatus = async () => {
    try {
      const response = await fetch('/api/proxy/api/splits/status');
      if (response.ok) {
        const data = await response.json();
        setSplitsStatus(data);
      }
    } catch (err) {
      console.error('Failed to fetch splits status:', err);
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

  const handleFetchSplits = async () => {
    setFetchingSplits(true);
    try {
      const response = await fetch('/api/proxy/api/splits/fetch', { method: 'POST' });
      if (response.ok) {
        // Poll every 2 seconds until complete (max 30 seconds)
        let attempts = 0;
        const pollSplits = async () => {
          attempts++;
          await fetchSplits();
          await fetchSplitsStatus();
          
          if (attempts < 15) {
            setTimeout(pollSplits, 2000);
          } else {
            await fetchTransactions(currentPage, pageSize);
            setFetchingSplits(false);
          }
        };
        setTimeout(pollSplits, 2000);
      }
    } catch (err) {
      console.error('Failed to fetch splits:', err);
      setFetchingSplits(false);
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
    fetchSplits();
    fetchSplitsStatus();
    const interval = setInterval(() => {
      fetchHealth();
      fetchFlexStatus();
      fetchSplitsStatus();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const isConnected = health?.database === 'connected';

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f9fafb' }}>
        <p style={{ color: '#6b7280' }}>Chargement...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f9fafb' }}>
        <div style={{ textAlign: 'center', color: '#dc2626', maxWidth: '600px', padding: '20px' }}>
          <h2 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '16px' }}>Erreur de connexion</h2>
          <p style={{ marginBottom: '16px' }}>{error}</p>
          <button onClick={() => window.location.reload()} style={{ padding: '12px 24px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer' }}>
            Recharger
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f9fafb' }}>
      <header style={{ backgroundColor: 'white', borderBottom: '1px solid #e5e7eb', padding: '16px 20px' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: '#1f2937' }}>IBKR Portfolio Tracker</h1>
          <span style={{ display: 'inline-flex', alignItems: 'center', padding: '6px 12px', borderRadius: '9999px', fontSize: '14px', fontWeight: '500', backgroundColor: isConnected ? '#dcfce7' : '#fef2f2', color: isConnected ? '#166534' : '#dc2626' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', marginRight: '8px', backgroundColor: isConnected ? '#22c55e' : '#ef4444' }} />
            {isConnected ? 'Connecté' : 'Déconnecté'}
          </span>
        </div>
      </header>

      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '32px 20px' }}>
        {/* Stats Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px', marginBottom: '32px' }}>
          <div style={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '14px', fontWeight: '500', color: '#6b7280', marginBottom: '8px' }}>Base de données</h3>
            <p style={{ fontSize: '24px', fontWeight: '600', color: '#1f2937' }}>{health?.database === 'connected' ? '✅ Connectée' : '❌ Erreur'}</p>
          </div>
          <div style={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '14px', fontWeight: '500', color: '#6b7280', marginBottom: '8px' }}>Transactions</h3>
            <p style={{ fontSize: '24px', fontWeight: '600', color: '#1f2937' }}>{health?.transactions ?? 0}</p>
          </div>
          <div style={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '14px', fontWeight: '500', color: '#6b7280', marginBottom: '8px' }}>Stock Splits</h3>
            <p style={{ fontSize: '24px', fontWeight: '600', color: '#1f2937' }}>{splitsStatus?.total_splits ?? 0} splits</p>
          </div>
          <div style={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '14px', fontWeight: '500', color: '#6b7280', marginBottom: '8px' }}>Splits Appliqués</h3>
            <p style={{ fontSize: '24px', fontWeight: '600', color: splitsStatus?.transactions_adjusted ? '#16a34a' : '#6b7280' }}>
              {splitsStatus?.transactions_adjusted ? `✅ ${splitsStatus.transactions_adjusted} tx` : '⏳ 0 tx'}
            </p>
          </div>
        </div>

        {/* Sync Status */}
        {flexStatus && (
          <div style={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '16px 24px', marginBottom: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={{ fontSize: '14px', color: '#6b7280' }}>Dernière sync: </span>
              <span style={{ fontSize: '14px', fontWeight: '500', color: '#1f2937' }}>{flexStatus.last_fetch_at ? new Date(flexStatus.last_fetch_at).toLocaleString('fr-FR') : 'Jamais'}</span>
              {flexStatus.last_fetch_status === 'success' && <span style={{ marginLeft: '12px', color: '#16a34a', fontSize: '14px' }}>✅ {flexStatus.records_fetched} enregistrements</span>}
              {flexStatus.last_fetch_status === 'fetching' && <span style={{ marginLeft: '12px', color: '#f59e0b', fontSize: '14px' }}>⏳ En cours...</span>}
            </div>
            <button onClick={handleFetchFromIBKR} disabled={fetching} style={{ backgroundColor: fetching ? '#9ca3af' : '#3b82f6', color: 'white', border: 'none', borderRadius: '8px', padding: '10px 20px', fontSize: '14px', fontWeight: '500', cursor: fetching ? 'not-allowed' : 'pointer' }}>
              {fetching ? '⏳ Récupération...' : '🔄 Sync from IBKR'}
            </button>
          </div>
        )}

        {/* Tabs */}
        <div style={{ display: 'flex', gap: '0', marginBottom: '0', borderBottom: '1px solid #e5e7eb' }}>
          {(['transactions', 'splits', 'adjusted'] as TabType[]).map((tab) => (
            <button key={tab} onClick={() => setActiveTab(tab)} style={{ padding: '12px 24px', fontSize: '14px', fontWeight: '500', border: 'none', borderBottom: activeTab === tab ? '2px solid #3b82f6' : '2px solid transparent', backgroundColor: 'transparent', color: activeTab === tab ? '#3b82f6' : '#6b7280', cursor: 'pointer' }}>
              {tab === 'transactions' && '📄 Transactions'}
              {tab === 'splits' && '📈 Stock Splits'}
              {tab === 'adjusted' && '✅ Transactions Ajustées'}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div style={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderTop: 'none', borderRadius: '0 0 8px 8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          
          {/* Tab 1: Transactions */}
          {activeTab === 'transactions' && (
            <div>
              <div style={{ padding: '20px 24px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937' }}>Transactions (Données brutes)</h2>
                {transactions && <span style={{ fontSize: '14px', color: '#6b7280' }}>{transactions.total} transactions</span>}
              </div>
              {!transactions?.data?.length ? (
                <div style={{ padding: '48px 24px', textAlign: 'center' }}>
                  <div style={{ fontSize: '48px', marginBottom: '16px' }}>📄</div>
                  <h3 style={{ fontSize: '18px', fontWeight: '500', color: '#1f2937', marginBottom: '8px' }}>Aucune transaction</h3>
                  <p style={{ fontSize: '14px', color: '#6b7280' }}>Récupérez vos transactions depuis IBKR.</p>
                </div>
              ) : (
                <div>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#f9fafb' }}>
                        <th onClick={() => handleSort('trade_date')} style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Date {sortBy === 'trade_date' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th onClick={() => handleSort('symbol')} style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Symbol {sortBy === 'symbol' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th onClick={() => handleSort('quantity')} style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Quantité {sortBy === 'quantity' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th onClick={() => handleSort('t_price')} style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Prix {sortBy === 't_price' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th onClick={() => handleSort('proceeds')} style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Montant {sortBy === 'proceeds' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Frais</th>
                      </tr>
                      <tr style={{ backgroundColor: '#f3f4f6' }}>
                        <th style={{ padding: '8px 16px' }}></th>
                        <th style={{ padding: '8px 16px' }}><input type="text" placeholder="Filtrer..." value={symbolFilter} onChange={(e) => handleSymbolFilter(e.target.value.toUpperCase())} style={{ width: '100%', padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '12px' }} /></th>
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
                          <td style={{ padding: '12px 16px', fontSize: '14px', color: tx.quantity >= 0 ? '#16a34a' : '#dc2626', textAlign: 'right' }}>{tx.quantity >= 0 ? '+' : ''}{tx.quantity.toFixed(2)}</td>
                          <td style={{ padding: '12px 16px', fontSize: '14px', color: '#1f2937', textAlign: 'right' }}>{tx.t_price ? `$${tx.t_price.toFixed(2)}` : '-'}</td>
                          <td style={{ padding: '12px 16px', fontSize: '14px', color: '#1f2937', textAlign: 'right' }}>{tx.proceeds ? `$${tx.proceeds.toFixed(2)}` : '-'}</td>
                          <td style={{ padding: '12px 16px', fontSize: '14px', color: '#6b7280', textAlign: 'right' }}>{tx.comm_fee ? `$${Math.abs(tx.comm_fee).toFixed(2)}` : '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div style={{ padding: '16px 24px', borderTop: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '14px', color: '#6b7280' }}>Afficher:</span>
                      {[25, 50, 100, 200].map((size) => (
                        <button key={size} onClick={() => handlePageSizeChange(size)} style={{ padding: '6px 12px', border: '1px solid #d1d5db', borderRadius: '6px', backgroundColor: pageSize === size ? '#3b82f6' : 'white', color: pageSize === size ? 'white' : '#374151', cursor: 'pointer', fontSize: '14px' }}>{size}</button>
                      ))}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <button onClick={() => fetchTransactions(currentPage - 1, pageSize)} disabled={currentPage === 1} style={{ padding: '8px 16px', border: '1px solid #d1d5db', borderRadius: '6px', backgroundColor: currentPage === 1 ? '#f3f4f6' : 'white', color: currentPage === 1 ? '#9ca3af' : '#374151', cursor: currentPage === 1 ? 'not-allowed' : 'pointer', fontSize: '14px' }}>← Précédent</button>
                      <span style={{ padding: '8px 16px', fontSize: '14px', color: '#6b7280' }}>Page {currentPage} / {transactions.pages}</span>
                      <button onClick={() => fetchTransactions(currentPage + 1, pageSize)} disabled={currentPage === transactions.pages} style={{ padding: '8px 16px', border: '1px solid #d1d5db', borderRadius: '6px', backgroundColor: currentPage === transactions.pages ? '#f3f4f6' : 'white', color: currentPage === transactions.pages ? '#9ca3af' : '#374151', cursor: currentPage === transactions.pages ? 'not-allowed' : 'pointer', fontSize: '14px' }}>Suivant →</button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Tab 2: Stock Splits */}
          {activeTab === 'splits' && (
            <div>
              <div style={{ padding: '20px 24px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937' }}>Stock Splits</h2>
                <button onClick={handleFetchSplits} disabled={fetchingSplits} style={{ backgroundColor: fetchingSplits ? '#9ca3af' : '#3b82f6', color: 'white', border: 'none', borderRadius: '8px', padding: '10px 20px', fontSize: '14px', fontWeight: '500', cursor: fetchingSplits ? 'not-allowed' : 'pointer' }}>
                  {fetchingSplits ? '⏳ Récupération...' : '📈 Get Stock Splits'}
                </button>
              </div>
              {!splits?.data?.length ? (
                <div style={{ padding: '48px 24px', textAlign: 'center' }}>
                  <div style={{ fontSize: '48px', marginBottom: '16px' }}>📈</div>
                  <h3 style={{ fontSize: '18px', fontWeight: '500', color: '#1f2937', marginBottom: '8px' }}>Aucun stock split</h3>
                  <p style={{ fontSize: '14px', color: '#6b7280' }}>Cliquez sur "Get Stock Splits" pour récupérer les splits depuis Yahoo Finance.</p>
                </div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ backgroundColor: '#f9fafb' }}>
                      <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Symbol</th>
                      <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Date</th>
                      <th style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Ratio</th>
                      <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Appliqué</th>
                    </tr>
                  </thead>
                  <tbody>
                    {splits.data.map((split) => (
                      <tr key={split.id} style={{ borderTop: '1px solid #e5e7eb' }}>
                        <td style={{ padding: '12px 16px', fontSize: '14px', fontWeight: '500', color: '#1f2937' }}>{split.symbol}</td>
                        <td style={{ padding: '12px 16px', fontSize: '14px', color: '#1f2937' }}>{split.split_date}</td>
                        <td style={{ padding: '12px 16px', fontSize: '14px', color: '#3b82f6', textAlign: 'right', fontWeight: '600' }}>{split.split_ratio}:1</td>
                        <td style={{ padding: '12px 16px', fontSize: '14px', color: split.applied_at ? '#16a34a' : '#f59e0b' }}>{split.applied_at ? '✅ Oui' : '⏳ Non'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* Tab 3: Adjusted Transactions */}
          {activeTab === 'adjusted' && (
            <div>
              <div style={{ padding: '20px 24px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937' }}>Transactions Ajustées (après splits)</h2>
                {transactions && <span style={{ fontSize: '14px', color: '#6b7280' }}>{splitsStatus?.transactions_adjusted ?? 0} ajustées / {transactions.total} total</span>}
              </div>
              {!transactions?.data?.length ? (
                <div style={{ padding: '48px 24px', textAlign: 'center' }}>
                  <div style={{ fontSize: '48px', marginBottom: '16px' }}>✅</div>
                  <h3 style={{ fontSize: '18px', fontWeight: '500', color: '#1f2937', marginBottom: '8px' }}>Aucune transaction</h3>
                  <p style={{ fontSize: '14px', color: '#6b7280' }}>Récupérez vos transactions et appliquez les splits.</p>
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '1000px' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#f9fafb' }}>
                        <th onClick={() => handleSort('trade_date')} style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Date {sortBy === 'trade_date' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th onClick={() => handleSort('symbol')} style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Symbol {sortBy === 'symbol' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th onClick={() => handleSort('quantity')} style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Qté Orig. {sortBy === 'quantity' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th onClick={() => handleSort('updated_quantity')} style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#16a34a', textTransform: 'uppercase', cursor: 'pointer' }}>Qté Ajustée {sortBy === 'updated_quantity' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th onClick={() => handleSort('t_price')} style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Prix Orig. {sortBy === 't_price' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th onClick={() => handleSort('updated_t_price')} style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#16a34a', textTransform: 'uppercase', cursor: 'pointer' }}>Prix Ajusté {sortBy === 'updated_t_price' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Splits</th>
                      </tr>
                      <tr style={{ backgroundColor: '#f3f4f6' }}>
                        <th style={{ padding: '8px 16px' }}></th>
                        <th style={{ padding: '8px 16px' }}><input type="text" placeholder="Filtrer..." value={symbolFilter} onChange={(e) => handleSymbolFilter(e.target.value.toUpperCase())} style={{ width: '100%', padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '12px' }} /></th>
                        <th style={{ padding: '8px 16px' }}></th>
                        <th style={{ padding: '8px 16px' }}></th>
                        <th style={{ padding: '8px 16px' }}></th>
                        <th style={{ padding: '8px 16px' }}></th>
                        <th style={{ padding: '8px 16px' }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {transactions.data.map((tx) => (
                        <tr key={tx.id} style={{ borderTop: '1px solid #e5e7eb', backgroundColor: tx.stock_splits_applied && tx.stock_splits_applied !== 'no split' ? '#f0fdf4' : 'white' }}>
                          <td style={{ padding: '12px 16px', fontSize: '14px', color: '#1f2937' }}>{tx.trade_date}</td>
                          <td style={{ padding: '12px 16px', fontSize: '14px', fontWeight: '500', color: '#1f2937' }}>{tx.symbol}</td>
                          <td style={{ padding: '12px 16px', fontSize: '14px', color: '#6b7280', textAlign: 'right' }}>{tx.quantity.toFixed(2)}</td>
                          <td style={{ padding: '12px 16px', fontSize: '14px', color: '#16a34a', textAlign: 'right', fontWeight: '600' }}>{tx.updated_quantity?.toFixed(2) ?? tx.quantity.toFixed(2)}</td>
                          <td style={{ padding: '12px 16px', fontSize: '14px', color: '#6b7280', textAlign: 'right' }}>{tx.t_price ? `$${tx.t_price.toFixed(2)}` : '-'}</td>
                          <td style={{ padding: '12px 16px', fontSize: '14px', color: '#16a34a', textAlign: 'right', fontWeight: '600' }}>{tx.updated_t_price ? `$${tx.updated_t_price.toFixed(2)}` : (tx.t_price ? `$${tx.t_price.toFixed(2)}` : '-')}</td>
                          <td style={{ padding: '12px 16px', fontSize: '12px', color: tx.stock_splits_applied && tx.stock_splits_applied !== 'no split' ? '#16a34a' : '#9ca3af' }}>{tx.stock_splits_applied || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div style={{ padding: '16px 24px', borderTop: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '14px', color: '#6b7280' }}>Afficher:</span>
                      {[25, 50, 100, 200].map((size) => (
                        <button key={size} onClick={() => handlePageSizeChange(size)} style={{ padding: '6px 12px', border: '1px solid #d1d5db', borderRadius: '6px', backgroundColor: pageSize === size ? '#3b82f6' : 'white', color: pageSize === size ? 'white' : '#374151', cursor: 'pointer', fontSize: '14px' }}>{size}</button>
                      ))}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <button onClick={() => fetchTransactions(currentPage - 1, pageSize)} disabled={currentPage === 1} style={{ padding: '8px 16px', border: '1px solid #d1d5db', borderRadius: '6px', backgroundColor: currentPage === 1 ? '#f3f4f6' : 'white', color: currentPage === 1 ? '#9ca3af' : '#374151', cursor: currentPage === 1 ? 'not-allowed' : 'pointer', fontSize: '14px' }}>← Précédent</button>
                      <span style={{ padding: '8px 16px', fontSize: '14px', color: '#6b7280' }}>Page {currentPage} / {transactions.pages}</span>
                      <button onClick={() => fetchTransactions(currentPage + 1, pageSize)} disabled={currentPage === transactions.pages} style={{ padding: '8px 16px', border: '1px solid #d1d5db', borderRadius: '6px', backgroundColor: currentPage === transactions.pages ? '#f3f4f6' : 'white', color: currentPage === transactions.pages ? '#9ca3af' : '#374151', cursor: currentPage === transactions.pages ? 'not-allowed' : 'pointer', fontSize: '14px' }}>Suivant →</button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
