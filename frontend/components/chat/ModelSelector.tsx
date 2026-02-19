'use client';

import { useState, useEffect } from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { gatewayApi } from '@/lib/api';
import { cn } from '@/lib/utils';

export interface ModelSelectorProps {
  selected: string;
  onSelect: (model: string) => void;
  onProviderChange?: (provider: string) => void;
  initialProvider?: string;
  className?: string;
  showProvider?: boolean;
}

export function ModelSelector({
  selected,
  onSelect,
  onProviderChange,
  initialProvider,
  className,
  showProvider = true,
}: ModelSelectorProps) {
  const [providers, setProviders] = useState<Array<{ provider: string; name: string }>>([]);
  const [providerMap, setProviderMap] = useState<Record<string, string>>({});
  const [selectedProvider, setSelectedProvider] = useState<string | null>(initialProvider ?? null);
  const [models, setModels] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch providers on mount (once)
  useEffect(() => {
    const fetchProviders = async () => {
      try {
        const providerList = await gatewayApi.getProviders();
        setProviders(providerList);

        const map: Record<string, string> = {};
        providerList.forEach(p => { map[p.provider] = p.name; });
        setProviderMap(map);

        // Use initialProvider if it's in the list; otherwise fall back to first provider
        const providerIds = providerList.map(p => p.provider);
        const startProvider = initialProvider && providerIds.includes(initialProvider)
          ? initialProvider
          : providerList[0]?.provider;
        if (startProvider) {
          setSelectedProvider(startProvider);
          if (onProviderChange) onProviderChange(startProvider);
        }
      } catch (error) {
        console.error('Failed to fetch providers:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchProviders();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch models when provider changes
  useEffect(() => {
    if (!selectedProvider) return;
    const fetchModels = async () => {
      try {
        const providerModels = await gatewayApi.getModels(selectedProvider);
        setModels(providerModels);
        // Auto-select first model if current selection is not in this provider's list
        if (providerModels.length > 0 && !providerModels.includes(selected)) {
          onSelect(providerModels[0]);
        }
      } catch (error) {
        console.error('Failed to fetch models:', error);
      }
    };
    fetchModels();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProvider]);

  const handleProviderChange = (provider: string) => {
    setSelectedProvider(provider);
    if (onProviderChange) {
      onProviderChange(provider);
    }
  };

  if (isLoading) {
    return (
      <div className={className}>
        <Label className="text-sm font-medium mb-2 block">Loading...</Label>
        <Select disabled>
          <SelectTrigger className="w-full">
            <SelectValue>Loading models...</SelectValue>
          </SelectTrigger>
        </Select>
      </div>
    );
  }

  return (
    <div className={cn('space-y-4', className)}>
      {showProvider && providers.length > 0 && (
        <div>
          <Label htmlFor="provider-select" className="text-sm font-medium mb-2 block">
            Provider
          </Label>
          <Select
            value={selectedProvider || ''}
            onValueChange={handleProviderChange}
          >
            <SelectTrigger id="provider-select" className="w-full">
              <SelectValue placeholder="Select provider">
                {selectedProvider ? (providerMap[selectedProvider] || selectedProvider) : 'Select provider'}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {providers.map((providerConfig) => (
                <SelectItem key={providerConfig.provider} value={providerConfig.provider}>
                  {providerConfig.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
      <div>
        <Label htmlFor="model-select" className="text-sm font-medium mb-2 block">
          Model
        </Label>
        <Select
          value={selected}
          onValueChange={onSelect}
          disabled={models.length === 0}
        >
          <SelectTrigger id="model-select" className="w-full">
            <SelectValue placeholder="Select model">
              {selected || 'Select model'}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {models.length === 0 ? (
              <SelectItem value="" disabled>No models available</SelectItem>
            ) : (
              models.map((model) => (
                <SelectItem key={model} value={model}>
                  {model}
                </SelectItem>
              ))
            )}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
