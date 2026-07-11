'use client';

import { Card, CardContent } from '@/components/ui/card';
import { verdictColors, verdictLabel, type Verdict } from '@/lib/screener';
import { formatPct, type Actions } from '@/lib/dashboard';

interface Props {
  data: Actions
  onSelectSymbol: (symbol: string) => void
  onOpenPortfolio?: () => void
  onOpenResearch?: () => void
}

export function ActionQueue({ data, onSelectSymbol, onOpenPortfolio, onOpenResearch }: Props) {
  const sell = data.sell;
  const topSell = sell.slice(0, 3);
  const restSell = sell.slice(3);
  const critical = sell.filter((s) => s.n_fired >= 5).length;

  const buy = data.buy;
  const topBuy = buy.slice(0, 4);
  const restBuy = buy.slice(4);
  const strongBuyCount = buy.filter((b) => b.verdict === 'strong_buy').length;

  return (
    <Card className="py-0">
      <CardContent className="p-5">
        <div className="flex items-baseline justify-between">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Action queue — today
          </div>
          <span className="text-[11px] text-muted-foreground">
            sell rules on holdings · buy verdicts from screener
          </span>
        </div>

        <div className="mt-3 flex flex-col gap-2">
          <div className="text-xs font-bold text-red-600">
            ▼ SELL SIGNALS — {sell.length} holding{sell.length === 1 ? '' : 's'} fired
            {critical > 0 ? `, ${critical} critical` : ''}
          </div>
          {topSell.length === 0 && (
            <div className="text-xs text-muted-foreground">No sell signals firing today.</div>
          )}
          {topSell.map((s) => (
            <div
              key={s.symbol}
              onClick={() => onSelectSymbol(s.symbol)}
              className="flex cursor-pointer items-center justify-between rounded-md border border-red-200 bg-red-50 px-3 py-2 tabular-nums"
            >
              <div>
                <b>{s.symbol}</b>{' '}
                <span className="text-xs text-muted-foreground">
                  {s.quantity} sh · {formatPct(s.return_pct)} vs cost
                </span>
              </div>
              <div className="font-mono text-xs text-red-600">
                {s.n_fired} fired: {s.fired.join(' · ')}
              </div>
            </div>
          ))}
          {restSell.length > 0 && (
            <div className="pl-0.5 text-xs text-muted-foreground">
              + {restSell.length} more ({restSell.map((s) => s.symbol).join(', ')}) →{' '}
              <span className="cursor-pointer text-primary" onClick={onOpenPortfolio}>
                open Portfolio
              </span>
            </div>
          )}
        </div>

        <div className="mt-4 flex flex-col gap-2">
          <div className="text-xs font-bold text-green-600">
            ▲ BUY CANDIDATES — top screener verdicts
            {strongBuyCount > 0 ? ` (${strongBuyCount} strong buy)` : ''}
          </div>
          {topBuy.length === 0 && (
            <div className="text-xs text-muted-foreground">No buy candidates today.</div>
          )}
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {topBuy.map((b) => {
              const colors = verdictColors(b.verdict as Verdict | null);
              return (
                <div
                  key={b.symbol}
                  onClick={() => onSelectSymbol(b.symbol)}
                  className="flex cursor-pointer items-center justify-between rounded-md border border-green-200 bg-green-50 px-3 py-2"
                >
                  <div>
                    <b>{b.symbol}</b>{' '}
                    {b.name && <span className="text-xs text-muted-foreground">{b.name}</span>}
                  </div>
                  <div className="font-mono text-xs">
                    <span style={{ color: colors.fg }} className="font-bold">
                      {verdictLabel(b.verdict as Verdict | null).toUpperCase()}
                    </span>{' '}
                    · {b.score_total != null ? Math.round(b.score_total) : '—'}
                    {b.gates_passed != null ? ` · gates ${b.gates_passed}` : ''}
                  </div>
                </div>
              );
            })}
          </div>
          {restBuy.length > 0 && (
            <div className="text-xs text-muted-foreground">
              + {restBuy.map((b) => b.symbol).join(', ')} →{' '}
              <span className="cursor-pointer text-primary" onClick={onOpenResearch}>
                open Research
              </span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
