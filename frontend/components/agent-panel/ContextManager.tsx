'use client';

import { useState } from 'react';
import { ChatContextObject } from '@/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { X, Database, Layout, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ContextManagerProps {
  objects: ChatContextObject[];
  onRemove: (objectId: string) => void;
}

export function ContextManager({ objects, onRemove }: ContextManagerProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (objects.length === 0) {
    return (
      <div className="text-xs text-muted-foreground text-center py-2 italic">
        No object in context — add a datasource or view from the explorer to query data
      </div>
    );
  }

  // Group objects by type for better organization
  const datasources = objects.filter(obj => obj.object_type === 'datasource');
  const views = objects.filter(obj => obj.object_type === 'view');

  // If only one object, show it directly without grouping
  if (objects.length === 1) {
    const obj = objects[0];
    return (
      <div className="space-y-1.5">
        <Card key={obj.object_id} className="p-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 flex-1 min-w-0">
              {obj.object_type === 'datasource' ? (
                <Database className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400 flex-shrink-0" />
              ) : (
                <Layout className="h-3.5 w-3.5 text-green-600 dark:text-green-400 flex-shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <div className="font-medium text-xs truncate">{obj.object_name || obj.object_id}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400 capitalize">{obj.object_type}</div>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onRemove(obj.object_id)}
              className="h-6 w-6 p-0 flex-shrink-0"
            >
              <X className="h-3 w-3" />
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  // Multiple objects: show collapsed summary by default
  return (
    <div className="space-y-1.5">
      <Card 
        className="p-2 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 flex-1 min-w-0">
            <Database className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400 flex-shrink-0" />
            {datasources.length > 0 && (
              <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
                {datasources.length} {datasources.length === 1 ? 'datasource' : 'datasources'}
              </span>
            )}
            {datasources.length > 0 && views.length > 0 && (
              <span className="text-xs text-gray-500 dark:text-gray-400">•</span>
            )}
            <Layout className="h-3.5 w-3.5 text-green-600 dark:text-green-400 flex-shrink-0" />
            {views.length > 0 && (
              <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
                {views.length} {views.length === 1 ? 'view' : 'views'}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {isExpanded ? (
              <ChevronUp className="h-3.5 w-3.5 text-gray-500 flex-shrink-0" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5 text-gray-500 flex-shrink-0" />
            )}
          </div>
        </div>
      </Card>

      {isExpanded && (
        <div className="space-y-1.5 pl-2 border-l-2 border-gray-200 dark:border-gray-700">
          {objects.map((obj) => (
            <Card key={obj.object_id} className="p-2">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 flex-1 min-w-0">
                  {obj.object_type === 'datasource' ? (
                    <Database className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                  ) : (
                    <Layout className="h-3.5 w-3.5 text-green-600 dark:text-green-400 flex-shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-xs truncate">{obj.object_name || obj.object_id}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 capitalize">{obj.object_type}</div>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemove(obj.object_id);
                  }}
                  className="h-6 w-6 p-0 flex-shrink-0"
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
