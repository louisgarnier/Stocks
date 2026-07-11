'use client';

import { Card, CardContent } from '@/components/ui/card';
import { formatEur, formatPct, formatSignedEur, type NetWorth } from '@/lib/dashboard';

export function NetWorthCard({ data }: { data: NetWorth }) {
  const dayColor = data.day_change_eur >= 0 ? 'text-green-600' : 'text-red-600';
  return (
    <Card className="py-0">
      <CardContent className="p-5">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Net worth · EUR
        </div>
        <div className="mt-2 text-4xl font-extrabold tracking-tight tabular-nums">
          {formatEur(data.value_eur)}
        </div>
        <div className={`mt-1 text-sm font-semibold ${dayColor}`}>
          {formatSignedEur(data.day_change_eur)} today{' '}
          <span className="font-normal text-muted-foreground">
            ({formatPct(data.day_change_pct)})
          </span>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2.5 border-t pt-4">
          <div>
            <div className="text-xs text-muted-foreground">Unrealized P&amp;L</div>
            <div
              className={`text-base font-bold tabular-nums ${
                data.unrealized_pnl_eur != null
                  ? data.unrealized_pnl_eur >= 0
                    ? 'text-green-600'
                    : 'text-red-600'
                  : 'text-muted-foreground'
              }`}
            >
              {formatSignedEur(data.unrealized_pnl_eur)}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Positions</div>
            <div className="text-base font-bold tabular-nums">{data.positions}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">USD exposure</div>
            <div className="text-base font-bold tabular-nums">
              {data.usd_exposure_pct.toFixed(1)}%
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Cash</div>
            <div className="text-base font-bold text-muted-foreground">
              — <span className="text-[10px]">(not tracked yet)</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
