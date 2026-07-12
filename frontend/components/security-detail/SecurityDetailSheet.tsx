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
    last_updated: string | null;
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
  fundamentals: {
    gross_margin: number | null;
    roe: number | null;
    roic: number | null;
    levered_fcf_margin: number | null;
    interest_cover: number | null;
    eps_5y_growth: number | null;
    gates_passed: number | null;
    gates_total: number | null;
    market_cap: number | null;
    trailing_pe: number | null;
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
  technical: {
    momentum_5d: number | null;
    momentum_20d: number | null;
    momentum_60d: number | null;
    multi_factor_momentum: number | null;
    ma_cross_status: string | null;
    trend_aligned: number | null;
    volume_spike: number | null;
    near_52w_high: number | null;
    dist_from_52w_high: number | null;
    mrsi: number | null;
    signal_date: string | null;
  } | null;
  breakout: {
    status: string;
    direction: string;
    strength: number | null;
    volume_ratio: number | null;
    support: number | null;
    resistance: number | null;
    range_pct: number | null;
    duration_days: number | null;
    date: string | null;
  };
  zigzag: {
    deviation_pct: number;
    window_days: number;
    swings: Array<{ date: string; price: number; type: string }>;
  };
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
          {data && data.bars.length > 0 && <LastCloseHeader data={data} />}
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
            <p className="text-xs text-muted-foreground">
              as of {fmtDate(data.position.last_updated)} · IBKR Flex (T-1, end-of-day)
            </p>
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

      {data.indicators && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Indicators (as of {data.indicators.time})</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-3 gap-3 text-sm">
            <Stat label="MA 50" value={fmt(data.indicators.ma_50)} />
            <Stat label="MA 100" value={fmt(data.indicators.ma_100)} />
            <Stat label="MA 150" value={fmt(data.indicators.ma_150)} />
            <Stat label="MA 200" value={fmt(data.indicators.ma_200)} />
            <Stat label="BB upper" value={fmt(data.indicators.bb_upper_20)} />
            <Stat label="BB lower" value={fmt(data.indicators.bb_lower_20)} />
            <Stat label="BB width" value={data.indicators.bb_width != null ? data.indicators.bb_width.toFixed(3) : "—"} />
            <Stat label="RSI(14)" value={data.indicators.rsi_14 != null ? data.indicators.rsi_14.toFixed(1) : "—"} />
            <Stat
              label="MRSI"
              value={
                data.indicators.mrsi != null
                  ? `${data.indicators.mrsi > 0 ? "+" : ""}${data.indicators.mrsi.toFixed(3)}`
                  : "—"
              }
              colorClass={
                data.indicators.mrsi != null
                  ? data.indicators.mrsi > 0
                    ? "text-green-600"
                    : data.indicators.mrsi < 0
                      ? "text-red-600"
                      : undefined
                  : undefined
              }
            />
            <Stat label="ATR(14)" value={data.indicators.atr_14 != null ? data.indicators.atr_14.toFixed(2) : "—"} />
            <Stat label="Vol MA(20)" value={fmt(data.indicators.volume_ma_20)} />
          </CardContent>
        </Card>
      )}
      {!data.indicators && (
        <Card>
          <CardContent className="text-sm text-muted-foreground py-4">
            No indicators yet for {data.symbol}. Run &quot;Sync indicators&quot; from the
            Sync IBKR pipeline.
          </CardContent>
        </Card>
      )}

      <TechnicalSignalsCard data={data} />

      {data.fundamentals && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Fundamentals</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-3 gap-3 text-sm">
            <Stat label="Gross margin" value={pct(data.fundamentals.gross_margin)} />
            <Stat label="ROE" value={pct(data.fundamentals.roe)} />
            <Stat label="ROIC" value={pct(data.fundamentals.roic)} />
            <Stat label="Levered FCF margin" value={pct(data.fundamentals.levered_fcf_margin)} />
            <Stat
              label="Interest cover"
              value={data.fundamentals.interest_cover != null ? `${data.fundamentals.interest_cover.toFixed(1)}×` : "—"}
            />
            <Stat label="EPS 5y growth" value={pct(data.fundamentals.eps_5y_growth)} />
            <Stat
              label="Quality gates"
              value={
                data.fundamentals.gates_passed != null && data.fundamentals.gates_total != null
                  ? `${data.fundamentals.gates_passed}/${data.fundamentals.gates_total}`
                  : "—"
              }
            />
            <Stat label="Market cap" value={compact(data.fundamentals.market_cap)} />
            <Stat
              label="Trailing P/E"
              value={data.fundamentals.trailing_pe != null ? data.fundamentals.trailing_pe.toFixed(1) : "—"}
            />
          </CardContent>
        </Card>
      )}

      {data.bars.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Recent bars ({data.bars.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border max-h-72 overflow-auto">
              <Table>
                <TableHeader className="sticky top-0 bg-card">
                  <TableRow>
                    <TableHead className="text-xs">Date</TableHead>
                    <TableHead className="text-right text-xs">Open</TableHead>
                    <TableHead className="text-right text-xs">High</TableHead>
                    <TableHead className="text-right text-xs">Low</TableHead>
                    <TableHead className="text-right text-xs">Close</TableHead>
                    <TableHead className="text-right text-xs">Volume</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.bars.map((b) => (
                    <TableRow key={b.time}>
                      <TableCell className="text-xs font-mono">{b.time}</TableCell>
                      <TableCell className="text-right text-xs font-mono tabular-nums">{b.open != null ? b.open.toFixed(2) : "—"}</TableCell>
                      <TableCell className="text-right text-xs font-mono tabular-nums">{b.high != null ? b.high.toFixed(2) : "—"}</TableCell>
                      <TableCell className="text-right text-xs font-mono tabular-nums">{b.low != null ? b.low.toFixed(2) : "—"}</TableCell>
                      <TableCell className="text-right text-xs font-mono tabular-nums font-semibold">{b.close != null ? b.close.toFixed(2) : "—"}</TableCell>
                      <TableCell className="text-right text-xs font-mono tabular-nums">{b.volume != null ? b.volume.toLocaleString("en-US") : "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}
      {data.bars.length === 0 && (
        <Card>
          <CardContent className="text-sm text-muted-foreground py-4">
            No market data yet for {data.symbol}. Run &quot;Sync market data&quot; from
            the Configuration tab.
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function TechnicalSignalsCard({ data }: { data: SecurityDetail }) {
  const t = data.technical;
  const breakout = data.breakout ?? {
    status: "no_consolidation_patterns", direction: "none", strength: null,
    volume_ratio: null, support: null, resistance: null, range_pct: null,
    duration_days: null, date: null,
  };
  const zigzag = data.zigzag ?? { deviation_pct: 0, window_days: 0, swings: [] };
  const maCross = t?.ma_cross_status ?? null;
  const maCrossColor = maCross
    ? maCross.includes("Bullish")
      ? "text-green-600"
      : maCross.includes("Bearish")
        ? "text-red-600"
        : undefined
    : undefined;
  const breakoutCellColor =
    breakout.status === "no_consolidation_patterns"
      ? "text-muted-foreground"
      : breakout.direction === "bullish"
        ? "text-green-600"
        : breakout.direction === "bearish"
          ? "text-red-600"
          : undefined;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Technical signals</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="rounded-md border p-3">
          <p className="text-xs font-semibold text-muted-foreground">
            Signals{t?.signal_date ? ` as of ${t.signal_date}` : ""}
          </p>
          {t ? (
            <div className="grid grid-cols-3 gap-3 text-sm mt-2">
              <Stat label="Momentum 5d" value={signedPct(t.momentum_5d)} colorClass={signColor(t.momentum_5d)} />
              <Stat label="Momentum 20d" value={signedPct(t.momentum_20d)} colorClass={signColor(t.momentum_20d)} />
              <Stat label="Momentum 60d" value={signedPct(t.momentum_60d)} colorClass={signColor(t.momentum_60d)} />
              <Stat label="Multi-factor" value={signedNum(t.multi_factor_momentum)} colorClass={signColor(t.multi_factor_momentum)} />
              <Stat label="MA cross" value={maCross ?? "—"} colorClass={maCrossColor} />
              <Stat label="vs 52w high" value={signedPct(t.dist_from_52w_high)} colorClass={signColor(t.dist_from_52w_high)} />
              <Stat
                label="Breakout"
                value={breakout.status === "no_consolidation_patterns" ? "no pattern" : breakout.direction}
                colorClass={breakoutCellColor}
              />
              <Stat label="Volume spike" value={t.volume_spike == null ? "—" : t.volume_spike ? "yes" : "no"} />
              <Stat
                label={`MRSI vs ${data.universe?.benchmark ?? "benchmark"}`}
                value={t.mrsi != null ? `${t.mrsi > 0 ? "+" : ""}${t.mrsi.toFixed(3)}` : "—"}
                colorClass={signColor(t.mrsi)}
              />
            </div>
          ) : (
            <p className="text-sm text-muted-foreground mt-2">
              No technical signals yet for {data.symbol}. Run the screener to compute momentum &amp; trend signals.
            </p>
          )}
        </div>

        <div className="rounded-md border p-3">
          <p className="text-xs font-semibold text-muted-foreground">
            ZigZag swings <span className="font-normal">· {zigzag.window_days}d window · {zigzag.deviation_pct}% deviation</span>
          </p>
          {zigzag.swings.length > 0 ? (
            <>
              <svg width="100%" height={90} viewBox="0 0 400 90" preserveAspectRatio="none" className="mt-2">
                {zigzagPath(zigzag.swings) && (
                  <polyline points={zigzagPath(zigzag.swings)} fill="none" stroke="#4fd08d" strokeWidth="2" />
                )}
                {zigzagPoints(zigzag.swings).map((p, i) => (
                  <circle key={i} cx={p.x} cy={p.y} r={3} fill={p.type === "peak" ? "#4fd08d" : "#e88b83"} />
                ))}
              </svg>
              <p className="text-[10px] font-mono text-muted-foreground mt-2 leading-relaxed break-words">
                {zigzag.swings
                  .map((s) => `${s.type === "peak" ? "▲" : "▼"} ${s.date.slice(5)} @${s.price}`)
                  .join(" → ")}
              </p>
            </>
          ) : (
            <p className="text-sm text-muted-foreground mt-2">No swings detected in the current window.</p>
          )}
        </div>

        {breakout.status !== "no_consolidation_patterns" && (
          <div className="rounded-md border p-3">
            <p className="text-xs font-semibold flex items-center gap-2">
              Breakout
              <Badge variant={breakout.direction === "bullish" ? "default" : "secondary"} className="text-[10px]">
                {breakout.direction === "bullish" ? "▲" : breakout.direction === "bearish" ? "▼" : ""} {breakout.status}
                {breakout.date ? ` · ${breakout.date}` : ""}
              </Badge>
            </p>
            <div className="grid grid-cols-2 gap-3 text-sm mt-2">
              <Stat
                label="Consolidation base"
                value={
                  breakout.support != null && breakout.resistance != null
                    ? `${breakout.support.toFixed(2)} → ${breakout.resistance.toFixed(2)}`
                    : "—"
                }
              />
              <Stat
                label="Duration"
                value={breakout.duration_days != null ? `${breakout.duration_days} days` : "—"}
              />
              <Stat
                label="Breakout strength"
                value={breakout.strength != null ? `${breakout.strength > 0 ? "+" : ""}${breakout.strength.toFixed(2)}%` : "—"}
                colorClass={signColor(breakout.strength)}
              />
              <Stat
                label="Volume ratio"
                value={breakout.volume_ratio != null ? `${breakout.volume_ratio.toFixed(2)}×` : "—"}
              />
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function zigzagPoints(swings: Array<{ date: string; price: number; type: string }>) {
  if (swings.length === 0) return [];
  const w = 400;
  const h = 90;
  const prices = swings.map((s) => s.price);
  const [lo, hi] = [Math.min(...prices), Math.max(...prices)];
  const x = (i: number) => (swings.length === 1 ? w / 2 : (i / (swings.length - 1)) * (w - 20) + 10);
  const y = (v: number) => h - ((v - lo) / (hi - lo || 1)) * (h - 16) - 8;
  return swings.map((s, i) => ({ x: x(i), y: y(s.price), type: s.type }));
}

function zigzagPath(swings: Array<{ date: string; price: number; type: string }>) {
  const pts = zigzagPoints(swings);
  if (pts.length < 2) return "";
  return pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
}

function signColor(n: number | null | undefined): string | undefined {
  if (n == null) return undefined;
  if (n > 0) return "text-green-600";
  if (n < 0) return "text-red-600";
  return undefined;
}

function signedPct(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
}

function signedNum(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}`;
}

function LastCloseHeader({ data }: { data: SecurityDetail }) {
  const latest = data.bars[0];
  if (!latest || latest.close == null) return null;
  const prev = data.bars[1];
  const change = prev?.close != null ? latest.close - prev.close : null;
  const pct = change != null && prev?.close ? (change / prev.close) * 100 : null;
  const currency = data.universe?.currency ?? data.position?.currency ?? null;
  const color = change == null ? "" : change >= 0 ? "text-green-600" : "text-red-600";
  return (
    <div className="flex items-baseline gap-3 pt-1">
      <span className="text-2xl font-mono font-semibold tabular-nums">
        {fmtCur(latest.close, currency)}
      </span>
      {change != null && pct != null && (
        <span className={`text-sm font-mono tabular-nums ${color}`}>
          {change >= 0 ? "+" : ""}{change.toFixed(2)} ({pct >= 0 ? "+" : ""}{pct.toFixed(2)}%)
        </span>
      )}
      <span className="text-xs text-muted-foreground">EOD close · {latest.time}</span>
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

function pct(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

function compact(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n.toLocaleString("en-US")}`;
}

function fmtCur(n: number, currency: string | null | undefined): string {
  const sym = currency === "EUR" ? "€" : currency === "GBP" ? "£" : "$";
  return `${sym}${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtDate(ts: string | null | undefined): string {
  if (!ts) return "—";
  return ts.length >= 10 ? ts.slice(0, 10) : ts;
}
