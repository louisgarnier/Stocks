'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  fetchDashboard,
  type AllocationMode,
  type DashboardPayload,
  type DashboardWindow,
} from '@/lib/dashboard';
import { NetWorthCard } from './NetWorthCard';
import { AllocationDonut } from './AllocationDonut';
import { PerformanceChart } from './PerformanceChart';
import { ActionQueue } from './ActionQueue';
import { MoversCard } from './MoversCard';
import { StalenessChips } from './StalenessChips';
import { useSync } from '@/lib/sync-context';

interface Props {
  onSelectSymbol: (symbol: string) => void
}

export function Dashboard({ onSelectSymbol }: Props) {
  const [activeWindow, setActiveWindow] = useState<DashboardWindow>('6M');
  const [allocMode, setAllocMode] = useState<AllocationMode>('sector');
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const requestSeq = useRef(0);
  const { runAll, anyRunning, syncVersion } = useSync();

  useEffect(() => {
    const seq = ++requestSeq.current;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchDashboard(activeWindow)
      .then((d) => {
        if (!cancelled && seq === requestSeq.current) setData(d);
      })
      .catch((e) => {
        if (!cancelled && seq === requestSeq.current) {
          setError(e instanceof Error ? e.message : 'Failed to load dashboard');
        }
      })
      .finally(() => {
        if (!cancelled && seq === requestSeq.current) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeWindow, syncVersion]);

  if (error) {
    return (
      <div className="p-6 text-sm text-red-600">
        Failed to load dashboard: {error}
      </div>
    );
  }

  if (loading && !data) {
    return <div className="p-6 text-sm text-muted-foreground">Loading dashboard…</div>;
  }

  if (!data) return null;

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <StalenessChips asOf={data.as_of} />
        <button
          type="button"
          onClick={runAll}
          disabled={anyRunning}
          className="rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground disabled:opacity-60"
        >
          {anyRunning ? 'Syncing…' : 'Sync all'}
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.1fr_1fr_1.3fr]">
        <NetWorthCard data={data.net_worth} />
        <AllocationDonut data={data.allocation[allocMode]} mode={allocMode} onMode={setAllocMode} />
        <PerformanceChart
          data={data.performance}
          activeWindow={activeWindow}
          onWindowChange={setActiveWindow}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.6fr_1fr]">
        <ActionQueue data={data.actions} onSelectSymbol={onSelectSymbol} />
        <MoversCard data={data.movers} onSelectSymbol={onSelectSymbol} />
      </div>
    </div>
  );
}
