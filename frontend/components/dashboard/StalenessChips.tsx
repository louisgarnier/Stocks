'use client';

import { relativeStaleness, type AsOf } from '@/lib/dashboard';

const LABELS: Record<keyof AsOf, string> = {
  prices: 'prices',
  signals: 'signals',
  fundamentals: 'fundamentals',
  ibkr: 'IBKR',
};

export function StalenessChips({ asOf }: { asOf: AsOf }) {
  const keys = Object.keys(LABELS) as (keyof AsOf)[];
  return (
    <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
      {keys.map((key) => {
        const { label, level } = relativeStaleness(asOf[key]);
        const cls =
          level === 'fresh'
            ? 'bg-success/15 text-success'
            : level === 'stale'
              ? 'bg-warning/15 text-warning'
              : 'bg-muted text-muted-foreground';
        return (
          <span key={key} className={`rounded-full px-2.5 py-1 ${cls}`}>
            ● {LABELS[key]} {label}
          </span>
        );
      })}
    </div>
  );
}
