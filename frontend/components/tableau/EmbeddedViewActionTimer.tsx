'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ViewEmbedder } from './ViewEmbedder';
import { cn } from '@/lib/utils';

function formatElapsed(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  if (m > 0) return `${m}m ${s % 60}s`;
  return `${(ms / 1000).toFixed(2)}s`;
}

interface EmbeddedViewActionTimerProps {
  viewId: string;
  viewName?: string;
  filters?: Record<string, string>;
  hideTabs?: boolean;
  hideToolbar?: boolean;
  device?: 'desktop' | 'phone' | 'tablet';
  onError?: (error: Error) => void;
  onLastActionDuration?: (ms: number | null) => void;
  onDisplayMs?: (ms: number | null) => void;
  className?: string;
}

export function EmbeddedViewActionTimer({
  viewId,
  viewName,
  filters,
  hideTabs = false,
  hideToolbar = false,
  device = 'desktop',
  onError,
  onLastActionDuration,
  onDisplayMs,
  className = '',
}: EmbeddedViewActionTimerProps) {
  const lastEventTsRef = useRef<number>(Date.now());
  const isStoppedRef = useRef(false);
  const [displayMs, setDisplayMs] = useState<number | null>(null);

  useEffect(() => {
    lastEventTsRef.current = Date.now();
    isStoppedRef.current = false;
    setDisplayMs(0);
    const tick = () => {
      if (!isStoppedRef.current) {
        setDisplayMs(Date.now() - lastEventTsRef.current);
      }
    };
    const id = setInterval(tick, 100);
    return () => clearInterval(id);
  }, [viewId]);

  const handleUserAction = useCallback(
    (_type: string, _description: string, durationMs: number) => {
      isStoppedRef.current = true;
      onLastActionDuration?.(durationMs);
      setDisplayMs(durationMs);
    },
    [onLastActionDuration]
  );

  useEffect(() => {
    onDisplayMs?.(displayMs);
  }, [displayMs, onDisplayMs]);

  return (
    <div className={cn('relative w-full h-full min-h-0', className)}>
      <ViewEmbedder
        viewId={viewId}
        viewName={viewName}
        filters={filters}
        hideTabs={hideTabs}
        hideToolbar={hideToolbar}
        device={device}
        onError={onError}
        onUserAction={handleUserAction}
        lastEventTsRef={lastEventTsRef}
        className="h-full w-full"
      />
    </div>
  );
}

export { formatElapsed };
