'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card } from '@/components/ui/card';
import { RefreshCw, CheckCircle2, XCircle, Sparkles, ChevronDown, ChevronUp, Hash, Type } from 'lucide-react';
import { vizqlApi, type EnrichSchemaResponse } from '@/lib/api';

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
    } catch (err: any) {
      const isTimeout = err.code === 'ECONNABORTED' || /timeout/i.test(err.message || '');
      let errorMessage = err.response?.data?.detail || err.message || 'Failed to enrich schema';
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
    } catch (err: any) {
      const isTimeout = err.code === 'ECONNABORTED' || /timeout/i.test(err.message || '');
      let errorMessage = err.response?.data?.detail || err.message || 'Failed to refresh schema';
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
                <div className="space-y-4 mt-4">
                  {/* Measures */}
                  {result.enriched_schema.measures.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <Hash className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                          Measures ({result.enriched_schema.measures.length})
                        </h4>
                      </div>
                      <div className="space-y-1 pl-6">
                        {result.enriched_schema.measures.map((measureName) => {
                          const field = result.enriched_schema.fields.find(
                            (f) => f.fieldCaption === measureName
                          );
                          return (
                            <div
                              key={measureName}
                              className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400"
                            >
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <span className="font-medium">{measureName}</span>
                                  {field && (
                                    <>
                                      <span className="text-gray-400 dark:text-gray-500">•</span>
                                      <span className="text-gray-500 dark:text-gray-500">
                                        {field.dataType}
                                      </span>
                                      {(field.defaultAggregation || field.suggestedAggregation) && (
                                        <>
                                          <span className="text-gray-400 dark:text-gray-500">•</span>
                                          <span className="px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded text-xs">
                                            {field.defaultAggregation || field.suggestedAggregation}
                                          </span>
                                        </>
                                      )}
                                    </>
                                  )}
                                </div>
                                {field && (field.min != null || field.max != null || field.cardinality != null || field.formula) && (
                                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 pl-4 space-y-0.5">
                                    {field.min != null && field.max != null && (
                                      <span>Range: {field.min} - {field.max}</span>
                                    )}
                                    {field.cardinality != null && typeof field.cardinality === 'number' && (
                                      <>
                                        {field.min != null && <span className="mx-1">•</span>}
                                        <span>Distinct: {field.cardinality.toLocaleString()}</span>
                                      </>
                                    )}
                                    {field.formula && (
                                      <div className="mt-1">
                                        <span className="font-medium text-gray-600 dark:text-gray-300">Formula:</span>
                                        <code className="ml-1 text-xs bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded font-mono break-all">
                                          {field.formula}
                                        </code>
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Dimensions */}
                  {result.enriched_schema.dimensions.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <Type className="h-4 w-4 text-green-600 dark:text-green-400" />
                        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                          Dimensions ({result.enriched_schema.dimensions.length})
                        </h4>
                      </div>
                      <div className="space-y-1 pl-6">
                        {result.enriched_schema.dimensions.map((dimensionName) => {
                          const field = result.enriched_schema.fields.find(
                            (f) => f.fieldCaption === dimensionName
                          );
                          return (
                            <div
                              key={dimensionName}
                              className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400"
                            >
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <span className="font-medium">{dimensionName}</span>
                                  {field && (
                                    <>
                                      <span className="text-gray-400 dark:text-gray-500">•</span>
                                      <span className="text-gray-500 dark:text-gray-500">
                                        {field.dataType}
                                      </span>
                                      {field.fieldType && field.fieldType !== 'UNKNOWN' && (
                                        <>
                                          <span className="text-gray-400 dark:text-gray-500">•</span>
                                          <span className="text-gray-500 dark:text-gray-500">
                                            {field.fieldType}
                                          </span>
                                        </>
                                      )}
                                    </>
                                  )}
                                </div>
                                {field && (field.cardinality != null || (field.sample_values && field.sample_values.length > 0) || field.formula) && (
                                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 pl-4 space-y-0.5">
                                    {field.cardinality != null && typeof field.cardinality === 'number' && (
                                      <span>Distinct: {field.cardinality.toLocaleString()}</span>
                                    )}
                                    {field.sample_values && field.sample_values.length > 0 && (
                                      <>
                                        {field.cardinality != null && <span className="mx-1">•</span>}
                                        <span>
                                          Samples: {field.sample_values.slice(0, 3).join(", ")}
                                          {field.sample_values.length > 3 && "..."}
                                        </span>
                                      </>
                                    )}
                                    {field.formula && (
                                      <div className="mt-1">
                                        <span className="font-medium text-gray-600 dark:text-gray-300">Formula:</span>
                                        <code className="ml-1 text-xs bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded font-mono break-all">
                                          {field.formula}
                                        </code>
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* All Fields (if measures/dimensions are empty) */}
                  {result.enriched_schema.measures.length === 0 &&
                    result.enriched_schema.dimensions.length === 0 &&
                    result.enriched_schema.fields.length > 0 && (
                      <div>
                        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                          All Fields ({result.enriched_schema.fields.length})
                        </h4>
                        <div className="space-y-1 pl-6">
                          {result.enriched_schema.fields.map((field) => (
                            <div
                              key={field.fieldCaption}
                              className="text-xs text-gray-600 dark:text-gray-400"
                            >
                              <div className="flex items-center gap-2">
                                <span className="font-medium">{field.fieldCaption}</span>
                                <span className="text-gray-400 dark:text-gray-500">•</span>
                                <span className="text-gray-500 dark:text-gray-500">
                                  {field.dataType}
                                </span>
                                <span className="text-gray-400 dark:text-gray-500">•</span>
                                <span className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded text-xs">
                                  {field.fieldRole}
                                </span>
                              </div>
                              {field.formula && (
                                <div className="mt-1 pl-4">
                                  <span className="font-medium text-gray-600 dark:text-gray-300">Formula:</span>
                                  <code className="ml-1 text-xs bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded font-mono break-all">
                                    {field.formula}
                                  </code>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                </div>
              )}
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
