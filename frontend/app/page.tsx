'use client';

import { useEffect, useState } from 'react';

interface HealthResponse {
  status: string;
  database: string;
  transactions: number;
  positions: number;
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
  currency: string | null;
}

interface TransactionsResponse {
  data: Transaction[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

interface ImportLog {
  id: number;
  filename: string;
  import_date: string;
  parsed: number;
  inserted: number;
  skipped: number;
  errors: number;
  status: string;
}

interface ImportLogsResponse {
  logs: ImportLog[];
  total: number;
}

type TabType = 'load' | 'transactions';

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<TabType>('load');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [transactions, setTransactions] = useState<TransactionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [sortBy, setSortBy] = useState('trade_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [symbolFilter, setSymbolFilter] = useState<string>('');
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{success: boolean, message: string, parsed: number, inserted: number, skipped: number, errors: number, error_details?: string[]} | null>(null);
  const [importLogs, setImportLogs] = useState<ImportLogsResponse | null>(null);
  const [selectedTransactions, setSelectedTransactions] = useState<Set<string>>(new Set());

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

  const fetchImportLogs = async () => {
    try {
      const response = await fetch('/api/proxy/api/transactions/import-logs');
      if (response.ok) {
        const data = await response.json();
        console.log('📋 Import logs fetched:', data);
        setImportLogs(data);
      } else {
        console.error('❌ Failed to fetch import logs:', response.status, response.statusText);
        const errorData = await response.json().catch(() => ({}));
        console.error('Error details:', errorData);
      }
    } catch (err) {
      console.error('❌ Failed to fetch import logs:', err);
    }
  };

  const fetchTransactions = async (page: number = 1, limit: number = pageSize, sort: string = sortBy, order: string = sortOrder, symbol: string = symbolFilter) => {
    try {
      let url = `/api/proxy/api/transactions?page=${page}&limit=${limit}&sort_by=${sort}&sort_order=${order}`;
      if (symbol) url += `&symbol=${symbol}`;
      
      console.log('📡 Fetching transactions:', url);
      const response = await fetch(url);
      
      if (response.ok) {
        const data = await response.json();
        console.log('✅ Transactions fetched:', {
          total: data.total,
          dataLength: data.data?.length || 0,
          page: data.page,
          pages: data.pages,
          firstTransaction: data.data?.[0]
        });
        console.log('📦 Full response data:', data);
        setTransactions(data);
        setCurrentPage(page);
      } else {
        const errorText = await response.text();
        console.error('❌ Failed to fetch transactions:', response.status);
        console.error('   Response text:', errorText);
        try {
          const errorData = JSON.parse(errorText);
          console.error('   Error details:', errorData);
        } catch {
          console.error('   Raw error:', errorText);
        }
      }
    } catch (err) {
      console.error('❌ Failed to fetch transactions:', err);
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

  const handleDeleteAllTransactions = async () => {
    if (!confirm('⚠️ Are you sure you want to delete ALL transactions? This action cannot be undone.')) {
      return;
    }
    
    try {
      const response = await fetch('/api/proxy/api/transactions', {
        method: 'DELETE',
      });
      
      if (response.ok) {
        const result = await response.json();
        alert(`✅ ${result.message}`);
        setSelectedTransactions(new Set()); // Clear selections
        // Force immediate refresh of all data
        await Promise.all([
          fetchHealth(),
          fetchTransactions(1, pageSize),
          fetchImportLogs()
        ]);
        // Force a second refresh after a short delay to ensure data is synced
        setTimeout(() => {
          fetchHealth();
        }, 500);
      } else {
        const error = await response.json().catch(() => ({detail: 'Delete failed'}));
        alert(`❌ Error: ${error.detail || 'Failed to delete transactions'}`);
      }
    } catch (err) {
      console.error('Delete error:', err);
      alert('❌ Failed to delete transactions');
    }
  };

  const handleDeleteSelectedTransactions = async () => {
    if (selectedTransactions.size === 0) {
      alert('⚠️ Please select at least one transaction to delete.');
      return;
    }

    if (!confirm(`⚠️ Are you sure you want to delete ${selectedTransactions.size} selected transaction(s)? This action cannot be undone.`)) {
      return;
    }

    try {
      const response = await fetch('/api/proxy/api/transactions/delete-batch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(Array.from(selectedTransactions)),
      });

      if (response.ok) {
        const result = await response.json();
        alert(`✅ ${result.message}`);
        setSelectedTransactions(new Set()); // Clear selections
        // Refresh data
        await Promise.all([
          fetchHealth(),
          fetchTransactions(currentPage, pageSize, sortBy, sortOrder, symbolFilter),
          fetchImportLogs()
        ]);
        setTimeout(() => {
          fetchHealth();
        }, 500);
      } else {
        const error = await response.json().catch(() => ({detail: 'Delete failed'}));
        alert(`❌ Error: ${error.detail || 'Failed to delete transactions'}`);
      }
    } catch (err) {
      console.error('Delete error:', err);
      alert('❌ Failed to delete transactions');
    }
  };

  const handleToggleTransaction = (transactionId: string) => {
    const newSelected = new Set(selectedTransactions);
    if (newSelected.has(transactionId)) {
      newSelected.delete(transactionId);
    } else {
      newSelected.add(transactionId);
    }
    setSelectedTransactions(newSelected);
  };

  const handleSelectAll = () => {
    if (!transactions?.data) return;
    
    if (selectedTransactions.size === transactions.data.length) {
      // Deselect all
      setSelectedTransactions(new Set());
    } else {
      // Select all
      const allIds = new Set(transactions.data.map(tx => tx.transaction_id));
      setSelectedTransactions(allIds);
    }
  };

  const handleDeleteImportLogs = async () => {
    if (!confirm('⚠️ Are you sure you want to delete ALL import history? This action cannot be undone.')) {
      return;
    }
    
    try {
      const response = await fetch('/api/proxy/api/transactions/import-logs', {
        method: 'DELETE',
      });
      
      if (response.ok) {
        const result = await response.json();
        alert(`✅ ${result.message}`);
        await fetchImportLogs();
          } else {
        const error = await response.json().catch(() => ({detail: 'Delete failed'}));
        alert(`❌ Error: ${error.detail || 'Failed to delete import logs'}`);
      }
    } catch (err) {
      console.error('Delete error:', err);
      alert('❌ Failed to delete import logs');
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('/api/proxy/api/transactions/upload', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const result = await response.json();
        setUploadResult(result);
        // Refresh all data after upload
        await Promise.all([
          fetchHealth(),
          fetchImportLogs(),
          activeTab === 'transactions' ? fetchTransactions(1, pageSize) : Promise.resolve()
        ]);
        // Force a second refresh after a short delay to ensure data is synced
        setTimeout(() => {
          fetchHealth();
        }, 500);
      } else {
        const error = await response.json().catch(() => ({message: 'Upload failed'}));
        setUploadResult({
          success: false,
          message: error.message || 'Upload failed',
          parsed: error.parsed || 0,
          inserted: error.inserted || 0,
          skipped: error.skipped || 0,
          errors: error.errors || 1,
          error_details: error.error_details || []
        });
        await fetchImportLogs(); // Refresh logs even on error
      }
    } catch (err) {
      console.error('Upload error:', err);
      setUploadResult({
        success: false,
        message: `Upload error: ${err instanceof Error ? err.message : 'Unknown error'}`,
        parsed: 0,
        inserted: 0,
        skipped: 0,
        errors: 1,
        error_details: [err instanceof Error ? err.message : 'Unknown error']
      });
      await fetchImportLogs(); // Refresh logs even on error
    } finally {
      setUploading(false);
      // Reset file input
      event.target.value = '';
    }
  };

  useEffect(() => {
    fetchHealth();
    fetchImportLogs();
    if (activeTab === 'transactions') {
    fetchTransactions();
    }
    // Refresh health every 5 seconds to keep stats updated
    const interval = setInterval(() => {
      fetchHealth();
    }, 5000);
    return () => clearInterval(interval);
  }, [activeTab]);
  
  // Fetch transactions when switching to transactions tab
  useEffect(() => {
    if (activeTab === 'transactions') {
      console.log('🔄 Tab changed to transactions, fetching...');
      fetchTransactions();
    }
  }, [activeTab]);

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
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: '0', marginBottom: '0', borderBottom: '1px solid #e5e7eb' }}>
          {(['load', 'transactions'] as TabType[]).map((tab) => (
            <button key={tab} onClick={() => {
              console.log(`🔄 Tab clicked: ${tab}`);
              setActiveTab(tab);
              if (tab === 'transactions') {
                console.log('📡 Fetching transactions on tab click...');
                fetchTransactions(1, pageSize, sortBy, sortOrder, symbolFilter);
              }
            }} style={{ padding: '12px 24px', fontSize: '14px', fontWeight: '500', border: 'none', borderBottom: activeTab === tab ? '2px solid #3b82f6' : '2px solid transparent', backgroundColor: 'transparent', color: activeTab === tab ? '#3b82f6' : '#6b7280', cursor: 'pointer' }}>
              {tab === 'load' && '📥 Load Trades'}
              {tab === 'transactions' && '📄 Transactions'}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div style={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderTop: 'none', borderRadius: '0 0 8px 8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          
          {/* Tab 1: Load Trades */}
          {activeTab === 'load' && (
            <div style={{ padding: '48px 24px' }}>
              <div style={{ textAlign: 'center', marginBottom: '32px' }}>
                <div style={{ fontSize: '48px', marginBottom: '16px' }}>📥</div>
                <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937', marginBottom: '8px' }}>Load Trades</h2>
                <p style={{ fontSize: '14px', color: '#6b7280', marginBottom: '24px' }}>Upload a CSV file to import transactions</p>
                
                <div style={{ display: 'inline-block', position: 'relative' }}>
                  <input 
                    type="file" 
                    accept=".csv"
                    onChange={handleFileUpload}
                    disabled={uploading}
                    style={{ display: 'none' }}
                    id="file-upload"
                  />
                  <label
                    htmlFor="file-upload"
                    style={{
                      display: 'inline-block',
                      padding: '12px 24px',
                      backgroundColor: uploading ? '#9ca3af' : '#3b82f6',
                      color: 'white',
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '14px',
                      fontWeight: '500',
                      cursor: uploading ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {uploading ? '⏳ Uploading...' : '📁 Choose CSV File'}
                  </label>
                </div>
              </div>

              {/* Import History */}
              <div style={{ marginTop: '32px', marginBottom: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#1f2937' }}>Import History</h3>
                  {importLogs && importLogs.logs && importLogs.logs.length > 0 && (
                  <button 
                      onClick={handleDeleteImportLogs}
                      style={{
                        padding: '8px 16px',
                        backgroundColor: '#dc2626',
                        color: 'white',
                        border: 'none',
                        borderRadius: '6px',
                        fontSize: '13px',
                        fontWeight: '500',
                        cursor: 'pointer',
                      }}
                    >
                      🗑️ Clear Import History
                  </button>
                  )}
                </div>
                {!importLogs || !importLogs.logs || importLogs.logs.length === 0 ? (
                  <div style={{ padding: '24px', textAlign: 'center', backgroundColor: '#f9fafb', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
                    <p style={{ fontSize: '14px', color: '#6b7280' }}>No import history yet.</p>
              </div>
                ) : (
                  <div style={{ border: '1px solid #e5e7eb', borderRadius: '8px', overflow: 'hidden' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                      <thead>
                        <tr style={{ backgroundColor: '#f9fafb' }}>
                          <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: '600', color: '#6b7280', borderBottom: '1px solid #e5e7eb' }}>Date/Time</th>
                          <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: '600', color: '#6b7280', borderBottom: '1px solid #e5e7eb' }}>Filename</th>
                          <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: '600', color: '#6b7280', borderBottom: '1px solid #e5e7eb' }}>Parsed</th>
                          <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: '600', color: '#6b7280', borderBottom: '1px solid #e5e7eb' }}>Inserted</th>
                          <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: '600', color: '#6b7280', borderBottom: '1px solid #e5e7eb' }}>Skipped</th>
                          <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: '600', color: '#6b7280', borderBottom: '1px solid #e5e7eb' }}>Errors</th>
                          <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: '600', color: '#6b7280', borderBottom: '1px solid #e5e7eb' }}>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {importLogs.logs.map((log) => (
                          <tr key={log.id} style={{ borderBottom: '1px solid #e5e7eb' }}>
                            <td style={{ padding: '10px 12px', color: '#1f2937' }}>
                              {new Date(log.import_date).toLocaleString('fr-FR', {
                                year: 'numeric',
                                month: '2-digit',
                                day: '2-digit',
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit'
                              })}
                            </td>
                            <td style={{ padding: '10px 12px', color: '#1f2937', fontWeight: '500' }}>{log.filename}</td>
                            <td style={{ padding: '10px 12px', textAlign: 'center', color: '#1f2937' }}>{log.parsed}</td>
                            <td style={{ padding: '10px 12px', textAlign: 'center', color: '#16a34a', fontWeight: '600' }}>{log.inserted}</td>
                            <td style={{ padding: '10px 12px', textAlign: 'center', color: '#f59e0b' }}>{log.skipped}</td>
                            <td style={{ padding: '10px 12px', textAlign: 'center', color: log.errors > 0 ? '#dc2626' : '#16a34a', fontWeight: log.errors > 0 ? '600' : '400' }}>{log.errors}</td>
                            <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                              <span style={{ 
                                padding: '4px 8px', 
                                borderRadius: '4px', 
                                fontSize: '11px', 
                                fontWeight: '600',
                                backgroundColor: log.status === 'success' ? '#dcfce7' : log.status === 'error' ? '#fef2f2' : '#fef3c7',
                                color: log.status === 'success' ? '#166534' : log.status === 'error' ? '#dc2626' : '#92400e'
                              }}>
                                {log.status === 'success' ? '✅ Success' : log.status === 'error' ? '❌ Error' : '⚠️ Partial'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Upload Results */}
              {uploadResult && (
                <div style={{
                  backgroundColor: uploadResult.success ? '#f0fdf4' : '#fef2f2',
                  border: `1px solid ${uploadResult.success ? '#86efac' : '#fecaca'}`,
                  borderRadius: '8px',
                  padding: '16px 24px',
                  marginTop: '24px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', marginBottom: '16px' }}>
                    <span style={{ fontSize: '20px', marginRight: '8px' }}>{uploadResult.success ? '✅' : '❌'}</span>
                    <span style={{ fontSize: '16px', fontWeight: '600', color: uploadResult.success ? '#166534' : '#dc2626' }}>
                      {uploadResult.message}
                    </span>
                  </div>
                  
                  {/* Stats Grid */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: uploadResult.errors > 0 ? '16px' : '0' }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Parsed</div>
                      <div style={{ fontSize: '24px', fontWeight: '600', color: '#1f2937' }}>{uploadResult.parsed}</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Inserted</div>
                      <div style={{ fontSize: '24px', fontWeight: '600', color: '#16a34a' }}>{uploadResult.inserted}</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Skipped</div>
                      <div style={{ fontSize: '24px', fontWeight: '600', color: '#f59e0b' }}>{uploadResult.skipped}</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Errors</div>
                      <div style={{ fontSize: '24px', fontWeight: '600', color: uploadResult.errors > 0 ? '#dc2626' : '#16a34a' }}>{uploadResult.errors}</div>
                    </div>
                  </div>

                  {/* Error Details */}
                  {uploadResult.errors > 0 && uploadResult.error_details && uploadResult.error_details.length > 0 && (
                    <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid #e5e7eb' }}>
                      <div style={{ fontSize: '14px', fontWeight: '600', color: '#dc2626', marginBottom: '8px' }}>
                        Error Details:
                      </div>
                      <div style={{ maxHeight: '200px', overflowY: 'auto', backgroundColor: '#fff', padding: '12px', borderRadius: '4px', fontSize: '12px', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                        {uploadResult.error_details.map((error, idx) => (
                          <div key={idx} style={{ marginBottom: '4px', color: '#dc2626' }}>
                            {error}
                          </div>
                        ))}
                      </div>
                  </div>
                )}
              </div>
              )}
            </div>
          )}

          {/* Tab 2: Transactions */}
          {activeTab === 'transactions' && (
            <div>
              <div style={{ padding: '20px 24px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937' }}>Transactions</h2>
                  {transactions && <span style={{ fontSize: '14px', color: '#6b7280' }}>{transactions.total} transactions</span>}
                  {selectedTransactions.size > 0 && (
                    <span style={{ fontSize: '14px', color: '#3b82f6', fontWeight: '500' }}>
                      {selectedTransactions.size} selected
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {selectedTransactions.size > 0 && (
                    <button
                      onClick={handleDeleteSelectedTransactions}
                      style={{
                        padding: '8px 16px',
                        backgroundColor: '#dc2626',
                        color: 'white',
                        border: 'none',
                        borderRadius: '6px',
                        fontSize: '13px',
                        fontWeight: '500',
                        cursor: 'pointer',
                      }}
                    >
                      🗑️ Delete Selected ({selectedTransactions.size})
                    </button>
                  )}
                  {transactions && transactions.total > 0 && (
                    <button
                      onClick={handleDeleteAllTransactions}
                      style={{
                        padding: '8px 16px',
                        backgroundColor: '#dc2626',
                        color: 'white',
                        border: 'none',
                        borderRadius: '6px',
                        fontSize: '13px',
                        fontWeight: '500',
                        cursor: 'pointer',
                      }}
                    >
                      🗑️ Delete All Transactions
                    </button>
                  )}
                </div>
              </div>
              {(() => {
                console.log('🔍 Render - transactions state:', {
                  transactions: transactions,
                  hasTransactions: !!transactions,
                  hasData: !!transactions?.data,
                  dataLength: transactions?.data?.length,
                  total: transactions?.total
                });
                return null;
              })()}
              {!transactions?.data?.length ? (
                <div style={{ padding: '48px 24px', textAlign: 'center' }}>
                  <div style={{ fontSize: '48px', marginBottom: '16px' }}>📄</div>
                  <h3 style={{ fontSize: '18px', fontWeight: '500', color: '#1f2937', marginBottom: '8px' }}>Aucune transaction</h3>
                  <p style={{ fontSize: '14px', color: '#6b7280' }}>Chargez des transactions depuis l'onglet "Load Trades".</p>
                  {transactions && (
                    <div style={{ marginTop: '16px', padding: '12px', backgroundColor: '#f3f4f6', borderRadius: '6px', fontSize: '12px', textAlign: 'left', maxWidth: '500px', margin: '16px auto 0' }}>
                      <p><strong>Debug Info:</strong></p>
                      <p>transactions.total = {transactions.total}</p>
                      <p>transactions.data = {transactions.data ? `Array(${transactions.data.length})` : 'null/undefined'}</p>
                      <p>transactions.page = {transactions.page}</p>
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#f9fafb' }}>
                        <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', width: '40px' }}>
                          <input
                            type="checkbox"
                            checked={transactions.data.length > 0 && selectedTransactions.size === transactions.data.length}
                            onChange={handleSelectAll}
                            style={{ cursor: 'pointer' }}
                          />
                        </th>
                        <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Transaction ID</th>
                        <th onClick={() => handleSort('trade_date')} style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Date {sortBy === 'trade_date' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th onClick={() => handleSort('symbol')} style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Symbol {sortBy === 'symbol' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Type</th>
                        <th onClick={() => handleSort('quantity')} style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Quantité {sortBy === 'quantity' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th onClick={() => handleSort('t_price')} style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Prix {sortBy === 't_price' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Proceeds</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Frais</th>
                      </tr>
                      <tr style={{ backgroundColor: '#f3f4f6' }}>
                        <th style={{ padding: '8px 16px' }}></th>
                        <th style={{ padding: '8px 16px' }}></th>
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
                        <tr key={tx.id} style={{ borderTop: '1px solid #e5e7eb' }}>
                          <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                            <input
                              type="checkbox"
                              checked={selectedTransactions.has(tx.transaction_id)}
                              onChange={() => handleToggleTransaction(tx.transaction_id)}
                              style={{ cursor: 'pointer' }}
                            />
                          </td>
                          <td style={{ padding: '12px 16px', fontSize: '12px', color: '#6b7280', fontFamily: 'monospace' }}>{tx.transaction_id}</td>
                          <td style={{ padding: '12px 16px', fontSize: '14px', color: '#1f2937' }}>{tx.trade_date}</td>
                          <td style={{ padding: '12px 16px', fontSize: '14px', fontWeight: '500', color: '#1f2937' }}>{tx.symbol}</td>
                          <td style={{ padding: '12px 16px', fontSize: '14px', textAlign: 'center' }}><span style={{ padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: '600', backgroundColor: tx.quantity >= 0 ? '#dcfce7' : '#fef2f2', color: tx.quantity >= 0 ? '#16a34a' : '#dc2626' }}>{tx.quantity >= 0 ? 'BUY' : 'SELL'}</span></td>
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
                        <button key={size} onClick={() => {
                          setPageSize(size);
                          setCurrentPage(1);
                          fetchTransactions(1, size);
                        }} style={{ padding: '6px 12px', border: '1px solid #d1d5db', borderRadius: '6px', backgroundColor: pageSize === size ? '#3b82f6' : 'white', color: pageSize === size ? 'white' : '#374151', cursor: 'pointer', fontSize: '14px' }}>{size}</button>
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
