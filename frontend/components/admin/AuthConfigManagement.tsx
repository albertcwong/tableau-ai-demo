'use client';

import { useState, useEffect } from 'react';
import { adminApi, AuthConfigResponse, AuthConfigUpdate } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert } from '@/components/ui/alert';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Save, Loader2 } from 'lucide-react';
import { extractErrorMessage } from '@/lib/utils';

export function AuthConfigManagement() {
  const [config, setConfig] = useState<AuthConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  const [easKeyTouched, setEasKeyTouched] = useState(false);
  const [formData, setFormData] = useState<AuthConfigUpdate>({
    enable_password_auth: true,
    enable_oauth_auth: false,
    auth0_domain: '',
    auth0_client_id: '',
    auth0_client_secret: '',
    auth0_audience: '',
    auth0_issuer: '',
    auth0_tableau_metadata_field: '',
    backend_api_url: '',
    tableau_oauth_frontend_redirect: '',
    eas_jwt_key_pem: '',
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
        enable_password_auth: authConfig.enable_password_auth,
        enable_oauth_auth: authConfig.enable_oauth_auth,
        auth0_domain: authConfig.auth0_domain || '',
        auth0_client_id: authConfig.auth0_client_id || '',
        auth0_client_secret: authConfig.auth0_client_secret || '',
        auth0_audience: authConfig.auth0_audience || '',
        auth0_issuer: authConfig.auth0_issuer || '',
        auth0_tableau_metadata_field: authConfig.auth0_tableau_metadata_field || '',
        backend_api_url: authConfig.backend_api_url || '',
        tableau_oauth_frontend_redirect: authConfig.tableau_oauth_frontend_redirect || '',
        eas_jwt_key_pem: '',
      });
      setEasKeyTouched(false);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to load authentication configuration'));
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

      // Validate that at least one auth method is enabled
      if (!formData.enable_password_auth && !formData.enable_oauth_auth) {
        setError('At least one authentication method must be enabled');
        return;
      }

      // Validate OAuth config if enabling OAuth
      if (formData.enable_oauth_auth) {
        if (!formData.auth0_domain?.trim()) {
          setError('Auth0 Domain is required when OAuth authentication is enabled');
          return;
        }
        if (!formData.auth0_client_id?.trim()) {
          setError('Auth0 Client ID is required when OAuth authentication is enabled');
          return;
        }
        if (!formData.auth0_audience?.trim()) {
          setError('Auth0 Audience is required when OAuth authentication is enabled');
          return;
        }
      }

      const payload: AuthConfigUpdate = { ...formData };
      if (!easKeyTouched) delete payload.eas_jwt_key_pem;
      const updatedConfig = await adminApi.updateAuthConfig(payload);
      setConfig(updatedConfig);
      setSuccess('Authentication configuration updated successfully. Changes take effect immediately.');
      
      // Clear success message after 5 seconds
      setTimeout(() => setSuccess(null), 5000);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to update authentication configuration'));
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
      {error && (
        <Alert variant="destructive">
          {error}
        </Alert>
      )}
      
      {success && (
        <Alert className="bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800 text-green-800 dark:text-green-200">
          {success}
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Authentication Methods</CardTitle>
            <CardDescription>
              Select which authentication methods are available for non-admin users
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="enable_password_auth"
                checked={formData.enable_password_auth || false}
                onChange={(e) =>
                  setFormData({ ...formData, enable_password_auth: e.target.checked })
                }
              />
              <Label htmlFor="enable_password_auth" className="cursor-pointer">
                Enable Password Authentication
              </Label>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400 ml-6">
              Allow users to log in with username and password
            </p>

            <div className="flex items-center space-x-2 mt-4">
              <Checkbox
                id="enable_oauth_auth"
                checked={formData.enable_oauth_auth || false}
                onChange={(e) =>
                  setFormData({ ...formData, enable_oauth_auth: e.target.checked })
                }
              />
              <Label htmlFor="enable_oauth_auth" className="cursor-pointer">
                Enable OAuth Authentication (Auth0)
              </Label>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400 ml-6">
              Allow users to log in with Auth0 OAuth
            </p>
          </CardContent>
        </Card>

        {formData.enable_oauth_auth && (
          <Card>
            <CardHeader>
              <CardTitle>Auth0 Configuration</CardTitle>
              <CardDescription>
                Configure Auth0 OAuth settings. Get these values from your Auth0 dashboard.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="auth0_domain">Auth0 Domain *</Label>
                <Input
                  id="auth0_domain"
                  type="text"
                  placeholder="your-tenant.auth0.com"
                  value={formData.auth0_domain || ''}
                  onChange={(e) =>
                    setFormData({ ...formData, auth0_domain: e.target.value })
                  }
                  required={formData.enable_oauth_auth}
                />
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Your Auth0 tenant domain (e.g., mycompany.auth0.com)
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="auth0_client_id">Auth0 Client ID *</Label>
                <Input
                  id="auth0_client_id"
                  type="text"
                  placeholder="your-spa-client-id"
                  value={formData.auth0_client_id || ''}
                  onChange={(e) =>
                    setFormData({ ...formData, auth0_client_id: e.target.value })
                  }
                  required={formData.enable_oauth_auth}
                />
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Your Auth0 SPA (Single Page Application) Client ID from the Auth0 dashboard
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="auth0_client_secret">Auth0 Client Secret (Optional)</Label>
                <Input
                  id="auth0_client_secret"
                  type="password"
                  placeholder="your-client-secret"
                  value={formData.auth0_client_secret || ''}
                  onChange={(e) =>
                    setFormData({ ...formData, auth0_client_secret: e.target.value })
                  }
                />
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Optional: Client secret for server-side token exchange (not needed for SPAs, but may be required for some flows)
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="auth0_audience">Auth0 Audience *</Label>
                <Input
                  id="auth0_audience"
                  type="text"
                  placeholder="https://tableau-ai-demo-api"
                  value={formData.auth0_audience || ''}
                  onChange={(e) =>
                    setFormData({ ...formData, auth0_audience: e.target.value })
                  }
                  required={formData.enable_oauth_auth}
                />
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  The API identifier from your Auth0 API configuration
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="auth0_issuer">Auth0 Issuer (Optional)</Label>
                <Input
                  id="auth0_issuer"
                  type="text"
                  placeholder="https://your-tenant.auth0.com/"
                  value={formData.auth0_issuer || ''}
                  onChange={(e) =>
                    setFormData({ ...formData, auth0_issuer: e.target.value })
                  }
                />
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Auth0 issuer URL (defaults to https://your-domain.auth0.com/ if not provided)
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="auth0_tableau_metadata_field">Auth0 Tableau Metadata Field (Optional)</Label>
                <Input
                  id="auth0_tableau_metadata_field"
                  type="text"
                  placeholder="app_metadata.tableau_username"
                  value={formData.auth0_tableau_metadata_field || ''}
                  onChange={(e) =>
                    setFormData({ ...formData, auth0_tableau_metadata_field: e.target.value })
                  }
                />
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Field path in Auth0 token to extract Tableau username. Examples:
                  <br />
                  • <code className="text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">app_metadata.tableau_username</code> - for app_metadata
                  <br />
                  • <code className="text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">user_metadata.tableau_username</code> - for user_metadata
                  <br />
                  • <code className="text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">tableau_username</code> - for top-level claim
                  <br />
                  • <code className="text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">https://tableau-ai-demo-api/tableau_username</code> - for namespaced claim
                  <br />
                  Leave empty to disable automatic Tableau username mapping.
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle>Connected App OAuth Trust / EAS URLs</CardTitle>
            <CardDescription>
              Backend and frontend URLs for OAuth callback. EAS JWT key for backend-constructed JWTs.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="backend_api_url">Backend API URL</Label>
              <Input
                id="backend_api_url"
                type="url"
                placeholder="https://your-backend.example.com or https://xxx.ngrok-free.app"
                value={formData.backend_api_url || ''}
                onChange={(e) => setFormData({ ...formData, backend_api_url: e.target.value })}
              />
              <p className="text-sm text-gray-500 dark:text-gray-400">
                OAuth callback base. Tableau registers this as EAS issuer.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="tableau_oauth_frontend_redirect">Frontend Redirect URL</Label>
              <Input
                id="tableau_oauth_frontend_redirect"
                type="url"
                placeholder="https://localhost:3000"
                value={formData.tableau_oauth_frontend_redirect || ''}
                onChange={(e) => setFormData({ ...formData, tableau_oauth_frontend_redirect: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>EAS JWT Key (RSA private key PEM)</Label>
              {config?.eas_jwt_key_configured && (
                <p className="text-sm text-green-600 dark:text-green-400">Key configured. Upload or paste to replace.</p>
              )}
              <Input
                type="file"
                accept=".pem"
                className="max-w-xs"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) {
                    setEasKeyTouched(true);
                    const r = new FileReader();
                    r.onload = () => setFormData((prev) => ({ ...prev, eas_jwt_key_pem: (r.result as string) || '' }));
                    r.readAsText(f);
                  }
                  e.target.value = '';
                }}
              />
              <textarea
                className="w-full min-h-[80px] font-mono text-sm p-2 border rounded"
                placeholder="Or paste PEM content. Leave empty to keep existing."
                value={formData.eas_jwt_key_pem || ''}
                onChange={(e) => {
                  setEasKeyTouched(true);
                  setFormData({ ...formData, eas_jwt_key_pem: e.target.value });
                }}
              />
              {config?.eas_jwt_key_configured && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setEasKeyTouched(true);
                    setFormData((prev) => ({ ...prev, eas_jwt_key_pem: '' }));
                  }}
                >
                  Clear key
                </Button>
              )}
              <p className="text-sm text-gray-500 dark:text-gray-400">
                RSA 2048-bit key. Generate: openssl genrsa -out eas_jwt_key.pem 2048
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
                Save Configuration
              </>
            )}
          </Button>
        </div>
      </form>

      {config && (
        <Card>
          <CardHeader>
            <CardTitle>Current Configuration</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <div>
                <span className="font-medium">Password Auth:</span>{' '}
                <span className={config.enable_password_auth ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}>
                  {config.enable_password_auth ? 'Enabled' : 'Disabled'}
                </span>
              </div>
              <div>
                <span className="font-medium">OAuth Auth:</span>{' '}
                <span className={config.enable_oauth_auth ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}>
                  {config.enable_oauth_auth ? 'Enabled' : 'Disabled'}
                </span>
              </div>
              {config.enable_oauth_auth && (
                <>
                  <div>
                    <span className="font-medium">Auth0 Domain:</span>{' '}
                    <span className="text-gray-600 dark:text-gray-400">{config.auth0_domain || 'Not set'}</span>
                  </div>
                  <div>
                    <span className="font-medium">Auth0 Audience:</span>{' '}
                    <span className="text-gray-600 dark:text-gray-400">{config.auth0_audience || 'Not set'}</span>
                  </div>
                </>
              )}
              <div>
                <span className="font-medium">Backend API URL:</span>{' '}
                <span className="text-gray-600 dark:text-gray-400">{config.backend_api_url || 'Not set (using .env)'}</span>
              </div>
              <div>
                <span className="font-medium">Frontend Redirect URL:</span>{' '}
                <span className="text-gray-600 dark:text-gray-400">{config.tableau_oauth_frontend_redirect || 'Not set (using .env)'}</span>
              </div>
              <div>
                <span className="font-medium">EAS JWT Key:</span>{' '}
                <span className={config.eas_jwt_key_configured ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}>
                  {config.eas_jwt_key_configured ? 'Configured' : 'Not configured'}
                </span>
              </div>
              <div className="pt-2 text-xs text-gray-500 dark:text-gray-400">
                Last updated: {new Date(config.updated_at).toLocaleString()}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
