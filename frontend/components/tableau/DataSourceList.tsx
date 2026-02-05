'use client';

import { useEffect, useState } from 'react';
import { getDatasources } from '@/lib/tableau';
import type { TableauDatasource } from '@/types';

interface DataSourceListProps {
  projectId?: string;
  onSelect?: (datasource: TableauDatasource) => void;
  className?: string;
}

/**
 * DataSourceList component for displaying a list of Tableau datasources
 */
export function DataSourceList({
  projectId,
  onSelect,
  className = '',
}: DataSourceListProps) {
  const [datasources, setDatasources] = useState<TableauDatasource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadDatasources() {
      try {
        setLoading(true);
        setError(null);

        const data = await getDatasources(projectId);
        if (!mounted) return;

        setDatasources(data);
        setLoading(false);
      } catch (err: any) {
        if (!mounted) return;
        let errorMessage = 'Failed to load datasources';
        if (err.response?.status === 401 || err.response?.status === 503) {
          errorMessage = 'Tableau server is not accessible. Please ensure you are connected to the VPN and have authenticated with Tableau.';
        } else if (err instanceof Error) {
          errorMessage = err.message;
        }
        setError(errorMessage);
        setLoading(false);
      }
    }

    loadDatasources();

    return () => {
      mounted = false;
    };
  }, [projectId]);

  if (loading) {
    return (
      <div className={`flex items-center justify-center p-8 ${className}`}>
        <div className="text-center">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]" />
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">Loading datasources...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20 ${className}`}>
        <p className="text-sm font-medium text-red-800 dark:text-red-200">
          Error loading datasources
        </p>
        <p className="mt-1 text-sm text-red-600 dark:text-red-300">{error}</p>
      </div>
    );
  }

  if (datasources.length === 0) {
    return (
      <div className={`rounded-lg border border-gray-200 bg-gray-50 p-8 text-center dark:border-gray-700 dark:bg-gray-800 ${className}`}>
        <p className="text-sm text-gray-600 dark:text-gray-400">No datasources found</p>
      </div>
    );
  }

  return (
    <div className={`space-y-2 ${className}`}>
      {datasources.map((datasource) => (
        <button
          key={datasource.id}
          onClick={() => onSelect?.(datasource)}
          className={`w-full rounded-lg border border-gray-200 bg-white p-4 text-left transition-colors hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:hover:bg-gray-700 ${
            onSelect ? 'cursor-pointer' : 'cursor-default'
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">
                {datasource.name}
              </h3>
              {datasource.project_name && (
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Project: {datasource.project_name}
                </p>
              )}
            </div>
            {datasource.id && (
              <span className="ml-4 text-xs text-gray-400 dark:text-gray-500">
                {datasource.id.slice(0, 8)}...
              </span>
            )}
          </div>
        </button>
      ))}
    </div>
  );
}
