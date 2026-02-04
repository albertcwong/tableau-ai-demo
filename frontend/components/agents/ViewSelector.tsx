'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import type { TableauView } from '@/types';
import { apiClient } from '@/lib/api';

interface ViewSelectorProps {
  selectedViews: string[];
  onSelectionChange: (views: string[]) => void;
}

export function ViewSelector({ selectedViews, onSelectionChange }: ViewSelectorProps) {
  const [views, setViews] = useState<TableauView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadViews();
  }, []);

  const loadViews = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/api/v1/tableau/views');
      const data = response.data;
      setViews(Array.isArray(data.views) ? data.views : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load views');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleView = (viewId: string) => {
    if (selectedViews.includes(viewId)) {
      onSelectionChange(selectedViews.filter((id) => id !== viewId));
    } else {
      onSelectionChange([...selectedViews, viewId]);
    }
  };

  if (loading) {
    return (
      <Card className="p-4">
        <h3 className="font-semibold mb-2">Select Views</h3>
        <p className="text-sm text-gray-600 dark:text-gray-400">Loading views...</p>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-4">
        <h3 className="font-semibold mb-2">Select Views</h3>
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      </Card>
    );
  }

  return (
    <Card className="p-4">
      <h3 className="font-semibold mb-4">
        Select Views ({selectedViews.length} selected)
      </h3>

      {views.length === 0 ? (
        <p className="text-sm text-gray-600 dark:text-gray-400">
          No views available. Please create views in Tableau first.
        </p>
      ) : (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {views.map((view) => (
            <label
              key={view.id}
              className="flex items-center space-x-2 p-2 hover:bg-gray-50 dark:hover:bg-gray-800 rounded cursor-pointer"
            >
              <input
                type="checkbox"
                checked={selectedViews.includes(view.id)}
                onChange={() => handleToggleView(view.id)}
                className="rounded"
              />
              <span className="text-sm">{view.name}</span>
            </label>
          ))}
        </div>
      )}
    </Card>
  );
}
