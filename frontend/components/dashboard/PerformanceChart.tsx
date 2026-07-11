'use client';

import { Card, CardContent } from '@/components/ui/card';
import { DASHBOARD_WINDOWS, formatPct, type DashboardWindow, type Performance } from '@/lib/dashboard';

// Verbatim from the Task 5 brief — maps a normalized series to an SVG path.
const toPath = (pts: { value: number }[], w = 400, h = 120) => {
  if (pts.length < 2) return '';
  const vals = pts.map((p) => p.value);
  const [lo, hi] = [Math.min(...vals), Math.max(...vals)];
  const y = (v: number) => h - ((v - lo) / (hi - lo || 1)) * (h - 16) - 8;
  const x = (i: number) => (i / (pts.length - 1)) * w;
  return pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ');
};

interface Props {
  data: Performance
  activeWindow: DashboardWindow
  onWindowChange: (window: DashboardWindow) => void
}

export function PerformanceChart({ data, activeWindow, onWindowChange }: Props) {
  const portfolioPath = toPath(data.portfolio);
  const benchmarkPath = toPath(data.benchmark);
  const portfolioReturn = data.portfolio.length
    ? data.portfolio[data.portfolio.length - 1].value - 100
    : null;
  const benchmarkReturn = data.benchmark.length
    ? data.benchmark[data.benchmark.length - 1].value - 100
    : null;

  return (
    <Card className="py-0">
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Performance vs S&amp;P 500
          </div>
          <div className="flex gap-1 text-[11px]">
            {DASHBOARD_WINDOWS.map((w) => (
              <button
                key={w}
                type="button"
                onClick={() => onWindowChange(w)}
                className={`rounded-full px-2 py-0.5 font-semibold ${
                  activeWindow === w
                    ? 'bg-accent text-accent-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {w}
              </button>
            ))}
          </div>
        </div>

        <svg width="100%" height={120} viewBox="0 0 400 120" preserveAspectRatio="none" className="mt-3">
          <line x1="0" y1="30" x2="400" y2="30" stroke="var(--color-border)" strokeWidth="1" />
          <line x1="0" y1="60" x2="400" y2="60" stroke="var(--color-border)" strokeWidth="1" />
          <line x1="0" y1="90" x2="400" y2="90" stroke="var(--color-border)" strokeWidth="1" />
          {benchmarkPath && (
            <path d={benchmarkPath} fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeDasharray="4 3" />
          )}
          {portfolioPath && <path d={portfolioPath} fill="none" stroke="#5b9bd5" strokeWidth="2.5" />}
        </svg>

        <div className="mt-1.5 flex gap-4 text-xs tabular-nums">
          <span>
            <span className="text-[#5b9bd5]">━</span> Portfolio{' '}
            <b className={portfolioReturn != null && portfolioReturn < 0 ? 'text-red-600' : 'text-green-600'}>
              {formatPct(portfolioReturn)}
            </b>
          </span>
          <span>
            <span className="text-muted-foreground">┄</span> ^GSPC <b>{formatPct(benchmarkReturn)}</b>
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
