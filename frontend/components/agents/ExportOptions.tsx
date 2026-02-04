'use client';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import type { ExportViewsResponse } from '@/types';

interface ExportOptionsProps {
  format: 'json' | 'csv' | 'excel';
  onFormatChange: (format: 'json' | 'csv' | 'excel') => void;
  onExport: () => void;
  isExporting: boolean;
  exportResult: ExportViewsResponse | null;
}

export function ExportOptions({
  format,
  onFormatChange,
  onExport,
  isExporting,
  exportResult,
}: ExportOptionsProps) {
  const handleDownload = () => {
    if (!exportResult) return;

    const dataStr = JSON.stringify(exportResult.datasets, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `export-${Date.now()}.${format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Card className="p-4">
      <h3 className="font-semibold mb-4">Export Views</h3>

      <div className="space-y-4">
        {/* Format Selection */}
        <div>
          <label className="text-sm font-medium mb-2 block">Export Format</label>
          <select
            value={format}
            onChange={(e) => onFormatChange(e.target.value as 'json' | 'csv' | 'excel')}
            className="w-full p-2 border rounded-md"
          >
            <option value="json">JSON</option>
            <option value="csv">CSV</option>
            <option value="excel">Excel</option>
          </select>
        </div>

        {/* Export Button */}
        <Button
          onClick={onExport}
          disabled={isExporting}
          className="w-full"
        >
          {isExporting ? 'Exporting...' : 'Export Views'}
        </Button>

        {/* Export Results */}
        {exportResult && (
          <div className="space-y-2">
            <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
              <p className="text-sm font-medium mb-1">Export Complete</p>
              <p className="text-sm text-gray-700 dark:text-gray-300">
                {exportResult.view_count} views exported | {exportResult.total_rows} total rows
              </p>
            </div>

            {/* Download Button */}
            <Button
              onClick={handleDownload}
              variant="outline"
              className="w-full"
            >
              Download Export
            </Button>

            {/* Export Details */}
            <div className="space-y-2">
              {exportResult.datasets.map((dataset, idx) => (
                <div
                  key={idx}
                  className="p-2 bg-gray-50 dark:bg-gray-800 rounded text-xs"
                >
                  <p className="font-medium">View {dataset.view_id}</p>
                  <p className="text-gray-600 dark:text-gray-400">
                    {dataset.row_count} rows × {dataset.columns?.length || 0} columns
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
