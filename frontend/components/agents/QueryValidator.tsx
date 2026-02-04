'use client';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import type { VizQLExecuteResponse } from '@/types';

interface QueryValidatorProps {
  vizqlQuery: string;
  onExecute: () => void;
  isExecuting: boolean;
  executeResult: VizQLExecuteResponse | null;
}

export function QueryValidator({
  vizqlQuery,
  onExecute,
  isExecuting,
  executeResult,
}: QueryValidatorProps) {
  const isValid = vizqlQuery.trim().length > 0 && vizqlQuery.toUpperCase().includes('SELECT');

  return (
    <Card className="p-4">
      <h3 className="font-semibold mb-4">Query Validator & Execution</h3>

      <div className="space-y-4">
        {/* Validation Status */}
        <div className="flex items-center gap-2">
          <span className="text-sm">Status:</span>
          <span
            className={`text-xs px-2 py-1 rounded ${
              isValid
                ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200'
                : 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200'
            }`}
          >
            {isValid ? 'Valid Syntax' : 'Invalid Syntax'}
          </span>
        </div>

        {/* Execute Button */}
        <Button
          onClick={onExecute}
          disabled={!isValid || isExecuting}
          className="w-full"
        >
          {isExecuting ? 'Executing...' : 'Execute Query'}
        </Button>

        {/* Execution Results */}
        {executeResult && (
          <div className="space-y-2">
            <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
              <p className="text-sm font-medium mb-1">Execution Results</p>
              <p className="text-sm text-gray-700 dark:text-gray-300">
                Rows: {executeResult.row_count} | Columns: {executeResult.columns.length}
              </p>
            </div>

            {/* Data Table */}
            {executeResult.data.length > 0 && (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-gray-100 dark:bg-gray-800">
                      {executeResult.columns.map((col, idx) => (
                        <th
                          key={idx}
                          className="border p-2 text-left font-medium"
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {executeResult.data.slice(0, 10).map((row, rowIdx) => (
                      <tr key={rowIdx} className="border-b">
                        {row.map((cell, cellIdx) => (
                          <td key={cellIdx} className="border p-2">
                            {String(cell)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {executeResult.data.length > 10 && (
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-2">
                    Showing first 10 of {executeResult.data.length} rows
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
