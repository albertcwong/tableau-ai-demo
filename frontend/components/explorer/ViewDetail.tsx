'use client';

import { ViewEmbedder } from '@/components/tableau/ViewEmbedder';
import { Card } from '@/components/ui/card';
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
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">{viewName}</h2>
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
      <Card className="p-4">
        <div className="w-full" style={{ height: '600px' }}>
          <ViewEmbedder viewId={viewId} />
        </div>
      </Card>
    </div>
  );
}
