import {
  SIGNAL_GROUPS,
  fetchSignalSettings,
  updateSignalSetting,
  type SignalSetting,
} from '@/lib/holding-signals';

const ALL_TYPES = [
  'ma50_break', 'ma100_break', 'ma150_break', 'ma200_break', 'death_cross',
  'volume_dryup', 'distribution_day', 'rsi_weakness', 'mrsi_flip',
  'trailing_drawdown', 'stop_loss',
];

afterEach(() => jest.restoreAllMocks());

test('SIGNAL_GROUPS covers exactly the 11 signal types in 3 groups', () => {
  expect(SIGNAL_GROUPS).toHaveLength(3);
  const types = SIGNAL_GROUPS.flatMap((g) => g.signals.map((s) => s.type));
  expect(types.sort()).toEqual([...ALL_TYPES].sort());
  const withUnit = SIGNAL_GROUPS.flatMap((g) => g.signals).filter((s) => s.thresholdUnit);
  expect(withUnit.map((s) => s.type).sort()).toEqual(['stop_loss', 'trailing_drawdown']);
});

test('fetchSignalSettings GETs the settings endpoint and returns items', async () => {
  const items: SignalSetting[] = [
    { signal_type: 'ma50_break', enabled: true, threshold: null },
  ];
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ items }) }) as jest.Mock;
  await expect(fetchSignalSettings()).resolves.toEqual(items);
  expect(global.fetch).toHaveBeenCalledWith('/api/proxy/api/holding-signals/settings');
});

test('updateSignalSetting POSTs the full setting and throws on failure', async () => {
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true }) }) as jest.Mock;
  const s: SignalSetting = { signal_type: 'stop_loss', enabled: true, threshold: 0.12 };
  await updateSignalSetting(s);
  expect(global.fetch).toHaveBeenCalledWith(
    '/api/proxy/api/holding-signals/settings',
    expect.objectContaining({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(s),
    }),
  );
  (global.fetch as jest.Mock).mockResolvedValue({ ok: false, status: 500 });
  await expect(updateSignalSetting(s)).rejects.toThrow('updateSignalSetting: HTTP 500');
});
