'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ViewSelector } from './ViewSelector';
import { ExportOptions } from './ExportOptions';
import { SummaryViewer } from './SummaryViewer';
import { agentsApi } from '@/lib/api';
import { useAgentContext } from './AgentContext';
import type { ExportViewsResponse, GenerateSummaryResponse, AggregateViewsResponse } from '@/types';

export function SummaryPanel() {
  const { selectedViews, setSelectedViews } = useAgentContext();
  const [exportResult, setExportResult] = useState<ExportViewsResponse | null>(null);
  const [summaryResult, setSummaryResult] = useState<GenerateSummaryResponse | null>(null);
  const [aggregateResult, setAggregateResult] = useState<AggregateViewsResponse | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isAggregating, setIsAggregating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exportFormat, setExportFormat] = useState<'json' | 'csv' | 'excel'>('json');
  const [summaryFormat, setSummaryFormat] = useState<'html' | 'markdown' | 'pdf'>('html');

  const handleExport = async () => {
    if (selectedViews.length === 0) {
      setError('Please select at least one view');
      return;
    }

    setIsExporting(true);
    setError(null);

    try {
      const result = await agentsApi.exportViews({
        view_ids: selectedViews,
        format: exportFormat,
      });
      setExportResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export views');
    } finally {
      setIsExporting(false);
    }
  };

  const handleGenerateSummary = async () => {
    if (selectedViews.length === 0) {
      setError('Please select at least one view');
      return;
    }

    setIsGenerating(true);
    setError(null);

    try {
      const result = await agentsApi.generateSummary({
        view_ids: selectedViews,
        format: summaryFormat,
        include_visualizations: true,
      });
      setSummaryResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate summary');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleAggregate = async (aggregationType: 'sum' | 'avg' | 'count' | 'max' | 'min', column?: string) => {
    if (selectedViews.length === 0) {
      setError('Please select at least one view');
      return;
    }

    setIsAggregating(true);
    setError(null);

    try {
      const result = await agentsApi.aggregateViews({
        view_ids: selectedViews,
        aggregation_type: aggregationType,
        column,
      });
      setAggregateResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to aggregate views');
    } finally {
      setIsAggregating(false);
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold mb-4">Summary Agent</h2>

      {/* View Selector */}
      <ViewSelector
        selectedViews={selectedViews}
        onSelectionChange={setSelectedViews}
      />

      {/* Export Options */}
      <ExportOptions
        format={exportFormat}
        onFormatChange={setExportFormat}
        onExport={handleExport}
        isExporting={isExporting}
        exportResult={exportResult}
      />

      {/* Summary Generation */}
      <Card className="p-4">
        <h3 className="font-semibold mb-4">Generate Summary Report</h3>
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Report Format</label>
            <select
              value={summaryFormat}
              onChange={(e) => setSummaryFormat(e.target.value as 'html' | 'markdown' | 'pdf')}
              className="w-full p-2 border rounded-md"
            >
              <option value="html">HTML</option>
              <option value="markdown">Markdown</option>
              <option value="pdf">PDF</option>
            </select>
          </div>
          <Button
            onClick={handleGenerateSummary}
            disabled={isGenerating || selectedViews.length === 0}
            className="w-full"
          >
            {isGenerating ? 'Generating...' : 'Generate Summary'}
          </Button>
        </div>
      </Card>

      {/* Aggregation */}
      <Card className="p-4">
        <h3 className="font-semibold mb-4">Aggregate Views</h3>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => handleAggregate('sum')}
            disabled={isAggregating || selectedViews.length === 0}
            variant="outline"
          >
            Sum
          </Button>
          <Button
            onClick={() => handleAggregate('avg')}
            disabled={isAggregating || selectedViews.length === 0}
            variant="outline"
          >
            Average
          </Button>
          <Button
            onClick={() => handleAggregate('count')}
            disabled={isAggregating || selectedViews.length === 0}
            variant="outline"
          >
            Count
          </Button>
          <Button
            onClick={() => handleAggregate('max')}
            disabled={isAggregating || selectedViews.length === 0}
            variant="outline"
          >
            Max
          </Button>
          <Button
            onClick={() => handleAggregate('min')}
            disabled={isAggregating || selectedViews.length === 0}
            variant="outline"
          >
            Min
          </Button>
        </div>
        {aggregateResult && (
          <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <p className="text-sm font-medium">Total: {aggregateResult.total}</p>
            <div className="mt-2 space-y-1">
              {Object.entries(aggregateResult.by_view).map(([viewId, value]) => (
                <p key={viewId} className="text-xs">
                  {viewId}: {value}
                </p>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* Summary Viewer */}
      {summaryResult && (
        <SummaryViewer summary={summaryResult} />
      )}

      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
          <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
        </div>
      )}
    </div>
  );
}
