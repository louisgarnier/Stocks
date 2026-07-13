'use client';

import { useSync } from '@/lib/sync-context';

export function SyncToolbar() {
  const { state, anyRunning, runFundamentals, runTechnical, runCompute, runAll } = useSync();

  const Btn = ({
    stepKey,
    label,
    icon,
    subtitle,
    primary,
    onClick,
  }: {
    stepKey: 'fundamentals' | 'technical' | 'compute' | 'all';
    label: string;
    icon: string;
    subtitle: string;
    primary?: boolean;
    onClick: () => void;
  }) => {
    const st = state[stepKey];
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
        <button
          type="button"
          onClick={onClick}
          disabled={anyRunning}
          style={{
            background: primary ? '#4f46e5' : '#fff',
            border: `1px solid ${primary ? '#4f46e5' : '#e2e5ea'}`,
            borderRadius: '8px',
            padding: primary ? '8px 16px' : '8px 13px',
            fontWeight: primary ? 700 : 600,
            fontSize: '13px',
            cursor: anyRunning ? 'default' : 'pointer',
            opacity: anyRunning && !st.running ? 0.6 : 1,
            color: primary ? '#fff' : '#0f1729',
            whiteSpace: 'nowrap',
          }}
        >
          {st.running ? '…' : icon} {label}
        </button>
        <span
          style={{
            fontSize: '10px',
            color: st.error ? '#dc2626' : st.status === 'Done ✓' ? '#16a34a' : '#94a3b8',
          }}
        >
          {st.status ?? subtitle}
        </span>
      </div>
    );
  };

  return (
    <div
      style={{
        display: 'flex',
        gap: '10px',
        alignItems: 'stretch',
        background: '#fff',
        border: '1px solid #e8eaed',
        borderRadius: '12px',
        padding: '12px',
        flexWrap: 'wrap',
      }}
    >
      <Btn stepKey="fundamentals" label="Fundamentals" icon="⟳" subtitle="fetch + auto-rescore" onClick={runFundamentals} />
      <Btn stepKey="technical" label="Technical" icon="⟳" subtitle="prices + indicators" onClick={runTechnical} />
      <Btn stepKey="compute" label="Compute signals" icon="⟳" subtitle="screen + score" onClick={runCompute} />
      <Btn stepKey="all" label="Run all" icon="▶" subtitle="Technical → Fundamentals → Compute" primary onClick={runAll} />
    </div>
  );
}
