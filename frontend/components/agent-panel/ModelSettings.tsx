'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { ChevronDown, ChevronUp } from 'lucide-react';
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
  const [expanded, setExpanded] = useState(false);
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
      const modelList = await gatewayApi.getModels(selectedProvider || provider);
      setModels(modelList);
    } catch (err) {
      console.error('Failed to load models:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleExpand = () => {
    if (!expanded) {
      loadProviders();
      loadModels();
    }
    setExpanded(!expanded);
  };

  const handleProviderChange = async (newProvider: string) => {
    onProviderChange(newProvider);
    await loadModels(newProvider);
    if (models.length > 0) {
      onModelChange(models[0]);
    }
  };

  return (
    <div className="border-t pt-4">
      <Button
        variant="ghost"
        onClick={handleExpand}
        className="w-full justify-between"
      >
        <span className="text-sm font-medium">Model Settings</span>
        {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </Button>
      
      {expanded && (
        <div className="mt-4 space-y-4">
          <div>
            <Label htmlFor="provider">Provider</Label>
            <Select
              id="provider"
              value={provider}
              onChange={(e) => handleProviderChange(e.target.value)}
              disabled={loading}
              className="w-full"
            >
              {providers.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </Select>
          </div>
          
          <div>
            <Label htmlFor="model">Model</Label>
            <Select
              id="model"
              value={model}
              onChange={(e) => onModelChange(e.target.value)}
              disabled={loading}
              className="w-full"
            >
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </Select>
          </div>
        </div>
      )}
    </div>
  );
}
