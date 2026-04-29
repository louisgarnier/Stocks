"use client";

import { useEffect, useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

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
  const symbolForBenchmark = data.universe?.benchmark ?? "—";
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">About</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-1">
          <div className="flex flex-wrap gap-1 mb-2">
            {data.universe?.sources.map((s) => (
              <Badge key={s} variant="outline" className="text-xs">{s}</Badge>
            )) ?? null}
          </div>
          <p className="text-xs text-muted-foreground">
            Sector: {data.universe?.sector ?? "—"}
            {" · "}Currency: {data.universe?.currency ?? "—"}
            {" · "}Benchmark for MRSI: {symbolForBenchmark}
          </p>
        </CardContent>
      </Card>

      {data.is_held && data.position && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Position</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 text-sm">
            <Stat label="Quantity" value={fmt(data.position.quantity)} />
            <Stat label="Avg cost" value={data.position.cost_basis_price != null ? `${fmtCur(data.position.cost_basis_price, data.position.currency)}` : "—"} />
            <Stat label="Market value" value={data.position.position_value != null ? fmtCur(data.position.position_value, data.position.currency) : "—"} />
            <Stat
              label="Unrealized P&L"
              value={data.position.unrealized_pnl != null ? `${data.position.unrealized_pnl >= 0 ? "+" : ""}${fmtCur(data.position.unrealized_pnl, data.position.currency)}` : "—"}
              colorClass={data.position.unrealized_pnl != null ? (data.position.unrealized_pnl >= 0 ? "text-green-600" : "text-red-600") : undefined}
            />
          </CardContent>
        </Card>
      )}

      {data.is_held && data.transactions.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Transactions ({data.transactions.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border max-h-72 overflow-auto">
              <Table>
                <TableHeader className="sticky top-0 bg-card">
                  <TableRow>
                    <TableHead className="text-xs">Date</TableHead>
                    <TableHead className="text-right text-xs">Side</TableHead>
                    <TableHead className="text-right text-xs">Qty</TableHead>
                    <TableHead className="text-right text-xs">Price</TableHead>
                    <TableHead className="text-right text-xs">Proceeds</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.transactions.map((t) => (
                    <TableRow key={t.transaction_id}>
                      <TableCell className="text-xs font-mono">{t.trade_date}</TableCell>
                      <TableCell className={`text-right text-xs font-semibold ${t.quantity >= 0 ? "text-green-600" : "text-red-600"}`}>
                        {t.quantity >= 0 ? "BUY" : "SELL"}
                      </TableCell>
                      <TableCell className="text-right text-xs font-mono tabular-nums">{fmt(Math.abs(t.quantity))}</TableCell>
                      <TableCell className="text-right text-xs font-mono tabular-nums">{t.t_price != null ? t.t_price.toFixed(2) : "—"}</TableCell>
                      <TableCell className="text-right text-xs font-mono tabular-nums">{t.proceeds != null ? t.proceeds.toFixed(2) : "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Indicator + bars cards land in Tasks 5 and 6 */}
    </div>
  );
}

function Stat({ label, value, colorClass }: { label: string; value: string; colorClass?: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className={`font-mono font-semibold tabular-nums ${colorClass ?? ""}`}>{value}</p>
    </div>
  );
}

function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function fmtCur(n: number, currency: string | null | undefined): string {
  const sym = currency === "EUR" ? "€" : currency === "GBP" ? "£" : "$";
  return `${sym}${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
