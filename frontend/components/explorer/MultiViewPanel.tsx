'use client';

import { useState, useEffect } from 'react';
import { ViewDropZone } from './ViewDropZone';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Grid } from 'lucide-react';
import type { TableauView } from '@/types';

interface MultiViewPanelProps {
  gridWidth: number;
  gridHeight: number;
  onGridChange: (width: number, height: number) => void;
  views: Array<TableauView | null>;
  onViewsChange: (views: Array<TableauView | null>) => void;
  onAddToContext?: (objectId: string, objectType: 'datasource' | 'view', objectName?: string) => void;
  contextObjects?: Array<{ object_id: string; object_type: 'datasource' | 'view' }>;
}

export function MultiViewPanel({ 
  gridWidth, 
  gridHeight, 
  onGridChange,
  views, 
  onViewsChange,
  onAddToContext,
  contextObjects = []
}: MultiViewPanelProps) {
  const [widthInput, setWidthInput] = useState(gridWidth.toString());
  const [heightInput, setHeightInput] = useState(gridHeight.toString());

  useEffect(() => {
    setWidthInput(gridWidth.toString());
    setHeightInput(gridHeight.toString());
  }, [gridWidth, gridHeight]);

  const totalSlots = gridWidth * gridHeight;

  // Adjust views array when grid size changes
  useEffect(() => {
    const currentLength = views.length;
    if (currentLength < totalSlots) {
      const newViews = [...views];
      while (newViews.length < totalSlots) {
        newViews.push(null);
      }
      onViewsChange(newViews);
    } else if (currentLength > totalSlots) {
      onViewsChange(views.slice(0, totalSlots));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [totalSlots]);

  const handleGridSizeChange = () => {
    const width = parseInt(widthInput, 10);
    const height = parseInt(heightInput, 10);
    
    if (width >= 1 && width <= 6 && height >= 1 && height <= 6) {
      onGridChange(width, height);
    }
  };

  const handleDrop = (index: number, view: TableauView) => {
    const newViews = [...views];
    // Check if view already exists in another slot
    const existingIndex = newViews.findIndex(v => v?.id === view.id);
    if (existingIndex !== -1 && existingIndex !== index) {
      // Swap views if dropping on a different slot
      const temp = newViews[index];
      newViews[index] = view;
      newViews[existingIndex] = temp;
    } else {
      newViews[index] = view;
    }
    onViewsChange(newViews);
  };

  const handleViewRemove = (index: number) => {
    const newViews = [...views];
    newViews[index] = null;
    onViewsChange(newViews);
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800 shrink-0 bg-white dark:bg-gray-900">
        <div className="flex items-center gap-2">
          <Grid className="h-5 w-5 text-gray-500 dark:text-gray-400" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">View Canvas</h2>
          <span className="text-sm text-gray-500 dark:text-gray-400">
            ({views.filter(v => v !== null).length} / {totalSlots})
          </span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Label htmlFor="grid-width" className="text-sm text-gray-600 dark:text-gray-400">
              Width:
            </Label>
            <Input
              id="grid-width"
              type="number"
              min="1"
              max="6"
              value={widthInput}
              onChange={(e) => setWidthInput(e.target.value)}
              onBlur={handleGridSizeChange}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleGridSizeChange();
                }
              }}
              className="w-16 h-8 text-sm"
            />
          </div>
          <div className="flex items-center gap-2">
            <Label htmlFor="grid-height" className="text-sm text-gray-600 dark:text-gray-400">
              Height:
            </Label>
            <Input
              id="grid-height"
              type="number"
              min="1"
              max="6"
              value={heightInput}
              onChange={(e) => setHeightInput(e.target.value)}
              onBlur={handleGridSizeChange}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleGridSizeChange();
                }
              }}
              className="w-16 h-8 text-sm"
            />
          </div>
        </div>
      </div>
      <div className="flex-1 min-h-0 overflow-auto p-4">
        <div 
          className="grid gap-4"
          style={{ 
            gridTemplateColumns: `repeat(${gridWidth}, 1fr)`,
            gridTemplateRows: `repeat(${gridHeight}, 1fr)`,
            height: '100%'
          }}
        >
          {views.slice(0, totalSlots).map((view, index) => (
            <ViewDropZone
              key={index}
              view={view}
              onRemove={() => handleViewRemove(index)}
              onDrop={(droppedView) => handleDrop(index, droppedView)}
              onAddToContext={onAddToContext}
              contextObjects={contextObjects}
              className="min-h-[400px]"
            />
          ))}
        </div>
      </div>
    </div>
  );
}
