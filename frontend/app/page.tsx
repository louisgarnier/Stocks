'use client';

import { useEffect, useState, Fragment } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { RefreshCcw, X, Plus, Database } from "lucide-react";
import { toast } from "sonner";
import { SecurityDetailSheet } from "@/components/security-detail/SecurityDetailSheet";
import { SignalPill } from '@/components/positions/SignalPill';
import { SignalsExpandPanel } from '@/components/positions/SignalsExpandPanel';
import { fetchHoldingSignals, countFired, type SignalsBySymbol } from '@/lib/holding-signals';
import { visibleTransactions, selectableIds } from '@/lib/journal';
import { SyncRunsPanel } from '@/components/sync-runs/SyncRunsPanel';
import { fetchSyncRuns, type SyncRun } from '@/lib/sync-runs';
import { ResearchGrid } from '@/components/research/ResearchGrid';
import { Dashboard as DashboardTab } from '@/components/dashboard/Dashboard';
import { SyncToolbar } from '@/components/research/SyncToolbar';
import { TuningPanel } from '@/components/research/TuningPanel';

interface HealthResponse {
  status: string;
  database: string;
  transactions: number;
  positions: number;
}

interface UniverseSymbol {
  symbol: string;
  name: string | null;
  sector: string | null;
  currency: string | null;
  exchange: string | null;
  benchmark: string | null;
  sources: string[];
  enabled: boolean;
  added_at: string;
  last_synced_at: string | null;
}

interface IndexInfo {
  name: string;
  enabled: boolean;
  last_refreshed_at: string | null;
  symbol_count: number;
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
  asset_category: string | null;
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
  cost_basis_money: number;
  cost_basis_price: number;
  mark_price: number;
  position_value: number;
  unrealized_pnl: number;
  currency: string;
  asset_category: string;
  last_updated: string;
}

interface PositionsResponse {
  success: boolean;
  positions: Position[];
  summary: {
    total_positions: number;
    last_updated: string | null;
  };
}

type TabType = 'dashboard' | 'positions' | 'transactions' | 'browse-universe' | 'configuration';
type TransactionsSubTab = 'original' | 'split-adjusted' | 'corporate-actions';

function previousBusinessDay(d: Date): Date {
  const r = new Date(d);
  r.setDate(r.getDate() - 1);
  while (r.getDay() === 0 || r.getDay() === 6) {
    r.setDate(r.getDate() - 1);
  }
  return r;
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  const [transactionsSubTab, setTransactionsSubTab] = useState<TransactionsSubTab>('original');
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
  const [dateFromFilter, setDateFromFilter] = useState<string>('');
  const [dateToFilter, setDateToFilter] = useState<string>('');
  const [sideFilter, setSideFilter] = useState<'' | 'buy' | 'sell'>('');
  const [showCash, setShowCash] = useState(false);
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
  const [updatedTxDateFrom, setUpdatedTxDateFrom] = useState<string>('');
  const [updatedTxDateTo, setUpdatedTxDateTo] = useState<string>('');
  const [updatedTxCaType, setUpdatedTxCaType] = useState<string>('');
  const [caDateFrom, setCaDateFrom] = useState<string>('');
  const [caDateTo, setCaDateTo] = useState<string>('');
  const [selectedUpdatedTx, setSelectedUpdatedTx] = useState<Set<number>>(new Set());
  const [positions, setPositions] = useState<PositionsResponse | null>(null);
  const [positionsLoading, setPositionsLoading] = useState(false);
  const [positionsSortBy, setPositionsSortBy] = useState<'symbol' | 'quantity' | 'cost_basis_price' | 'position_value' | 'unrealized_pnl'>('position_value');
  const [positionsSortOrder, setPositionsSortOrder] = useState<'asc' | 'desc'>('desc');
  const [positionsSymbolFilter, setPositionsSymbolFilter] = useState<string>('');
  const [signalsBySymbol, setSignalsBySymbol] = useState<SignalsBySymbol>({});
  const [expandedSignalSymbols, setExpandedSignalSymbols] = useState<Set<string>>(new Set());
  const [onlySignalsFired, setOnlySignalsFired] = useState(false);
  const [universe, setUniverse] = useState<UniverseSymbol[]>([]);
  const [indices, setIndices] = useState<IndexInfo[]>([]);
  const [universeLoading, setUniverseLoading] = useState(false);
  const [manualSymbolInput, setManualSymbolInput] = useState<string>('');
  const [fundamentalsSyncing, setFundamentalsSyncing] = useState(false);
  const [fundamentalsStatus, setFundamentalsStatus] = useState<{
    last_run: string | null;
    suggested_next: string | null;
    overdue: boolean;
  } | null>(null);
  const [syncRuns, setSyncRuns] = useState<SyncRun[]>([]);
  const [syncRunsLoading, setSyncRunsLoading] = useState(false);

  const refreshSyncRuns = async () => {
    setSyncRunsLoading(true);
    try {
      const r = await fetchSyncRuns(50);
      setSyncRuns(r.items);
    } catch (e) {
      console.warn('fetchSyncRuns failed', e);
    } finally {
      setSyncRunsLoading(false);
    }
  };
  const [showTuning, setShowTuning] = useState<boolean>(false);
  const [researchKey, setResearchKey] = useState<number>(0);
  const refreshResearch = () => setResearchKey((k) => k + 1);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);

  type SyncStepStatus = 'pending' | 'ok' | 'error';
  type SyncStepName = 'positions' | 'transactions' | 'corporate_actions' | 'splits';
  const STEP_LABELS: Record<SyncStepName, string> = {
    positions: '📊 Positions',
    transactions: '📋 Transactions',
    corporate_actions: '📑 Corporate Actions',
    splits: '✂️ Splits',
  };
  const [syncSteps, setSyncSteps] = useState<{ name: SyncStepName; status: SyncStepStatus }[] | null>(null);

  const fetchUniverse = async () => {
    try {
      const r = await fetch('/api/proxy/api/universe');
      if (r.ok) setUniverse((await r.json()).symbols);
    } catch (e) { console.error('fetchUniverse', e); }
  };

  const fetchIndices = async () => {
    try {
      const r = await fetch('/api/proxy/api/universe/indices');
      if (r.ok) setIndices((await r.json()).indices);
    } catch (e) { console.error('fetchIndices', e); }
  };

  const handleToggleIndex = async (name: string) => {
    await fetch(`/api/proxy/api/universe/indices/${name}/toggle`, { method: 'POST' });
    await fetchIndices();
  };

  const handleRefreshIndex = async (name: string) => {
    setUniverseLoading(true);
    try {
      await fetch(`/api/proxy/api/universe/indices/${name}/refresh`, { method: 'POST' });
      await fetchIndices();
      await fetchUniverse();
    } finally {
      setUniverseLoading(false);
    }
  };

  const handleAddManualSymbol = async () => {
    const sym = manualSymbolInput.trim().toUpperCase();
    if (!sym) return;
    await fetch('/api/proxy/api/universe/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol: sym }),
    });
    setManualSymbolInput('');
    await fetchUniverse();
    await refreshSyncRuns();
  };

  const handleRemoveManualSymbol = async (sym: string) => {
    await fetch(`/api/proxy/api/universe/manual/${sym}`, { method: 'DELETE' });
    await fetchUniverse();
  };

  const fetchFundamentalsStatus = async () => {
    try {
      const r = await fetch('/api/proxy/api/sync/fundamentals/status');
      if (r.ok) setFundamentalsStatus(await r.json());
    } catch (e) { console.error('fetchFundamentalsStatus', e); }
  };

  const handleSyncFundamentals = async () => {
    setFundamentalsSyncing(true);
    toast('Fundamentals refresh started', { description: 'Fetching yfinance fundamentals for the universe — this can take a few minutes.' });
    try {
      const r = await fetch('/api/proxy/api/sync/fundamentals', { method: 'POST' });
      const body = await r.json();
      if (r.ok) {
        toast.success('Fundamentals refresh complete', { description: JSON.stringify(body) });
      } else {
        toast.error('Fundamentals refresh failed', { description: JSON.stringify(body) });
      }
      await fetchFundamentalsStatus();
    } catch (e) {
      toast.error('Fundamentals refresh failed', { description: e instanceof Error ? e.message : String(e) });
    } finally {
      setFundamentalsSyncing(false);
    }
  };

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

  const fetchCorporateActions = async (
    typeFilter: string = caTypeFilter,
    symbolFilter: string = caSymbolFilter,
    dateFrom: string = caDateFrom,
    dateTo: string = caDateTo,
  ) => {
    try {
      let url = '/api/proxy/api/corporate-actions?limit=500&sort_by=ex_date&sort_order=desc';
      if (typeFilter) url += `&ca_type=${typeFilter}`;
      if (symbolFilter) url += `&symbol=${encodeURIComponent(symbolFilter)}`;
      if (dateFrom) url += `&date_from=${dateFrom}`;
      if (dateTo) url += `&date_to=${dateTo}`;
      
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
    if (!confirm('Delete all corporate actions?')) return;
    
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
    if (!confirm(`Delete ${selectedCAs.size} selected corporate action(s)?`)) return;
    
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

  const fetchTransactions = async (
    page: number = 1,
    limit: number = pageSize,
    sort: string = sortBy,
    order: string = sortOrder,
    symbol: string = symbolFilter,
    dateFrom: string = dateFromFilter,
    dateTo: string = dateToFilter,
    side: '' | 'buy' | 'sell' = sideFilter,
  ) => {
    try {
      let url = `/api/proxy/api/transactions?page=${page}&limit=${limit}&sort_by=${sort}&sort_order=${order}`;
      if (symbol) url += `&symbol=${encodeURIComponent(symbol)}`;
      if (dateFrom) url += `&date_from=${dateFrom}`;
      if (dateTo) url += `&date_to=${dateTo}`;
      if (side) url += `&side=${side}`;
      
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

  const fetchUpdatedTransactions = async (
    page: number = 1,
    symbol: string = updatedTxSymbolFilter,
    dateFrom: string = updatedTxDateFrom,
    dateTo: string = updatedTxDateTo,
    caType: string = updatedTxCaType,
  ) => {
    try {
      let url = `/api/proxy/api/updated-transactions?page=${page}&limit=${pageSize}&sort_by=trade_date&sort_order=desc`;
      if (symbol) url += `&symbol=${encodeURIComponent(symbol)}`;
      if (dateFrom) url += `&date_from=${dateFrom}`;
      if (dateTo) url += `&date_to=${dateTo}`;
      if (caType) url += `&ca_type=${caType}`;

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
    try {
      const map = await fetchHoldingSignals();
      setSignalsBySymbol(map);
    } catch (err) {
      console.warn('⚠️ holding-signals fetch failed:', err);
      setSignalsBySymbol({});
    }
  };

  const handlePositionsSort = (column: 'symbol' | 'quantity' | 'cost_basis_price' | 'position_value' | 'unrealized_pnl') => {
    const newOrder = positionsSortBy === column && positionsSortOrder === 'desc' ? 'asc' : 'desc';
    setPositionsSortBy(column);
    setPositionsSortOrder(newOrder);
  };

  const toggleSignalExpand = (symbol: string) => {
    setExpandedSignalSymbols((prev) => {
      const next = new Set(prev);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      return next;
    });
  };

  const getSortedAndFilteredPositions = (): Position[] => {
    if (!positions?.positions) return [];
    
    let filtered = positions.positions;
    
    // Apply symbol filter
    if (positionsSymbolFilter) {
      filtered = filtered.filter((pos: Position) =>
        pos.symbol.toLowerCase().includes(positionsSymbolFilter.toLowerCase())
      );
    }

    if (onlySignalsFired) {
      filtered = filtered.filter((pos: Position) => countFired(signalsBySymbol[pos.symbol] ?? []) > 0);
    }

    // Apply sorting
    return [...filtered].sort((a: Position, b: Position) => {
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
    fetchUpdatedTransactions(1, symbol, updatedTxDateFrom, updatedTxDateTo, updatedTxCaType);
  };

  const handleUpdatedTxDateFrom = (value: string) => {
    setUpdatedTxDateFrom(value);
    setUpdatedTxPage(1);
    fetchUpdatedTransactions(1, updatedTxSymbolFilter, value, updatedTxDateTo, updatedTxCaType);
  };

  const handleUpdatedTxDateTo = (value: string) => {
    setUpdatedTxDateTo(value);
    setUpdatedTxPage(1);
    fetchUpdatedTransactions(1, updatedTxSymbolFilter, updatedTxDateFrom, value, updatedTxCaType);
  };

  const handleUpdatedTxCaType = (value: string) => {
    setUpdatedTxCaType(value);
    setUpdatedTxPage(1);
    fetchUpdatedTransactions(1, updatedTxSymbolFilter, updatedTxDateFrom, updatedTxDateTo, value);
  };

  const handleClearUpdatedTxFilters = () => {
    setUpdatedTxSymbolFilter('');
    setUpdatedTxDateFrom('');
    setUpdatedTxDateTo('');
    setUpdatedTxCaType('');
    setUpdatedTxPage(1);
    fetchUpdatedTransactions(1, '', '', '', '');
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
    fetchTransactions(1, pageSize, sortBy, sortOrder, symbol, dateFromFilter, dateToFilter, sideFilter);
  };

  const handleDateFromFilter = (value: string) => {
    setDateFromFilter(value);
    setCurrentPage(1);
    fetchTransactions(1, pageSize, sortBy, sortOrder, symbolFilter, value, dateToFilter, sideFilter);
  };

  const handleDateToFilter = (value: string) => {
    setDateToFilter(value);
    setCurrentPage(1);
    fetchTransactions(1, pageSize, sortBy, sortOrder, symbolFilter, dateFromFilter, value, sideFilter);
  };

  const handleSideFilter = (value: '' | 'buy' | 'sell') => {
    setSideFilter(value);
    setCurrentPage(1);
    fetchTransactions(1, pageSize, sortBy, sortOrder, symbolFilter, dateFromFilter, dateToFilter, value);
  };

  const handleClearAllFilters = () => {
    setSymbolFilter('');
    setDateFromFilter('');
    setDateToFilter('');
    setSideFilter('');
    setCurrentPage(1);
    fetchTransactions(1, pageSize, sortBy, sortOrder, '', '', '', '');
  };

  const handleDeleteAllTransactions = async () => {
    const t = window.prompt('Type DELETE to remove all transactions');
    if (t !== 'DELETE') {
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
          (activeTab === 'transactions' && transactionsSubTab === 'corporate-actions') ? fetchCorporateActions() : Promise.resolve()
        ]);
        // Force a second refresh after a short delay to ensure data is synced
        setTimeout(() => {
          fetchHealth();
          fetchSecurities();
          fetchCAStatus();
          if (activeTab === 'transactions' && transactionsSubTab === 'corporate-actions') {
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

    // Select only the rows the table actually renders — CASH legs are hidden by
    // default (showCash), so "select all" must not sweep up an unseen row.
    const visibleIds = selectableIds(transactions.data, showCash);

    if (selectedTransactions.size === visibleIds.length) {
      // Deselect all
      setSelectedTransactions(new Set());
    } else {
      // Select all (visible only)
      setSelectedTransactions(new Set(visibleIds));
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

  const handleFlexImport = async () => {
    setFlexLoading(true);
    setShowFlexDropdown(false);
    setSyncSteps([
      { name: 'positions', status: 'pending' },
      { name: 'transactions', status: 'pending' },
      { name: 'corporate_actions', status: 'pending' },
      { name: 'splits', status: 'pending' },
    ]);

    try {
      const response = await fetch('/api/proxy/api/sync/ibkr', { method: 'POST' });

      if (response.ok) {
        const result = await response.json();
        const stepSummary = (result.steps || [])
          .map((s: { name: string; status: string }) => `${s.status === 'ok' ? '✅' : '❌'} ${s.name}`)
          .join(' · ');
        setUploadResult({
          success: result.success,
          message: stepSummary || 'Sync complete',
          parsed: 0,
          inserted: 0,
          skipped: 0,
          errors: result.success ? 0 : 1,
        });
        setSyncSteps((result.steps || []).map((s: { name: string; status: string }) => ({
          name: s.name as SyncStepName,
          status: (s.status === 'ok' ? 'ok' : 'error') as SyncStepStatus,
        })));
        setTimeout(() => setSyncSteps(null), 5000);
        await Promise.all([
          fetchHealth(),
          fetchImportLogs(),
          fetchCAStatus(),
          fetchTransactions(1, pageSize, sortBy, sortOrder, symbolFilter),
        ]);
        await fetchPositions();
        await refreshSyncRuns();
        setTimeout(() => fetchHealth(), 500);
      } else {
        const error = await response.json().catch(() => ({ detail: 'Sync failed' }));
        setUploadResult({
          success: false,
          message: error.detail || 'Sync failed',
          parsed: 0,
          inserted: 0,
          skipped: 0,
          errors: 1,
          error_details: [error.detail || 'Unknown error']
        });
        setSyncSteps([
          { name: 'positions', status: 'error' },
          { name: 'transactions', status: 'error' },
          { name: 'corporate_actions', status: 'error' },
          { name: 'splits', status: 'error' },
        ]);
        setTimeout(() => setSyncSteps(null), 5000);
        await fetchImportLogs();
      }
    } catch (err) {
      console.error('Sync error:', err);
      setUploadResult({
        success: false,
        message: `Sync error: ${err instanceof Error ? err.message : 'Unknown error'}`,
        parsed: 0,
        inserted: 0,
        skipped: 0,
        errors: 1,
        error_details: [err instanceof Error ? err.message : 'Unknown error']
      });
      setSyncSteps([
        { name: 'positions', status: 'error' },
        { name: 'transactions', status: 'error' },
        { name: 'corporate_actions', status: 'error' },
        { name: 'splits', status: 'error' },
      ]);
      setTimeout(() => setSyncSteps(null), 5000);
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
    fetchPositions();
    fetchUniverse();
    fetchIndices();
    fetchFundamentalsStatus();
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

  const getStalenessBadge = (): { text: string; bg: string; fg: string } | null => {
    const ts = positions?.summary?.last_updated;
    if (!ts) return null;
    const ageMs = Date.now() - new Date(ts).getTime();
    const ageHours = ageMs / 3_600_000;
    let text: string;
    if (ageHours < 1) {
      const mins = Math.max(1, Math.round(ageMs / 60_000));
      text = `Last sync: ${mins}m ago`;
    } else if (ageHours < 24) {
      text = `Last sync: ${Math.round(ageHours)}h ago`;
    } else {
      const days = Math.round(ageHours / 24);
      text = `Last sync: ${days}d ago`;
    }
    if (ageHours < 6) return { text, bg: '#dcfce7', fg: '#166534' };
    if (ageHours < 24) return { text, bg: '#fef9c3', fg: '#854d0e' };
    return { text, bg: '#fef2f2', fg: '#dc2626' };
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f9fafb' }}>
        <p style={{ color: '#6b7280' }}>Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f9fafb' }}>
        <div style={{ textAlign: 'center', color: '#dc2626', maxWidth: '600px', padding: '20px' }}>
          <h2 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '16px' }}>Connection error</h2>
          <p style={{ marginBottom: '16px' }}>{error}</p>
          <button onClick={() => window.location.reload()} style={{ padding: '12px 24px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer' }}>
            Reload
          </button>
        </div>
      </div>
    );
  }

  const visibleTxData = transactions ? visibleTransactions(transactions.data, showCash) : [];
  const hiddenCashCount = (transactions?.data.length ?? 0) - visibleTxData.length;

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f9fafb' }}>
      <SecurityDetailSheet symbol={selectedSymbol} onClose={() => setSelectedSymbol(null)} />
      <header style={{ backgroundColor: 'white', borderBottom: '1px solid #e5e7eb', padding: '16px 20px' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: '#1f2937' }}>IBKR Portfolio Tracker</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              onClick={() => handleFlexImport()}
              disabled={flexLoading}
              title="Test API connection, fetch latest IBKR holdings and transactions"
              style={{
                padding: '8px 16px',
                backgroundColor: flexLoading ? '#9ca3af' : '#2563eb',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: '500',
                cursor: flexLoading ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              {flexLoading ? '⏳ Syncing…' : '🔄 Sync IBKR'}
            </button>
            {(() => {
              const badge = getStalenessBadge();
              return badge ? (
                <span style={{ display: 'inline-flex', alignItems: 'center', padding: '6px 12px', borderRadius: '9999px', fontSize: '13px', fontWeight: '500', backgroundColor: badge.bg, color: badge.fg }}>
                  {badge.text}
                </span>
              ) : null;
            })()}
            <span style={{ display: 'inline-flex', alignItems: 'center', padding: '6px 12px', borderRadius: '9999px', fontSize: '14px', fontWeight: '500', backgroundColor: isConnected ? '#dcfce7' : '#fef2f2', color: isConnected ? '#166534' : '#dc2626' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', marginRight: '8px', backgroundColor: isConnected ? '#22c55e' : '#ef4444' }} />
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </header>

      {syncSteps && (
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '12px 20px', display: 'flex', gap: '12px' }}>
          {syncSteps.map((step) => {
            const icon = step.status === 'pending' ? '⏳' : step.status === 'ok' ? '✅' : '❌';
            const bg = step.status === 'pending' ? '#f3f4f6' : step.status === 'ok' ? '#dcfce7' : '#fef2f2';
            const fg = step.status === 'pending' ? '#6b7280' : step.status === 'ok' ? '#166534' : '#dc2626';
            return (
              <div key={step.name} style={{ flex: 1, padding: '8px 12px', borderRadius: '6px', backgroundColor: bg, color: fg, fontSize: '13px', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span>{icon}</span>
                <span>{STEP_LABELS[step.name]}</span>
              </div>
            );
          })}
        </div>
      )}

      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '32px 20px' }}>
        {/* Top-level Tabs */}
        <div style={{ display: 'flex', gap: '0', marginBottom: '0', borderBottom: '1px solid #e5e7eb' }}>
          <button
            onClick={() => setActiveTab('dashboard')}
            style={{ padding: '12px 24px', fontSize: '14px', fontWeight: '500', border: 'none', borderBottom: activeTab === 'dashboard' ? '2px solid #3b82f6' : '2px solid transparent', backgroundColor: 'transparent', color: activeTab === 'dashboard' ? '#3b82f6' : '#6b7280', cursor: 'pointer' }}
          >
            🏠 Dashboard
          </button>
          <button
            onClick={() => { setActiveTab('positions'); fetchPositions(); }}
            style={{ padding: '12px 24px', fontSize: '14px', fontWeight: '500', border: 'none', borderBottom: activeTab === 'positions' ? '2px solid #3b82f6' : '2px solid transparent', backgroundColor: 'transparent', color: activeTab === 'positions' ? '#3b82f6' : '#6b7280', cursor: 'pointer' }}
          >
            📊 Positions
          </button>
          <button
            onClick={() => {
              setActiveTab('transactions');
              if (transactionsSubTab === 'original') fetchTransactions(1, pageSize, sortBy, sortOrder, symbolFilter);
              else if (transactionsSubTab === 'split-adjusted') fetchUpdatedTransactions();
              else if (transactionsSubTab === 'corporate-actions') { fetchSecurities(); fetchCorporateActions(); }
            }}
            style={{ padding: '12px 24px', fontSize: '14px', fontWeight: '500', border: 'none', borderBottom: activeTab === 'transactions' ? '2px solid #3b82f6' : '2px solid transparent', backgroundColor: 'transparent', color: activeTab === 'transactions' ? '#3b82f6' : '#6b7280', cursor: 'pointer' }}
          >
            📔 Journal
          </button>
          <button
            onClick={() => setActiveTab('browse-universe')}
            style={{ padding: '12px 24px', fontSize: '14px', fontWeight: '500', border: 'none', borderBottom: activeTab === 'browse-universe' ? '2px solid #3b82f6' : '2px solid transparent', backgroundColor: 'transparent', color: activeTab === 'browse-universe' ? '#3b82f6' : '#6b7280', cursor: 'pointer' }}
          >
            🌐 Browse Universe
          </button>
          <button
            onClick={() => { setActiveTab('configuration'); refreshSyncRuns(); fetchFundamentalsStatus(); }}
            style={{ padding: '12px 24px', fontSize: '14px', fontWeight: '500', border: 'none', borderBottom: activeTab === 'configuration' ? '2px solid #3b82f6' : '2px solid transparent', backgroundColor: 'transparent', color: activeTab === 'configuration' ? '#3b82f6' : '#6b7280', cursor: 'pointer' }}
          >
            ⚙️ Settings
          </button>
        </div>

        {/* Sub-tabs for Transactions */}
        {activeTab === 'transactions' && (
          <div style={{ display: 'flex', gap: '0', marginBottom: '0', borderBottom: '1px solid #e5e7eb', backgroundColor: '#f9fafb' }}>
            <button
              onClick={() => { setTransactionsSubTab('original'); fetchTransactions(1, pageSize, sortBy, sortOrder, symbolFilter); }}
              style={{ padding: '8px 20px', fontSize: '13px', fontWeight: '500', border: 'none', borderBottom: transactionsSubTab === 'original' ? '2px solid #3b82f6' : '2px solid transparent', backgroundColor: 'transparent', color: transactionsSubTab === 'original' ? '#3b82f6' : '#6b7280', cursor: 'pointer' }}
            >
              Original
            </button>
            <button
              onClick={() => { setTransactionsSubTab('split-adjusted'); fetchUpdatedTransactions(); }}
              style={{ padding: '8px 20px', fontSize: '13px', fontWeight: '500', border: 'none', borderBottom: transactionsSubTab === 'split-adjusted' ? '2px solid #3b82f6' : '2px solid transparent', backgroundColor: 'transparent', color: transactionsSubTab === 'split-adjusted' ? '#3b82f6' : '#6b7280', cursor: 'pointer' }}
            >
              Split-Adjusted
            </button>
            <button
              onClick={() => { setTransactionsSubTab('corporate-actions'); fetchSecurities(); fetchCorporateActions(); }}
              style={{ padding: '8px 20px', fontSize: '13px', fontWeight: '500', border: 'none', borderBottom: transactionsSubTab === 'corporate-actions' ? '2px solid #3b82f6' : '2px solid transparent', backgroundColor: 'transparent', color: transactionsSubTab === 'corporate-actions' ? '#3b82f6' : '#6b7280', cursor: 'pointer' }}
            >
              Corporate Actions
            </button>
          </div>
        )}

        {/* Tab Content */}
        <div style={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderTop: 'none', borderRadius: '0 0 8px 8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>

          {/* Tab: Dashboard — net worth, allocation, performance, action queue, movers */}
          {activeTab === 'dashboard' && <DashboardTab onSelectSymbol={setSelectedSymbol} />}

          {/* Tab: Browse Universe — searchable table of every tracked symbol */}
          {activeTab === 'browse-universe' && (
            <div className="p-6 space-y-4">
              {/* Research — unified per-stock view (technical + fundamental) */}
              <div className="space-y-3">
                <div className="flex items-baseline justify-between">
                  <div>
                    <h2 className="text-xl font-bold tracking-tight">Research</h2>
                    <p className="text-sm text-muted-foreground">
                      One row = all technical + fundamental data across your tracked universe.
                    </p>
                  </div>
                  <button
                    onClick={() => setShowTuning((v) => !v)}
                    className="text-sm font-medium px-3 py-2 rounded-md border bg-card hover:bg-secondary/40"
                  >
                    ⚙ {showTuning ? 'Hide' : 'Tune'} parameters
                  </button>
                </div>
                <SyncToolbar onSynced={refreshResearch} />
                {showTuning && <TuningPanel onRerun={refreshResearch} />}
                <ResearchGrid key={researchKey} onSelectSymbol={setSelectedSymbol} />
              </div>
            </div>
          )}

          {/* Tab 1: Configuration (formerly Load Trades) */}
          {activeTab === 'configuration' && (
            <div>
              {/* Universe management — shadcn-styled */}
              <div className="p-6 space-y-6">
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <Database className="w-5 h-5" />
                      Tracked Universe
                    </CardTitle>
                    <Badge variant="secondary">{universe.length} symbols</Badge>
                  </CardHeader>
                  <CardContent className="space-y-6">

                    {/* Index toggles */}
                    <div>
                      <h4 className="text-sm font-semibold mb-3 text-foreground">Index lists</h4>
                      <div className="space-y-2">
                        {indices.map((idx) => (
                          <div key={idx.name} className="flex items-center justify-between p-3 rounded-md border bg-card">
                            <div className="flex items-center gap-3">
                              <Switch
                                checked={idx.enabled}
                                onCheckedChange={() => handleToggleIndex(idx.name)}
                                id={`switch-${idx.name}`}
                              />
                              <label htmlFor={`switch-${idx.name}`} className="text-sm font-medium cursor-pointer">
                                {idx.name.toUpperCase()}
                              </label>
                              <Badge variant="outline" className="text-xs">
                                {idx.symbol_count} symbols
                              </Badge>
                              {idx.last_refreshed_at && (
                                <span className="text-xs text-muted-foreground">
                                  Refreshed {new Date(idx.last_refreshed_at).toLocaleDateString()}
                                </span>
                              )}
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleRefreshIndex(idx.name)}
                              disabled={universeLoading}
                            >
                              <RefreshCcw className="w-4 h-4 mr-1" />
                              Refresh
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Manual tickers */}
                    <div>
                      <h4 className="text-sm font-semibold mb-3 text-foreground">Custom tickers</h4>
                      <div className="flex gap-2 mb-3">
                        <Input
                          placeholder="Add ticker (e.g. NVDA)"
                          value={manualSymbolInput}
                          onChange={(e) => setManualSymbolInput(e.target.value.toUpperCase())}
                          onKeyDown={(e) => { if (e.key === 'Enter') handleAddManualSymbol(); }}
                          className="max-w-xs"
                        />
                        <Button onClick={handleAddManualSymbol} disabled={!manualSymbolInput.trim()}>
                          <Plus className="w-4 h-4 mr-1" />
                          Add
                        </Button>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {universe
                          .filter((s) => s.sources.includes('manual'))
                          .map((s) => (
                            <Badge key={s.symbol} variant="secondary" className="gap-1">
                              {s.symbol}
                              <button
                                onClick={() => handleRemoveManualSymbol(s.symbol)}
                                className="ml-1 hover:text-destructive"
                                title="Remove"
                              >
                                <X className="w-3 h-3" />
                              </button>
                            </Badge>
                          ))}
                        {universe.filter((s) => s.sources.includes('manual')).length === 0 && (
                          <span className="text-sm text-muted-foreground">No manual tickers yet.</span>
                        )}
                      </div>
                    </div>

                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between">
                    <CardTitle>Fundamentals</CardTitle>
                    <Button onClick={handleSyncFundamentals} disabled={fundamentalsSyncing} variant="outline">
                      <RefreshCcw className={`w-4 h-4 mr-2 ${fundamentalsSyncing ? 'animate-spin' : ''}`} />
                      {fundamentalsSyncing ? 'Refreshing…' : 'Refresh fundamentals'}
                    </Button>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <p className="text-sm text-muted-foreground">
                      Last run: {fundamentalsStatus?.last_run ? new Date(fundamentalsStatus.last_run).toLocaleDateString() : 'never'}
                      {' · '}
                      Suggested next: {fundamentalsStatus?.suggested_next ? new Date(fundamentalsStatus.suggested_next).toLocaleDateString() : '—'}
                      {fundamentalsStatus?.overdue && (
                        <span
                          className="ml-2 px-2 py-0.5 rounded-full text-xs font-medium"
                          style={{ backgroundColor: '#fef3c7', color: '#b45309' }}
                        >
                          Overdue
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Pulls fundamentals (sector, market cap, etc.) from yfinance for every enabled symbol. Recommended cadence: every 30 days.
                    </p>
                  </CardContent>
                </Card>

              </div>

              {/* Existing configuration content below */}
              <div style={{ padding: '48px 24px' }}>
              {/* Database Stats Panel */}
              {health && (
                <div style={{ maxWidth: '400px', margin: '0 auto 32px', padding: '16px', backgroundColor: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
                  <h3 style={{ fontSize: '14px', fontWeight: '600', color: '#1f2937', marginBottom: '12px' }}>Database</h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                    <span style={{ fontSize: '16px' }}>✅</span>
                    <span style={{ fontSize: '14px', color: '#16a34a', fontWeight: '500' }}>Connected</span>
                  </div>
                  <div style={{ fontSize: '14px', color: '#6b7280' }}>
                    <strong>Transactions:</strong> {health.transactions?.toLocaleString() || 0}
                  </div>
                </div>
              )}
              
              <div style={{ textAlign: 'center', marginBottom: '32px' }}>
                <div style={{ fontSize: '48px', marginBottom: '16px' }}>📥</div>
                <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937', marginBottom: '8px' }}>Settings</h2>
                <p style={{ fontSize: '14px', color: '#6b7280', marginBottom: '24px' }}>Upload a CSV file or sync from IBKR</p>
                
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
                          onClick={() => handleFlexImport()}
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
                          onClick={() => handleFlexImport()}
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

              {/* Sync Runs — every sync action across IBKR, market data, analytics, manual ticker adds */}
              <SyncRunsPanel runs={syncRuns} onRefresh={refreshSyncRuns} loading={syncRunsLoading} />

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
            </div>
          )}

          {/* Tab 2: Transactions - Original */}
          {activeTab === 'transactions' && transactionsSubTab === 'original' && (
            <div>
              <div style={{ padding: '20px 24px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937' }}>Transactions</h2>
                  {transactions && <span style={{ fontSize: '14px', color: '#6b7280' }}>{transactions.total} transactions</span>}
                  {hiddenCashCount > 0 && (
                    <span style={{ fontSize: '12px', color: '#9ca3af' }}>{hiddenCashCount} cash/forex row{hiddenCashCount === 1 ? '' : 's'} hidden on this page</span>
                  )}
                  {(symbolFilter || dateFromFilter || dateToFilter || sideFilter) && (
                    <button
                      onClick={handleClearAllFilters}
                      style={{ padding: '4px 12px', backgroundColor: '#fef3c7', border: '1px solid #fcd34d', borderRadius: '4px', fontSize: '12px', color: '#92400e', cursor: 'pointer' }}
                    >
                      Clear filters ✕
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
                </div>
              </div>
              {/* Filter toolbar — always visible */}
              <div style={{ padding: '12px 24px', borderBottom: '1px solid #e5e7eb', backgroundColor: '#f9fafb', display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <label style={{ fontSize: '11px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase' }}>Symbol</label>
                  <input
                    type="text"
                    placeholder="e.g. NVDA"
                    value={symbolFilter}
                    onChange={(e) => handleSymbolFilter(e.target.value.toUpperCase())}
                    style={{ padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '13px', width: '140px' }}
                  />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <label style={{ fontSize: '11px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase' }}>Date from</label>
                  <input
                    type="date"
                    value={dateFromFilter}
                    onChange={(e) => handleDateFromFilter(e.target.value)}
                    style={{ padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '13px' }}
                  />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <label style={{ fontSize: '11px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase' }}>Date to</label>
                  <input
                    type="date"
                    value={dateToFilter}
                    onChange={(e) => handleDateToFilter(e.target.value)}
                    style={{ padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '13px' }}
                  />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <label style={{ fontSize: '11px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase' }}>Side</label>
                  <select
                    value={sideFilter}
                    onChange={(e) => handleSideFilter(e.target.value as '' | 'buy' | 'sell')}
                    style={{ padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '13px', backgroundColor: 'white' }}
                  >
                    <option value="">All</option>
                    <option value="buy">Buy</option>
                    <option value="sell">Sell</option>
                  </select>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <label style={{ fontSize: '11px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase' }}>&nbsp;</label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: '#374151', cursor: 'pointer', padding: '6px 0' }}>
                    <input
                      type="checkbox"
                      checked={showCash}
                      onChange={(e) => setShowCash(e.target.checked)}
                      style={{ cursor: 'pointer' }}
                    />
                    Show cash & forex
                  </label>
                </div>
              </div>
              {!transactions?.data?.length ? (
                <div style={{ padding: '48px 24px', textAlign: 'center' }}>
                  <div style={{ fontSize: '48px', marginBottom: '16px' }}>📄</div>
                  <h3 style={{ fontSize: '18px', fontWeight: '500', color: '#1f2937', marginBottom: '8px' }}>No transactions</h3>
                  <p style={{ fontSize: '14px', color: '#6b7280' }}>Load transactions from the &quot;Settings&quot; tab.</p>
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
                            checked={visibleTxData.length > 0 && selectedTransactions.size === visibleTxData.length}
                            onChange={handleSelectAll}
                            style={{ cursor: 'pointer' }}
                          />
                        </th>
                        <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Transaction ID</th>
                        <th onClick={() => handleSort('trade_date')} style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Date {sortBy === 'trade_date' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th onClick={() => handleSort('symbol')} style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Symbol {sortBy === 'symbol' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Type</th>
                        <th onClick={() => handleSort('quantity')} style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Qty {sortBy === 'quantity' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th onClick={() => handleSort('t_price')} style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', cursor: 'pointer' }}>Price {sortBy === 't_price' && (sortOrder === 'desc' ? '↓' : '↑')}</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Proceeds</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase' }}>Fees</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleTxData.map((tx) => (
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
                      <span style={{ fontSize: '14px', color: '#6b7280' }}>Show:</span>
                      {[25, 50, 100, 200].map((size) => (
                        <button key={size} onClick={() => {
                          setPageSize(size);
                          setCurrentPage(1);
                          fetchTransactions(1, size);
                        }} style={{ padding: '6px 12px', border: '1px solid #d1d5db', borderRadius: '6px', backgroundColor: pageSize === size ? '#3b82f6' : 'white', color: pageSize === size ? 'white' : '#374151', cursor: 'pointer', fontSize: '14px' }}>{size}</button>
                      ))}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <button onClick={() => fetchTransactions(currentPage - 1, pageSize)} disabled={currentPage === 1} style={{ padding: '8px 16px', border: '1px solid #d1d5db', borderRadius: '6px', backgroundColor: currentPage === 1 ? '#f3f4f6' : 'white', color: currentPage === 1 ? '#9ca3af' : '#374151', cursor: currentPage === 1 ? 'not-allowed' : 'pointer', fontSize: '14px' }}>← Previous</button>
                      <span style={{ padding: '8px 16px', fontSize: '14px', color: '#6b7280' }}>Page {currentPage} / {transactions.pages}</span>
                      <button onClick={() => fetchTransactions(currentPage + 1, pageSize)} disabled={currentPage === transactions.pages} style={{ padding: '8px 16px', border: '1px solid #d1d5db', borderRadius: '6px', backgroundColor: currentPage === transactions.pages ? '#f3f4f6' : 'white', color: currentPage === transactions.pages ? '#9ca3af' : '#374151', cursor: currentPage === transactions.pages ? 'not-allowed' : 'pointer', fontSize: '14px' }}>Next →</button>
                    </div>
                  </div>
                </div>
              )}
              {transactions && transactions.total > 0 && (
                <div style={{ padding: '20px 24px', borderTop: '1px solid #e5e7eb', marginTop: '16px' }}>
                  <div style={{ fontSize: '11px', fontWeight: '500', color: '#9ca3af', textTransform: 'uppercase', marginBottom: '6px' }}>Danger zone</div>
                  <button
                    onClick={handleDeleteAllTransactions}
                    style={{
                      padding: 0,
                      background: 'none',
                      border: 'none',
                      color: '#dc2626',
                      fontSize: '13px',
                      textDecoration: 'underline',
                      cursor: 'pointer',
                    }}
                  >
                    Delete all transactions
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Tab 3: Transactions - Split-Adjusted */}
          {activeTab === 'transactions' && transactionsSubTab === 'split-adjusted' && (
            <div>
              <div style={{ padding: '20px 24px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937' }}>Split-Adjusted Transactions</h2>
                  {updatedTransactions && <span style={{ fontSize: '14px', color: '#6b7280' }}>{updatedTransactions.total} rows</span>}
                  {(updatedTxSymbolFilter || updatedTxDateFrom || updatedTxDateTo || updatedTxCaType) && (
                    <button
                      onClick={handleClearUpdatedTxFilters}
                      style={{ padding: '4px 12px', backgroundColor: '#fef3c7', border: '1px solid #fcd34d', borderRadius: '4px', fontSize: '12px', color: '#92400e', cursor: 'pointer' }}
                    >
                      Clear filters ✕
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
              {/* Filter toolbar — always visible */}
              <div style={{ padding: '12px 24px', borderBottom: '1px solid #e5e7eb', backgroundColor: '#f9fafb', display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <label style={{ fontSize: '11px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase' }}>Symbol</label>
                  <input
                    type="text"
                    placeholder="e.g. NVDA"
                    value={updatedTxSymbolFilter}
                    onChange={(e) => handleUpdatedTxSymbolFilter(e.target.value.toUpperCase())}
                    style={{ padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '13px', width: '140px' }}
                  />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <label style={{ fontSize: '11px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase' }}>Date from</label>
                  <input
                    type="date"
                    value={updatedTxDateFrom}
                    onChange={(e) => handleUpdatedTxDateFrom(e.target.value)}
                    style={{ padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '13px' }}
                  />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <label style={{ fontSize: '11px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase' }}>Date to</label>
                  <input
                    type="date"
                    value={updatedTxDateTo}
                    onChange={(e) => handleUpdatedTxDateTo(e.target.value)}
                    style={{ padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '13px' }}
                  />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <label style={{ fontSize: '11px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase' }}>CA Type</label>
                  <select
                    value={updatedTxCaType}
                    onChange={(e) => handleUpdatedTxCaType(e.target.value)}
                    style={{ padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '13px', backgroundColor: 'white' }}
                  >
                    <option value="">All</option>
                    <option value="split">Split</option>
                    <option value="dividend">Dividend</option>
                    <option value="capital_gain">Capital Gain</option>
                  </select>
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
                      <button onClick={() => fetchUpdatedTransactions(updatedTxPage - 1)} disabled={updatedTxPage === 1} style={{ padding: '8px 16px', border: '1px solid #d1d5db', borderRadius: '6px', backgroundColor: updatedTxPage === 1 ? '#f3f4f6' : 'white', color: updatedTxPage === 1 ? '#9ca3af' : '#374151', cursor: updatedTxPage === 1 ? 'not-allowed' : 'pointer', fontSize: '14px' }}>← Previous</button>
                      <span style={{ padding: '8px 16px', fontSize: '14px', color: '#6b7280' }}>Page {updatedTxPage} / {updatedTransactions.pages}</span>
                      <button onClick={() => fetchUpdatedTransactions(updatedTxPage + 1)} disabled={updatedTxPage === updatedTransactions.pages} style={{ padding: '8px 16px', border: '1px solid #d1d5db', borderRadius: '6px', backgroundColor: updatedTxPage === updatedTransactions.pages ? '#f3f4f6' : 'white', color: updatedTxPage === updatedTransactions.pages ? '#9ca3af' : '#374151', cursor: updatedTxPage === updatedTransactions.pages ? 'not-allowed' : 'pointer', fontSize: '14px' }}>Next →</button>
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

          {/* Tab 4: Transactions - Corporate Actions */}
          {activeTab === 'transactions' && transactionsSubTab === 'corporate-actions' && (
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
                    <p>No securities in database.</p>
                    <p style={{ fontSize: '12px' }}>Load transactions from the &quot;Settings&quot; tab.</p>
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

                {/* Filter toolbar — always visible */}
                <div style={{ padding: '12px 16px', marginBottom: '16px', borderRadius: '6px', backgroundColor: '#f9fafb', border: '1px solid #e5e7eb', display: 'flex', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <label style={{ fontSize: '11px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase' }}>Symbol</label>
                    <input
                      type="text"
                      placeholder="e.g. NVDA"
                      value={caSymbolFilter}
                      onChange={(e) => {
                        const v = e.target.value.toUpperCase();
                        setCaSymbolFilter(v);
                        fetchCorporateActions(caTypeFilter, v, caDateFrom, caDateTo);
                      }}
                      style={{ padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '13px', width: '140px' }}
                    />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <label style={{ fontSize: '11px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase' }}>Date from</label>
                    <input
                      type="date"
                      value={caDateFrom}
                      onChange={(e) => {
                        setCaDateFrom(e.target.value);
                        fetchCorporateActions(caTypeFilter, caSymbolFilter, e.target.value, caDateTo);
                      }}
                      style={{ padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '13px' }}
                    />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <label style={{ fontSize: '11px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase' }}>Date to</label>
                    <input
                      type="date"
                      value={caDateTo}
                      onChange={(e) => {
                        setCaDateTo(e.target.value);
                        fetchCorporateActions(caTypeFilter, caSymbolFilter, caDateFrom, e.target.value);
                      }}
                      style={{ padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '13px' }}
                    />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <label style={{ fontSize: '11px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase' }}>Type</label>
                    <select
                      value={caTypeFilter}
                      onChange={(e) => {
                        setCaTypeFilter(e.target.value);
                        fetchCorporateActions(e.target.value, caSymbolFilter, caDateFrom, caDateTo);
                      }}
                      style={{ padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '13px', backgroundColor: 'white' }}
                    >
                      <option value="">All</option>
                      <option value="dividend">Dividend</option>
                      <option value="split">Split</option>
                      <option value="capital_gain">Capital Gain</option>
                    </select>
                  </div>
                  {(caSymbolFilter || caTypeFilter || caDateFrom || caDateTo) && (
                    <button
                      onClick={() => {
                        setCaSymbolFilter('');
                        setCaTypeFilter('');
                        setCaDateFrom('');
                        setCaDateTo('');
                        fetchCorporateActions('', '', '', '');
                      }}
                      style={{ padding: '6px 12px', backgroundColor: '#fef3c7', border: '1px solid #fcd34d', borderRadius: '4px', fontSize: '12px', color: '#92400e', cursor: 'pointer', alignSelf: 'flex-end' }}
                    >
                      Clear filters ✕
                    </button>
                  )}
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
                    <p>No corporate actions.</p>
                    <p style={{ fontSize: '12px' }}>Click on &quot;Fetch from yfinance&quot; to retrieve the data.</p>
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
                  <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937', marginBottom: '4px' }}>📊 Portfolio Positions (IBKR)</h3>
                  {positions?.summary?.last_updated && (
                    <>
                      <p style={{ fontSize: '13px', color: '#374151', fontWeight: 500 }}>
                        Data as of: {previousBusinessDay(new Date(positions.summary.last_updated)).toISOString().slice(0, 10)} close
                        <span style={{ color: '#9ca3af', fontWeight: 400 }}> · IBKR Flex (T-1, end-of-day)</span>
                      </p>
                      <p style={{ fontSize: '12px', color: '#9ca3af' }}>
                        Last sync: {new Date(positions.summary.last_updated).toLocaleString()}
                      </p>
                    </>
                  )}
                </div>
              </div>

              {/* Summary Cards */}
              {positions?.summary && (
                <div style={{ display: 'flex', gap: '16px', marginBottom: '24px' }}>
                  <div style={{ backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '8px', padding: '16px', minWidth: '180px' }}>
                    <p style={{ fontSize: '12px', color: '#2563eb', fontWeight: '500' }}>Open Positions</p>
                    <p style={{ fontSize: '24px', fontWeight: '600', color: '#1d4ed8' }}>{positions.summary.total_positions}</p>
                  </div>
                  {(() => {
                    const heldSyms = positions?.positions?.map((p) => p.symbol) ?? [];
                    const flagged = heldSyms.filter((s) => countFired(signalsBySymbol[s] ?? []) > 0).length;
                    if (flagged === 0) return null;
                    return (
                      <div style={{ backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', padding: '16px', minWidth: '180px' }}>
                        <p style={{ fontSize: '12px', color: '#dc2626', fontWeight: '500', margin: 0 }}>⚠️ Holdings with sell signals</p>
                        <p style={{ fontSize: '24px', fontWeight: '600', color: '#b91c1c', margin: 0 }}>
                          {flagged}<span style={{ fontSize: '14px', fontWeight: 500, color: '#9ca3af', marginLeft: '6px' }}>of {heldSyms.length}</span>
                        </p>
                      </div>
                    );
                  })()}
                </div>
              )}

              {/* Positions Table with Filter and Sort */}
              <div style={{ marginBottom: '32px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#1f2937' }}>IBKR Open Positions</h4>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#6b7280', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={onlySignalsFired}
                        onChange={(e) => setOnlySignalsFired(e.target.checked)}
                        style={{ cursor: 'pointer' }}
                      />
                      Only with signals fired
                    </label>
                    <input
                      type="text"
                      placeholder="Filter by symbol..."
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
                </div>
                {positions?.positions && positions.positions.length > 0 ? (
                  <div style={{ overflowX: 'auto', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ backgroundColor: '#f9fafb' }}>
                          {[
                            { key: 'symbol' as const, label: 'Symbol', align: 'left' },
                            { key: 'quantity' as const, label: 'Qty', align: 'right' },
                            { key: 'cost_basis_price' as const, label: 'Avg Cost', align: 'right' },
                            { key: 'position_value' as const, label: 'Market Value', align: 'right' },
                            { key: 'unrealized_pnl' as const, label: 'Unrealized P&L', align: 'right' },
                          ].map((col) => (
                            <th
                              key={col.key}
                              onClick={() => handlePositionsSort(col.key)}
                              style={{
                                padding: '12px',
                                textAlign: col.align as 'left' | 'right' | 'center',
                                fontSize: '12px',
                                fontWeight: '600',
                                color: '#6b7280',
                                borderBottom: '1px solid #e5e7eb',
                                cursor: 'pointer',
                                userSelect: 'none',
                                whiteSpace: 'nowrap'
                              }}
                            >
                              {col.label} {positionsSortBy === col.key && (positionsSortOrder === 'asc' ? '▲' : '▼')}
                            </th>
                          ))}
                          <th style={{ padding: '12px', textAlign: 'center', fontSize: '12px', fontWeight: 600, color: '#6b7280', borderBottom: '1px solid #e5e7eb', width: '120px' }}>
                            Signals
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {getSortedAndFilteredPositions().map((pos: Position) => {
                          const currencySymbol = pos.currency === 'EUR' ? '€' : pos.currency === 'GBP' ? '£' : '$';
                          const signals = signalsBySymbol[pos.symbol] ?? [];
                          const hasData = signals.length > 0;
                          const fired = countFired(signals);
                          const expanded = expandedSignalSymbols.has(pos.symbol);
                          return (
                            <Fragment key={pos.symbol}>
                              <tr
                                style={{ borderBottom: '1px solid #e5e7eb', cursor: 'pointer', background: fired > 0 && expanded ? '#fff7f7' : undefined }}
                                onClick={() => setSelectedSymbol(pos.symbol)}
                              >
                                <td style={{ padding: '12px', fontSize: '14px', fontWeight: '600', color: '#1f2937' }}>
                                  {pos.symbol}
                                  <span style={{ fontSize: '11px', color: '#9ca3af', fontWeight: '400', marginLeft: '6px' }}>{pos.currency}</span>
                                </td>
                                <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', color: '#1f2937' }}>
                                  {pos.quantity.toFixed(0)}
                                </td>
                                <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', color: '#1f2937' }}>
                                  {currencySymbol}{pos.cost_basis_price.toFixed(2)}
                                </td>
                                <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', fontWeight: '500', color: '#1f2937' }}>
                                  {currencySymbol}{(pos.position_value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </td>
                                <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', fontWeight: '500', color: pos.unrealized_pnl >= 0 ? '#16a34a' : '#dc2626' }}>
                                  {pos.unrealized_pnl >= 0 ? '+' : ''}{currencySymbol}{(pos.unrealized_pnl || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </td>
                                <td style={{ padding: '12px', textAlign: 'center' }}>
                                  <SignalPill firedCount={fired} hasData={hasData} expanded={expanded} onToggle={() => toggleSignalExpand(pos.symbol)} />
                                </td>
                              </tr>
                              {expanded && hasData && fired > 0 && (
                                <SignalsExpandPanel signals={signals} currency={pos.currency} colSpan={6} />
                              )}
                            </Fragment>
                          );
                        })}
                      </tbody>
                      <tfoot>
                        {(() => {
                          const filteredPos = getSortedAndFilteredPositions();
                          const usdPositions = filteredPos.filter(p => p.currency === 'USD');
                          const eurPositions = filteredPos.filter(p => p.currency === 'EUR');
                          const otherPositions = filteredPos.filter(p => p.currency !== 'USD' && p.currency !== 'EUR');
                          
                          const usdTotal = usdPositions.reduce((sum, pos) => sum + (pos.position_value || 0), 0);
                          const usdPnl = usdPositions.reduce((sum, pos) => sum + (pos.unrealized_pnl || 0), 0);
                          const eurTotal = eurPositions.reduce((sum, pos) => sum + (pos.position_value || 0), 0);
                          const eurPnl = eurPositions.reduce((sum, pos) => sum + (pos.unrealized_pnl || 0), 0);
                          const otherTotal = otherPositions.reduce((sum, pos) => sum + (pos.position_value || 0), 0);
                          const otherPnl = otherPositions.reduce((sum, pos) => sum + (pos.unrealized_pnl || 0), 0);
                          
                          return (
                            <>
                              {usdPositions.length > 0 && (
                                <tr style={{ backgroundColor: '#f9fafb', borderTop: '2px solid #d1d5db' }}>
                                  <td colSpan={3} style={{ padding: '12px', fontSize: '14px', fontWeight: '700', color: '#1f2937' }}>
                                    TOTAL USD ({usdPositions.length} positions)
                                  </td>
                                  <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', fontWeight: '700', color: '#1f2937' }}>
                                    ${usdTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                  </td>
                                  <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', fontWeight: '700', color: usdPnl >= 0 ? '#16a34a' : '#dc2626' }}>
                                    {usdPnl >= 0 ? '+' : ''}${usdPnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                  </td>
                                  <td style={{ padding: '12px' }} />
                                </tr>
                              )}
                              {eurPositions.length > 0 && (
                                <tr style={{ backgroundColor: '#f9fafb', borderTop: usdPositions.length === 0 ? '2px solid #d1d5db' : '1px solid #e5e7eb' }}>
                                  <td colSpan={3} style={{ padding: '12px', fontSize: '14px', fontWeight: '700', color: '#1f2937' }}>
                                    TOTAL EUR ({eurPositions.length} positions)
                                  </td>
                                  <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', fontWeight: '700', color: '#1f2937' }}>
                                    €{eurTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                  </td>
                                  <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', fontWeight: '700', color: eurPnl >= 0 ? '#16a34a' : '#dc2626' }}>
                                    {eurPnl >= 0 ? '+' : ''}€{eurPnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                  </td>
                                  <td style={{ padding: '12px' }} />
                                </tr>
                              )}
                              {otherPositions.length > 0 && (
                                <tr style={{ backgroundColor: '#f9fafb', borderTop: (usdPositions.length === 0 && eurPositions.length === 0) ? '2px solid #d1d5db' : '1px solid #e5e7eb' }}>
                                  <td colSpan={3} style={{ padding: '12px', fontSize: '14px', fontWeight: '700', color: '#1f2937' }}>
                                    TOTAL OTHER ({otherPositions.length} positions)
                                  </td>
                                  <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', fontWeight: '700', color: '#1f2937' }}>
                                    ${otherTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                  </td>
                                  <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', fontWeight: '700', color: otherPnl >= 0 ? '#16a34a' : '#dc2626' }}>
                                    {otherPnl >= 0 ? '+' : ''}${otherPnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                  </td>
                                  <td style={{ padding: '12px' }} />
                                </tr>
                              )}
                            </>
                          );
                        })()}
                      </tfoot>
                    </table>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '32px', color: '#9ca3af', backgroundColor: '#f9fafb', borderRadius: '8px' }}>
                    <p>No IBKR positions loaded.</p>
                    <p style={{ fontSize: '12px' }}>Import trades via &quot;Load Data&quot; tab to sync positions from IBKR.</p>
                  </div>
                )}
              </div>

              {/* Disclaimer */}
              <div style={{ padding: '12px 16px', backgroundColor: '#f9fafb', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
                <p style={{ fontSize: '11px', color: '#9ca3af' }}>
                  ℹ️ Positions and cost basis are imported directly from IBKR (source of truth).
                </p>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
