import { render, screen, waitFor } from '@testing-library/react';
import { Dashboard } from '@/components/dashboard/Dashboard';
import { SyncProvider } from '@/lib/sync-context';

function renderDashboard(props: { onSelectSymbol: (symbol: string) => void }) {
  return render(
    <SyncProvider>
      <Dashboard {...props} />
    </SyncProvider>,
  );
}

function makePayload(valueEur: number) {
  return {
    as_of: { prices: '2026-07-09', signals: '2026-07-09', fundamentals: '2026-07-10T14:21:00Z', ibkr: '2026-07-10T09:09:00Z' },
    fx_rate: 1.1,
    net_worth: { value_eur: valueEur, day_change_eur: 614, day_change_pct: 0.52, unrealized_pnl_eur: 29911, positions: 18, usd_exposure_pct: 87.1 },
    allocation: { sector: [{ label: 'Technology', value_eur: 57815, pct: 48.9 }], position: [], currency: [] },
    performance: { portfolio: [{ date: '2026-01-02', value: 100 }, { date: '2026-07-09', value: 118.4 }], benchmark: [{ date: '2026-01-02', value: 100 }, { date: '2026-07-09', value: 111.2 }] },
    movers: [{ symbol: 'SOFI', close: 18.62, prev_close: 17.73, change_pct: 5.02, day_pnl_eur: 573 }],
    actions: { sell: [{ symbol: 'RGTI', quantity: 29, return_pct: -57.9, fired: ['stop_loss'], n_fired: 6 }], buy: [{ symbol: 'SPG', name: 'Simon Property Group', verdict: 'strong_buy', score_total: 77.3, gates_passed: 7 }] },
  };
}

const payload = makePayload(118339);

beforeEach(() => {
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => payload }) as jest.Mock;
});

test('renders net worth, action queue and movers from the API', async () => {
  renderDashboard({ onSelectSymbol: () => {} });
  await waitFor(() => expect(screen.getByText(/€118,339/)).toBeInTheDocument());
  expect(screen.getByText('RGTI')).toBeInTheDocument();
  expect(screen.getByText('SPG')).toBeInTheDocument();
  expect(screen.getByText('SOFI')).toBeInTheDocument();
  expect(screen.getByText(/Technology/)).toBeInTheDocument();
});

test('clicking a mover calls onSelectSymbol', async () => {
  const onSelect = jest.fn();
  renderDashboard({ onSelectSymbol: onSelect });
  await waitFor(() => screen.getByText('SOFI'));
  screen.getByText('SOFI').click();
  expect(onSelect).toHaveBeenCalledWith('SOFI');
});

test('out-of-order responses: latest window request wins', async () => {
  const resolvers: Array<(value: any) => void> = [];

  global.fetch = jest.fn(() => {
    return new Promise((resolve) => {
      resolvers.push(resolve);
    });
  }) as jest.Mock;

  renderDashboard({ onSelectSymbol: () => {} });

  // Initial mount triggers the 6M fetch. Resolve it so the window pills render
  // (Dashboard shows a full-page loading state until the first response lands).
  await waitFor(() => expect(resolvers).toHaveLength(1));
  resolvers[0]({ ok: true, json: async () => makePayload(50000) });
  await waitFor(() => expect(screen.getByText(/€50,000/)).toBeInTheDocument());

  // Rapidly switch windows twice, without letting either request resolve, so
  // the two fetches are genuinely in flight at once — the real race the
  // requestSeq guard in Dashboard.tsx protects against.
  screen.getByText('1M').click();
  await waitFor(() => expect(resolvers).toHaveLength(2));
  screen.getByText('3M').click();
  await waitFor(() => expect(resolvers).toHaveLength(3));

  // Resolve the newer (3M) request first with payload B, then the now-stale
  // (1M) request with payload A.
  resolvers[2]({ ok: true, json: async () => makePayload(200000) });
  resolvers[1]({ ok: true, json: async () => makePayload(100000) });

  // The rendered net worth must reflect the latest request, never the stale one.
  await waitFor(() => expect(screen.getByText(/€200,000/)).toBeInTheDocument());
  expect(screen.queryByText(/€100,000/)).not.toBeInTheDocument();
});
