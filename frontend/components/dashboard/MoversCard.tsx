'use client';

import { Card, CardContent } from '@/components/ui/card';
import { formatPct, formatSignedEur, type Mover } from '@/lib/dashboard';

const MAX_PER_SIDE = 5;

interface Props {
  data: Mover[]
  onSelectSymbol: (symbol: string) => void
}

function Row({ m, onSelectSymbol }: { m: Mover; onSelectSymbol: (symbol: string) => void }) {
  const color = m.change_pct >= 0 ? 'text-green-600' : 'text-red-600';
  return (
    <div
      onClick={() => onSelectSymbol(m.symbol)}
      className="flex cursor-pointer items-center justify-between"
    >
      <span>
        <b>{m.symbol}</b> <span className="text-muted-foreground">${m.close.toFixed(2)}</span>
      </span>
      <b className={color}>
        {formatPct(m.change_pct)} · {formatSignedEur(m.day_pnl_eur)}
      </b>
    </div>
  );
}

export function MoversCard({ data, onSelectSymbol }: Props) {
  const gainers = data
    .filter((m) => m.change_pct >= 0)
    .sort((a, b) => b.change_pct - a.change_pct)
    .slice(0, MAX_PER_SIDE);
  const losers = data
    .filter((m) => m.change_pct < 0)
    .sort((a, b) => a.change_pct - b.change_pct)
    .slice(0, MAX_PER_SIDE);

  return (
    <Card className="py-0">
      <CardContent className="p-5">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Today&apos;s movers — holdings
        </div>
        <div className="mt-3 flex flex-col gap-1.5 text-xs tabular-nums">
          {data.length === 0 && <div className="text-muted-foreground">No price data yet.</div>}
          {gainers.map((m) => (
            <Row key={m.symbol} m={m} onSelectSymbol={onSelectSymbol} />
          ))}
          {gainers.length > 0 && losers.length > 0 && <div className="my-1 border-t" />}
          {losers.map((m) => (
            <Row key={m.symbol} m={m} onSelectSymbol={onSelectSymbol} />
          ))}
        </div>
        <div className="mt-3 border-t pt-2.5 font-mono text-[10px] text-muted-foreground">
          click any row → detail sheet
        </div>
      </CardContent>
    </Card>
  );
}
