'use client';

import { useState, useEffect } from 'react';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { gatewayApi } from '@/lib/api';

interface ModelSettingsProps {
  provider: string;
  model: string;
  onProviderChange: (provider: string) => void;
  onModelChange: (model: string) => void;
}

export function ModelSettings({
  provider,
  model,
  onProviderChange,
  onModelChange,
}: ModelSettingsProps) {
  const [providers, setProviders] = useState<string[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const loadProviders = async () => {
    if (providers.length > 0) return;
    setLoading(true);
    try {
      const providerList = await gatewayApi.getProviders();
      setProviders(providerList);
    } catch (err) {
      console.error('Failed to load providers:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadModels = async (selectedProvider?: string) => {
    setLoading(true);
    try {
      // Fetch models filtered by provider
      const providerToUse = selectedProvider || provider;
      const modelList = await gatewayApi.getModels(providerToUse);
      setModels(modelList);
      
      // If current model is not in the filtered list, select first model
      if (modelList.length > 0 && !modelList.includes(model)) {
        onModelChange(modelList[0]);
      }
    } catch (err) {
      console.error('Failed to load models:', err);
    } finally {
      setLoading(false);
    }
  };

  // Load providers on mount
  useEffect(() => {
    loadProviders();
  }, []);

  // Load models on mount and when provider changes
  useEffect(() => {
    if (provider) {
      loadModels(provider);
    }
  }, [provider]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleProviderChange = async (newProvider: string) => {
    onProviderChange(newProvider);
    // Reload models for the new provider
    await loadModels(newProvider);
  };

  return (
    <div>
      <h3 className="text-sm font-semibold mb-4">Model Settings</h3>
      <div className="space-y-4">
        <div>
          <Label htmlFor="provider">Provider</Label>
          <Select
            value={provider}
            onValueChange={handleProviderChange}
            disabled={loading}
          >
            <SelectTrigger id="provider" className="w-full">
              <SelectValue placeholder="Select provider">
                {provider}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {providers.map((p) => (
                <SelectItem key={p} value={p}>
                  {p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        
        <div>
          <Label htmlFor="model">Model</Label>
          <Select
            value={model}
            onValueChange={onModelChange}
            disabled={loading}
          >
            <SelectTrigger id="model" className="w-full">
              <SelectValue placeholder="Select model">
                {model}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {models.length === 0 ? (
                <SelectItem value="loading" disabled>
                  Loading models...
                </SelectItem>
              ) : (
                models.map((m) => (
                  <SelectItem key={m} value={m}>
                    {m}
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );
}
