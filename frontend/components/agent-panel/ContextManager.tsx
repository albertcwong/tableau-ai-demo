'use client';

import { ChatContextObject } from '@/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { X, Database, Layout } from 'lucide-react';

interface ContextManagerProps {
  objects: ChatContextObject[];
  onRemove: (objectId: string) => void;
}

export function ContextManager({ objects, onRemove }: ContextManagerProps) {
  if (objects.length === 0) {
    return (
      <div className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
        No objects in context. Add datasources or views from the explorer.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {objects.map((obj) => (
        <Card key={obj.object_id} className="p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 flex-1">
              {obj.object_type === 'datasource' ? (
                <Database className="h-4 w-4 text-blue-600 dark:text-blue-400" />
              ) : (
                <Layout className="h-4 w-4 text-green-600 dark:text-green-400" />
              )}
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm truncate">{obj.object_name || obj.object_id}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400 capitalize">{obj.object_type}</div>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onRemove(obj.object_id)}
              className="h-8 w-8 p-0"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );
}
