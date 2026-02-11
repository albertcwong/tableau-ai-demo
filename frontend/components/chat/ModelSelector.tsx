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
  className?: string;
  showProvider?: boolean;
}

export function ModelSelector({
  selected,
  onSelect,
  onProviderChange,
  className,
  showProvider = true,
}: ModelSelectorProps) {
  const [providers, setProviders] = useState<Array<{ provider: string; name: string }>>([]);
  const [providerMap, setProviderMap] = useState<Record<string, string>>({});
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch providers on mount
  useEffect(() => {
    const fetchProviders = async () => {
      try {
        const providerList = await gatewayApi.getProviders();
        setProviders(providerList);
        
        // Create a map of provider -> display name for quick lookup
        const map: Record<string, string> = {};
        providerList.forEach(p => {
          map[p.provider] = p.name;
        });
        setProviderMap(map);
        
        let foundProvider: string | null = null;
        
        // If we have a selected model, determine its provider
        if (selected) {
          // Find provider for selected model by fetching models for each provider
          for (const providerConfig of providerList) {
            const providerModels = await gatewayApi.getModels(providerConfig.provider);
            if (providerModels.includes(selected)) {
              foundProvider = providerConfig.provider;
              setSelectedProvider(providerConfig.provider);
              if (onProviderChange) {
                onProviderChange(providerConfig.provider);
              }
              setModels(providerModels);
              break;
            }
          }
          // If not found, fetch all models
          if (!foundProvider) {
            const allModels = await gatewayApi.getModels();
            setModels(allModels);
            // Default to first provider if model not found
            if (providerList.length > 0) {
              const defaultProvider = providerList[0].provider;
              setSelectedProvider(defaultProvider);
              if (onProviderChange) {
                onProviderChange(defaultProvider);
              }
            }
          }
        } else {
          // Fetch ALL models from all providers (no provider filter)
          const allModels = await gatewayApi.getModels();
          setModels(allModels);
          // Auto-select first model if none selected
          if (allModels.length > 0) {
            onSelect(allModels[0]);
          }
          // Set provider to first one for display, but show all models
          if (providerList.length > 0) {
            const defaultProvider = providerList[0].provider;
            setSelectedProvider(defaultProvider);
            if (onProviderChange) {
              onProviderChange(defaultProvider);
            }
          }
        }
        } catch (error) {
          console.error('Failed to fetch providers:', error);
          // Fallback: try to get models from health endpoint or use minimal defaults
          try {
            // Try health endpoint with models included
            const health = await gatewayApi.health(true);
            if (health.models && health.models.length > 0) {
              setModels(health.models);
            } else {
              // Try direct models endpoint as fallback
              const allModels = await gatewayApi.getModels();
              if (allModels.length > 0) {
                setModels(allModels);
              } else {
                // Minimal fallback - just the most common models
                setModels(['gpt-4', 'gpt-3.5-turbo', 'claude-3-5-sonnet']);
              }
            }
            // Set default provider in fallback case
            if (providerList.length > 0) {
              const defaultProvider = providerList[0].provider;
              setSelectedProvider(defaultProvider);
              if (onProviderChange) {
                onProviderChange(defaultProvider);
              }
            }
          } catch (healthError) {
            // Last resort: minimal fallback
            console.error('Failed to fetch from health/models endpoints:', healthError);
            setModels(['gpt-4', 'gpt-3.5-turbo']);
            // Still try to set a default provider if we have providers
            if (providerList.length > 0) {
              const defaultProvider = providerList[0].provider;
              setSelectedProvider(defaultProvider);
              if (onProviderChange) {
                onProviderChange(defaultProvider);
              }
            }
          }
        } finally {
        setIsLoading(false);
      }
    };

    fetchProviders();
  }, [selected]);

  // Fetch models when provider changes
  useEffect(() => {
    if (selectedProvider) {
      const fetchModels = async () => {
        try {
          const providerModels = await gatewayApi.getModels(selectedProvider);
          setModels(providerModels);
          // Auto-select first model if current selection not in new list
          if (providerModels.length > 0 && !providerModels.includes(selected)) {
            onSelect(providerModels[0]);
          }
        } catch (error) {
          console.error('Failed to fetch models:', error);
        }
      };
      fetchModels();
    } else {
      // Fetch all models if no provider selected
      const fetchAllModels = async () => {
        try {
          const allModels = await gatewayApi.getModels();
          setModels(allModels);
        } catch (error) {
          console.error('Failed to fetch all models:', error);
        }
      };
      fetchAllModels();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProvider, selected]);

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
