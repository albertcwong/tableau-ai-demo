'use client';

import { useState } from 'react';
import { EmbeddedViewActionTimer, formatElapsed } from '@/components/tableau/EmbeddedViewActionTimer';
import { Button } from '@/components/ui/button';

interface ViewDetailProps {
  viewId: string;
  viewName: string;
  onAddToContext?: (objectId: string, objectType: 'datasource' | 'view', objectName?: string) => void;
  contextObjects?: Array<{ object_id: string; object_type: 'datasource' | 'view' }>;
}

export function ViewDetail({
  viewId,
  viewName,
  onAddToContext,
  contextObjects = [],
}: ViewDetailProps) {
  const [lastActionMs, setLastActionMs] = useState<number | null>(null);
  const isInContext = contextObjects.some(
    (ctx) => ctx.object_id === viewId && ctx.object_type === 'view'
  );

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between gap-3 p-4 border-b border-gray-200 dark:border-gray-800 shrink-0">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white truncate min-w-0">{viewName}</h2>
        <span className="text-xs font-mono tabular-nums text-gray-500 dark:text-gray-400 shrink-0">
          {lastActionMs != null ? formatElapsed(lastActionMs) : '—'}
        </span>
        {onAddToContext && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onAddToContext(viewId, 'view', viewName)}
            disabled={isInContext}
            title={isInContext ? 'Already in context' : 'Add to Chat'}
            className="shrink-0"
          >
            {isInContext ? 'In Context' : 'Add to Chat'}
          </Button>
        )}
      </div>
      <div className="flex-1 min-h-0 overflow-hidden relative">
        <EmbeddedViewActionTimer
          viewId={viewId}
          className="absolute inset-0"
          onLastActionDuration={setLastActionMs}
          onDisplayMs={setLastActionMs}
        />
      </div>
    </div>
  );
}
