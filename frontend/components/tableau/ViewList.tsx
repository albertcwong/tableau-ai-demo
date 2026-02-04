'use client';

import { useEffect, useState } from 'react';
import { getViews } from '@/lib/tableau';
import type { TableauView } from '@/types';

interface ViewListProps {
  datasourceId?: string;
  workbookId?: string;
  onSelect?: (view: TableauView) => void;
  className?: string;
}

/**
 * ViewList component for displaying a list of Tableau views
 */
export function ViewList({
  datasourceId,
  workbookId,
  onSelect,
  className = '',
}: ViewListProps) {
  const [views, setViews] = useState<TableauView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadViews() {
      try {
        setLoading(true);
        setError(null);

        const data = await getViews(datasourceId, workbookId);
        if (!mounted) return;

        setViews(data);
        setLoading(false);
      } catch (err) {
        if (!mounted) return;
        const errorMessage = err instanceof Error ? err.message : 'Failed to load views';
        setError(errorMessage);
        setLoading(false);
      }
    }

    loadViews();

    return () => {
      mounted = false;
    };
  }, [datasourceId, workbookId]);

  if (loading) {
    return (
      <div className={`flex items-center justify-center p-8 ${className}`}>
        <div className="text-center">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]" />
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">Loading views...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20 ${className}`}>
        <p className="text-sm font-medium text-red-800 dark:text-red-200">
          Error loading views
        </p>
        <p className="mt-1 text-sm text-red-600 dark:text-red-300">{error}</p>
      </div>
    );
  }

  if (views.length === 0) {
    return (
      <div className={`rounded-lg border border-gray-200 bg-gray-50 p-8 text-center dark:border-gray-700 dark:bg-gray-800 ${className}`}>
        <p className="text-sm text-gray-600 dark:text-gray-400">No views found</p>
      </div>
    );
  }

  return (
    <div className={`space-y-2 ${className}`}>
      {views.map((view) => (
        <button
          key={view.id}
          onClick={() => onSelect?.(view)}
          className={`w-full rounded-lg border border-gray-200 bg-white p-4 text-left transition-colors hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:hover:bg-gray-700 ${
            onSelect ? 'cursor-pointer' : 'cursor-default'
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">
                {view.name}
              </h3>
              <div className="mt-1 space-y-0.5">
                {view.workbook_name && (
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Workbook: {view.workbook_name}
                  </p>
                )}
                {view.datasource_id && (
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Datasource: {view.datasource_id.slice(0, 8)}...
                  </p>
                )}
              </div>
            </div>
            {view.id && (
              <span className="ml-4 text-xs text-gray-400 dark:text-gray-500">
                {view.id.slice(0, 8)}...
              </span>
            )}
          </div>
        </button>
      ))}
    </div>
  );
}
