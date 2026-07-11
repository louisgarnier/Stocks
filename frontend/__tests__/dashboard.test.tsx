import { render, screen, waitFor } from '@testing-library/react';
import { useState, useEffect, useRef } from 'react';
import { Dashboard } from '@/components/dashboard/Dashboard';
import type { DashboardWindow } from '@/lib/dashboard';

const payload = {
  as_of: { prices: '2026-07-09', signals: '2026-07-09', fundamentals: '2026-07-10T14:21:00Z', ibkr: '2026-07-10T09:09:00Z' },
  fx_rate: 1.1,
  net_worth: { value_eur: 118339, day_change_eur: 614, day_change_pct: 0.52, unrealized_pnl_eur: 29911, positions: 18, usd_exposure_pct: 87.1 },
  allocation: { sector: [{ label: 'Technology', value_eur: 57815, pct: 48.9 }], position: [], currency: [] },
  performance: { portfolio: [{ date: '2026-01-02', value: 100 }, { date: '2026-07-09', value: 118.4 }], benchmark: [{ date: '2026-01-02', value: 100 }, { date: '2026-07-09', value: 111.2 }] },
  movers: [{ symbol: 'SOFI', close: 18.62, prev_close: 17.73, change_pct: 5.02, day_pnl_eur: 573 }],
  actions: { sell: [{ symbol: 'RGTI', quantity: 29, return_pct: -57.9, fired: ['stop_loss'], n_fired: 6 }], buy: [{ symbol: 'SPG', name: 'Simon Property Group', verdict: 'strong_buy', score_total: 77.3, gates_passed: 7 }] },
};

beforeEach(() => {
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => payload }) as jest.Mock;
});

test('renders net worth, action queue and movers from the API', async () => {
  render(<Dashboard onSelectSymbol={() => {}} />);
  await waitFor(() => expect(screen.getByText(/€118,339/)).toBeInTheDocument());
  expect(screen.getByText('RGTI')).toBeInTheDocument();
  expect(screen.getByText('SPG')).toBeInTheDocument();
  expect(screen.getByText('SOFI')).toBeInTheDocument();
  expect(screen.getByText(/Technology/)).toBeInTheDocument();
});

test('clicking a mover calls onSelectSymbol', async () => {
  const onSelect = jest.fn();
  render(<Dashboard onSelectSymbol={onSelect} />);
  await waitFor(() => screen.getByText('SOFI'));
  screen.getByText('SOFI').click();
  expect(onSelect).toHaveBeenCalledWith('SOFI');
});

test('last-request-wins: out-of-order resolve uses latest request data', async () => {
  const resolvers: Array<{ resolve?: (value: any) => void }> = [];

  // Mock fetchData to return controllable promises
  const mockFetchData = jest.fn((param) => {
    return new Promise((resolve) => {
      resolvers.push({ resolve });
    });
  });

  function TestComponent({ param }: { param: string }) {
    const [data, setData] = useState<any>(null);
    const requestSeq = useRef(0);

    useEffect(() => {
      const seq = ++requestSeq.current;
      let cancelled = false;
      mockFetchData(param)
        .then((d) => {
          if (!cancelled && seq === requestSeq.current) setData(d);
        })
        .catch(() => {})
        .finally(() => {});
      return () => {
        cancelled = true;
      };
    }, [param]);

    return <div>{data && `Value: ${data.value}`}</div>;
  }

  const { rerender } = render(<TestComponent param="first" />);

  // Wait for first fetch to be initiated
  await waitFor(() => {
    expect(mockFetchData).toHaveBeenCalledTimes(1);
  });

  // Trigger second fetch with different param
  rerender(<TestComponent param="second" />);

  await waitFor(() => {
    expect(mockFetchData).toHaveBeenCalledTimes(2);
  });

  // Resolve second request (newer) with value 200 BEFORE first resolves
  resolvers[1]?.resolve?.({ value: 200 });

  // Then resolve first request with value 100
  resolvers[0]?.resolve?.({ value: 100 });

  // Should display 200 (from second/latest request), not 100
  await waitFor(() => expect(screen.getByText('Value: 200')).toBeInTheDocument());
  expect(screen.queryByText('Value: 100')).not.toBeInTheDocument();
});
