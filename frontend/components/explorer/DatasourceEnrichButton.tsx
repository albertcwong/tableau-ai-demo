'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card } from '@/components/ui/card';
import { RefreshCw, CheckCircle2, XCircle, Sparkles, ChevronDown, ChevronUp, Hash, Type } from 'lucide-react';
import { vizqlApi, type EnrichSchemaResponse } from '@/lib/api';
import { extractErrorMessage } from '@/lib/utils';
import { SchemaProfilingView } from './SchemaProfilingView';

interface DatasourceEnrichButtonProps {
  datasourceId: string;
  datasourceName?: string;
  onEnriched?: (result: EnrichSchemaResponse) => void;
}

export function DatasourceEnrichButton({ 
  datasourceId, 
  datasourceName,
  onEnriched 
}: DatasourceEnrichButtonProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<EnrichSchemaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  const handleEnrich = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const data = await vizqlApi.enrichSchema(datasourceId, false, true);
      setResult(data);
      
      if (onEnriched) {
        onEnriched(data);
      }
    } catch (err: unknown) {
      const e = err as { code?: string; message?: string };
      const isTimeout = e?.code === 'ECONNABORTED' || /timeout/i.test(e?.message || '');
      let errorMessage = extractErrorMessage(err, 'Failed to enrich schema');
      if (isTimeout) {
        errorMessage = 'Request timed out. The enrichment may have completed on the server. Try clicking the refresh button to load cached results.';
      }
      setError(errorMessage);
      console.error('Enrichment failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const data = await vizqlApi.enrichSchema(datasourceId, true, true);
      setResult(data);
      
      if (onEnriched) {
        onEnriched(data);
      }
    } catch (err: unknown) {
      const e = err as { code?: string; message?: string };
      const isTimeout = e?.code === 'ECONNABORTED' || /timeout/i.test(e?.message || '');
      let errorMessage = extractErrorMessage(err, 'Failed to refresh schema');
      if (isTimeout) {
        errorMessage = 'Request timed out. The server may still be processing. Try again in a moment.';
      }
      setError(errorMessage);
      console.error('Refresh failed:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Button 
          onClick={handleEnrich} 
          disabled={loading}
          variant="outline"
          size="sm"
          className="flex items-center gap-2"
        >
          {loading ? (
            <>
              <RefreshCw className="h-4 w-4 animate-spin" />
              Enriching...
            </>
          ) : result ? (
            <>
              <Sparkles className="h-4 w-4" />
              Re-enrich Schema
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              Enrich Schema for AI
            </>
          )}
        </Button>
        
        {result && (
          <Button
            onClick={handleRefresh}
            disabled={loading}
            variant="ghost"
            size="sm"
            title="Force refresh from Tableau API"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        )}
      </div>

      {error && (
        <Alert variant="destructive" className="py-2">
          <XCircle className="h-4 w-4" />
          <AlertDescription className="text-sm">{error}</AlertDescription>
        </Alert>
      )}

      {result && !error && (
        <div className="space-y-2">
          <Alert className="py-2 bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800">
            <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
            <AlertDescription className="text-sm text-green-800 dark:text-green-200">
              <div className="space-y-1">
                <div>
                  <strong>Enriched:</strong> {result.field_count} fields
                  {' '}({result.measure_count} measures, {result.dimension_count} dimensions)
                </div>
                {result.cached && (
                  <div className="text-xs text-green-600 dark:text-green-400">
                    Using cached data (1 hour TTL). Click refresh to force update.
                  </div>
                )}
              </div>
            </AlertDescription>
          </Alert>

          {/* Enriched Schema Details */}
          {result.enriched_schema && (
            <Card className="p-4 border-green-200 dark:border-green-800">
              <button
                onClick={() => setShowDetails(!showDetails)}
                className="w-full flex items-center justify-between text-left mb-2"
              >
                <h3 className="font-semibold text-sm text-gray-900 dark:text-gray-100">
                  Enriched Schema Details
                </h3>
                {showDetails ? (
                  <ChevronUp className="h-4 w-4 text-gray-500" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-gray-500" />
                )}
              </button>

              {showDetails && (
                <div className="mt-4">
                  <SchemaProfilingView enrichedSchema={result.enriched_schema} onEnriched={onEnriched} />
                </div>
              )}
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
