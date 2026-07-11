'use client';

import { Card, CardContent } from '@/components/ui/card';
import { formatEurCompact, type AllocationItem, type AllocationMode } from '@/lib/dashboard';

const PALETTE = ['#5b9bd5', '#8f7ee8', '#d9a441', '#4fd08d', '#e88b83', '#94a3b8'];

const MODE_LABEL: Record<AllocationMode, string> = {
  sector: 'Sector',
  position: 'Position',
  currency: 'Currency',
};

// r=15.9 -> circumference ~= 99.9, so pct values (0-100) can be used directly as
// dasharray/dashoffset units, matching the approved mockup's technique.
const R = 15.9;
const CIRC = 2 * Math.PI * R;
const START_OFFSET = CIRC / 4; // rotates the first segment's start to 12 o'clock

interface Segment {
  label: string
  pct: number
  value_eur: number
  color: string
}

function toSegments(data: AllocationItem[]): Segment[] {
  const sorted = [...data].sort((a, b) => b.pct - a.pct);
  const top = sorted.slice(0, 5);
  const rest = sorted.slice(5);
  const segments: Segment[] = top.map((item, i) => ({
    label: item.label,
    pct: item.pct,
    value_eur: item.value_eur,
    color: PALETTE[i % PALETTE.length],
  }));
  if (rest.length > 0) {
    segments.push({
      label: `${rest.length} more`,
      pct: rest.reduce((s, r) => s + r.pct, 0),
      value_eur: rest.reduce((s, r) => s + r.value_eur, 0),
      color: PALETTE[PALETTE.length - 1],
    });
  }
  return segments;
}

interface Props {
  data: AllocationItem[]
  mode: AllocationMode
  onMode: (mode: AllocationMode) => void
}

export function AllocationDonut({ data, mode, onMode }: Props) {
  const segments = toSegments(data);
  const top = segments[0];

  let cursor = START_OFFSET;
  const arcs = segments.map((seg) => {
    const arcLen = (seg.pct / 100) * CIRC;
    const dashoffset = cursor;
    cursor -= arcLen;
    return { ...seg, arcLen, dashoffset };
  });

  return (
    <Card className="py-0">
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Allocation
          </div>
          <div className="flex gap-1 text-[11px]">
            {(Object.keys(MODE_LABEL) as AllocationMode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => onMode(m)}
                className={`rounded-full px-2 py-0.5 font-semibold ${
                  mode === m
                    ? 'bg-accent text-accent-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {MODE_LABEL[m]}
              </button>
            ))}
          </div>
        </div>

        {segments.length === 0 ? (
          <div className="mt-6 text-sm text-muted-foreground">No allocation data.</div>
        ) : (
          <div className="mt-3 flex items-center gap-4">
            <svg width={130} height={130} viewBox="0 0 42 42" role="img" aria-label={`${MODE_LABEL[mode]} allocation donut`}>
              <circle cx="21" cy="21" r={R} fill="none" stroke="var(--color-border)" strokeWidth="6" />
              {arcs.map((seg) => (
                <circle
                  key={seg.label}
                  cx="21"
                  cy="21"
                  r={R}
                  fill="none"
                  stroke={seg.color}
                  strokeWidth="6"
                  strokeDasharray={`${seg.arcLen.toFixed(2)} ${(CIRC - seg.arcLen).toFixed(2)}`}
                  strokeDashoffset={seg.dashoffset.toFixed(2)}
                />
              ))}
              <text x="21" y="23" textAnchor="middle" fontSize="7" fontWeight="700" fill="var(--color-foreground)">
                {top ? `${top.pct.toFixed(1)}%` : ''}
              </text>
            </svg>
            <div className="flex flex-col gap-1.5 text-xs tabular-nums">
              {arcs.map((seg) => (
                <div key={seg.label} className="flex items-center gap-1.5">
                  <span style={{ color: seg.color }}>●</span>
                  <span>{seg.label}</span>
                  <b className="ml-auto pl-4 font-semibold">
                    {seg.pct.toFixed(1)}% · {formatEurCompact(seg.value_eur)}
                  </b>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
