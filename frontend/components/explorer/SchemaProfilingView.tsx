'use client';

import { useState, useMemo } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Hash, Type, BarChart2, Calendar, ToggleLeft, ArrowUpDown, ArrowDown, ArrowUp } from 'lucide-react';
import type { EnrichSchemaResponse } from '@/lib/api';
import { ValueDetailModal } from './ValueDetailModal';

interface SchemaProfilingViewProps {
  enrichedSchema: EnrichSchemaResponse['enriched_schema'];
  onEnriched?: (result: EnrichSchemaResponse) => void;
}

type SortMode = 'cardinality' | 'alphabetical';

const MAX_BAR_WIDTH = 300;
const MIN_BAR_WIDTH = 4;
const MAX_VISIBLE_ITEMS = 10;

function getDataTypeIcon(dataType: string) {
  const dt = dataType.toUpperCase();
  if (dt === 'STRING') return Type;
  if (dt === 'INTEGER') return Hash;
  if (['REAL', 'DOUBLE', 'FLOAT'].includes(dt)) return BarChart2;
  if (['DATE', 'DATETIME'].includes(dt)) return Calendar;
  if (dt === 'BOOLEAN') return ToggleLeft;
  return Type;
}

export function SchemaProfilingView({ enrichedSchema }: SchemaProfilingViewProps) {
  const [selectedField, setSelectedField] = useState<any>(null);
  const [dimensionSort, setDimensionSort] = useState<SortMode>('cardinality');
  const [measureSort, setMeasureSort] = useState<SortMode>('cardinality');

  const dimensions = useMemo(() => {
    const dims = enrichedSchema.dimensions
      .map(name => enrichedSchema.fields.find(f => f.fieldCaption === name))
      .filter(Boolean) as typeof enrichedSchema.fields;
    
    if (dimensionSort === 'cardinality') {
      return [...dims].sort((a, b) => {
        const aCard = a.cardinality ?? 0;
        const bCard = b.cardinality ?? 0;
        return bCard - aCard;
      });
    } else {
      return [...dims].sort((a, b) => a.fieldCaption.localeCompare(b.fieldCaption));
    }
  }, [enrichedSchema.dimensions, enrichedSchema.fields, dimensionSort]);

  const measures = useMemo(() => {
    const meas = enrichedSchema.measures
      .map(name => enrichedSchema.fields.find(f => f.fieldCaption === name))
      .filter(Boolean) as typeof enrichedSchema.fields;
    
    if (measureSort === 'cardinality') {
      return [...meas].sort((a, b) => {
        const aRange = (a.max ?? 0) - (a.min ?? 0);
        const bRange = (b.max ?? 0) - (b.min ?? 0);
        return bRange - aRange;
      });
    } else {
      return [...meas].sort((a, b) => a.fieldCaption.localeCompare(b.fieldCaption));
    }
  }, [enrichedSchema.measures, enrichedSchema.fields, measureSort]);

  const maxCardinality = useMemo(() => {
    return Math.max(...dimensions.map(d => d.cardinality ?? 0), 1);
  }, [dimensions]);

  const maxRange = useMemo(() => {
    return Math.max(...measures.map(m => (m.max ?? 0) - (m.min ?? 0)), 1);
  }, [measures]);

  const getBarWidth = (cardinality: number | null | undefined, isMeasure: boolean) => {
    if (isMeasure) {
      const range = (cardinality ?? 0);
      return Math.max(MIN_BAR_WIDTH, (range / maxRange) * MAX_BAR_WIDTH);
    } else {
      const card = cardinality ?? 0;
      return Math.max(MIN_BAR_WIDTH, (card / maxCardinality) * MAX_BAR_WIDTH);
    }
  };

  const getHoverTooltip = (field: typeof enrichedSchema.fields[0]) => {
    if (field.fieldRole === 'MEASURE') {
      const parts = [];
      if (field.min != null) parts.push(`Min: ${field.min}`);
      if (field.max != null) parts.push(`Max: ${field.max}`);
      if (field.median != null) parts.push(`Median: ${field.median}`);
      return parts.join(', ') || 'No stats available';
    } else {
      const parts = [];
      if (field.cardinality != null) {
        parts.push(`Cardinality: ${field.cardinality.toLocaleString()}`);
      }
      if (field.sample_values && field.sample_values.length > 0) {
        const sampleStr = field.sample_values.slice(0, 5).join(', ');
        const more = field.sample_values.length > 5 ? '...' : '';
        parts.push(`Samples: ${sampleStr}${more}`);
      }
      return parts.join(' | ') || 'No stats available';
    }
  };

  return (
    <>
      <div className="space-y-6">
        {/* Dimensions Section */}
        {dimensions.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Type className="h-4 w-4 text-green-600 dark:text-green-400" />
                <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                  Dimensions ({dimensions.length})
                </h4>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => setDimensionSort(dimensionSort === 'cardinality' ? 'alphabetical' : 'cardinality')}
                >
                  {dimensionSort === 'cardinality' ? (
                    <>
                      <ArrowDown className="h-3 w-3 mr-1" />
                      Cardinality
                    </>
                  ) : (
                    <>
                      <ArrowUpDown className="h-3 w-3 mr-1" />
                      Alphabetical
                    </>
                  )}
                </Button>
              </div>
            </div>
            {dimensions.length > MAX_VISIBLE_ITEMS ? (
              <ScrollArea className="h-[280px]">
                <div className="space-y-2 pr-4">
                  {dimensions.map((field) => {
                    const barWidth = getBarWidth(field.cardinality, false);
                    return (
                      <div
                        key={field.fieldCaption}
                        className="group relative flex items-center gap-3 p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
                        onClick={() => setSelectedField(field)}
                        title={getHoverTooltip(field)}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-medium text-gray-900 dark:text-gray-100 truncate">
                            {field.fieldCaption}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <div className="text-xs text-gray-500 dark:text-gray-400 w-16 text-right">
                            {field.cardinality?.toLocaleString() ?? 'N/A'}
                          </div>
                          <div className="relative w-[300px] h-6 bg-gray-200 dark:bg-gray-700 rounded overflow-hidden">
                            <div
                              className="h-full bg-blue-200 dark:bg-blue-800/50 transition-all"
                              style={{ width: `${barWidth}px` }}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </ScrollArea>
            ) : (
              <div className="space-y-2">
                {dimensions.map((field) => {
                  const barWidth = getBarWidth(field.cardinality, false);
                  return (
                    <div
                      key={field.fieldCaption}
                      className="group relative flex items-center gap-3 p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
                      onClick={() => setSelectedField(field)}
                      title={getHoverTooltip(field)}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-medium text-gray-900 dark:text-gray-100 truncate">
                          {field.fieldCaption}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <div className="text-xs text-gray-500 dark:text-gray-400 w-16 text-right">
                          {field.cardinality?.toLocaleString() ?? 'N/A'}
                        </div>
                        <div className="relative w-[300px] h-6 bg-gray-200 dark:bg-gray-700 rounded overflow-hidden">
                          <div
                            className="h-full bg-blue-200 dark:bg-blue-800/50 transition-all"
                            style={{ width: `${barWidth}px` }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Measures Section */}
        {measures.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Hash className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                  Measures ({measures.length})
                </h4>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => setMeasureSort(measureSort === 'cardinality' ? 'alphabetical' : 'cardinality')}
                >
                  {measureSort === 'cardinality' ? (
                    <>
                      <ArrowDown className="h-3 w-3 mr-1" />
                      Range
                    </>
                  ) : (
                    <>
                      <ArrowUpDown className="h-3 w-3 mr-1" />
                      Alphabetical
                    </>
                  )}
                </Button>
              </div>
            </div>
            {measures.length > MAX_VISIBLE_ITEMS ? (
              <ScrollArea className="h-[280px]">
                <div className="space-y-2 pr-4">
                  {measures.map((field) => {
                    const range = (field.max ?? 0) - (field.min ?? 0);
                    const barWidth = getBarWidth(range, true);
                    return (
                      <div
                        key={field.fieldCaption}
                        className="group relative flex items-center gap-3 p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
                        onClick={() => setSelectedField(field)}
                        title={getHoverTooltip(field)}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-medium text-gray-900 dark:text-gray-100 truncate">
                            {field.fieldCaption}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <div className="text-xs text-gray-500 dark:text-gray-400 w-20 text-right">
                            {field.min != null && field.max != null
                              ? `${field.min.toLocaleString()} - ${field.max.toLocaleString()}`
                              : 'N/A'}
                          </div>
                          <div className="relative w-[300px] h-6 bg-gray-200 dark:bg-gray-700 rounded overflow-hidden">
                            <div
                              className="h-full bg-blue-200 dark:bg-blue-800/50 transition-all"
                              style={{ width: `${barWidth}px` }}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </ScrollArea>
            ) : (
              <div className="space-y-2">
                {measures.map((field) => {
                  const range = (field.max ?? 0) - (field.min ?? 0);
                  const barWidth = getBarWidth(range, true);
                  return (
                    <div
                      key={field.fieldCaption}
                      className="group relative flex items-center gap-3 p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
                      onClick={() => setSelectedField(field)}
                      title={getHoverTooltip(field)}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-medium text-gray-900 dark:text-gray-100 truncate">
                          {field.fieldCaption}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <div className="text-xs text-gray-500 dark:text-gray-400 w-20 text-right">
                          {field.min != null && field.max != null
                            ? `${field.min.toLocaleString()} - ${field.max.toLocaleString()}`
                            : 'N/A'}
                        </div>
                        <div className="relative w-[300px] h-6 bg-gray-200 dark:bg-gray-700 rounded overflow-hidden">
                          <div
                            className="h-full bg-blue-200 dark:bg-blue-800/50 transition-all"
                            style={{ width: `${barWidth}px` }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {dimensions.length === 0 && measures.length === 0 && (
          <div className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
            Enrich schema to see distribution.
          </div>
        )}
      </div>

      {selectedField && (
        <ValueDetailModal
          field={selectedField}
          onClose={() => setSelectedField(null)}
        />
      )}
    </>
  );
}
