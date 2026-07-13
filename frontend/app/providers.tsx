'use client';

import { SyncProvider } from '@/lib/sync-context';

export function Providers({ children }: { children: React.ReactNode }) {
  return <SyncProvider>{children}</SyncProvider>;
}
