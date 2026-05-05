export type SyncAction = 'ibkr' | 'market_data' | 'analytics' | 'manual_add'
export type SyncStatus = 'success' | 'partial' | 'error'

export interface SyncRun {
  id: number
  started_at: string
  finished_at: string | null
  duration_ms: number | null
  action: SyncAction | string
  status: SyncStatus | string
  summary: string | null
  details: unknown | null
}

export interface SyncRunsResponse {
  items: SyncRun[]
  count: number
  total: number
}

const ACTION_LABELS: Record<string, string> = {
  ibkr: 'Sync IBKR',
  market_data: 'Sync market data',
  analytics: 'Recompute analytics',
  manual_add: 'Add manual ticker',
}

export function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action
}

const STATUS_STYLES: Record<string, { bg: string; fg: string; label: string }> = {
  success: { bg: '#dcfce7', fg: '#15803d', label: '✅ Success' },
  partial: { bg: '#fef3c7', fg: '#92400e', label: '⚠️ Partial' },
  error:   { bg: '#fef2f2', fg: '#dc2626', label: '❌ Error' },
}

export function statusStyle(status: string): { bg: string; fg: string; label: string } {
  return STATUS_STYLES[status] ?? { bg: '#f3f4f6', fg: '#6b7280', label: status }
}

export function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '—'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.round(ms / 1000)}s`
}

export async function fetchSyncRuns(limit = 50): Promise<SyncRunsResponse> {
  const res = await fetch(`/api/proxy/api/sync/runs?limit=${limit}`)
  if (!res.ok) throw new Error(`fetchSyncRuns: HTTP ${res.status}`)
  return res.json()
}
