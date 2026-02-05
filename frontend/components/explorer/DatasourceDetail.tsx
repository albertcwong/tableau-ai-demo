'use client';

import { useEffect, useState, useRef } from 'react';
import { tableauExplorerApi } from '@/lib/api';
import type { DatasourceSample } from '@/types';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Code2, Play, Loader2, ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react';
import { DatasourceEnrichButton } from './DatasourceEnrichButton';

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
  const [sample, setSample] = useState<DatasourceSample | null>(null);
  const [query, setQuery] = useState<string>('');
  const queryRef = useRef<string>('');
  const [queryError, setQueryError] = useState<string | null>(null);
  const [queryResults, setQueryResults] = useState<{ columns: string[]; data: unknown[][]; row_count: number } | null>(null);
  const [executing, setExecuting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortColumn, setSortColumn] = useState<number | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  
  // Keep ref in sync with state
  useEffect(() => {
    queryRef.current = query;
  }, [query]);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        // Check if there's a stored query from chat interface
        const storedQueryKey = `vizql_query_${datasourceId}`;
        const storedQuery = localStorage.getItem(storedQueryKey);
        console.log('DatasourceDetail mount - datasourceId:', datasourceId, 'storedQuery:', storedQuery ? 'found' : 'not found');
        if (storedQuery) {
          console.log('Loading stored query into editor');
          // Validate that stored query is valid JSON before setting it
          try {
            JSON.parse(storedQuery);
            setQuery(storedQuery);
            localStorage.removeItem(storedQueryKey); // Clear after loading
          } catch (err) {
            console.error('Stored query is not valid JSON:', err);
            setError('Stored query contains invalid JSON. Please try loading the query again.');
            localStorage.removeItem(storedQueryKey); // Clear invalid query
          }
        } else {
          const sampleData = await tableauExplorerApi.getDatasourceSample(datasourceId, 100);
          setSample(sampleData);
          if (sampleData.query) {
            setQuery(JSON.stringify(sampleData.query, null, 2));
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load datasource sample');
      } finally {
        setLoading(false);
      }
    };

    loadData();
    
    // Listen for loadVizQLQuery event (for when query is loaded after component mounts)
    const handleLoadQuery = (event: CustomEvent) => {
      console.log('DatasourceDetail received loadVizQLQuery event:', event.detail);
      if (event.detail && event.detail.datasourceId === datasourceId) {
        console.log('Loading query from event into editor');
        try {
          const queryStr = typeof event.detail.query === 'string' 
            ? event.detail.query 
            : JSON.stringify(event.detail.query, null, 2);
          // Validate JSON before setting
          JSON.parse(queryStr);
          setQuery(queryStr);
          // Also clear from localStorage if it exists
          localStorage.removeItem(`vizql_query_${datasourceId}`);
        } catch (err) {
          console.error('Failed to stringify/validate query from event:', err);
          setError('Failed to load query: Invalid JSON format');
        }
      }
    };
    
    window.addEventListener('loadVizQLQuery', handleLoadQuery as EventListener);
    
    // Also check localStorage periodically in case query was stored after mount
    // This handles the case where query is stored before datasource is selected
    const checkInterval = setInterval(() => {
      const storedQueryKey = `vizql_query_${datasourceId}`;
      const storedQuery = localStorage.getItem(storedQueryKey);
      if (storedQuery && storedQuery !== queryRef.current && storedQuery.trim() !== '') {
        try {
          // Validate JSON before setting
          JSON.parse(storedQuery);
          console.log('Found query in localStorage on interval check, loading into editor');
          setQuery(storedQuery);
          localStorage.removeItem(storedQueryKey);
        } catch (err) {
          console.error('Stored query is not valid JSON on interval check:', err);
          localStorage.removeItem(storedQueryKey); // Clear invalid query
        }
      }
    }, 200); // Check every 200ms for faster response
    
    return () => {
      window.removeEventListener('loadVizQLQuery', handleLoadQuery as EventListener);
      clearInterval(checkInterval);
    };
  }, [datasourceId]);

  // Reset sort when datasource changes
  useEffect(() => {
    setSortColumn(null);
    setSortDirection('asc');
  }, [datasourceId]);

  const handleSort = (columnIndex: number) => {
    if (sortColumn === columnIndex) {
      // Toggle direction if clicking the same column
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      // New column, default to ascending
      setSortColumn(columnIndex);
      setSortDirection('asc');
    }
  };

  const sortData = (data: unknown[][], columnIndex: number, direction: 'asc' | 'desc'): unknown[][] => {
    return [...data].sort((a, b) => {
      const aVal = a[columnIndex];
      const bVal = b[columnIndex];
      
      // Handle null/undefined values
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return direction === 'asc' ? -1 : 1;
      if (bVal == null) return direction === 'asc' ? 1 : -1;
      
      // Try numeric comparison first
      const aNum = typeof aVal === 'string' ? parseFloat(aVal) : typeof aVal === 'number' ? aVal : NaN;
      const bNum = typeof bVal === 'string' ? parseFloat(bVal) : typeof bVal === 'number' ? bVal : NaN;
      
      if (!isNaN(aNum) && !isNaN(bNum)) {
        return direction === 'asc' ? aNum - bNum : bNum - aNum;
      }
      
      // String comparison
      const aStr = String(aVal).toLowerCase();
      const bStr = String(bVal).toLowerCase();
      
      if (aStr < bStr) return direction === 'asc' ? -1 : 1;
      if (aStr > bStr) return direction === 'asc' ? 1 : -1;
      return 0;
    });
  };

  const handleExecuteQuery = async () => {
    setExecuting(true);
    setQueryError(null);
    setQueryResults(null);
    setSortColumn(null);
    setSortDirection('asc');

    try {
      let cleanedQuery = query.trim();
      
      // Handle case where query might be double-stringified (wrapped in quotes)
      if (cleanedQuery.startsWith('"') && cleanedQuery.endsWith('"')) {
        try {
          cleanedQuery = JSON.parse(cleanedQuery);
          // If successful, re-stringify it properly
          cleanedQuery = JSON.stringify(cleanedQuery, null, 2);
        } catch {
          // If that fails, continue with original
        }
      }
      
      // Parse the JSON
      let parsedQuery;
      try {
        parsedQuery = JSON.parse(cleanedQuery);
      } catch (parseError) {
        // Provide detailed error message with context
        if (parseError instanceof SyntaxError) {
          const errorMsg = parseError.message || 'Unknown parsing error';
          // Extract line and column numbers from error message
          const match = errorMsg.match(/line (\d+) column (\d+)/);
          if (match) {
            const lineNum = parseInt(match[1]);
            const colNum = parseInt(match[2]);
            const lines = cleanedQuery.split('\n');
            const problemLine = lines[lineNum - 1] || '';
            const context = problemLine.substring(Math.max(0, colNum - 30), colNum + 30);
            setQueryError(`Failed to parse query JSON: ${errorMsg}\n\nProblem at line ${lineNum}, column ${colNum}:\n${context}\n${' '.repeat(Math.min(30, colNum))}^`);
          } else {
            setQueryError(`Failed to parse query JSON: ${errorMsg}\n\nPlease check that your JSON is valid and doesn't contain unescaped control characters.`);
          }
        } else {
          setQueryError(`Failed to parse query: ${parseError instanceof Error ? parseError.message : 'Unknown error'}`);
        }
        return;
      }
      
      const results = await tableauExplorerApi.executeVDSQuery(datasourceId, parsedQuery);
      setQueryResults(results);
    } catch (err) {
      if (err instanceof SyntaxError) {
        const errorMsg = err.message || 'Invalid JSON format';
        setQueryError(`Failed to parse query JSON: ${errorMsg}`);
      } else {
        setQueryError(err instanceof Error ? err.message : 'Failed to execute query');
      }
    } finally {
      setExecuting(false);
    }
  };

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
      
      <div className="space-y-4">
        <Card className="p-4">
          <DatasourceEnrichButton 
            datasourceId={datasourceId}
            datasourceName={datasourceName}
          />
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <Code2 className="h-4 w-4 text-gray-500 dark:text-gray-400" />
            <h3 className="font-semibold text-gray-900 dark:text-white">VizQL Data Service Query</h3>
          </div>
          <div className="space-y-3">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full h-64 font-mono text-sm bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded p-3 text-gray-900 dark:text-gray-100 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
              placeholder="Enter VizQL Data Service query as JSON..."
            />
            {queryError && (
              <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 p-2 rounded">
                {queryError}
              </div>
            )}
            <div className="flex justify-end">
              <Button
                onClick={handleExecuteQuery}
                disabled={!query || executing}
                className="flex items-center gap-2"
              >
                {executing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Executing...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    Execute Query
                  </>
                )}
              </Button>
            </div>
          </div>
        </Card>
        
        <Card className="p-4">
          <h3 className="font-semibold mb-4">
            Query Results ({queryResults?.row_count || sample?.row_count || 0} rows)
          </h3>
          {queryResults ? (
            <div className="overflow-x-auto overflow-y-auto max-h-[60vh] border rounded">
              <table className="w-full border-collapse text-sm">
                <thead className="sticky top-0 bg-white dark:bg-gray-900 z-10">
                  <tr className="border-b">
                    {queryResults.columns.map((col, idx) => {
                      const isSorted = sortColumn === idx;
                      return (
                        <th 
                          key={idx} 
                          className="text-left p-2 font-medium cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 select-none"
                          onClick={() => handleSort(idx)}
                        >
                          <div className="flex items-center gap-1">
                            <span>{col}</span>
                            {isSorted ? (
                              sortDirection === 'asc' ? (
                                <ArrowUp className="h-3 w-3" />
                              ) : (
                                <ArrowDown className="h-3 w-3" />
                              )
                            ) : (
                              <ArrowUpDown className="h-3 w-3 opacity-30" />
                            )}
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {(sortColumn !== null 
                    ? sortData(queryResults.data, sortColumn, sortDirection)
                    : queryResults.data
                  ).map((row, rowIdx) => (
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
          ) : (
            <div className="overflow-x-auto overflow-y-auto max-h-[60vh] border rounded">
              <table className="w-full border-collapse text-sm">
                <thead className="sticky top-0 bg-white dark:bg-gray-900 z-10">
                  <tr className="border-b">
                    {sample?.columns.map((col, idx) => {
                      const isSorted = sortColumn === idx;
                      return (
                        <th 
                          key={idx} 
                          className="text-left p-2 font-medium cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 select-none"
                          onClick={() => handleSort(idx)}
                        >
                          <div className="flex items-center gap-1">
                            <span>{col}</span>
                            {isSorted ? (
                              sortDirection === 'asc' ? (
                                <ArrowUp className="h-3 w-3" />
                              ) : (
                                <ArrowDown className="h-3 w-3" />
                              )
                            ) : (
                              <ArrowUpDown className="h-3 w-3 opacity-30" />
                            )}
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {(sample?.data && sortColumn !== null
                    ? sortData(sample.data, sortColumn, sortDirection)
                    : sample?.data || []
                  ).map((row, rowIdx) => (
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
          )}
        </Card>
      </div>
    </div>
  );
}
