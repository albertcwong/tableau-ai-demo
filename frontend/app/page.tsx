'use client';

import { useState } from 'react';
import Link from 'next/link';
import { DataSourceList, ViewList, ViewEmbedder } from '@/components/tableau';
import { Button } from '@/components/ui/button';
import type { TableauDatasource, TableauView } from '@/types';

export default function Home() {
  const [selectedDatasource, setSelectedDatasource] = useState<TableauDatasource | null>(null);
  const [selectedView, setSelectedView] = useState<TableauView | null>(null);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="container mx-auto px-3 sm:px-4 py-4 sm:py-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 sm:mb-8 gap-4">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
            Tableau AI Demo - Component Testing
          </h1>
          <div className="flex gap-2">
            <Link href="/agents">
              <Button variant="default" className="bg-blue-600 hover:bg-blue-700">
                Multi-Agent Dashboard
              </Button>
            </Link>
            <Link href="/chat-test">
              <Button variant="outline">Chat Test</Button>
            </Link>
            <Link href="/mcp-test">
              <Button variant="outline">MCP Test</Button>
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
          {/* Datasources Panel */}
          <div className="lg:col-span-1">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 sm:p-6">
              <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-white mb-3 sm:mb-4">
                Datasources
              </h2>
              <DataSourceList
                onSelect={(ds) => {
                  setSelectedDatasource(ds);
                  setSelectedView(null); // Clear selected view when datasource changes
                }}
              />
            </div>
          </div>

          {/* Views Panel */}
          <div className="lg:col-span-1">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 sm:p-6">
              <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-white mb-3 sm:mb-4">
                Views
                {selectedDatasource && (
                  <span className="text-xs sm:text-sm font-normal text-gray-500 dark:text-gray-400 ml-1 sm:ml-2 block sm:inline">
                    (filtered by {selectedDatasource.name})
                  </span>
                )}
              </h2>
              <ViewList
                datasourceId={selectedDatasource?.id}
                onSelect={(view) => setSelectedView(view)}
              />
            </div>
          </div>

          {/* View Embedder Panel */}
          <div className="lg:col-span-1">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 sm:p-6">
              <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-white mb-3 sm:mb-4">
                Embedded View
              </h2>
              {selectedView ? (
                <div className="space-y-4">
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    <p className="font-medium">{selectedView.name}</p>
                    {selectedView.workbook_name && (
                      <p className="text-xs mt-1">Workbook: {selectedView.workbook_name}</p>
                    )}
                  </div>
                  <ViewEmbedder
                    viewId={selectedView.id}
                    className="border border-gray-200 dark:border-gray-700 rounded"
                  />
                </div>
              ) : (
                <div className="flex items-center justify-center h-64 text-gray-500 dark:text-gray-400">
                  <p className="text-sm">Select a view to embed</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Full-width embed section */}
        {selectedView && (
          <div className="mt-4 sm:mt-6 bg-white dark:bg-gray-800 rounded-lg shadow p-4 sm:p-6">
            <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-white mb-3 sm:mb-4">
              Full View: {selectedView.name}
            </h2>
            <ViewEmbedder
              viewId={selectedView.id}
              className="border border-gray-200 dark:border-gray-700 rounded"
            />
          </div>
        )}
      </div>
    </div>
  );
}
