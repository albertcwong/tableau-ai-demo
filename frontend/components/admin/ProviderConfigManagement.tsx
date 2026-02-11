'use client';

import { useState, useEffect } from 'react';
import { adminApi, ProviderConfigResponse, ProviderConfigCreate, ProviderConfigUpdate } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert } from '@/components/ui/alert';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Pencil, Trash2, Plus, X } from 'lucide-react';
import { extractErrorMessage } from '@/lib/utils';

const PROVIDER_TYPES = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'salesforce', label: 'Salesforce' },
  { value: 'vertex', label: 'Vertex AI' },
  { value: 'apple_endor', label: 'Apple Endor' },
];

export function ProviderConfigManagement() {
  const [configs, setConfigs] = useState<ProviderConfigResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingConfigId, setEditingConfigId] = useState<number | null>(null);
  const [formData, setFormData] = useState<ProviderConfigCreate>({
    name: '',
    provider_type: 'openai',
    api_key: '',
    salesforce_client_id: '',
    salesforce_private_key_path: '',
    salesforce_username: '',
    salesforce_models_api_url: '',
    vertex_project_id: '',
    vertex_location: '',
    vertex_service_account_path: '',
    apple_endor_endpoint: '',
    apple_endor_app_id: '',
    apple_endor_app_password: '',
    apple_endor_other_app: undefined,
    apple_endor_context: '',
    apple_endor_one_time_token: false,
  });

  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    try {
      setLoading(true);
      setError(null);
      const configsList = await adminApi.listProviderConfigs();
      setConfigs(configsList);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to load configurations'));
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      provider_type: 'openai',
      api_key: '',
      salesforce_client_id: '',
      salesforce_private_key_path: '',
      salesforce_username: '',
      salesforce_models_api_url: '',
      vertex_project_id: '',
      vertex_location: '',
      vertex_service_account_path: '',
      apple_endor_endpoint: '',
      apple_endor_app_id: '',
      apple_endor_app_password: '',
      apple_endor_other_app: undefined,
      apple_endor_context: '',
      apple_endor_one_time_token: false,
    });
    setEditingConfigId(null);
    setShowCreateForm(false);
  };

  const handleEditConfig = (config: ProviderConfigResponse) => {
    setFormData({
      name: config.name,
      provider_type: config.provider_type,
      api_key: '', // Don't pre-populate secrets for security
      salesforce_client_id: config.salesforce_client_id || '',
      salesforce_private_key_path: config.salesforce_private_key_path || '',
      salesforce_username: config.salesforce_username || '',
      salesforce_models_api_url: config.salesforce_models_api_url || '',
      vertex_project_id: config.vertex_project_id || '',
      vertex_location: config.vertex_location || '',
      vertex_service_account_path: config.vertex_service_account_path || '',
      apple_endor_endpoint: config.apple_endor_endpoint || '',
      apple_endor_app_id: config.apple_endor_app_id || '',
      apple_endor_app_password: '', // Don't pre-populate secrets
      apple_endor_other_app: config.apple_endor_other_app || undefined,
      apple_endor_context: config.apple_endor_context || '',
      apple_endor_one_time_token: config.apple_endor_one_time_token || false,
    });
    setEditingConfigId(config.id);
    setShowCreateForm(true);
  };

  const handleCreateConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setError(null);
      
      // Validate required fields based on provider type
      if (formData.provider_type === 'openai' || formData.provider_type === 'anthropic') {
        if (!formData.api_key) {
          setError('API key is required for this provider type');
          return;
        }
      } else if (formData.provider_type === 'apple_endor') {
        if (!formData.apple_endor_app_id || !formData.apple_endor_app_password) {
          setError('App ID and App Password are required for Endor');
          return;
        }
      } else if (formData.provider_type === 'salesforce') {
        if (!formData.salesforce_client_id || !formData.salesforce_private_key_path || !formData.salesforce_username) {
          setError('Salesforce requires client ID, private key path, and username');
          return;
        }
      } else if (formData.provider_type === 'vertex') {
        if (!formData.vertex_project_id || !formData.vertex_service_account_path) {
          setError('Vertex AI requires project ID and service account path');
          return;
        }
      }

      if (editingConfigId) {
        // Update existing config
        const updateData: ProviderConfigUpdate = {
          name: formData.name,
          provider_type: formData.provider_type,
          ...(formData.api_key ? { api_key: formData.api_key } : {}),
          salesforce_client_id: formData.salesforce_client_id || undefined,
          salesforce_private_key_path: formData.salesforce_private_key_path || undefined,
          salesforce_username: formData.salesforce_username || undefined,
          salesforce_models_api_url: formData.salesforce_models_api_url || undefined,
          vertex_project_id: formData.vertex_project_id || undefined,
          vertex_location: formData.vertex_location || undefined,
          vertex_service_account_path: formData.vertex_service_account_path || undefined,
          apple_endor_endpoint: formData.apple_endor_endpoint || undefined,
          apple_endor_app_id: formData.apple_endor_app_id || undefined,
          ...(formData.apple_endor_app_password ? { apple_endor_app_password: formData.apple_endor_app_password } : {}),
          apple_endor_other_app: formData.apple_endor_other_app || undefined,
          apple_endor_context: formData.apple_endor_context || undefined,
          apple_endor_one_time_token: formData.apple_endor_one_time_token || undefined,
        };
        await adminApi.updateProviderConfig(editingConfigId, updateData);
      } else {
        // Create new config
        await adminApi.createProviderConfig(formData);
      }
      resetForm();
      loadConfigs();
    } catch (err: unknown) {
      setError(extractErrorMessage(err, `Failed to ${editingConfigId ? 'update' : 'create'} configuration`));
    }
  };

  const handleDeleteConfig = async (configId: number) => {
    if (!confirm('Are you sure you want to delete this configuration?')) return;
    try {
      setError(null);
      await adminApi.deleteProviderConfig(configId);
      loadConfigs();
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to delete configuration'));
    }
  };

  const getProviderLabel = (providerType: string) => {
    return PROVIDER_TYPES.find(p => p.value === providerType)?.label || providerType;
  };

  const shouldShowField = (field: string) => {
    const providerType = formData.provider_type;
    if (field === 'api_key') {
      return ['openai', 'anthropic'].includes(providerType);
    }
    if (field.startsWith('salesforce_')) {
      return providerType === 'salesforce';
    }
    if (field.startsWith('vertex_')) {
      return providerType === 'vertex';
    }
    if (field.startsWith('apple_endor_')) {
      return providerType === 'apple_endor';
    }
    return false;
  };

  if (loading) {
    return <div className="text-center py-8">Loading configurations...</div>;
  }

  return (
    <div className="space-y-4">
      {error && (
        <Alert variant="destructive">{error}</Alert>
      )}

      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold">Providers</h2>
        <Button 
          onClick={() => {
            if (showCreateForm) {
              resetForm();
            } else {
              setShowCreateForm(true);
            }
          }}
          title={showCreateForm ? 'Cancel' : 'Add Configuration'}
        >
          {showCreateForm ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
        </Button>
      </div>

      {showCreateForm && (
        <Card>
          <CardHeader>
            <CardTitle>{editingConfigId ? 'Edit Provider Configuration' : 'Create New Provider Configuration'}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateConfig} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Display Name</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Production OpenAI"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="provider_type">Provider Type</Label>
                <Select
                  value={formData.provider_type}
                  onValueChange={(value) => setFormData({ ...formData, provider_type: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select provider type" />
                  </SelectTrigger>
                  <SelectContent>
                    {PROVIDER_TYPES.map((provider) => (
                      <SelectItem key={provider.value} value={provider.value}>
                        {provider.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {shouldShowField('api_key') && (
                <div className="space-y-2">
                  <Label htmlFor="api_key">API Key</Label>
                  <Input
                    id="api_key"
                    type="password"
                    value={formData.api_key}
                    onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                    placeholder={editingConfigId ? "Leave empty to keep existing key" : ""}
                    required={!editingConfigId}
                  />
                  {editingConfigId && (
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Leave empty to keep the existing API key unchanged.
                    </p>
                  )}
                </div>
              )}

              {shouldShowField('salesforce_client_id') && (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="salesforce_client_id">Salesforce Client ID</Label>
                    <Input
                      id="salesforce_client_id"
                      value={formData.salesforce_client_id}
                      onChange={(e) => setFormData({ ...formData, salesforce_client_id: e.target.value })}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="salesforce_private_key_path">Private Key Path</Label>
                    <Input
                      id="salesforce_private_key_path"
                      value={formData.salesforce_private_key_path}
                      onChange={(e) => setFormData({ ...formData, salesforce_private_key_path: e.target.value })}
                      placeholder="./credentials/salesforce-private-key.pem"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="salesforce_username">Username</Label>
                    <Input
                      id="salesforce_username"
                      value={formData.salesforce_username}
                      onChange={(e) => setFormData({ ...formData, salesforce_username: e.target.value })}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="salesforce_models_api_url">Models API URL</Label>
                    <Input
                      id="salesforce_models_api_url"
                      value={formData.salesforce_models_api_url}
                      onChange={(e) => setFormData({ ...formData, salesforce_models_api_url: e.target.value })}
                      placeholder="https://api.salesforce.com/einstein/platform/v1"
                    />
                  </div>
                </>
              )}

              {shouldShowField('vertex_project_id') && (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="vertex_project_id">GCP Project ID</Label>
                    <Input
                      id="vertex_project_id"
                      value={formData.vertex_project_id}
                      onChange={(e) => setFormData({ ...formData, vertex_project_id: e.target.value })}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="vertex_location">Location</Label>
                    <Input
                      id="vertex_location"
                      value={formData.vertex_location}
                      onChange={(e) => setFormData({ ...formData, vertex_location: e.target.value })}
                      placeholder="us-central1"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="vertex_service_account_path">Service Account Path</Label>
                    <Input
                      id="vertex_service_account_path"
                      value={formData.vertex_service_account_path}
                      onChange={(e) => setFormData({ ...formData, vertex_service_account_path: e.target.value })}
                      placeholder="./credentials/vertex-sa.json"
                      required
                    />
                  </div>
                </>
              )}

              {shouldShowField('apple_endor_endpoint') && (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="apple_endor_app_id">App ID</Label>
                    <Input
                      id="apple_endor_app_id"
                      value={formData.apple_endor_app_id}
                      onChange={(e) => setFormData({ ...formData, apple_endor_app_id: e.target.value })}
                      placeholder="Your Apple Endor App ID"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="apple_endor_app_password">App Password</Label>
                    <Input
                      id="apple_endor_app_password"
                      type="password"
                      value={formData.apple_endor_app_password}
                      onChange={(e) => setFormData({ ...formData, apple_endor_app_password: e.target.value })}
                      placeholder={editingConfigId ? "Leave empty to keep existing password" : "Your Apple Endor App Password"}
                      required={!editingConfigId}
                    />
                    {editingConfigId && (
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Leave empty to keep the existing password unchanged.
                      </p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="apple_endor_other_app">Other App</Label>
                    <Input
                      id="apple_endor_other_app"
                      type="number"
                      value={formData.apple_endor_other_app || ''}
                      onChange={(e) => setFormData({ ...formData, apple_endor_other_app: e.target.value ? parseInt(e.target.value) : undefined })}
                      placeholder="199323"
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Default: 199323
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="apple_endor_context">Context</Label>
                    <Input
                      id="apple_endor_context"
                      value={formData.apple_endor_context}
                      onChange={(e) => setFormData({ ...formData, apple_endor_context: e.target.value })}
                      placeholder="endor"
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Default: "endor"
                    </p>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center space-x-2">
                      <input
                        id="apple_endor_one_time_token"
                        type="checkbox"
                        checked={formData.apple_endor_one_time_token || false}
                        onChange={(e) => setFormData({ ...formData, apple_endor_one_time_token: e.target.checked })}
                        className="h-4 w-4"
                      />
                      <Label htmlFor="apple_endor_one_time_token" className="cursor-pointer">
                        One Time Token
                      </Label>
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      If checked, tokens will be single-use only
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="apple_endor_endpoint">Endpoint URL</Label>
                    <Input
                      id="apple_endor_endpoint"
                      value={formData.apple_endor_endpoint}
                      onChange={(e) => setFormData({ ...formData, apple_endor_endpoint: e.target.value })}
                      placeholder="https://api.endor.apple.com"
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Default: https://api.endor.apple.com
                    </p>
                  </div>
                </>
              )}

              <div className="flex gap-2">
                <Button 
                  type="submit"
                  title={editingConfigId ? 'Update Configuration' : 'Create Configuration'}
                >
                  {editingConfigId ? <Pencil className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                </Button>
                <Button 
                  type="button" 
                  variant="outline" 
                  onClick={resetForm}
                  title="Cancel"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="border rounded-lg overflow-x-auto">
        <table className="w-full min-w-full">
          <thead className="bg-gray-100 dark:bg-gray-800">
            <tr>
              <th className="px-4 py-2 text-left">ID</th>
              <th className="px-4 py-2 text-left">Name</th>
              <th className="px-4 py-2 text-left">Provider Type</th>
              <th className="px-4 py-2 text-left">Status</th>
              <th className="px-4 py-2 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {configs.map((config) => (
              <tr key={config.id} className="border-t">
                <td className="px-4 py-2">{config.id}</td>
                <td className="px-4 py-2">{config.name}</td>
                <td className="px-4 py-2">{getProviderLabel(config.provider_type)}</td>
                <td className="px-4 py-2">
                  <span className={config.is_active ? 'text-green-600' : 'text-red-600'}>
                    {config.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-4 py-2">
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleEditConfig(config)}
                      title="Edit Configuration"
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDeleteConfig(config.id)}
                      title="Delete Configuration"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {configs.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            No configurations found. Create one to get started.
          </div>
        )}
      </div>
    </div>
  );
}
