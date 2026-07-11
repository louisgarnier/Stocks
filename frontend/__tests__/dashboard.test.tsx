import { render, screen, waitFor } from '@testing-library/react';
import { Dashboard } from '@/components/dashboard/Dashboard';

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
