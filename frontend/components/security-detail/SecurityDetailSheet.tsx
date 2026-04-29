"use client";

import { useEffect, useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";

export interface SecurityDetail {
  symbol: string;
  is_held: boolean;
  universe: {
    symbol: string;
    name: string | null;
    sector: string | null;
    currency: string | null;
    exchange: string | null;
    benchmark: string | null;
    sources: string[];
    enabled: boolean;
    added_at: string;
    last_synced_at: string | null;
  } | null;
  position: {
    quantity: number;
    cost_basis_money: number | null;
    cost_basis_price: number | null;
    mark_price: number | null;
    position_value: number | null;
    unrealized_pnl: number | null;
    currency: string | null;
  } | null;
  transactions: Array<{
    transaction_id: string;
    trade_date: string;
    quantity: number;
    t_price: number | null;
    proceeds: number | null;
    comm_fee: number | null;
    currency: string | null;
  }>;
  indicators: {
    time: string;
    ma_50: number | null;
    ma_100: number | null;
    ma_150: number | null;
    ma_200: number | null;
    bb_upper_20: number | null;
    bb_lower_20: number | null;
    bb_width: number | null;
    rsi_14: number | null;
    mrsi: number | null;
    atr_14: number | null;
    volume_ma_20: number | null;
  } | null;
  bars: Array<{
    time: string;
    open: number | null;
    high: number | null;
    low: number | null;
    close: number | null;
    adj_close: number | null;
    volume: number | null;
  }>;
}

interface Props {
  symbol: string | null;
  onClose: () => void;
}

export function SecurityDetailSheet({ symbol, onClose }: Props) {
  const [data, setData] = useState<SecurityDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`/api/proxy/api/security/${encodeURIComponent(symbol)}/detail`)
      .then(async (r) => {
        if (!r.ok) {
          throw new Error(`HTTP ${r.status}: ${await r.text()}`);
        }
        return r.json();
      })
      .then((d: SecurityDetail) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  return (
    <Sheet open={symbol !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full sm:max-w-2xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <span className="font-mono">{symbol ?? ""}</span>
            {data && (
              <Badge variant={data.is_held ? "default" : "secondary"}>
                {data.is_held ? "Held" : "Not held"}
              </Badge>
            )}
            {data?.universe?.currency && (
              <Badge variant="outline" className="text-xs">{data.universe.currency}</Badge>
            )}
          </SheetTitle>
          {data?.universe?.name && (
            <p className="text-sm text-muted-foreground">{data.universe.name}</p>
          )}
        </SheetHeader>

        <div className="p-4 space-y-4">
          {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {error && <p className="text-sm text-destructive">Error: {error}</p>}
          {data && <SecurityDetailContent data={data} />}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function SecurityDetailContent({ data }: { data: SecurityDetail }) {
  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Sources: {data.universe?.sources.join(", ") ?? "—"}
        {data.universe?.sector ? ` · Sector: ${data.universe.sector}` : ""}
      </p>
      <p className="text-xs text-muted-foreground">
        Detail rendering: pending Tasks 4–6.
      </p>
    </div>
  );
}
