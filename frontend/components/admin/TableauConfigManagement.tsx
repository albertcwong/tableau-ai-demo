'use client';

import { useState, useEffect } from 'react';
import { adminApi, TableauConfigResponse, TableauConfigCreate, TableauConfigUpdate } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert } from '@/components/ui/alert';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Pencil, Trash2, Plus, X } from 'lucide-react';
import { extractErrorMessage } from '@/lib/utils';

export function TableauConfigManagement() {
  const [configs, setConfigs] = useState<TableauConfigResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingConfigId, setEditingConfigId] = useState<number | null>(null);
  const [formData, setFormData] = useState<TableauConfigCreate>({
    name: '',
    server_url: '',
    site_id: '',
    api_version: '3.15',
    client_id: '',
    client_secret: '',
    secret_id: '',
    allow_pat_auth: false,
    allow_standard_auth: false,
    skip_ssl_verify: false,
  });

  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    try {
      setLoading(true);
      setError(null);
      const configsList = await adminApi.listTableauConfigs();
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
      server_url: '',
      site_id: '',
      api_version: '3.15',
      client_id: '',
      client_secret: '',
      secret_id: '',
      allow_pat_auth: false,
      allow_standard_auth: false,
      skip_ssl_verify: false,
    });
    setEditingConfigId(null);
    setShowCreateForm(false);
  };

  const handleEditConfig = (config: TableauConfigResponse) => {
    setFormData({
      name: config.name,
      server_url: config.server_url,
      site_id: config.site_id || '',
      api_version: config.api_version || '3.15',
      client_id: config.client_id ?? '',
      client_secret: '', // Don't pre-populate secret for security
      secret_id: config.secret_id || '',
      allow_pat_auth: config.allow_pat_auth || false,
      allow_standard_auth: config.allow_standard_auth || false,
      skip_ssl_verify: config.skip_ssl_verify || false,
    });
    setEditingConfigId(config.id);
    setShowCreateForm(true);
  };

  const handleCreateConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setError(null);
      
      // Warn about mixed content if frontend is HTTPS and server URL is HTTP
      if (typeof window !== 'undefined' && window.location.protocol === 'https:') {
        try {
          const serverUrl = new URL(formData.server_url);
          if (serverUrl.protocol === 'http:') {
            const warning = 'Warning: This application is served over HTTPS, but the Tableau server URL uses HTTP. This will cause Mixed Content errors and prevent views from loading. Consider configuring your Tableau server to use HTTPS, or update the server URL to use HTTPS.';
            if (!confirm(warning + '\n\nDo you want to continue anyway?')) {
              return;
            }
          }
        } catch (urlError) {
          // Invalid URL format, let backend validation handle it
        }
      }
      
      if (editingConfigId) {
        // Update existing config
        const updateData: TableauConfigUpdate = {
          name: formData.name,
          server_url: formData.server_url,
          site_id: formData.site_id || undefined,
          api_version: formData.api_version || undefined,
          client_id: formData.client_id,
          ...(formData.client_secret ? { client_secret: formData.client_secret } : {}),
          secret_id: formData.secret_id || undefined,
          allow_pat_auth: formData.allow_pat_auth,
          allow_standard_auth: formData.allow_standard_auth,
          skip_ssl_verify: formData.skip_ssl_verify,
        };
        await adminApi.updateTableauConfig(editingConfigId, updateData);
      } else {
        // Create new config
        await adminApi.createTableauConfig({
          ...formData,
          allow_pat_auth: formData.allow_pat_auth || false,
          allow_standard_auth: formData.allow_standard_auth || false,
          skip_ssl_verify: formData.skip_ssl_verify || false,
        });
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
      await adminApi.deleteTableauConfig(configId);
      loadConfigs();
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to delete configuration'));
    }
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
        <h2 className="text-xl font-semibold">Tableau Connected Apps</h2>
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
            <CardTitle>{editingConfigId ? 'Edit Tableau Configuration' : 'Create New Tableau Configuration'}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateConfig} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Display Name</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Production Server"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="server_url">Server URL</Label>
                <Input
                  id="server_url"
                  value={formData.server_url}
                  onChange={(e) => setFormData({ ...formData, server_url: e.target.value })}
                  placeholder="https://tableau.example.com"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="site_id">Site ID (optional)</Label>
                <Input
                  id="site_id"
                  value={formData.site_id}
                  onChange={(e) => setFormData({ ...formData, site_id: e.target.value })}
                  placeholder="Leave empty for default site"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="api_version">API Version</Label>
                <Input
                  id="api_version"
                  value={formData.api_version}
                  onChange={(e) => setFormData({ ...formData, api_version: e.target.value })}
                  placeholder="3.15"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Tableau REST API version (e.g., 3.15, 3.22). Defaults to 3.15.
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="client_id">Connected App Client ID (optional)</Label>
                <Input
                  id="client_id"
                  value={formData.client_id ?? ''}
                  onChange={(e) => setFormData({ ...formData, client_id: e.target.value })}
                  placeholder="Required for Connected App auth, or enable PAT auth below"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="client_secret">Connected App Secret (optional)</Label>
                <Input
                  id="client_secret"
                  type="password"
                  value={formData.client_secret ?? ''}
                  onChange={(e) => setFormData({ ...formData, client_secret: e.target.value })}
                  placeholder={editingConfigId ? "Leave empty to keep existing secret" : "Required for Connected App auth, or enable PAT auth below"}
                />
                {editingConfigId && (
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Leave empty to keep the existing secret unchanged.
                  </p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="secret_id">Secret ID (optional)</Label>
                <Input
                  id="secret_id"
                  value={formData.secret_id}
                  onChange={(e) => setFormData({ ...formData, secret_id: e.target.value })}
                  placeholder="Defaults to Client ID if not provided"
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <input
                    id="allow_pat_auth"
                    type="checkbox"
                    checked={formData.allow_pat_auth || false}
                    onChange={(e) => setFormData({ ...formData, allow_pat_auth: e.target.checked })}
                    className="h-4 w-4"
                  />
                  <Label htmlFor="allow_pat_auth" className="cursor-pointer">
                    Allow Personal Access Token Authentication
                  </Label>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  If enabled, users can authenticate with their own PAT instead of using the Connected App
                </p>
              </div>
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <input
                    id="allow_standard_auth"
                    type="checkbox"
                    checked={formData.allow_standard_auth || false}
                    onChange={(e) => setFormData({ ...formData, allow_standard_auth: e.target.checked })}
                    className="h-4 w-4"
                  />
                  <Label htmlFor="allow_standard_auth" className="cursor-pointer">
                    Allow Username/Password Authentication
                  </Label>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  If enabled, users can authenticate with Tableau username and password
                </p>
              </div>
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <input
                    id="skip_ssl_verify"
                    type="checkbox"
                    checked={formData.skip_ssl_verify || false}
                    onChange={(e) => setFormData({ ...formData, skip_ssl_verify: e.target.checked })}
                    className="h-4 w-4"
                  />
                  <Label htmlFor="skip_ssl_verify" className="cursor-pointer">
                    Skip SSL certificate verification
                  </Label>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Use for self-signed certs or internal servers. Not recommended for production.
                </p>
              </div>
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
              <th className="px-4 py-2 text-left">Server URL</th>
              <th className="px-4 py-2 text-left">Site ID</th>
              <th className="px-4 py-2 text-left">API Version</th>
              <th className="px-4 py-2 text-left">Status</th>
              <th className="px-4 py-2 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {configs.map((config) => (
              <tr key={config.id} className="border-t">
                <td className="px-4 py-2">{config.id}</td>
                <td className="px-4 py-2">{config.name}</td>
                <td className="px-4 py-2 break-words max-w-xs">
                  <div className="flex items-center gap-2">
                    <span>{config.server_url}</span>
                    {typeof window !== 'undefined' && window.location.protocol === 'https:' && config.server_url.startsWith('http://') && (
                      <span className="text-xs text-red-600 dark:text-red-400" title="Mixed Content Warning: HTTP server URL with HTTPS frontend">
                        ⚠️
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-2">{config.site_id || '(default)'}</td>
                <td className="px-4 py-2">{config.api_version || '3.15'}</td>
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
