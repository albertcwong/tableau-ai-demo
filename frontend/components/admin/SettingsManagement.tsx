'use client';

import { useState, useEffect } from 'react';
import { adminApi, AuthConfigResponse } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert } from '@/components/ui/alert';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Save, Loader2 } from 'lucide-react';
import { extractErrorMessage } from '@/lib/utils';

export function SettingsManagement() {
  const [config, setConfig] = useState<AuthConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    cors_origins: '',
    mcp_server_name: '',
    mcp_transport: '',
    mcp_log_level: '',
    redis_token_ttl: undefined as number | undefined,
  });
  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      setError(null);
      const authConfig = await adminApi.getAuthConfig();
      setConfig(authConfig);
      setFormData({
        cors_origins: authConfig.cors_origins || '',
        mcp_server_name: authConfig.mcp_server_name || '',
        mcp_transport: authConfig.mcp_transport || '',
        mcp_log_level: authConfig.mcp_log_level || '',
        redis_token_ttl: authConfig.redis_token_ttl ?? undefined,
      });
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to load settings'));
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      setError(null);
      setSuccess(null);
      await adminApi.updateAuthConfig({
        cors_origins: formData.cors_origins || undefined,
        mcp_server_name: formData.mcp_server_name || undefined,
        mcp_transport: formData.mcp_transport || undefined,
        mcp_log_level: formData.mcp_log_level || undefined,
        redis_token_ttl: formData.redis_token_ttl,
      });
      await loadConfig();
      setSuccess('Settings saved. CORS and Redis TTL require backend restart to take effect.');
      setTimeout(() => setSuccess(null), 5000);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to save settings'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && <Alert variant="destructive">{error}</Alert>}
      {success && (
        <Alert className="bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800 text-green-800 dark:text-green-200">
          {success}
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Application Settings</CardTitle>
            <CardDescription>
              CORS, MCP server, and Redis token cache. Override defaults from .env.
              CORS and Redis Token TTL require backend restart to take effect.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="cors_origins">CORS Origins</Label>
              <Input
                id="cors_origins"
                type="text"
                placeholder="http://localhost:3000,https://localhost:3000"
                value={formData.cors_origins}
                onChange={(e) => setFormData({ ...formData, cors_origins: e.target.value })}
              />
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Comma-separated allowed origins. Restart required.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="mcp_server_name">MCP Server Name</Label>
              <Input
                id="mcp_server_name"
                type="text"
                placeholder="tableau-ai-demo-mcp"
                value={formData.mcp_server_name}
                onChange={(e) => setFormData({ ...formData, mcp_server_name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mcp_transport">MCP Transport</Label>
              <Input
                id="mcp_transport"
                type="text"
                placeholder="stdio"
                value={formData.mcp_transport}
                onChange={(e) => setFormData({ ...formData, mcp_transport: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mcp_log_level">MCP Log Level</Label>
              <Input
                id="mcp_log_level"
                type="text"
                placeholder="info"
                value={formData.mcp_log_level}
                onChange={(e) => setFormData({ ...formData, mcp_log_level: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="redis_token_ttl">Redis Token TTL (seconds)</Label>
              <Input
                id="redis_token_ttl"
                type="number"
                placeholder="3600"
                value={formData.redis_token_ttl ?? ''}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    redis_token_ttl: e.target.value ? parseInt(e.target.value, 10) : undefined,
                  })
                }
              />
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Token cache TTL. Restart required.
              </p>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button type="submit" disabled={saving}>
            {saving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                Save Settings
              </>
            )}
          </Button>
        </div>
      </form>

      {config && (
        <Card>
          <CardHeader>
            <CardTitle>Current Values</CardTitle>
            <CardDescription>Effective values (DB overrides .env when set)</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <div>
                <span className="font-medium">CORS Origins:</span>{' '}
                <span className="text-gray-600 dark:text-gray-400">
                  {config.resolved_cors_origins ?? config.cors_origins ?? '(default)'}
                </span>
              </div>
              <div>
                <span className="font-medium">MCP Server Name:</span>{' '}
                <span className="text-gray-600 dark:text-gray-400">
                  {config.resolved_mcp_server_name ?? config.mcp_server_name ?? '(default)'}
                </span>
              </div>
              <div>
                <span className="font-medium">MCP Transport:</span>{' '}
                <span className="text-gray-600 dark:text-gray-400">
                  {config.resolved_mcp_transport ?? config.mcp_transport ?? '(default)'}
                </span>
              </div>
              <div>
                <span className="font-medium">MCP Log Level:</span>{' '}
                <span className="text-gray-600 dark:text-gray-400">
                  {config.resolved_mcp_log_level ?? config.mcp_log_level ?? '(default)'}
                </span>
              </div>
              <div>
                <span className="font-medium">Redis Token TTL:</span>{' '}
                <span className="text-gray-600 dark:text-gray-400">
                  {config.resolved_redis_token_ttl ?? config.redis_token_ttl ?? '(default)'}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
