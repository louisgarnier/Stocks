import { render, screen, act, waitFor } from '@testing-library/react';
import { SyncProvider, useSync } from '@/lib/sync-context';

// A tiny consumer we can mount/unmount to prove provider state outlives it.
function Probe() {
  const { state, anyRunning, syncVersion, runCompute } = useSync();
  return (
    <div>
      <span data-testid="compute-status">{state.compute.status ?? 'idle'}</span>
      <span data-testid="any-running">{anyRunning ? 'yes' : 'no'}</span>
      <span data-testid="version">{syncVersion}</span>
      <button onClick={runCompute}>compute</button>
    </div>
  );
}

beforeEach(() => {
  // Never-resolving fetch by default so we can observe the "running" window.
  global.fetch = jest.fn(() => new Promise(() => {})) as unknown as typeof fetch;
});

test('runCompute posts to the screen endpoint and sets running state', async () => {
  render(
    <SyncProvider>
      <Probe />
    </SyncProvider>,
  );
  expect(screen.getByTestId('compute-status').textContent).toBe('idle');
  act(() => {
    screen.getByText('compute').click();
  });
  await waitFor(() => expect(screen.getByTestId('any-running').textContent).toBe('yes'));
  expect(screen.getByTestId('compute-status').textContent).toMatch(/Running/);
  expect(global.fetch).toHaveBeenCalledWith(
    '/api/proxy/api/sync/screen',
    expect.objectContaining({ method: 'POST' }),
  );
});

test('a second run is ignored while one is already running (no double-start)', async () => {
  render(
    <SyncProvider>
      <Probe />
    </SyncProvider>,
  );
  act(() => screen.getByText('compute').click());
  await waitFor(() => expect(screen.getByTestId('any-running').textContent).toBe('yes'));
  (global.fetch as jest.Mock).mockClear();
  act(() => screen.getByText('compute').click()); // second click while running
  expect(global.fetch).not.toHaveBeenCalled();
});

test('successful run flips running off and bumps syncVersion', async () => {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve({}) }),
  ) as unknown as typeof fetch;
  render(
    <SyncProvider>
      <Probe />
    </SyncProvider>,
  );
  const before = Number(screen.getByTestId('version').textContent);
  act(() => screen.getByText('compute').click());
  await waitFor(() =>
    expect(screen.getByTestId('compute-status').textContent).toMatch(/Done/),
  );
  expect(screen.getByTestId('any-running').textContent).toBe('no');
  expect(Number(screen.getByTestId('version').textContent)).toBe(before + 1);
});

test('useSync outside provider throws', () => {
  // Suppress React's error boundary console noise for this assertion.
  const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
  expect(() => render(<Probe />)).toThrow(/useSync must be used within SyncProvider/);
  spy.mockRestore();
});
