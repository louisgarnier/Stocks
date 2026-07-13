import { render, screen, act, waitFor } from '@testing-library/react';
import { SyncProvider } from '@/lib/sync-context';
import { StalenessChips } from '@/components/dashboard/StalenessChips';
import type { AsOf } from '@/lib/dashboard';

const asOf: AsOf = {
  prices: '2026-07-10',
  signals: '2026-07-10',
  fundamentals: '2026-07-10',
  ibkr: '2026-07-12',
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
