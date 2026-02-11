'use client';

import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Hash, Type, BarChart2, Calendar, ToggleLeft } from 'lucide-react';

interface ValueDetailModalProps {
  field: {
    fieldCaption: string;
    fieldRole: string;
    dataType: string;
    value_counts?: Array<{ value: string; count: number }>;
    cardinality?: number | null;
    min?: number | null;
    max?: number | null;
    median?: number | null;
    defaultAggregation?: string;
    suggestedAggregation?: string;
    null_percentage?: number | null;
  };
  onClose: () => void;
}

function getDataTypeIcon(dataType: string) {
  const dt = dataType.toUpperCase();
  if (dt === 'STRING') return Type;
  if (dt === 'INTEGER') return Hash;
  if (['REAL', 'DOUBLE', 'FLOAT'].includes(dt)) return BarChart2;
  if (['DATE', 'DATETIME'].includes(dt)) return Calendar;
  if (dt === 'BOOLEAN') return ToggleLeft;
  return Type;
}

export function ValueDetailModal({ field, onClose }: ValueDetailModalProps) {
  const Icon = getDataTypeIcon(field.dataType);
  const isMeasure = field.fieldRole === 'MEASURE';

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Icon className="h-5 w-5 text-gray-600 dark:text-gray-400" />
            <span>{field.fieldCaption}</span>
            {isMeasure && (
              <span className="text-xs font-normal text-gray-500 dark:text-gray-400 ml-2">
                - Measure Statistics
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        {isMeasure ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-4">
              {field.min != null && (
                <div>
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400">Min</div>
                  <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                    {field.min.toLocaleString()}
                  </div>
                </div>
              )}
              {field.max != null && (
                <div>
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400">Max</div>
                  <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                    {field.max.toLocaleString()}
                  </div>
                </div>
              )}
              {field.median != null && (
                <div>
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400">Median</div>
                  <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                    {field.median.toLocaleString()}
                  </div>
                </div>
              )}
              {(field.defaultAggregation || field.suggestedAggregation) && (
                <div>
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400">Default Aggregation</div>
                  <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                    {field.defaultAggregation || field.suggestedAggregation}
                  </div>
                </div>
              )}
              {field.null_percentage != null && (
                <div>
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400">Null %</div>
                  <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                    {field.null_percentage.toFixed(2)}%
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {field.cardinality != null && (
              <div className="text-xs text-gray-500 dark:text-gray-400">
                {field.value_counts?.length ?? 0} of {field.cardinality.toLocaleString()} distinct values shown
              </div>
            )}
            {field.value_counts && field.value_counts.length > 0 ? (
              <ScrollArea className="h-[400px]">
                <div className="space-y-1">
                  <div className="grid grid-cols-2 gap-4 pb-2 border-b border-gray-200 dark:border-gray-700 font-medium text-xs text-gray-700 dark:text-gray-300">
                    <div>Value</div>
                    <div className="text-right">Count</div>
                  </div>
                  {field.value_counts.map((vc, idx) => (
                    <div
                      key={idx}
                      className="grid grid-cols-2 gap-4 py-1 text-xs hover:bg-gray-50 dark:hover:bg-gray-800 rounded"
                    >
                      <div className="text-gray-900 dark:text-gray-100 truncate">{vc.value}</div>
                      <div className="text-right text-gray-600 dark:text-gray-400">
                        {vc.count.toLocaleString()}
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            ) : (
              <div className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
                No value counts available
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
