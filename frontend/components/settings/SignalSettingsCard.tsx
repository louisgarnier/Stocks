'use client';

import { useEffect, useState } from 'react';
import { Bell } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  SIGNAL_GROUPS,
  fetchSignalSettings,
  updateSignalSetting,
  signalLabel,
  type SignalSetting,
} from '@/lib/holding-signals';

const TOTAL = SIGNAL_GROUPS.reduce((n, g) => n + g.signals.length, 0);

type SettingsMap = Record<string, SignalSetting>;

export function SignalSettingsCard() {
  const [settings, setSettings] = useState<SettingsMap | null>(null);
  const [thresholdDraft, setThresholdDraft] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<'idle' | 'saved' | 'recomputed' | 'error'>('idle');
  const [recomputing, setRecomputing] = useState(false);

  useEffect(() => {
    fetchSignalSettings()
      .then((items) => {
        const map: SettingsMap = {};
        const drafts: Record<string, string> = {};
        for (const s of items) {
          map[s.signal_type] = s;
          if (s.threshold != null) drafts[s.signal_type] = String(Math.round(s.threshold * 100));
        }
        setSettings(map);
        setThresholdDraft(drafts);
      })
      .catch(() => setStatus('error'));
  }, []);

  async function save(next: SignalSetting) {
    const prev = settings?.[next.signal_type];
    setSettings((m) => ({ ...m!, [next.signal_type]: next }));
    try {
      await updateSignalSetting(next);
      setStatus('saved');
    } catch {
      if (prev) setSettings((m) => ({ ...m!, [next.signal_type]: prev }));
      setStatus('error');
    }
  }

  function commitThreshold(type: string) {
    const s = settings?.[type];
    if (!s) return;
    const pct = Math.min(95, Math.max(1, Math.round(Number(thresholdDraft[type]) || 0)));
    setThresholdDraft((d) => ({ ...d, [type]: String(pct) }));
    const threshold = pct / 100;
    if (threshold !== s.threshold) save({ ...s, threshold });
  }

  async function recompute() {
    setRecomputing(true);
    try {
      const res = await fetch('/api/proxy/api/sync/holding-signals', { method: 'POST' });
      setStatus(res.ok ? 'recomputed' : 'error');
    } catch {
      setStatus('error');
    } finally {
      setRecomputing(false);
    }
  }

  const enabledCount = settings
    ? Object.values(settings).filter((s) => s.enabled).length
    : 0;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Bell className="w-5 h-5" />
          Sell Signals
        </CardTitle>
        <Badge variant="secondary">{settings ? `${enabledCount} / ${TOTAL} enabled` : '…'}</Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground">
          Toggles apply on the next signals sync. Disabled signals stop firing everywhere
          (Positions tab, Dashboard action queue).
        </p>

        {settings === null ? (
          <div className="text-sm text-muted-foreground">
            {status === 'error' ? 'Failed to load signal settings.' : 'Loading…'}
          </div>
        ) : (
          <>
            {SIGNAL_GROUPS.map((group) => (
              <div key={group.title}>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {group.title}
                </h4>
                <div className="space-y-2">
                  {group.signals.map(({ type, trigger, thresholdUnit }) => {
                    const s = settings[type];
                    if (!s) return null;
                    return (
                      <div
                        key={type}
                        className={`flex items-center gap-3 rounded-md border bg-card p-3 ${s.enabled ? '' : 'opacity-55'}`}
                      >
                        <Switch
                          checked={s.enabled}
                          onCheckedChange={(checked) => save({ ...s, enabled: checked })}
                          aria-label={signalLabel(type)}
                          id={`signal-${type}`}
                        />
                        <label htmlFor={`signal-${type}`} className="w-40 cursor-pointer text-sm font-medium">
                          {signalLabel(type)}
                        </label>
                        <span className="text-xs text-muted-foreground">{trigger}</span>
                        {thresholdUnit && (
                          <>
                            <Input
                              className="h-7 w-16 text-right text-sm font-semibold"
                              inputMode="numeric"
                              aria-label={`${signalLabel(type)} threshold`}
                              value={thresholdDraft[type] ?? ''}
                              onChange={(e) =>
                                setThresholdDraft((d) => ({ ...d, [type]: e.target.value }))
                              }
                              onBlur={() => commitThreshold(type)}
                              onKeyDown={(e) => e.key === 'Enter' && commitThreshold(type)}
                            />
                            <span className="text-xs text-muted-foreground">{thresholdUnit}</span>
                          </>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}

            <div className="flex items-center gap-2 pt-1 text-xs text-muted-foreground">
              {status === 'saved' && (
                <span className="text-green-600">✓ Saved · takes effect on next signals sync</span>
              )}
              {status === 'recomputed' && <span className="text-green-600">✓ Signals recomputed</span>}
              {status === 'error' && <span className="text-red-600">✗ Save failed — change reverted</span>}
              <Button
                variant="outline"
                size="sm"
                className="ml-auto"
                onClick={recompute}
                disabled={recomputing}
              >
                {recomputing ? '⏳ Recomputing…' : '↻ Recompute signals now'}
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
