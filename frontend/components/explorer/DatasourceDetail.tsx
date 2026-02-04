'use client';

import { useEffect, useState } from 'react';
import { tableauExplorerApi } from '@/lib/api';
import type { DatasourceSchema, DatasourceSample, ColumnSchema } from '@/types';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';

interface DatasourceDetailProps {
  datasourceId: string;
  datasourceName: string;
  onAddToContext?: (objectId: string, objectType: 'datasource' | 'view', objectName?: string) => void;
  contextObjects?: Array<{ object_id: string; object_type: 'datasource' | 'view' }>;
}

export function DatasourceDetail({ 
  datasourceId, 
  datasourceName,
  onAddToContext,
  contextObjects = [],
}: DatasourceDetailProps) {
  const [schema, setSchema] = useState<DatasourceSchema | null>(null);
  const [sample, setSample] = useState<DatasourceSample | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [schemaData, sampleData] = await Promise.all([
          tableauExplorerApi.getDatasourceSchema(datasourceId),
          tableauExplorerApi.getDatasourceSample(datasourceId, 100),
        ]);
        setSchema(schemaData);
        setSample(sampleData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load datasource details');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [datasourceId]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <Card className="p-4">
        <div className="text-red-600 dark:text-red-400">Error: {error}</div>
      </Card>
    );
  }

  const isInContext = contextObjects.some(
    (ctx) => ctx.object_id === datasourceId && ctx.object_type === 'datasource'
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">{datasourceName}</h2>
        {onAddToContext && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onAddToContext(datasourceId, 'datasource', datasourceName)}
            disabled={isInContext}
            title={isInContext ? 'Already in context' : 'Add to Chat'}
          >
            {isInContext ? 'In Context' : 'Add to Chat'}
          </Button>
        )}
      </div>
      
      <Tabs defaultValue="schema" className="w-full">
        <TabsList>
          <TabsTrigger value="schema">Schema</TabsTrigger>
          <TabsTrigger value="sample">Sample Data</TabsTrigger>
        </TabsList>
        
        <TabsContent value="schema" className="mt-4">
          <Card className="p-4">
            <h3 className="font-semibold mb-4">Columns ({schema?.columns.length || 0})</h3>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2">Name</th>
                    <th className="text-left p-2">Data Type</th>
                    <th className="text-left p-2">Type</th>
                  </tr>
                </thead>
                <tbody>
                  {schema?.columns.map((col: ColumnSchema, idx: number) => (
                    <tr key={idx} className="border-b">
                      <td className="p-2 font-medium">{col.name}</td>
                      <td className="p-2 text-gray-600 dark:text-gray-400">{col.data_type || col.remote_type || '-'}</td>
                      <td className="p-2">
                        {col.is_measure && <span className="text-blue-600 dark:text-blue-400">Measure</span>}
                        {col.is_dimension && <span className="text-green-600 dark:text-green-400">Dimension</span>}
                        {!col.is_measure && !col.is_dimension && <span className="text-gray-400">-</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </TabsContent>
        
        <TabsContent value="sample" className="mt-4">
          <Card className="p-4">
            <h3 className="font-semibold mb-4">
              Sample Data ({sample?.row_count || 0} rows)
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b">
                    {sample?.columns.map((col, idx) => (
                      <th key={idx} className="text-left p-2 font-medium">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sample?.data.map((row, rowIdx) => (
                    <tr key={rowIdx} className="border-b">
                      {row.map((cell, cellIdx) => (
                        <td key={cellIdx} className="p-2">
                          {String(cell ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
