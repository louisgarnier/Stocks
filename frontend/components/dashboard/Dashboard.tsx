'use client';

import { useCallback, useEffect, useState } from 'react';
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

interface Props {
  onSelectSymbol: (symbol: string) => void
}

export function Dashboard({ onSelectSymbol }: Props) {
  const [activeWindow, setActiveWindow] = useState<DashboardWindow>('6M');
  const [allocMode, setAllocMode] = useState<AllocationMode>('sector');
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (w: DashboardWindow) => {
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchDashboard(w);
      setData(payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(activeWindow);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeWindow]);

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
      <StalenessChips asOf={data.as_of} />

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
