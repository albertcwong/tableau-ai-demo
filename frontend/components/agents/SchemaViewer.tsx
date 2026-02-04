'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import type { TableauDatasource } from '@/types';

interface SchemaInfo {
  columns: string[];
  measures: Array<{ name: string; type: string; aggregation: string }>;
  dimensions: Array<{ name: string; type: string }>;
  data_types: Record<string, string>;
}

interface SchemaViewerProps {
  datasourceId: string;
}

export function SchemaViewer({ datasourceId }: SchemaViewerProps) {
  const [schema, setSchema] = useState<SchemaInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // In a real implementation, this would fetch schema from the API
    // For now, we'll use a placeholder
    setLoading(false);
    setSchema({
      columns: ['sales', 'region', 'year', 'product'],
      measures: [
        { name: 'sales', type: 'float', aggregation: 'sum' },
      ],
      dimensions: [
        { name: 'region', type: 'string' },
        { name: 'year', type: 'int' },
        { name: 'product', type: 'string' },
      ],
      data_types: {
        sales: 'float',
        region: 'string',
        year: 'int',
        product: 'string',
      },
    });
  }, [datasourceId]);

  if (loading) {
    return (
      <Card className="p-4">
        <h3 className="font-semibold mb-2">Schema</h3>
        <p className="text-sm text-gray-600 dark:text-gray-400">Loading...</p>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-4">
        <h3 className="font-semibold mb-2">Schema</h3>
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      </Card>
    );
  }

  if (!schema) {
    return null;
  }

  return (
    <Card className="p-4">
      <h3 className="font-semibold mb-4">Datasource Schema</h3>

      <div className="space-y-4">
        {/* Measures */}
        <div>
          <h4 className="text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">
            Measures ({schema.measures.length})
          </h4>
          <div className="flex flex-wrap gap-2">
            {schema.measures.map((measure) => (
              <span
                key={measure.name}
                className="px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 rounded text-xs"
              >
                {measure.name} ({measure.aggregation})
              </span>
            ))}
          </div>
        </div>

        {/* Dimensions */}
        <div>
          <h4 className="text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">
            Dimensions ({schema.dimensions.length})
          </h4>
          <div className="flex flex-wrap gap-2">
            {schema.dimensions.map((dim) => (
              <span
                key={dim.name}
                className="px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200 rounded text-xs"
              >
                {dim.name} ({dim.type})
              </span>
            ))}
          </div>
        </div>

        {/* All Columns */}
        <div>
          <h4 className="text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">
            All Columns ({schema.columns.length})
          </h4>
          <div className="flex flex-wrap gap-2">
            {schema.columns.map((col) => (
              <span
                key={col}
                className="px-2 py-1 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded text-xs"
              >
                {col}
              </span>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}
