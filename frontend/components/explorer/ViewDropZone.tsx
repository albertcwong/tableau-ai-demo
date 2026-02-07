'use client';

import { useState } from 'react';
import { ViewEmbedder } from '@/components/tableau/ViewEmbedder';
import { Button } from '@/components/ui/button';
import { X, MessageSquare, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TableauView } from '@/types';

interface ViewDropZoneProps {
  view: TableauView | null;
  onRemove: () => void;
  onDrop?: (view: TableauView) => void;
  onAddToContext?: (objectId: string, objectType: 'datasource' | 'view', objectName?: string) => void;
  contextObjects?: Array<{ object_id: string; object_type: 'datasource' | 'view' }>;
  className?: string;
}

export function ViewDropZone({ 
  view, 
  onRemove, 
  onDrop, 
  onAddToContext,
  contextObjects = [],
  className 
}: ViewDropZoneProps) {
  const [isDraggingOver, setIsDraggingOver] = useState(false);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);

    const viewData = e.dataTransfer.getData('application/json');
    if (viewData) {
      try {
        const droppedView = JSON.parse(viewData) as TableauView;
        onDrop?.(droppedView);
      } catch (err) {
        console.error('Failed to parse dropped view data:', err);
      }
    }
  };

  return (
    <div
      className={cn(
        'relative border-2 border-dashed rounded-lg transition-all',
        view ? 'border-gray-300 dark:border-gray-700' : 'border-gray-200 dark:border-gray-800',
        isDraggingOver && 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 scale-[1.02]',
        !view && 'hover:border-gray-300 dark:hover:border-gray-700',
        className
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {view ? (
        <div className="flex flex-col h-full min-h-0">
          <div className="flex items-center justify-between p-2 border-b border-gray-200 dark:border-gray-800 shrink-0 bg-white dark:bg-gray-900">
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-medium text-gray-900 dark:text-white truncate">
                {view.name}
              </h3>
              {view.workbook_name && (
                <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                  {view.workbook_name}
                </p>
              )}
            </div>
            <div className="flex items-center gap-1 shrink-0">
              {onAddToContext && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onAddToContext(view.id, 'view', view.name)}
                  disabled={contextObjects.some(
                    (ctx) => ctx.object_id === view.id && ctx.object_type === 'view'
                  )}
                  className="h-6 px-2 text-xs"
                  title={
                    contextObjects.some(
                      (ctx) => ctx.object_id === view.id && ctx.object_type === 'view'
                    )
                      ? 'Already in context'
                      : 'Add to Chat'
                  }
                >
                  {contextObjects.some(
                    (ctx) => ctx.object_id === view.id && ctx.object_type === 'view'
                  ) ? (
                    <>
                      <Check className="h-3 w-3 mr-1" />
                      In Context
                    </>
                  ) : (
                    <>
                      <MessageSquare className="h-3 w-3 mr-1" />
                      Add to Chat
                    </>
                  )}
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={onRemove}
                className="h-6 w-6 p-0 shrink-0"
                title="Remove view"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div className="flex-1 min-h-0 overflow-hidden">
            <ViewEmbedder viewId={view.id} className="h-full w-full" />
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-center h-full min-h-[300px] p-4">
          <div className="text-center text-gray-400 dark:text-gray-500">
            <p className="text-sm">Drop a view here</p>
            <p className="text-xs mt-1">or drag from the left panel</p>
          </div>
        </div>
      )}
    </div>
  );
}
