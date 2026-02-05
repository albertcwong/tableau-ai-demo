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
  className?: string;
  showProvider?: boolean;
}

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  vertex: 'Google Vertex AI',
  salesforce: 'Salesforce',
  apple: 'Apple Endor',
};

export function ModelSelector({
  selected,
  onSelect,
  className,
  showProvider = true,
}: ModelSelectorProps) {
  const [providers, setProviders] = useState<string[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch providers on mount
  useEffect(() => {
    const fetchProviders = async () => {
      try {
        const providerList = await gatewayApi.getProviders();
        setProviders(providerList);
        
        let foundProvider: string | null = null;
        
        // If we have a selected model, determine its provider
        if (selected) {
          // Find provider for selected model by fetching models for each provider
          for (const provider of providerList) {
            const providerModels = await gatewayApi.getModels(provider);
            if (providerModels.includes(selected)) {
              foundProvider = provider;
              setSelectedProvider(provider);
              setModels(providerModels);
              break;
            }
          }
          // If not found, fetch all models
          if (!foundProvider) {
            const allModels = await gatewayApi.getModels();
            setModels(allModels);
          }
        } else {
          // Default to first provider
          if (providerList.length > 0) {
            foundProvider = providerList[0];
            setSelectedProvider(providerList[0]);
            const providerModels = await gatewayApi.getModels(providerList[0]);
            setModels(providerModels);
            // Auto-select first model if none selected
            if (providerModels.length > 0) {
              onSelect(providerModels[0]);
            }
          } else {
            // Fallback: fetch all models
            const allModels = await gatewayApi.getModels();
            setModels(allModels);
          }
        }
      } catch (error) {
        console.error('Failed to fetch providers:', error);
        // Fallback to default models
        setModels([
          'gpt-4',
          'gpt-4-turbo',
          'gpt-4o',
          'gpt-3.5-turbo',
          'claude-3-opus',
          'claude-3-sonnet',
          'claude-3-haiku',
          'claude-3-5-sonnet',
          'gemini-pro',
          'gemini-1.5-pro',
          'gemini-1.5-flash',
          'sfdc-xgen',
          'einstein-gpt',
        ]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchProviders();
  }, []);

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
    }
  }, [selectedProvider]);

  const handleProviderChange = (provider: string) => {
    setSelectedProvider(provider);
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
                {selectedProvider ? (PROVIDER_LABELS[selectedProvider] || selectedProvider) : 'Select provider'}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {providers.map((provider) => (
                <SelectItem key={provider} value={provider}>
                  {PROVIDER_LABELS[provider] || provider}
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
