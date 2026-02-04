'use client';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { VizQLQueryResponse } from '@/types';

interface QueryBuilderProps {
  userQuery: string;
  onUserQueryChange: (query: string) => void;
  vizqlQuery: string;
  onVizqlQueryChange: (query: string) => void;
  onConstruct: () => void;
  isConstructing: boolean;
  queryResult: VizQLQueryResponse | null;
}

export function QueryBuilder({
  userQuery,
  onUserQueryChange,
  vizqlQuery,
  onVizqlQueryChange,
  onConstruct,
  isConstructing,
  queryResult,
}: QueryBuilderProps) {
  return (
    <Card className="p-4">
      <h3 className="font-semibold mb-4">Query Builder</h3>

      <div className="space-y-4">
        {/* Natural Language Input */}
        <div>
          <Label htmlFor="user-query">Natural Language Query</Label>
          <Input
            id="user-query"
            placeholder="e.g., Show me total sales by region for 2024"
            value={userQuery}
            onChange={(e) => onUserQueryChange(e.target.value)}
            className="mt-1"
          />
          <Button
            onClick={onConstruct}
            disabled={isConstructing || !userQuery.trim()}
            className="mt-2"
          >
            {isConstructing ? 'Constructing...' : 'Construct VizQL Query'}
          </Button>
        </div>

        {/* Generated VizQL Query */}
        <div>
          <Label htmlFor="vizql-query">VizQL Query</Label>
          <textarea
            id="vizql-query"
            placeholder="Generated VizQL query will appear here..."
            value={vizqlQuery}
            onChange={(e) => onVizqlQueryChange(e.target.value)}
            className="mt-1 w-full p-2 border rounded-md font-mono text-sm bg-gray-50 dark:bg-gray-800"
            rows={6}
          />
        </div>

        {/* Query Explanation */}
        {queryResult && (
          <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <p className="text-sm font-medium mb-1">Explanation:</p>
            <p className="text-sm text-gray-700 dark:text-gray-300">
              {queryResult.explanation}
            </p>
            <div className="mt-2 flex gap-2 flex-wrap">
              {queryResult.measures.length > 0 && (
                <span className="text-xs">
                  Measures: {queryResult.measures.join(', ')}
                </span>
              )}
              {queryResult.dimensions.length > 0 && (
                <span className="text-xs">
                  Dimensions: {queryResult.dimensions.join(', ')}
                </span>
              )}
            </div>
            <div className="mt-2">
              <span
                className={`text-xs px-2 py-1 rounded ${
                  queryResult.valid
                    ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200'
                    : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200'
                }`}
              >
                {queryResult.valid ? 'Valid' : 'Invalid'}
              </span>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
