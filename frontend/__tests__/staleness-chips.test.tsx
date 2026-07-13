import { render, screen, act, waitFor } from '@testing-library/react';
import { SyncProvider } from '@/lib/sync-context';
import { StalenessChips } from '@/components/dashboard/StalenessChips';
import type { AsOf } from '@/lib/dashboard';

const entry = (date: string | null, checked_at: string | null,
               level: 'fresh' | 'stale' | 'unknown') => ({ date, checked_at, level });

const asOf: AsOf = {
  prices: entry('2026-07-10', new Date(Date.now() - 2 * 36e5).toISOString(), 'fresh'),
  signals: entry('2026-07-10', new Date(Date.now() - 2 * 36e5).toISOString(), 'fresh'),
  fundamentals: entry('2026-07-08T09:00:00+00:00', new Date(Date.now() - 72 * 36e5).toISOString(), 'stale'),
  ibkr: entry(null, null, 'unknown'),
};

beforeEach(() => {
  global.fetch = jest.fn(() => new Promise(() => {})) as unknown as typeof fetch;
});

test('clicking the prices chip triggers the technical (market-data) sync', async () => {
  render(
    <SyncProvider>
      <StalenessChips asOf={asOf} />
    </SyncProvider>,
  );
  act(() => screen.getByRole('button', { name: /prices/ }).click());
  await waitFor(() =>
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/proxy/api/sync/market-data',
      expect.objectContaining({ method: 'POST' }),
    ),
  );
});

test('a chip shows a syncing state while its step runs', async () => {
  render(
    <SyncProvider>
      <StalenessChips asOf={asOf} />
    </SyncProvider>,
  );
  act(() => screen.getByRole('button', { name: /signals/ }).click());
  await waitFor(() =>
    expect(screen.getByRole('button', { name: /signals/ })).toHaveTextContent(/syncing|…/i),
  );
});

test('the IBKR chip is disabled while an external (header) IBKR sync is running, other chips are not', () => {
  render(
    <SyncProvider>
      <StalenessChips asOf={asOf} ibkrExternalSyncing={true} />
    </SyncProvider>,
  );
  expect(screen.getByRole('button', { name: /IBKR/ })).toBeDisabled();
  expect(screen.getByRole('button', { name: /prices/ })).not.toBeDisabled();
});

test('chips show the data date, not a relative age', () => {
  render(
    <SyncProvider>
      <StalenessChips asOf={asOf} />
    </SyncProvider>,
  );
  expect(screen.getByRole('button', { name: /prices/ })).toHaveTextContent('07-10');
  expect(screen.getByRole('button', { name: /fundamentals/ })).toHaveTextContent('07-08');
});

test('chips show a checked-ago subline and handle no-data', () => {
  render(
    <SyncProvider>
      <StalenessChips asOf={asOf} />
    </SyncProvider>,
  );
  expect(screen.getByRole('button', { name: /prices/ })).toHaveTextContent(/checked 2h ago/);
  const ibkr = screen.getByRole('button', { name: /IBKR/ });
  expect(ibkr).toHaveTextContent('—');
  expect(ibkr).toHaveTextContent(/never/);
});

test('level drives the chip color class', () => {
  render(
    <SyncProvider>
      <StalenessChips asOf={asOf} />
    </SyncProvider>,
  );
  expect(screen.getByRole('button', { name: /prices/ }).className).toMatch(/text-success/);
  expect(screen.getByRole('button', { name: /fundamentals/ }).className).toMatch(/text-warning/);
  expect(screen.getByRole('button', { name: /IBKR/ }).className).toMatch(/text-muted-foreground/);
});
