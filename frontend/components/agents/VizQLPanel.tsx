'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { SchemaViewer } from './SchemaViewer';
import { QueryBuilder } from './QueryBuilder';
import { QueryValidator } from './QueryValidator';
import { agentsApi } from '@/lib/api';
import { useAgentContext } from './AgentContext';
import type { VizQLQueryResponse, VizQLExecuteResponse } from '@/types';

export function VizQLPanel() {
  const { selectedDatasource } = useAgentContext();
  const [userQuery, setUserQuery] = useState('');
  const [vizqlQuery, setVizqlQuery] = useState('');
  const [queryResult, setQueryResult] = useState<VizQLQueryResponse | null>(null);
  const [executeResult, setExecuteResult] = useState<VizQLExecuteResponse | null>(null);
  const [isConstructing, setIsConstructing] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConstructQuery = async () => {
    if (!selectedDatasource || !userQuery.trim()) {
      setError('Please select a datasource and enter a query');
      return;
    }

    setIsConstructing(true);
    setError(null);

    try {
      const result = await agentsApi.constructVizQL({
        user_query: userQuery,
        datasource_id: selectedDatasource.id,
      });
      setQueryResult(result);
      setVizqlQuery(result.vizql);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to construct query');
    } finally {
      setIsConstructing(false);
    }
  };

  const handleExecuteQuery = async () => {
    if (!selectedDatasource || !vizqlQuery.trim()) {
      setError('Please select a datasource and enter a VizQL query');
      return;
    }

    setIsExecuting(true);
    setError(null);

    try {
      const result = await agentsApi.executeVizQL({
        datasource_id: selectedDatasource.id,
        vizql_query: vizqlQuery,
      });
      setExecuteResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to execute query');
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold mb-4">VizQL Agent</h2>

      {!selectedDatasource && (
        <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
          <p className="text-sm text-yellow-800 dark:text-yellow-200">
            Please select a datasource from the Analyst Agent panel first.
          </p>
        </div>
      )}

      {selectedDatasource && (
        <>
          {/* Schema Viewer */}
          <SchemaViewer datasourceId={selectedDatasource.id} />

          {/* Query Builder */}
          <QueryBuilder
            userQuery={userQuery}
            onUserQueryChange={setUserQuery}
            vizqlQuery={vizqlQuery}
            onVizqlQueryChange={setVizqlQuery}
            onConstruct={handleConstructQuery}
            isConstructing={isConstructing}
            queryResult={queryResult}
          />

          {/* Query Validator */}
          <QueryValidator
            vizqlQuery={vizqlQuery}
            onExecute={handleExecuteQuery}
            isExecuting={isExecuting}
            executeResult={executeResult}
          />
        </>
      )}

      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
          <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
        </div>
      )}
    </div>
  );
}
