import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import { SyncProvider } from '@/lib/sync-context';
import { SyncToolbar } from '@/components/research/SyncToolbar';

beforeEach(() => {
  global.fetch = jest.fn(() => new Promise(() => {})) as unknown as typeof fetch;
});

function mount() {
  return render(
    <SyncProvider>
      <SyncToolbar />
    </SyncProvider>,
  );
}

test('clicking Compute signals drives provider and shows Running on that button', async () => {
  mount();
  act(() => screen.getByRole('button', { name: /Compute signals/ }).click());
  await waitFor(() =>
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/proxy/api/sync/screen',
      expect.objectContaining({ method: 'POST' }),
    ),
  );
  // The Compute button's status line reflects running state.
  expect(screen.getByText(/Running/)).toBeInTheDocument();
});

test('progress persists when the toolbar unmounts and remounts (tab switch)', async () => {
  // Provider is mounted ABOVE the toolbar and stays mounted; a `show` flag
  // mounts/unmounts the toolbar to simulate leaving and returning to the tab.
  function Harness() {
    const [show, setShow] = React.useState(true);
    return (
      <SyncProvider>
        <button onClick={() => setShow((s) => !s)}>toggle</button>
        {show && <SyncToolbar />}
      </SyncProvider>
    );
  }
  render(<Harness />);

  // Start a sync while the toolbar is mounted (never-resolving fetch → stays Running).
  act(() => screen.getByRole('button', { name: /Compute signals/ }).click());
  await waitFor(() => expect(screen.getByText(/Running/)).toBeInTheDocument());

  // Leave the tab (unmount the toolbar) then return (remount it).
  act(() => screen.getByText('toggle').click()); // unmount toolbar
  expect(screen.queryByRole('button', { name: /Compute signals/ })).toBeNull();
  act(() => screen.getByText('toggle').click()); // remount toolbar

  // The remounted toolbar reflects the still-running step from provider state.
  expect(screen.getByText(/Running/)).toBeInTheDocument();
});
