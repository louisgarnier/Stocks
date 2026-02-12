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

interface Security {
  symbol: string;
  transaction_count: number;
  total_quantity: number;
  first_trade: string;
  last_trade: string;
  asset_category: string;
  currency: string;
}

interface SecuritiesResponse {
  data: Security[];
  total: number;
}

interface CorporateAction {
  id: number;
  sec_id: string;
  ca_type: string;
  ex_date: string;
  record_date: string | null;
  pay_date: string | null;
  declared_date: string | null;
  amount: number | null;
  currency: string | null;
  split_ratio: number | null;
  split_from: number | null;
  split_to: number | null;
  split_direction: string | null;
  dividend_type: string | null;
  frequency: string | null;
  adjusted: boolean;
  source: string;
  notes: string | null;
  created_at: string;
}

interface CorporateActionsResponse {
  data: CorporateAction[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

interface CAStatusData {
  status: 'grey' | 'green' | 'orange';
  last_fetched_at: string | null;
  has_actions: boolean;
}

interface CAStatusResponse {
  success: boolean;
  data: Record<string, CAStatusData>;
}

interface UpdatedTransaction {
  id: number;
  transaction_id: string;
  symbol: string;
  trade_date: string;
  original_quantity: number;
  original_price: number;
  updated_quantity: number;
  updated_price: number;
  split_ratio: number;
  ca_id: number | null;
  ca_type: string;
  ca_date: string;
  created_at: string;
}

interface UpdatedTransactionsResponse {
  data: UpdatedTransaction[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

interface Position {
  symbol: string;
  quantity: number;
  average_price: number;
  total_cost: number;
  transaction_count: number;
  adjusted_count: number;
  last_updated: string;
}

interface PositionsResponse {
  success: boolean;
  open_positions: Position[];
  closed_positions: Position[];
  total_symbols: number;
  open_count: number;
  closed_count: number;
  last_updated: string | null;
}

type TabType = 'load' | 'transactions' | 'updated-transactions' | 'adjusted-transactions' | 'corporate-actions' | 'positions';

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<TabType>('load');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [transactions, setTransactions] = useState<TransactionsResponse | null>(null);
  const [securities, setSecurities] = useState<SecuritiesResponse | null>(null);
  const [corporateActions, setCorporateActions] = useState<CorporateActionsResponse | null>(null);
  const [caLoading, setCaLoading] = useState(false);
  const [applySplitsLoading, setApplySplitsLoading] = useState(false);
  const [caTypeFilter, setCaTypeFilter] = useState<string>('');
  const [caSymbolFilter, setCaSymbolFilter] = useState<string>('');
  const [selectedCAs, setSelectedCAs] = useState<Set<number>>(new Set());
  const [caStatus, setCaStatus] = useState<Record<string, CAStatusData>>({});
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
  const [flexLoading, setFlexLoading] = useState(false);
  const [showFlexDropdown, setShowFlexDropdown] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [updatedTransactions, setUpdatedTransactions] = useState<UpdatedTransactionsResponse | null>(null);
  const [updatedTxPage, setUpdatedTxPage] = useState(1);
  const [updatedTxSymbolFilter, setUpdatedTxSymbolFilter] = useState<string>('');
  const [selectedUpdatedTx, setSelectedUpdatedTx] = useState<Set<number>>(new Set());
  const [positions, setPositions] = useState<PositionsResponse | null>(null);
  const [positionsLoading, setPositionsLoading] = useState(false);
  const [positionsSortBy, setPositionsSortBy] = useState<'symbol' | 'quantity' | 'average_price' | 'total_cost' | 'transaction_count'>('total_cost');
  const [positionsSortOrder, setPositionsSortOrder] = useState<'asc' | 'desc'>('desc');
  const [positionsSymbolFilter, setPositionsSymbolFilter] = useState<string>('');

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

  const fetchSecurities = async () => {
    try {
      const response = await fetch('/api/proxy/api/transactions/securities');
      if (response.ok) {
        const data = await response.json();
        setSecurities(data);
      }
    } catch (err) {
      console.error('Failed to fetch securities:', err);
    }
  };

  const fetchCAStatus = async () => {
    try {
      const response = await fetch('/api/proxy/api/corporate-actions/status');
      if (response.ok) {
        const data: CAStatusResponse = await response.json();
        if (data.success) {
          setCaStatus(data.data);
        }
      }
    } catch (err) {
      console.error('Failed to fetch CA status:', err);
    }
  };

  const fetchCorporateActions = async (typeFilter: string = caTypeFilter, symbolFilter: string = caSymbolFilter) => {
    try {
      let url = '/api/proxy/api/corporate-actions?limit=500&sort_by=ex_date&sort_order=desc';
      if (typeFilter) url += `&ca_type=${typeFilter}`;
      if (symbolFilter) url += `&symbol=${symbolFilter}`;
      
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        setCorporateActions(data);
      }
    } catch (err) {
      console.error('Failed to fetch corporate actions:', err);
    }
  };

  const handleQuickRefresh = async () => {
    setCaLoading(true);
    try {
      const response = await fetch('/api/proxy/api/corporate-actions/refresh', { method: 'POST' });
      if (response.ok) {
        await fetchCorporateActions();
        await fetchSecurities();
        await fetchCAStatus();
        await fetchUpdatedTransactions();
      } else {
        console.error('Failed to quick refresh corporate actions');
      }
    } catch (err) {
      console.error('Error quick refreshing corporate actions:', err);
    } finally {
      setCaLoading(false);
    }
  };

  const handleFetchCorporateActions = async () => {
    setCaLoading(true);
    try {
      const response = await fetch('/api/proxy/api/corporate-actions/fetch', { method: 'POST' });
      if (response.ok) {
        await fetchCorporateActions();
        await fetchSecurities();
        await fetchCAStatus();
        await fetchUpdatedTransactions();
      } else {
        console.error('Failed to fetch corporate actions from yfinance');
      }
    } catch (err) {
      console.error('Error fetching corporate actions:', err);
    } finally {
      setCaLoading(false);
    }
  };

  const handleDeleteCorporateActions = async () => {
    if (!confirm('Supprimer toutes les corporate actions ?')) return;
    
    try {
      const response = await fetch('/api/proxy/api/corporate-actions', { method: 'DELETE' });
      if (response.ok) {
        setCorporateActions(null);
        setSelectedCAs(new Set());
      }
    } catch (err) {
      console.error('Error deleting corporate actions:', err);
    }
  };

  const handleToggleCA = (id: number) => {
    setSelectedCAs(prev => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  };

  const handleSelectAllCAs = () => {
    if (!corporateActions) return;
    if (selectedCAs.size === corporateActions.data.length) {
      setSelectedCAs(new Set());
    } else {
      setSelectedCAs(new Set(corporateActions.data.map(ca => ca.id)));
    }
  };

  const handleDeleteSelectedCAs = async () => {
    if (selectedCAs.size === 0) return;
    if (!confirm(`Supprimer ${selectedCAs.size} corporate action(s) sélectionnée(s) ?`)) return;
    
    try {
      const response = await fetch('/api/proxy/api/corporate-actions/batch-delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: Array.from(selectedCAs) })
      });
      if (response.ok) {
        setSelectedCAs(new Set());
        await fetchCorporateActions();
      }
    } catch (err) {
      console.error('Error deleting selected CAs:', err);
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

  const fetchUpdatedTransactions = async (page: number = 1, symbol: string = updatedTxSymbolFilter) => {
    try {
      let url = `/api/proxy/api/updated-transactions?page=${page}&limit=${pageSize}&sort_by=trade_date&sort_order=desc`;
      if (symbol) url += `&symbol=${symbol}`;
      
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        setUpdatedTransactions(data);
        setUpdatedTxPage(page);
      }
    } catch (err) {
      console.error('❌ Failed to fetch updated transactions:', err);
    }
  };

  const fetchPositions = async () => {
    try {
      const response = await fetch('/api/proxy/api/positions');
      if (response.ok) {
        const data = await response.json();
        setPositions(data);
      }
    } catch (err) {
      console.error('❌ Failed to fetch positions:', err);
    }
  };

  const refreshPositions = async () => {
    setPositionsLoading(true);
    try {
      const response = await fetch('/api/proxy/api/positions/refresh', { method: 'POST' });
      if (response.ok) {
        await fetchPositions();
      }
    } catch (err) {
      console.error('❌ Failed to refresh positions:', err);
    } finally {
      setPositionsLoading(false);
    }
  };

  const handlePositionsSort = (column: 'symbol' | 'quantity' | 'average_price' | 'total_cost' | 'transaction_count') => {
    const newOrder = positionsSortBy === column && positionsSortOrder === 'desc' ? 'asc' : 'desc';
    setPositionsSortBy(column);
    setPositionsSortOrder(newOrder);
  };

  const getSortedAndFilteredPositions = () => {
    if (!positions?.open_positions) return [];
    
    let filtered = positions.open_positions;
    
    // Apply symbol filter
    if (positionsSymbolFilter) {
      filtered = filtered.filter(pos => 
        pos.symbol.toLowerCase().includes(positionsSymbolFilter.toLowerCase())
      );
    }
    
    // Apply sorting
    return [...filtered].sort((a, b) => {
      let aVal: number | string = a[positionsSortBy];
      let bVal: number | string = b[positionsSortBy];
      
      if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase();
        bVal = (bVal as string).toLowerCase();
      }
      
      if (aVal < bVal) return positionsSortOrder === 'asc' ? -1 : 1;
      if (aVal > bVal) return positionsSortOrder === 'asc' ? 1 : -1;
      return 0;
    });
  };

  const handleUpdatedTxSymbolFilter = (symbol: string) => {
    setUpdatedTxSymbolFilter(symbol);
    setUpdatedTxPage(1);
    fetchUpdatedTransactions(1, symbol);
  };

  const handleToggleUpdatedTx = (id: number) => {
    const newSelected = new Set(selectedUpdatedTx);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedUpdatedTx(newSelected);
  };

  const handleSelectAllUpdatedTx = () => {
    if (!updatedTransactions?.data) return;
    
    if (selectedUpdatedTx.size === updatedTransactions.data.length) {
      setSelectedUpdatedTx(new Set());
    } else {
      const allIds = new Set(updatedTransactions.data.map(utx => utx.id));
      setSelectedUpdatedTx(allIds);
    }
  };

  const handleDeleteSelectedUpdatedTx = async () => {
    if (selectedUpdatedTx.size === 0) {
      alert('⚠️ Please select at least one updated transaction to delete.');
      return;
    }

    if (!confirm(`⚠️ Are you sure you want to delete ${selectedUpdatedTx.size} selected updated transaction(s)?`)) {
      return;
    }

    try {
      const response = await fetch('/api/proxy/api/updated-transactions/delete-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Array.from(selectedUpdatedTx)),
      });

      if (response.ok) {
        const result = await response.json();
        alert(`✅ ${result.message}`);
        setSelectedUpdatedTx(new Set());
        setUpdatedTxPage(1);
        await fetchUpdatedTransactions(1, updatedTxSymbolFilter);
      } else {
        const error = await response.json().catch(() => ({detail: 'Delete failed'}));
        alert(`❌ Error: ${error.detail || 'Failed to delete updated transactions'}`);
      }
    } catch (err) {
      console.error('Delete error:', err);
      alert('❌ Failed to delete updated transactions');
    }
  };

  const handleDeleteAllUpdatedTx = async () => {
    if (!confirm('⚠️ Are you sure you want to delete ALL updated transactions?')) {
      return;
    }

    try {
      const response = await fetch('/api/proxy/api/updated-transactions', {
        method: 'DELETE',
      });

      if (response.ok) {
        const result = await response.json();
        alert(`✅ ${result.message}`);
        setSelectedUpdatedTx(new Set());
        await fetchUpdatedTransactions(1, updatedTxSymbolFilter);
      } else {
        const error = await response.json().catch(() => ({detail: 'Delete failed'}));
        alert(`❌ Error: ${error.detail || 'Failed to delete updated transactions'}`);
      }
    } catch (err) {
      console.error('Delete error:', err);
      alert('❌ Failed to delete updated transactions');
    }
  };

  const handleApplySplits = async () => {
    setApplySplitsLoading(true);
    try {
      const response = await fetch('/api/proxy/api/transactions/apply-splits', { method: 'POST' });
      if (response.ok) {
        const data = await response.json();
        alert(`✅ ${data.message}`);
        await fetchUpdatedTransactions(1, updatedTxSymbolFilter);
        // Auto-refresh positions after applying splits
        await fetch('/api/proxy/api/positions/refresh', { method: 'POST' });
      } else {
        const error = await response.json().catch(() => ({ detail: 'Apply splits failed' }));
        alert(`❌ Error: ${error.detail || 'Failed to apply splits'}`);
      }
    } catch (err) {
      console.error('Apply splits error:', err);
      alert('❌ Failed to apply splits');
    } finally {
      setApplySplitsLoading(false);
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
        setCurrentPage(1); // Reset to page 1 after deletion
        // Force immediate refresh of all data (including securities / CAs)
        await Promise.all([
          fetchHealth(),
          fetchTransactions(1, pageSize),
          fetchImportLogs(),
          fetchSecurities(),
          fetchCAStatus(),
          activeTab === 'corporate-actions' ? fetchCorporateActions() : Promise.resolve()
        ]);
        // Force a second refresh after a short delay to ensure data is synced
        setTimeout(() => {
          fetchHealth();
          fetchSecurities();
          fetchCAStatus();
          if (activeTab === 'corporate-actions') {
            fetchCorporateActions();
          }
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
        setCurrentPage(1); // Reset to page 1 after deletion
        // Refresh data
        await Promise.all([
          fetchHealth(),
          fetchTransactions(1, pageSize, sortBy, sortOrder, symbolFilter),
          fetchImportLogs(),
          fetchSecurities(),
          fetchCAStatus()
        ]);
        setTimeout(() => {
          fetchHealth();
          fetchSecurities();
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

  const handleExportCSV = async () => {
    setExporting(true);
    try {
      const response = await fetch('/api/proxy/api/transactions/export');
      
      if (response.ok) {
        // Get the filename from the response headers
        const contentDisposition = response.headers.get('Content-Disposition');
        const filenameMatch = contentDisposition?.match(/filename=(.+)/);
        const filename = filenameMatch ? filenameMatch[1] : 'transactions_export.csv';
        
        // Download the file
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        alert('❌ Failed to export transactions');
      }
    } catch (err) {
      console.error('Export error:', err);
      alert('❌ Failed to export transactions');
    } finally {
      setExporting(false);
    }
  };

  const handleFlexImport = async (queryType: 'last_year' | 'last_month') => {
    setFlexLoading(true);
    setShowFlexDropdown(false);
    
    try {
      const response = await fetch(`/api/proxy/api/transactions/flex-import?query_type=${queryType}`, {
        method: 'POST',
      });

      if (response.ok) {
        const result = await response.json();
        setUploadResult({
          success: true,
          message: result.message,
          parsed: result.fetched,
          inserted: result.inserted,
          skipped: result.skipped,
          errors: result.errors,
        });
        // Refresh all data including positions
        await Promise.all([
          fetchHealth(),
          fetchImportLogs(),
          fetchCAStatus(),
          activeTab === 'transactions' ? fetchTransactions(1, pageSize) : Promise.resolve(),
          fetch('/api/proxy/api/positions/refresh', { method: 'POST' })
        ]);
        setTimeout(() => fetchHealth(), 500);
      } else {
        const error = await response.json().catch(() => ({ detail: 'Flex import failed' }));
        setUploadResult({
          success: false,
          message: error.detail || 'Flex import failed',
          parsed: 0,
          inserted: 0,
          skipped: 0,
          errors: 1,
          error_details: [error.detail || 'Unknown error']
        });
        await fetchImportLogs();
      }
    } catch (err) {
      console.error('Flex import error:', err);
      setUploadResult({
        success: false,
        message: `Flex import error: ${err instanceof Error ? err.message : 'Unknown error'}`,
        parsed: 0,
        inserted: 0,
        skipped: 0,
        errors: 1,
        error_details: [err instanceof Error ? err.message : 'Unknown error']
      });
      await fetchImportLogs();
    } finally {
      setFlexLoading(false);
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
        // Refresh all data after upload including positions
        await Promise.all([
          fetchHealth(),
          fetchImportLogs(),
          fetchCAStatus(),
          activeTab === 'transactions' ? fetchTransactions(1, pageSize) : Promise.resolve(),
          fetch('/api/proxy/api/positions/refresh', { method: 'POST' })
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
    fetchCAStatus();
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
          {(['load', 'transactions', 'updated-transactions', 'corporate-actions', 'positions'] as TabType[]).map((tab) => (
            <button key={tab} onClick={() => {
              console.log(`🔄 Tab clicked: ${tab}`);
              setActiveTab(tab);
              if (tab === 'transactions') {
                console.log('📡 Fetching transactions on tab click...');
                fetchTransactions(1, pageSize, sortBy, sortOrder, symbolFilter);
              }
              if (tab === 'updated-transactions') {
                console.log('📡 Fetching updated transactions on tab click...');
                fetchUpdatedTransactions();
              }
              if (tab === 'corporate-actions') {
                console.log('📡 Fetching securities and corporate actions on tab click...');
                fetchSecurities();
                fetchCorporateActions();
              }
              if (tab === 'positions') {
                console.log('📡 Fetching positions on tab click...');
                fetchPositions();
              }
            }} style={{ padding: '12px 24px', fontSize: '14px', fontWeight: '500', border: 'none', borderBottom: activeTab === tab ? '2px solid #3b82f6' : '2px solid transparent', backgroundColor: 'transparent', color: activeTab === tab ? '#3b82f6' : '#6b7280', cursor: 'pointer' }}>
              {tab === 'load' && '📥 Load Trades'}
              {tab === 'transactions' && '📄 Transactions'}
              {tab === 'updated-transactions' && '🔄 Updated Transactions'}
              {tab === 'corporate-actions' && '🏢 Corporate Actions'}
              {tab === 'positions' && '📊 Positions'}
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
                
                <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', alignItems: 'center' }}>
                  {/* CSV Upload Button */}
                  <div style={{ position: 'relative' }}>
                    <input 
                      type="file" 
                      accept=".csv"
                      onChange={handleFileUpload}
                      disabled={uploading || flexLoading}
                      style={{ display: 'none' }}
                      id="file-upload"
                    />
                    <label
                      htmlFor="file-upload"
                      style={{
                        display: 'inline-block',
                        padding: '12px 24px',
                        backgroundColor: uploading || flexLoading ? '#9ca3af' : '#3b82f6',
                        color: 'white',
                        border: 'none',
                        borderRadius: '8px',
                        fontSize: '14px',
                        fontWeight: '500',
                        cursor: uploading || flexLoading ? 'not-allowed' : 'pointer',
                      }}
                    >
                      {uploading ? '⏳ Uploading...' : '📁 Choose CSV File'}
                    </label>
                  </div>

                  {/* Flex Queries Dropdown Button */}
                  <div style={{ position: 'relative' }}>
                    <button
                      onClick={() => setShowFlexDropdown(!showFlexDropdown)}
                      disabled={flexLoading || uploading}
                      style={{
                        padding: '12px 24px',
                        backgroundColor: flexLoading || uploading ? '#9ca3af' : '#059669',
                        color: 'white',
                        border: 'none',
                        borderRadius: '8px',
                        fontSize: '14px',
                        fontWeight: '500',
                        cursor: flexLoading || uploading ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                      }}
                    >
                      {flexLoading ? '⏳ Loading...' : '📡 Flex Queries'}
                      <span style={{ fontSize: '10px' }}>▼</span>
                    </button>
                    
                    {showFlexDropdown && (
                      <div style={{
                        position: 'absolute',
                        top: '100%',
                        left: '0',
                        marginTop: '4px',
                        backgroundColor: 'white',
                        border: '1px solid #e5e7eb',
                        borderRadius: '8px',
                        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                        overflow: 'hidden',
                        zIndex: 10,
                        minWidth: '160px',
                      }}>
                        <button
                          onClick={() => handleFlexImport('last_year')}
                          style={{
                            display: 'block',
                            width: '100%',
                            padding: '12px 16px',
                            backgroundColor: 'white',
                            border: 'none',
                            textAlign: 'left',
                            fontSize: '14px',
                            cursor: 'pointer',
                            color: '#1f2937',
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f3f4f6'}
                          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'white'}
                        >
                          📅 Last Year
                        </button>
                        <button
                          onClick={() => handleFlexImport('last_month')}
                          style={{
                            display: 'block',
                            width: '100%',
                            padding: '12px 16px',
                            backgroundColor: 'white',
                            border: 'none',
                            borderTop: '1px solid #e5e7eb',
                            textAlign: 'left',
                            fontSize: '14px',
                            cursor: 'pointer',
                            color: '#1f2937',
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f3f4f6'}
                          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'white'}
                        >
                          📆 Last Month
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Export CSV Button */}
                  <button
                    onClick={handleExportCSV}
                    disabled={exporting || uploading || flexLoading}
                    style={{
                      padding: '12px 24px',
                      backgroundColor: exporting || uploading || flexLoading ? '#9ca3af' : '#7c3aed',
                      color: 'white',
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '14px',
                      fontWeight: '500',
                      cursor: exporting || uploading || flexLoading ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {exporting ? '⏳ Exporting...' : '📤 Export CSV'}
                  </button>
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
                  {symbolFilter && (
                    <button
                      onClick={() => handleSymbolFilter('')}
                      style={{
                        padding: '4px 12px',
                        backgroundColor: '#fef3c7',
                        border: '1px solid #fcd34d',
                        borderRadius: '4px',
                        fontSize: '12px',
                        color: '#92400e',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}
                    >
                      Filter: {symbolFilter} ✕
                    </button>
                  )}
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
                        <th style={{ padding: '8px 16px', display: 'flex', gap: '4px' }}><input type="text" placeholder="Filtrer..." value={symbolFilter} onChange={(e) => handleSymbolFilter(e.target.value.toUpperCase())} style={{ flex: 1, padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '12px' }} />{symbolFilter && <button onClick={() => handleSymbolFilter('')} style={{ padding: '4px 8px', backgroundColor: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '12px', cursor: 'pointer' }} title="Reset filter">✕</button>}</th>
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

          {/* Tab 3: Updated Transactions */}
          {activeTab === 'updated-transactions' && (
            <div>
              <div style={{ padding: '20px 24px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937' }}>Updated Transactions</h2>
                  {updatedTransactions && <span style={{ fontSize: '14px', color: '#6b7280' }}>{updatedTransactions.total} updated transactions</span>}
                  {updatedTxSymbolFilter && (
                    <button
                      onClick={() => handleUpdatedTxSymbolFilter('')}
                      style={{
                        padding: '4px 12px',
                        backgroundColor: '#fef3c7',
                        border: '1px solid #fcd34d',
                        borderRadius: '4px',
                        fontSize: '12px',
                        color: '#92400e',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}
                    >
                      Filter: {updatedTxSymbolFilter} ✕
                    </button>
                  )}
                  {selectedUpdatedTx.size > 0 && (
                    <span style={{ fontSize: '14px', color: '#3b82f6', fontWeight: '500' }}>
                      {selectedUpdatedTx.size} selected
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={handleApplySplits}
                    disabled={applySplitsLoading}
                    style={{
                      padding: '8px 16px',
                      backgroundColor: applySplitsLoading ? '#9ca3af' : '#10b981',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      fontSize: '13px',
                      fontWeight: '500',
                      cursor: applySplitsLoading ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {applySplitsLoading ? '⏳ Applying...' : '🔄 Apply Splits'}
                  </button>
                  {selectedUpdatedTx.size > 0 && (
                    <button
                      onClick={handleDeleteSelectedUpdatedTx}
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
                      🗑️ Delete Selected ({selectedUpdatedTx.size})
                    </button>
                  )}
                  {updatedTransactions && updatedTransactions.total > 0 && (
                    <button
                      onClick={handleDeleteAllUpdatedTx}
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
                      🗑️ Delete All
                    </button>
                  )}
                </div>
              </div>
              {updatedTransactions && updatedTransactions.data.length > 0 ? (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                        <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', width: '40px' }}>
                          <input
                            type="checkbox"
                            checked={updatedTransactions.data.length > 0 && selectedUpdatedTx.size === updatedTransactions.data.length}
                            onChange={handleSelectAllUpdatedTx}
                            style={{ cursor: 'pointer' }}
                          />
                        </th>
                        <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Symbol</th>
                        <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Date</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Original Qty</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Original Price</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Updated Qty</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Updated Price</th>
                        <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Split Ratio</th>
                        <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>CA Type</th>
                      </tr>
                      <tr style={{ backgroundColor: '#f3f4f6' }}>
                        <th style={{ padding: '8px 16px' }}></th>
                        <th style={{ padding: '8px 16px', display: 'flex', gap: '4px' }}>
                          <input 
                            type="text" 
                            placeholder="Filter..." 
                            value={updatedTxSymbolFilter} 
                            onChange={(e) => handleUpdatedTxSymbolFilter(e.target.value.toUpperCase())} 
                            style={{ flex: 1, padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '12px' }} 
                          />
                          {updatedTxSymbolFilter && (
                            <button 
                              onClick={() => handleUpdatedTxSymbolFilter('')} 
                              style={{ padding: '4px 8px', backgroundColor: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '12px', cursor: 'pointer' }} 
                              title="Reset filter"
                            >
                              ✕
                            </button>
                          )}
                        </th>
                        <th style={{ padding: '8px 16px' }}></th>
                        <th style={{ padding: '8px 16px' }}></th>
                        <th style={{ padding: '8px 16px' }}></th>
                        <th style={{ padding: '8px 16px' }}></th>
                        <th style={{ padding: '8px 16px' }}></th>
                        <th style={{ padding: '8px 16px' }}></th>
                        <th style={{ padding: '8px 16px' }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {updatedTransactions.data.map((utx) => (
                        <tr key={utx.id} style={{ borderTop: '1px solid #e5e7eb' }}>
                          <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                            <input
                              type="checkbox"
                              checked={selectedUpdatedTx.has(utx.id)}
                              onChange={() => handleToggleUpdatedTx(utx.id)}
                              style={{ cursor: 'pointer' }}
                            />
                          </td>
                          <td style={{ padding: '12px 16px', fontSize: '14px', fontWeight: '500', color: '#1f2937' }}>{utx.symbol}</td>
                          <td style={{ padding: '12px 16px', fontSize: '14px', color: '#1f2937' }}>{utx.trade_date}</td>
                          <td style={{ padding: '12px 16px', textAlign: 'right', fontSize: '14px', color: '#6b7280' }}>{utx.original_quantity.toFixed(2)}</td>
                          <td style={{ padding: '12px 16px', textAlign: 'right', fontSize: '14px', color: '#6b7280' }}>${utx.original_price.toFixed(2)}</td>
                          <td style={{ padding: '12px 16px', textAlign: 'right', fontSize: '14px', fontWeight: '500', color: '#059669' }}>{utx.updated_quantity.toFixed(2)}</td>
                          <td style={{ padding: '12px 16px', textAlign: 'right', fontSize: '14px', fontWeight: '500', color: '#059669' }}>${utx.updated_price.toFixed(2)}</td>
                          <td style={{ padding: '12px 16px', textAlign: 'center', fontSize: '14px', color: '#1f2937' }}>{utx.split_ratio.toFixed(2)}</td>
                          <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                            <span style={{ 
                              padding: '4px 8px', 
                              borderRadius: '4px', 
                              fontSize: '12px', 
                              fontWeight: '500',
                              backgroundColor: utx.ca_type === 'split' ? '#dbeafe' : '#fef3c7',
                              color: utx.ca_type === 'split' ? '#1e40af' : '#92400e'
                            }}>
                              {utx.ca_type}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 24px', borderTop: '1px solid #e5e7eb' }}>
                    <div style={{ fontSize: '14px', color: '#6b7280' }}>
                      Showing {((updatedTxPage - 1) * pageSize) + 1} to {Math.min(updatedTxPage * pageSize, updatedTransactions.total)} of {updatedTransactions.total}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <button onClick={() => fetchUpdatedTransactions(updatedTxPage - 1)} disabled={updatedTxPage === 1} style={{ padding: '8px 16px', border: '1px solid #d1d5db', borderRadius: '6px', backgroundColor: updatedTxPage === 1 ? '#f3f4f6' : 'white', color: updatedTxPage === 1 ? '#9ca3af' : '#374151', cursor: updatedTxPage === 1 ? 'not-allowed' : 'pointer', fontSize: '14px' }}>← Précédent</button>
                      <span style={{ padding: '8px 16px', fontSize: '14px', color: '#6b7280' }}>Page {updatedTxPage} / {updatedTransactions.pages}</span>
                      <button onClick={() => fetchUpdatedTransactions(updatedTxPage + 1)} disabled={updatedTxPage === updatedTransactions.pages} style={{ padding: '8px 16px', border: '1px solid #d1d5db', borderRadius: '6px', backgroundColor: updatedTxPage === updatedTransactions.pages ? '#f3f4f6' : 'white', color: updatedTxPage === updatedTransactions.pages ? '#9ca3af' : '#374151', cursor: updatedTxPage === updatedTransactions.pages ? 'not-allowed' : 'pointer', fontSize: '14px' }}>Suivant →</button>
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ padding: '48px 24px', textAlign: 'center' }}>
                  <div style={{ fontSize: '48px', marginBottom: '16px' }}>🔄</div>
                  <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937', marginBottom: '8px' }}>No Updated Transactions</h3>
                  <p style={{ fontSize: '14px', color: '#6b7280' }}>
                    Fetch Corporate Actions to apply splits and create updated transactions.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Tab 4: Corporate Actions */}
          {activeTab === 'corporate-actions' && (
            <div style={{ padding: '24px' }}>
              {/* Securities Summary Card */}
              <div style={{ 
                backgroundColor: 'white', 
                borderRadius: '12px', 
                border: '1px solid #e5e7eb',
                padding: '24px',
                marginBottom: '24px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
                  <div>
                    <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#1f2937', margin: 0 }}>
                      📊 Securities in Database
                    </h2>
                    <p style={{ fontSize: '14px', color: '#6b7280', marginTop: '4px' }}>
                      {securities?.total || 0} securities tracked
                    </p>
                  </div>
                  <div style={{ 
                    backgroundColor: '#3b82f6', 
                    color: 'white', 
                    padding: '8px 16px', 
                    borderRadius: '8px',
                    fontSize: '24px',
                    fontWeight: '700'
                  }}>
                    {securities?.total || 0}
                  </div>
                </div>
                
                {/* Securities Grid */}
                {securities && securities.data.length > 0 ? (
                  <div style={{ 
                    display: 'flex', 
                    flexWrap: 'wrap',
                    gap: '8px'
                  }}>
                    {securities.data.map((security) => {
                      const status = caStatus[security.symbol]?.status || 'grey';
                      const statusColors = {
                        grey: { bg: '#f9fafb', border: '#e5e7eb', hoverBg: '#f3f4f6', hoverBorder: '#d1d5db', text: '#1f2937', subtext: '#9ca3af' },
                        green: { bg: '#dcfce7', border: '#86efac', hoverBg: '#bbf7d0', hoverBorder: '#22c55e', text: '#166534', subtext: '#16a34a' },
                        orange: { bg: '#ffedd5', border: '#fdba74', hoverBg: '#fed7aa', hoverBorder: '#f97316', text: '#9a3412', subtext: '#ea580c' }
                      };
                      const colors = statusColors[status];
                      return (
                      <div 
                        key={security.symbol}
                        style={{ 
                          backgroundColor: colors.bg,
                          border: `1px solid ${colors.border}`,
                          borderRadius: '6px',
                          padding: '6px 10px',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = colors.hoverBg;
                          e.currentTarget.style.borderColor = colors.hoverBorder;
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = colors.bg;
                          e.currentTarget.style.borderColor = colors.border;
                        }}
                      >
                        <span style={{ 
                          fontSize: '13px', 
                          fontWeight: '600', 
                          color: colors.text
                        }}>
                          {security.symbol}
                        </span>
                        <span style={{ 
                          fontSize: '11px', 
                          color: colors.subtext
                        }}>
                          {security.transaction_count}
                        </span>
                      </div>
                    );})}
                  </div>
                ) : (
                  <div style={{ 
                    textAlign: 'center', 
                    padding: '32px',
                    color: '#9ca3af'
                  }}>
                    <div style={{ fontSize: '32px', marginBottom: '8px' }}>📭</div>
                    <p>Aucune security en base de données.</p>
                    <p style={{ fontSize: '12px' }}>Chargez des transactions depuis l&apos;onglet &quot;Load Trades&quot;.</p>
                  </div>
                )}
              </div>
              
              {/* Corporate Actions List */}
              <div style={{ 
                backgroundColor: 'white', 
                borderRadius: '12px',
                border: '1px solid #e5e7eb',
                padding: '24px',
                marginTop: '24px'
              }}>
                {/* Header with actions */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                  <div>
                    <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937', margin: 0 }}>
                      📋 Corporate Actions
                    </h2>
                    <p style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>
                      {corporateActions?.total || 0} actions (dividendes, splits...)
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      onClick={handleQuickRefresh}
                      disabled={caLoading}
                      style={{
                        padding: '8px 16px',
                        backgroundColor: caLoading ? '#9ca3af' : '#10b981',
                        color: 'white',
                        border: 'none',
                        borderRadius: '6px',
                        fontSize: '13px',
                        fontWeight: '500',
                        cursor: caLoading ? 'not-allowed' : 'pointer'
                      }}
                    >
                      {caLoading ? '⏳ Refreshing...' : '⚡ Quick Refresh'}
                    </button>
                    <button
                      onClick={handleFetchCorporateActions}
                      disabled={caLoading}
                      style={{
                        padding: '8px 16px',
                        backgroundColor: caLoading ? '#9ca3af' : '#3b82f6',
                        color: 'white',
                        border: 'none',
                        borderRadius: '6px',
                        fontSize: '13px',
                        fontWeight: '500',
                        cursor: caLoading ? 'not-allowed' : 'pointer'
                      }}
                    >
                      {caLoading ? '⏳ Fetching...' : '🔄 Fetch from yfinance'}
                    </button>
                    {selectedCAs.size > 0 && (
                      <button
                        onClick={handleDeleteSelectedCAs}
                        style={{
                          padding: '8px 16px',
                          backgroundColor: '#fee2e2',
                          color: '#dc2626',
                          border: '1px solid #fecaca',
                          borderRadius: '6px',
                          fontSize: '13px',
                          fontWeight: '500',
                          cursor: 'pointer'
                        }}
                      >
                        🗑️ Delete ({selectedCAs.size})
                      </button>
                    )}
                    <button
                      onClick={handleDeleteCorporateActions}
                      disabled={caLoading || !corporateActions?.total}
                      style={{
                        padding: '8px 16px',
                        backgroundColor: (caLoading || !corporateActions?.total) ? '#f3f4f6' : '#fee2e2',
                        color: (caLoading || !corporateActions?.total) ? '#9ca3af' : '#dc2626',
                        border: '1px solid #e5e7eb',
                        borderRadius: '6px',
                        fontSize: '13px',
                        fontWeight: '500',
                        cursor: (caLoading || !corporateActions?.total) ? 'not-allowed' : 'pointer'
                      }}
                    >
                      🗑️ Delete All
                    </button>
                  </div>
                </div>

                {/* Filters */}
                <div style={{ display: 'flex', gap: '12px', marginBottom: '16px' }}>
                  <select
                    value={caTypeFilter}
                    onChange={(e) => {
                      setCaTypeFilter(e.target.value);
                      fetchCorporateActions(e.target.value, caSymbolFilter);
                    }}
                    style={{
                      padding: '8px 12px',
                      border: '1px solid #d1d5db',
                      borderRadius: '6px',
                      fontSize: '13px',
                      backgroundColor: 'white'
                    }}
                  >
                    <option value="">Tous les types</option>
                    <option value="dividend">Dividendes</option>
                    <option value="split">Splits</option>
                    <option value="capital_gain">Capital Gains</option>
                  </select>
                  <input
                    type="text"
                    placeholder="Filtrer par symbol..."
                    value={caSymbolFilter}
                    onChange={(e) => {
                      setCaSymbolFilter(e.target.value.toUpperCase());
                      fetchCorporateActions(caTypeFilter, e.target.value.toUpperCase());
                    }}
                    style={{
                      padding: '8px 12px',
                      border: '1px solid #d1d5db',
                      borderRadius: '6px',
                      fontSize: '13px',
                      width: '150px'
                    }}
                  />
                </div>

                {/* Corporate Actions Table */}
                {corporateActions && corporateActions.data.length > 0 ? (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ backgroundColor: '#f9fafb' }}>
                          <th style={{ padding: '10px 12px', textAlign: 'center', width: '40px' }}>
                            <input
                              type="checkbox"
                              checked={corporateActions ? selectedCAs.size === corporateActions.data.length && corporateActions.data.length > 0 : false}
                              onChange={handleSelectAllCAs}
                              style={{ cursor: 'pointer' }}
                            />
                          </th>
                          <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Symbol</th>
                          <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Type</th>
                          <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Ex-Date</th>
                          <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Amount/Ratio</th>
                          <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Details</th>
                        </tr>
                      </thead>
                      <tbody>
                        {corporateActions.data.map((ca) => (
                          <tr key={ca.id} style={{ borderTop: '1px solid #e5e7eb', backgroundColor: selectedCAs.has(ca.id) ? '#eff6ff' : 'transparent' }}>
                            <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                              <input
                                type="checkbox"
                                checked={selectedCAs.has(ca.id)}
                                onChange={() => handleToggleCA(ca.id)}
                                style={{ cursor: 'pointer' }}
                              />
                            </td>
                            <td style={{ padding: '10px 12px', fontSize: '13px', fontWeight: '500', color: '#1f2937' }}>{ca.sec_id}</td>
                            <td style={{ padding: '10px 12px' }}>
                              <span style={{
                                padding: '3px 8px',
                                borderRadius: '4px',
                                fontSize: '11px',
                                fontWeight: '600',
                                backgroundColor: ca.ca_type === 'dividend' ? '#dcfce7' : ca.ca_type === 'split' ? '#fef3c7' : '#e0e7ff',
                                color: ca.ca_type === 'dividend' ? '#16a34a' : ca.ca_type === 'split' ? '#d97706' : '#4338ca'
                              }}>
                                {ca.ca_type === 'dividend' ? '💰 Dividend' : ca.ca_type === 'split' ? '📊 Split' : '📈 ' + ca.ca_type}
                              </span>
                            </td>
                            <td style={{ padding: '10px 12px', fontSize: '13px', color: '#1f2937' }}>{ca.ex_date}</td>
                            <td style={{ padding: '10px 12px', fontSize: '13px', color: '#1f2937', textAlign: 'right' }}>
                              {ca.ca_type === 'dividend' && ca.amount !== null ? `$${ca.amount.toFixed(4)}` : ''}
                              {ca.ca_type === 'split' && ca.split_ratio !== null ? `${ca.split_to}:${ca.split_from}` : ''}
                            </td>
                            <td style={{ padding: '10px 12px', fontSize: '12px', color: '#6b7280' }}>
                              {ca.ca_type === 'split' && ca.split_direction && (
                                <span style={{
                                  padding: '2px 6px',
                                  borderRadius: '3px',
                                  fontSize: '10px',
                                  fontWeight: '500',
                                  backgroundColor: ca.split_direction === 'forward' ? '#dcfce7' : '#fee2e2',
                                  color: ca.split_direction === 'forward' ? '#16a34a' : '#dc2626'
                                }}>
                                  {ca.split_direction === 'forward' ? '↗ Forward' : '↘ Reverse'}
                                </span>
                              )}
                              {ca.ca_type === 'dividend' && ca.currency && ` ${ca.currency}`}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '32px', color: '#9ca3af' }}>
                    <div style={{ fontSize: '32px', marginBottom: '8px' }}>📭</div>
                    <p>Aucune corporate action en base.</p>
                    <p style={{ fontSize: '12px' }}>Cliquez sur &quot;Fetch from yfinance&quot; pour récupérer les données.</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tab 5: Positions */}
          {activeTab === 'positions' && (
            <div style={{ padding: '24px' }}>
              {/* Header with Refresh Button */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937', marginBottom: '4px' }}>📊 Portfolio Positions</h3>
                  {positions?.last_updated && (
                    <p style={{ fontSize: '12px', color: '#9ca3af' }}>
                      Dernière mise à jour: {new Date(positions.last_updated).toLocaleString()}
                    </p>
                  )}
                </div>
                <button
                  onClick={refreshPositions}
                  disabled={positionsLoading}
                  style={{
                    padding: '10px 20px',
                    backgroundColor: positionsLoading ? '#9ca3af' : '#10b981',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    fontSize: '14px',
                    fontWeight: '500',
                    cursor: positionsLoading ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}
                >
                  {positionsLoading ? '⏳ Calcul...' : '🔄 Refresh Positions'}
                </button>
              </div>

              {/* Summary Cards */}
              {positions && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
                  <div style={{ backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '16px' }}>
                    <p style={{ fontSize: '12px', color: '#16a34a', fontWeight: '500' }}>Positions Ouvertes</p>
                    <p style={{ fontSize: '24px', fontWeight: '600', color: '#15803d' }}>{positions.open_count}</p>
                  </div>
                  <div style={{ backgroundColor: '#f5f5f5', border: '1px solid #e5e5e5', borderRadius: '8px', padding: '16px' }}>
                    <p style={{ fontSize: '12px', color: '#737373', fontWeight: '500' }}>Positions Fermées</p>
                    <p style={{ fontSize: '24px', fontWeight: '600', color: '#525252' }}>{positions.closed_count}</p>
                  </div>
                  <div style={{ backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '8px', padding: '16px' }}>
                    <p style={{ fontSize: '12px', color: '#2563eb', fontWeight: '500' }}>Total Symboles</p>
                    <p style={{ fontSize: '24px', fontWeight: '600', color: '#1d4ed8' }}>{positions.total_symbols}</p>
                  </div>
                </div>
              )}

              {/* Open Positions Table with Filter and Sort */}
              <div style={{ marginBottom: '32px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#1f2937' }}>🔓 Positions Ouvertes</h4>
                  <input
                    type="text"
                    placeholder="Filtrer par symbol..."
                    value={positionsSymbolFilter}
                    onChange={(e) => setPositionsSymbolFilter(e.target.value.toUpperCase())}
                    style={{
                      padding: '8px 12px',
                      border: '1px solid #d1d5db',
                      borderRadius: '6px',
                      fontSize: '13px',
                      width: '180px'
                    }}
                  />
                </div>
                {positions?.open_positions && positions.open_positions.length > 0 ? (
                  <div style={{ overflowX: 'auto', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ backgroundColor: '#f9fafb' }}>
                          <th 
                            onClick={() => handlePositionsSort('symbol')}
                            style={{ 
                              padding: '12px', 
                              textAlign: 'left', 
                              fontSize: '12px', 
                              fontWeight: '600', 
                              color: '#6b7280', 
                              borderBottom: '1px solid #e5e7eb',
                              cursor: 'pointer',
                              userSelect: 'none'
                            }}
                          >
                            Symbol {positionsSortBy === 'symbol' && (positionsSortOrder === 'asc' ? '▲' : '▼')}
                          </th>
                          <th 
                            onClick={() => handlePositionsSort('quantity')}
                            style={{ 
                              padding: '12px', 
                              textAlign: 'right', 
                              fontSize: '12px', 
                              fontWeight: '600', 
                              color: '#6b7280', 
                              borderBottom: '1px solid #e5e7eb',
                              cursor: 'pointer',
                              userSelect: 'none'
                            }}
                          >
                            Quantity {positionsSortBy === 'quantity' && (positionsSortOrder === 'asc' ? '▲' : '▼')}
                          </th>
                          <th 
                            onClick={() => handlePositionsSort('average_price')}
                            style={{ 
                              padding: '12px', 
                              textAlign: 'right', 
                              fontSize: '12px', 
                              fontWeight: '600', 
                              color: '#6b7280', 
                              borderBottom: '1px solid #e5e7eb',
                              cursor: 'pointer',
                              userSelect: 'none'
                            }}
                          >
                            Avg Price {positionsSortBy === 'average_price' && (positionsSortOrder === 'asc' ? '▲' : '▼')}
                          </th>
                          <th 
                            onClick={() => handlePositionsSort('total_cost')}
                            style={{ 
                              padding: '12px', 
                              textAlign: 'right', 
                              fontSize: '12px', 
                              fontWeight: '600', 
                              color: '#6b7280', 
                              borderBottom: '1px solid #e5e7eb',
                              cursor: 'pointer',
                              userSelect: 'none'
                            }}
                          >
                            Total Cost {positionsSortBy === 'total_cost' && (positionsSortOrder === 'asc' ? '▲' : '▼')}
                          </th>
                          <th 
                            onClick={() => handlePositionsSort('transaction_count')}
                            style={{ 
                              padding: '12px', 
                              textAlign: 'center', 
                              fontSize: '12px', 
                              fontWeight: '600', 
                              color: '#6b7280', 
                              borderBottom: '1px solid #e5e7eb',
                              cursor: 'pointer',
                              userSelect: 'none'
                            }}
                          >
                            Transactions {positionsSortBy === 'transaction_count' && (positionsSortOrder === 'asc' ? '▲' : '▼')}
                          </th>
                          <th style={{ padding: '12px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#6b7280', borderBottom: '1px solid #e5e7eb' }}>
                            Adjusted
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {getSortedAndFilteredPositions().map((pos) => (
                          <tr key={pos.symbol} style={{ borderBottom: '1px solid #e5e7eb' }}>
                            <td style={{ padding: '12px', fontSize: '14px', fontWeight: '600', color: '#1f2937' }}>{pos.symbol}</td>
                            <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', color: pos.quantity < 0 ? '#dc2626' : '#1f2937' }}>
                              {pos.quantity.toFixed(2)}
                            </td>
                            <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', color: '#1f2937' }}>
                              ${pos.average_price.toFixed(2)}
                            </td>
                            <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', fontWeight: '500', color: pos.total_cost < 0 ? '#dc2626' : '#16a34a' }}>
                              ${pos.total_cost.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </td>
                            <td style={{ padding: '12px', textAlign: 'center', fontSize: '13px', color: '#6b7280' }}>
                              {pos.transaction_count}
                            </td>
                            <td style={{ padding: '12px', textAlign: 'center' }}>
                              {pos.adjusted_count > 0 ? (
                                <span style={{ padding: '2px 8px', backgroundColor: '#fef3c7', color: '#d97706', borderRadius: '4px', fontSize: '11px', fontWeight: '500' }}>
                                  🔄 {pos.adjusted_count}
                                </span>
                              ) : (
                                <span style={{ color: '#9ca3af', fontSize: '12px' }}>-</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '32px', color: '#9ca3af', backgroundColor: '#f9fafb', borderRadius: '8px' }}>
                    <p>Aucune position ouverte.</p>
                    <p style={{ fontSize: '12px' }}>Cliquez sur &quot;Refresh Positions&quot; pour calculer les positions.</p>
                  </div>
                )}
              </div>

              {/* Closed Positions */}
              <div>
                <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#1f2937', marginBottom: '12px' }}>🔒 Positions Fermées ({positions?.closed_count || 0})</h4>
                {positions?.closed_positions && positions.closed_positions.length > 0 ? (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {positions.closed_positions.map((pos) => (
                      <span
                        key={pos.symbol}
                        style={{
                          padding: '4px 12px',
                          backgroundColor: '#f3f4f6',
                          color: '#6b7280',
                          borderRadius: '16px',
                          fontSize: '12px',
                          fontWeight: '500'
                        }}
                      >
                        {pos.symbol}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p style={{ color: '#9ca3af', fontSize: '14px' }}>Aucune position fermée.</p>
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
