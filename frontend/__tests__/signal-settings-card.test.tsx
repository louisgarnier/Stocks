import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { SignalSettingsCard } from '@/components/settings/SignalSettingsCard';

const SETTINGS = [
  { signal_type: 'ma50_break', enabled: true, threshold: null },
  { signal_type: 'ma100_break', enabled: true, threshold: null },
  { signal_type: 'ma150_break', enabled: false, threshold: null },
  { signal_type: 'ma200_break', enabled: true, threshold: null },
  { signal_type: 'death_cross', enabled: true, threshold: null },
  { signal_type: 'volume_dryup', enabled: true, threshold: null },
  { signal_type: 'distribution_day', enabled: true, threshold: null },
  { signal_type: 'rsi_weakness', enabled: true, threshold: null },
  { signal_type: 'mrsi_flip', enabled: true, threshold: null },
  { signal_type: 'trailing_drawdown', enabled: true, threshold: 0.1 },
  { signal_type: 'stop_loss', enabled: true, threshold: 0.08 },
];

function mockFetch() {
  global.fetch = jest.fn((url: string, opts?: RequestInit) => {
    if (!opts || !opts.method) {
      return Promise.resolve({ ok: true, json: async () => ({ items: SETTINGS }) });
    }
    return Promise.resolve({ ok: true, json: async () => ({ success: true }) });
  }) as jest.Mock;
}

beforeEach(() => mockFetch());
afterEach(() => jest.restoreAllMocks());

test('renders 11 switches and the enabled count badge', async () => {
  render(<SignalSettingsCard />);
  await waitFor(() => expect(screen.getAllByRole('switch')).toHaveLength(11));
  expect(screen.getByText('10 / 11 enabled')).toBeInTheDocument();
  expect(screen.getByText('Trend breaks')).toBeInTheDocument();
  expect(screen.getByText('Volume & momentum')).toBeInTheDocument();
  expect(screen.getByText('Risk')).toBeInTheDocument();
});

test('toggling a switch POSTs the flipped setting and shows Saved', async () => {
  render(<SignalSettingsCard />);
  await waitFor(() => expect(screen.getAllByRole('switch')).toHaveLength(11));
  fireEvent.click(screen.getByRole('switch', { name: /MA50 break/ }));
  await waitFor(() =>
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/proxy/api/holding-signals/settings',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ signal_type: 'ma50_break', enabled: false, threshold: null }),
      }),
    ),
  );
  expect(await screen.findByText(/Saved/)).toBeInTheDocument();
});

test('threshold input shows percent and saves fraction on blur', async () => {
  render(<SignalSettingsCard />);
  await waitFor(() => expect(screen.getAllByRole('switch')).toHaveLength(11));
  const input = screen.getByLabelText('Trailing drawdown threshold') as HTMLInputElement;
  expect(input.value).toBe('10');
  fireEvent.change(input, { target: { value: '12' } });
  fireEvent.blur(input);
  await waitFor(() =>
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/proxy/api/holding-signals/settings',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ signal_type: 'trailing_drawdown', enabled: true, threshold: 0.12 }),
      }),
    ),
  );
});

test('threshold is clamped to 1–95 %', async () => {
  render(<SignalSettingsCard />);
  await waitFor(() => expect(screen.getAllByRole('switch')).toHaveLength(11));
  const input = screen.getByLabelText('Stop loss threshold') as HTMLInputElement;
  fireEvent.change(input, { target: { value: '200' } });
  fireEvent.blur(input);
  await waitFor(() => expect(input.value).toBe('95'));
  expect(global.fetch).toHaveBeenCalledWith(
    '/api/proxy/api/holding-signals/settings',
    expect.objectContaining({
      body: JSON.stringify({ signal_type: 'stop_loss', enabled: true, threshold: 0.95 }),
    }),
  );
});

test('Recompute signals now POSTs the holding-signals sync', async () => {
  render(<SignalSettingsCard />);
  await waitFor(() => expect(screen.getAllByRole('switch')).toHaveLength(11));
  fireEvent.click(screen.getByRole('button', { name: /Recompute signals now/ }));
  await waitFor(() =>
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/proxy/api/sync/holding-signals',
      expect.objectContaining({ method: 'POST' }),
    ),
  );
  expect(await screen.findByText(/Signals recomputed/)).toBeInTheDocument();
});
