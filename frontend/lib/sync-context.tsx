'use client';

import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';

export type StepKey = 'fundamentals' | 'technical' | 'compute' | 'all' | 'ibkr';

export interface StepState {
  running: boolean;
  status: string | null;
  error: boolean;
}

const INITIAL: Record<StepKey, StepState> = {
  fundamentals: { running: false, status: null, error: false },
  technical: { running: false, status: null, error: false },
  compute: { running: false, status: null, error: false },
  all: { running: false, status: null, error: false },
  ibkr: { running: false, status: null, error: false },
};

interface SyncContextValue {
  state: Record<StepKey, StepState>;
  anyRunning: boolean;
  syncVersion: number;
  runFundamentals: () => void;
  runTechnical: () => void;
  runCompute: () => void;
  runAll: () => void;
  runIbkr: () => void;
}

const SyncContext = createContext<SyncContextValue | null>(null);

async function post(path: string): Promise<void> {
  const res = await fetch(`/api/proxy/api/sync/${path}`, { method: 'POST' });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof body === 'object' ? JSON.stringify(body) : String(body));
}

async function runTechnicalSteps(): Promise<void> {
  await post('market-data'); // prices
  await post('analytics'); // indicators
}

export function SyncProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<Record<StepKey, StepState>>(INITIAL);
  const [syncVersion, setSyncVersion] = useState(0);
  // Synchronous single-flight guard. A ref (not derived from state) so the
  // check is race-free and idempotent under React StrictMode's dev double-
  // invocation — the async work is fired from the event handler, NOT from
  // inside a setState updater (updaters must stay pure).
  const runningRef = useRef(false);

  const anyRunning = useMemo(() => Object.values(state).some((s) => s.running), [state]);

  const run = useCallback((key: StepKey, label: string, fn: () => Promise<void>) => {
    if (runningRef.current) return; // ignore overlapping starts
    runningRef.current = true;
    setState((s) => ({ ...s, [key]: { running: true, status: 'Running…', error: false } }));
    void (async () => {
      try {
        toast(`${label} sync started`);
        await fn();
        setState((s) => ({ ...s, [key]: { running: false, status: 'Done ✓', error: false } }));
        setSyncVersion((v) => v + 1);
        toast.success(`${label} sync complete`);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setState((s) => ({ ...s, [key]: { running: false, status: 'Failed', error: true } }));
        toast.error(`${label} sync failed`, { description: msg });
      } finally {
        runningRef.current = false;
      }
    })();
  }, []);

  const value = useMemo<SyncContextValue>(
    () => ({
      state,
      anyRunning,
      syncVersion,
      runFundamentals: () => run('fundamentals', 'Fundamentals', () => post('fundamentals')),
      runTechnical: () => run('technical', 'Technical', runTechnicalSteps),
      runCompute: () => run('compute', 'Compute', () => post('screen')),
      runAll: () =>
        run('all', 'Full', async () => {
          await runTechnicalSteps();
          await post('fundamentals');
          await post('screen');
        }),
      runIbkr: () => run('ibkr', 'IBKR', () => post('ibkr')),
    }),
    [state, anyRunning, syncVersion, run],
  );

  return <SyncContext.Provider value={value}>{children}</SyncContext.Provider>;
}

export function useSync(): SyncContextValue {
  const ctx = useContext(SyncContext);
  if (!ctx) throw new Error('useSync must be used within SyncProvider');
  return ctx;
}
