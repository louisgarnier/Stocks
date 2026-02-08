/**
 * API Client for Frontend - IBKR Portfolio Tracker
 * 
 * ⚠️ Before making changes, read: ../../docs/workflow/BEST_PRACTICES.md
 * Always check with the user before modifying this file.
 * 
 * Handles all communication with the backend API
 */

import { logAPI } from '@/src/utils/logger';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Generic fetch wrapper with error handling and logging
 */
async function fetchAPI<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const method = options?.method || 'GET';
  
  logAPI.request(method, endpoint);
  
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      logAPI.error(endpoint, `${response.status} ${response.statusText}`);
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      logAPI.success(endpoint);
      return {} as T;
    }

    logAPI.success(endpoint);
    return await response.json();
  } catch (error) {
    logAPI.error(endpoint, error);
    throw error;
  }
}

/**
 * Health check API
 */
export interface HealthResponse {
  status: string;
  database: string;
  database_path: string;
  transactions: number;
  positions: number;
}

export const healthAPI = {
  check: async (): Promise<HealthResponse> => {
    return fetchAPI<HealthResponse>('/health');
  },
};

/**
 * Transactions API (Phase 1)
 */
export interface Transaction {
  id: number;
  transaction_id: string;
  symbol: string;
  trade_date: string;
  quantity: number;
  t_price: number;
  proceeds: number;
  comm_fee: number;
  updated_quantity?: number;
  updated_t_price?: number;
  stock_splits_applied?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
}

export const transactionsAPI = {
  list: async (page = 1, limit = 50): Promise<PaginatedResponse<Transaction>> => {
    return fetchAPI<PaginatedResponse<Transaction>>(`/api/transactions?page=${page}&limit=${limit}`);
  },
};

/**
 * Flex API (Phase 1)
 */
export interface FlexStatus {
  last_fetch_at: string | null;
  last_fetch_status: string;
  last_fetch_message: string | null;
  records_fetched: number;
}

export const flexAPI = {
  fetch: async (): Promise<{ success: boolean; message: string; records: number }> => {
    return fetchAPI('/api/flex/fetch', { method: 'POST' });
  },
  status: async (): Promise<FlexStatus> => {
    return fetchAPI<FlexStatus>('/api/flex/status');
  },
};

/**
 * Positions API (Phase 4)
 */
export interface Position {
  id: number;
  symbol: string;
  total_updated_quantity: number;
  transaction_count: number;
}

export const positionsAPI = {
  list: async (): Promise<Position[]> => {
    return fetchAPI<Position[]>('/api/positions');
  },
};




