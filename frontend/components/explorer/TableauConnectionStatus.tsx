'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { authApi, userSettingsApi, type TableauConfigOption, type TableauAuthResponse } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, CheckCircle2, XCircle, Server, X } from 'lucide-react';
import { HiOutlineLink } from 'react-icons/hi';
import { FaUnlink } from 'react-icons/fa';
import { useAuth } from '@/components/auth/AuthContext';
import { extractErrorMessage } from '@/lib/utils';

interface TableauConnectionStatusProps {
  onConnectionChange?: (connected: boolean, config?: TableauConfigOption) => void;
  onSiteChange?: () => void;
}

export function TableauConnectionStatus({ onConnectionChange, onSiteChange }: TableauConnectionStatusProps) {
  const { isAdmin, isAuthenticated } = useAuth();
  const [configs, setConfigs] = useState<TableauConfigOption[]>([]);
  const [selectedConfigId, setSelectedConfigId] = useState<number | null>(null);
  const [authType, setAuthType] = useState<'connected_app' | 'pat' | 'standard'>('connected_app');
  const [userPatConfigIds, setUserPatConfigIds] = useState<number[]>([]);
  const [userPasswordConfigIds, setUserPasswordConfigIds] = useState<number[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<{
    connected: boolean;
    config?: TableauConfigOption;
    authResponse?: TableauAuthResponse;
  }>({ connected: false });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sites, setSites] = useState<{ id?: string; name?: string; contentUrl?: string }[]>([]);
  const [switchingSite, setSwitchingSite] = useState(false);

  // Load configs on mount
  useEffect(() => {
    // Skip if user is not authenticated
    if (!isAuthenticated) {
      return;
    }
    loadConfigs();
    // Don't automatically restore connection state - let user explicitly connect
    // This prevents automatic API calls on page load
    // The stored config ID can be restored for UI purposes (in loadConfigs),
    // but connection state should only be set when user explicitly clicks "Connect"
  }, [isAuthenticated]);

  const loadConfigs = async () => {
    if (!isAuthenticated) return;
    try {
      const [configsList, pats, passwords] = await Promise.all([
        authApi.listTableauConfigs(),
        userSettingsApi.listTableauPATs().catch(() => []),
        userSettingsApi.listTableauPasswords().catch(() => []),
      ]);
      setConfigs(configsList);
      setUserPatConfigIds(pats.map((p) => p.tableau_server_config_id));
      setUserPasswordConfigIds(passwords.map((p) => p.tableau_server_config_id));
      const storedConfigId = localStorage.getItem('tableau_config_id');
      const storedAuthType = localStorage.getItem('tableau_auth_type');
      if (storedConfigId && configsList.find((c) => c.id === Number(storedConfigId))) {
        setSelectedConfigId(Number(storedConfigId));
      }
      if (storedAuthType === 'pat' || storedAuthType === 'connected_app' || storedAuthType === 'standard') {
        setAuthType(storedAuthType);
      }
    } catch (err) {
      console.error('Failed to load Tableau configs:', err);
      setError('Failed to load Tableau server configurations');
    }
  };

  const handleConnect = async () => {
    if (!selectedConfigId) {
      setError('Please select a Tableau server configuration');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const config = configs.find((c) => c.id === selectedConfigId);
      const hasCA = config?.has_connected_app ?? false;
      const effectiveAuthType = hasCA
        ? authType
        : config?.allow_pat_auth
          ? 'pat'
          : config?.allow_standard_auth
            ? 'standard'
            : 'pat';
      const authResponse = await authApi.authenticateTableau({
        config_id: selectedConfigId,
        auth_type: effectiveAuthType,
      });
      setConnectionStatus({
        connected: true,
        config,
        authResponse,
      });

      const canSwitchSite = effectiveAuthType === 'standard' || effectiveAuthType === 'pat';
      if (canSwitchSite && selectedConfigId) {
        try {
          const sitesList = await authApi.listSites(selectedConfigId, effectiveAuthType);
          setSites(sitesList);
        } catch {
          setSites([]);
        }
      } else {
        setSites([]);
      }

      // Store connection state
      localStorage.setItem('tableau_config_id', String(selectedConfigId));
      localStorage.setItem('tableau_auth_type', effectiveAuthType);
      localStorage.setItem('tableau_connected', 'true');
      if (authResponse.expires_at) {
        localStorage.setItem('tableau_token_expires_at', authResponse.expires_at);
      }

      onConnectionChange?.(true, config);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, "Failed to connect to Tableau server"));
      setConnectionStatus({ connected: false });
      onConnectionChange?.(false);
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = () => {
    setConnectionStatus({ connected: false });
    setSelectedConfigId(null);
    setSites([]);
    localStorage.removeItem('tableau_config_id');
    localStorage.removeItem('tableau_auth_type');
    localStorage.removeItem('tableau_connected');
    localStorage.removeItem('tableau_token_expires_at');
    localStorage.removeItem('tableau_site_content_url');
    onConnectionChange?.(false);
  };

  const canSwitchSite =
    connectionStatus.connected &&
    (authType === 'standard' || authType === 'pat') &&
    selectedConfigId &&
    sites.length > 0;

  const handleSwitchSite = async (siteContentUrl: string) => {
    if (!selectedConfigId || switchingSite) return;
    const currentUrl = sites.find((s) => s.id === connectionStatus.authResponse?.site_id)?.contentUrl ?? '';
    if (siteContentUrl === currentUrl) return;
    setSwitchingSite(true);
    setError(null);
    try {
      const authResponse = await authApi.switchSite({
        config_id: selectedConfigId,
        auth_type: authType as 'standard' | 'pat',
        site_content_url: siteContentUrl,
      });
      setConnectionStatus((prev) => ({ ...prev, authResponse }));
      if (authResponse.expires_at) {
        localStorage.setItem('tableau_token_expires_at', authResponse.expires_at);
      }
      localStorage.setItem('tableau_site_content_url', siteContentUrl);
      onConnectionChange?.(true, connectionStatus.config);
      onSiteChange?.();
    } catch (err: unknown) {
      setError(extractErrorMessage(err, "Failed to switch site"));
    } finally {
      setSwitchingSite(false);
    }
  };

  const selectedConfig = selectedConfigId ? configs.find((c) => c.id === selectedConfigId) : null;
  const hasConnectedApp = selectedConfig?.has_connected_app ?? false;
  const showAuthTypeSelect =
    selectedConfig?.allow_pat_auth || selectedConfig?.allow_standard_auth || !hasConnectedApp;
  const canUsePat = !!selectedConfig?.allow_pat_auth && userPatConfigIds.includes(selectedConfigId!);
  const canUseStandard =
    !!selectedConfig?.allow_standard_auth && userPasswordConfigIds.includes(selectedConfigId!);

  if (configs.length === 0 && !isAdmin) {
    return (
      <Alert>
        <Server className="h-4 w-4" />
        <AlertDescription>
          No Tableau server configurations available. Please contact your administrator.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-3">
      {configs.length > 0 && (
        <>
          <div className="flex items-center gap-2">
          <Select
            value={selectedConfigId?.toString() || ''}
            onValueChange={(value) => {
              setSelectedConfigId(Number(value));
              setError(null);
              const newConfig = configs.find((c) => c.id === Number(value));
              const hasCA = newConfig?.has_connected_app ?? false;
              if (!newConfig?.allow_pat_auth && !newConfig?.allow_standard_auth) setAuthType('connected_app');
              else if (!hasCA) setAuthType(newConfig?.allow_pat_auth ? 'pat' : 'standard');
              if (connectionStatus.connected) {
                handleDisconnect();
              }
            }}
            disabled={connectionStatus.connected || loading}
          >
            <SelectTrigger 
              className="flex-1"
              title={
                selectedConfigId 
                  ? (() => {
                      const config = configs.find(c => c.id === selectedConfigId);
                      if (!config) return undefined;
                      const urlParts = [config.server_url];
                      if (config.site_id) urlParts.push(`Site: ${config.site_id}`);
                      return urlParts.join(' / ');
                    })()
                  : undefined
              }
            >
              <SelectValue placeholder="Select Tableau server..." />
            </SelectTrigger>
            <SelectContent>
              {configs.map((config) => {
                const siteDisplay = config.site_id && config.site_id.trim() ? config.site_id : 'Default';
                return (
                  <SelectItem key={config.id} value={config.id.toString()}>
                    <span className="font-medium">{config.name}</span> ({siteDisplay})
                  </SelectItem>
                );
              })}
            </SelectContent>
          </Select>

          {connectionStatus.connected ? (
            <Button
              onClick={handleDisconnect}
              variant="destructive"
              size="sm"
              disabled={loading}
              title="Disconnect"
            >
              <FaUnlink className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              onClick={handleConnect}
              disabled={!selectedConfigId || loading}
              size="sm"
              title="Connect"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <HiOutlineLink className="h-4 w-4" />
              )}
            </Button>
          )}
        </div>
        {showAuthTypeSelect && (
          <div className="flex items-center gap-2">
            <Select
              value={
                authType === 'connected_app' && !hasConnectedApp
                  ? selectedConfig?.allow_pat_auth
                    ? 'pat'
                    : 'standard'
                  : authType
              }
              onValueChange={(v) => {
                setAuthType(v as 'connected_app' | 'pat' | 'standard');
                setError(null);
              }}
              disabled={connectionStatus.connected || loading}
            >
              <SelectTrigger className="w-[200px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {hasConnectedApp && <SelectItem value="connected_app">Connected App</SelectItem>}
                <SelectItem value="pat" disabled={!canUsePat}>
                  Personal Access Token {!canUsePat && '(configure in Settings)'}
                </SelectItem>
                {selectedConfig?.allow_standard_auth && (
                  <SelectItem value="standard" disabled={!canUseStandard}>
                    Username/Password {!canUseStandard && '(configure in Settings)'}
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
            {(authType === 'pat' || !hasConnectedApp) && !canUsePat && selectedConfig?.allow_pat_auth && (
              <Link href="/settings">
                <Button variant="outline" size="sm">Add PAT in Settings</Button>
              </Link>
            )}
            {authType === 'standard' && !canUseStandard && (
              <Link href="/settings">
                <Button variant="outline" size="sm">Add credentials in Settings</Button>
              </Link>
            )}
          </div>
        )}
        </>
      )}

      {connectionStatus.connected && connectionStatus.config && (
        <div className="space-y-2">
          <Alert className="bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800">
            <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
            <AlertDescription className="text-green-800 dark:text-green-200">
              Connected to <strong>{connectionStatus.config.name}</strong>
              {connectionStatus.authResponse?.site_id && (
                <span> (Site: {connectionStatus.authResponse.site_id})</span>
              )}
            </AlertDescription>
          </Alert>
          {canSwitchSite && (
            <div className="flex items-center gap-2">
              <label className="text-sm text-muted-foreground shrink-0">Site:</label>
              <Select
                value={
                  (() => {
                    const contentUrl =
                      sites.find((s) => s.id === connectionStatus.authResponse?.site_id)?.contentUrl ?? '';
                    return contentUrl || '__default__';
                  })()
                }
                onValueChange={(v) => handleSwitchSite(v === '__default__' ? '' : v)}
                disabled={switchingSite}
              >
                <SelectTrigger className="w-[220px]">
                  <SelectValue placeholder="Switch site..." />
                </SelectTrigger>
                <SelectContent>
                  {sites.map((s) => {
                    const contentUrl = s.contentUrl ?? '';
                    const value = contentUrl || '__default__';
                    return (
                      <SelectItem key={s.id ?? value} value={value}>
                        {s.name ?? s.contentUrl ?? 'Default'}
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
              {switchingSite && (
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              )}
            </div>
          )}
        </div>
      )}

      {error && (
        <Alert variant="destructive" className="relative">
          <XCircle className="h-4 w-4" />
          <AlertDescription className="pr-8">{error}</AlertDescription>
          <Button
            variant="ghost"
            size="sm"
            className="absolute top-2 right-2 h-6 w-6 p-0 hover:bg-destructive/20"
            onClick={() => {
              setError(null);
              // Reset connection state to allow trying a different server
              setConnectionStatus({ connected: false });
            }}
            title="Dismiss error and try another server"
          >
            <X className="h-4 w-4" />
          </Button>
        </Alert>
      )}

      {configs.length === 0 && isAdmin && (
        <Alert>
          <AlertDescription>
            No Tableau server configurations found. Configure servers in the{' '}
            <strong>Admin Console</strong>.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
