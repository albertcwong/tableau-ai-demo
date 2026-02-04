'use client';

import { useState } from 'react';
import { ObjectIcon, ObjectType } from './ObjectIcon';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import type { TableauProject, TableauDatasource, TableauWorkbook, TableauView } from '@/types';

interface ObjectListProps {
  projects?: TableauProject[];
  datasources?: TableauDatasource[];
  workbooks?: TableauWorkbook[];
  views?: TableauView[];
  onSelectProject?: (project: TableauProject) => void;
  onSelectDatasource?: (datasource: TableauDatasource) => void;
  onSelectWorkbook?: (workbook: TableauWorkbook) => void;
  onSelectView?: (view: TableauView) => void;
  onAddToContext?: (objectId: string, objectType: 'datasource' | 'view', objectName?: string) => void;
  contextObjects?: Array<{ object_id: string; object_type: 'datasource' | 'view' }>;
}

export function ObjectList({
  projects = [],
  datasources = [],
  workbooks = [],
  views = [],
  onSelectProject,
  onSelectDatasource,
  onSelectWorkbook,
  onSelectView,
  onAddToContext,
  contextObjects = [],
}: ObjectListProps) {
  const allItems: Array<{
    id: string;
    name: string;
    type: ObjectType;
    data: TableauProject | TableauDatasource | TableauWorkbook | TableauView;
  }> = [
    ...projects.map((p) => ({ id: p.id, name: p.name, type: 'project' as const, data: p })),
    ...datasources.map((d) => ({ id: d.id, name: d.name, type: 'datasource' as const, data: d })),
    ...workbooks.map((w) => ({ id: w.id, name: w.name, type: 'workbook' as const, data: w })),
    ...views.map((v) => ({ id: v.id, name: v.name, type: 'view' as const, data: v })),
  ];

  // Deduplicate by type-id combination to prevent duplicate keys
  const seen = new Set<string>();
  const uniqueItems = allItems.filter((item) => {
    const key = `${item.type}-${item.id}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });

  const handleClick = (item: typeof allItems[0]) => {
    switch (item.type) {
      case 'project':
        onSelectProject?.(item.data as TableauProject);
        break;
      case 'datasource':
        onSelectDatasource?.(item.data as TableauDatasource);
        break;
      case 'workbook':
        onSelectWorkbook?.(item.data as TableauWorkbook);
        break;
      case 'view':
        onSelectView?.(item.data as TableauView);
        break;
    }
  };

  if (uniqueItems.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400">
        No items found
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {uniqueItems.map((item) => (
        <Card
          key={`${item.type}-${item.id}`}
          className="p-3 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
          onClick={() => handleClick(item)}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 flex-1">
              <ObjectIcon type={item.type} />
              <div className="flex-1">
                <div className="font-medium text-gray-900 dark:text-gray-100">{item.name}</div>
                {item.type === 'datasource' && (item.data as TableauDatasource).project_name && (
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    {(item.data as TableauDatasource).project_name}
                  </div>
                )}
                {item.type === 'workbook' && (item.data as TableauWorkbook).project_name && (
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    {(item.data as TableauWorkbook).project_name}
                  </div>
                )}
                {item.type === 'view' && (item.data as TableauView).workbook_name && (
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    {(item.data as TableauView).workbook_name}
                  </div>
                )}
              </div>
            </div>
            {(item.type === 'datasource' || item.type === 'view') && onAddToContext && (() => {
              const isInContext = contextObjects.some(
                (ctx) => ctx.object_id === item.id && ctx.object_type === item.type
              );
              return (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (!isInContext) {
                      onAddToContext(item.id, item.type, item.name);
                    }
                  }}
                  disabled={isInContext}
                  className="ml-2"
                  title={isInContext ? 'Already in context' : 'Add to Chat'}
                >
                  {isInContext ? 'In Context' : 'Add to Chat'}
                </Button>
              );
            })()}
          </div>
        </Card>
      ))}
    </div>
  );
}
