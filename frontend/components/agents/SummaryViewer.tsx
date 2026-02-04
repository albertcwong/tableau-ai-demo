'use client';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import type { GenerateSummaryResponse } from '@/types';

interface SummaryViewerProps {
  summary: GenerateSummaryResponse;
}

export function SummaryViewer({ summary }: SummaryViewerProps) {
  const handleDownload = () => {
    const blob = new Blob([summary.content], {
      type: summary.format === 'html' ? 'text/html' : 'text/markdown',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `summary-${Date.now()}.${summary.format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold">Summary Report</h3>
        <Button onClick={handleDownload} variant="outline" size="sm">
          Download
        </Button>
      </div>

      <div className="space-y-4">
        {/* Summary Stats */}
        <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <p className="text-sm">
            <span className="font-medium">{summary.view_count}</span> views |{' '}
            <span className="font-medium">{summary.total_rows}</span> total rows
          </p>
        </div>

        {/* Report Content */}
        {summary.format === 'html' ? (
          <div
            className="prose dark:prose-invert max-w-none"
            dangerouslySetInnerHTML={{ __html: summary.content }}
          />
        ) : (
          <pre className="p-4 bg-gray-50 dark:bg-gray-800 rounded overflow-x-auto text-sm">
            {summary.content}
          </pre>
        )}

        {/* Visualizations */}
        {summary.visualizations.length > 0 && (
          <div>
            <h4 className="text-sm font-medium mb-2">Visualizations</h4>
            <div className="space-y-2">
              {summary.visualizations.map((viz) => (
                <div
                  key={viz.view_id}
                  className="p-2 bg-gray-50 dark:bg-gray-800 rounded text-xs"
                >
                  <a
                    href={viz.embed_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    View {viz.view_id}
                  </a>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
