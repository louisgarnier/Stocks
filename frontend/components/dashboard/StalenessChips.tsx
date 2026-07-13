'use client';

import { shortDate, relativeTime, type AsOf } from '@/lib/dashboard';
import { useSync, type StepKey } from '@/lib/sync-context';

const LABELS: Record<keyof AsOf, string> = {
  prices: 'prices',
  signals: 'signals',
  fundamentals: 'fundamentals',
  ibkr: 'IBKR',
};

// Which provider step each chip triggers.
const STEP_FOR: Record<keyof AsOf, StepKey> = {
  prices: 'technical',
  signals: 'compute',
  fundamentals: 'fundamentals',
  ibkr: 'ibkr',
};

export function StalenessChips({
  asOf,
  ibkrExternalSyncing,
}: {
  asOf: AsOf
  ibkrExternalSyncing?: boolean
}) {
  const { state, anyRunning, runTechnical, runCompute, runFundamentals, runIbkr } = useSync();
  const ACTION: Record<StepKey, () => void> = {
    technical: runTechnical,
    compute: runCompute,
    fundamentals: runFundamentals,
    ibkr: runIbkr,
    all: () => {},
  };
  const keys = Object.keys(LABELS) as (keyof AsOf)[];
  return (
    <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
      {keys.map((key) => {
        const { date, checked_at, level } = asOf[key];
        const step = STEP_FOR[key];
        const running = state[step].running;
        const disabled = anyRunning || (key === 'ibkr' && !!ibkrExternalSyncing);
        const cls =
          level === 'fresh'
            ? 'bg-success/15 text-success'
            : level === 'stale'
              ? 'bg-warning/15 text-warning'
              : 'bg-muted text-muted-foreground';
        return (
          <button
            key={key}
            type="button"
            onClick={ACTION[step]}
            disabled={disabled}
            title={`Refresh ${LABELS[key]}`}
            className={`rounded-xl px-3 py-1.5 text-left leading-tight ${cls} ${disabled ? 'cursor-default opacity-70' : 'cursor-pointer hover:brightness-95'}`}
          >
            <span className="block">
              {running ? '…' : '●'} {LABELS[key]}{' '}
              <span className="font-semibold">{running ? 'syncing' : shortDate(date)}</span>
            </span>
            <span className="block text-[10px] opacity-75">
              {running ? ' ' : `checked ${relativeTime(checked_at)}`}
            </span>
          </button>
        );
      })}
    </div>
  );
}
