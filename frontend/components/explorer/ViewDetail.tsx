'use client';

import { ViewEmbedder } from '@/components/tableau/ViewEmbedder';
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
  const isInContext = contextObjects.some(
    (ctx) => ctx.object_id === viewId && ctx.object_type === 'view'
  );

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800 shrink-0">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">{viewName}</h2>
        {onAddToContext && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onAddToContext(viewId, 'view', viewName)}
            disabled={isInContext}
            title={isInContext ? 'Already in context' : 'Add to Chat'}
          >
            {isInContext ? 'In Context' : 'Add to Chat'}
          </Button>
        )}
      </div>
      <div className="flex-1 min-h-0 overflow-hidden">
        <ViewEmbedder viewId={viewId} className="h-full w-full" />
      </div>
    </div>
  );
}
