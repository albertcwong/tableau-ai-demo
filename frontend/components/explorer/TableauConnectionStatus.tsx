'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { authApi, userSettingsApi, type TableauConfigOption, type TableauAuthResponse, type SiteInfo } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, CheckCircle2, XCircle, Server, X, Search } from 'lucide-react';
import { HiOutlineLink } from 'react-icons/hi';
import { FaUnlink } from 'react-icons/fa';
import { useAuth } from '@/components/auth/AuthContext';
import { extractErrorMessage } from '@/lib/utils';

interface TableauConnectionStatusProps {
  onConnectionChange?: (connected: boolean, config?: TableauConfigOption) => void;
  onSiteChange?: () => void;
}

type AuthType = 'connected_app' | 'pat' | 'standard' | 'connected_app_oauth';

function resolveAuthType(
  config: TableauConfigOption | null,
  pref: AuthType | null,
  perServerPref: AuthType | null,
  patIds: number[],
  pwdIds: number[],
  configId: number | null
): AuthType {
  if (!config) return 'connected_app';
  const hasCA = config.has_connected_app ?? false;
  const hasOAuth = config.has_connected_app_oauth ?? false;
  const supported: AuthType[] = [];
  if (hasCA) supported.push('connected_app');
  if (hasOAuth) supported.push('connected_app_oauth');
  if (config.allow_pat_auth) supported.push('pat');
  if (config.allow_standard_auth) supported.push('standard');
  // Prefer per-server preference, then global preference, then first available
  if (perServerPref && supported.includes(perServerPref)) return perServerPref;
  if (pref && supported.includes(pref)) return pref;
  if (supported.includes('connected_app_oauth')) return 'connected_app_oauth';
  if (supported.includes('connected_app')) return 'connected_app';
  if (supported.includes('pat')) return 'pat';
  if (supported.includes('standard')) return 'standard';
  return 'connected_app';
}

export function TableauConnectionStatus({ onConnectionChange, onSiteChange }: TableauConnectionStatusProps) {
  const { isAdmin, isAuthenticated } = useAuth();
  const [configs, setConfigs] = useState<TableauConfigOption[]>([]);
  const [selectedConfigId, setSelectedConfigId] = useState<number | null>(null);
  const [preferredAuthType, setPreferredAuthType] = useState<'connected_app' | 'pat' | 'standard' | 'connected_app_oauth' | null>(null);
  const [perServerPreferences, setPerServerPreferences] = useState<Record<number, AuthType>>({});
  const [authType, setAuthType] = useState<AuthType>('connected_app');
  const [userPatConfigIds, setUserPatConfigIds] = useState<number[]>([]);
  const [userPasswordConfigIds, setUserPasswordConfigIds] = useState<number[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<{
    connected: boolean;
    config?: TableauConfigOption;
    authResponse?: TableauAuthResponse;
    authType?: AuthType;
  }>({ connected: false });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sites, setSites] = useState<SiteInfo[]>([]);
  const [sitesPagination, setSitesPagination] = useState<{ pageNumber: number; totalAvailable: number } | null>(null);
  const [siteSearchTerm, setSiteSearchTerm] = useState('');
  const [debouncedSiteSearch, setDebouncedSiteSearch] = useState('');
  const [loadingSites, setLoadingSites] = useState(false);
  const [switchingSite, setSwitchingSite] = useState(false);

  const connectedAuthType = connectionStatus.authType ?? authType;
  const canSwitchSite =
    connectionStatus.connected &&
    (connectedAuthType === 'standard' || connectedAuthType === 'pat') &&
    selectedConfigId;

  const loadSites = useCallback(
    async (pageNumber = 1, append = false) => {
      const auth = connectionStatus.authType ?? authType;
      if (!selectedConfigId || (auth !== 'standard' && auth !== 'pat')) return;
      setLoadingSites(true);
      try {
        const search = debouncedSiteSearch.length >= 1 ? debouncedSiteSearch : undefined;
        const result = await authApi.listSites(selectedConfigId, auth, 50, pageNumber, search);
        if (append) {
          setSites((prev) => [...prev, ...result.sites]);
        } else {
          setSites(result.sites);
        }
        setSitesPagination({
          pageNumber: result.pagination.page_number,
          totalAvailable: result.pagination.total_available,
        });
      } catch {
        setSites([]);
        setSitesPagination(null);
      } finally {
        setLoadingSites(false);
      }
    },
    [selectedConfigId, authType, connectionStatus.authType, debouncedSiteSearch]
  );

  // Load configs on mount
  useEffect(() => {
    if (!isAuthenticated) return;
    loadConfigs();
  }, [isAuthenticated]);

  // Debounce site search
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSiteSearch(siteSearchTerm), 400);
    return () => clearTimeout(t);
  }, [siteSearchTerm]);

  // Resolve authType when selectedConfigId or preferences change
  useEffect(() => {
    const cfg = selectedConfigId ? configs.find((c) => c.id === selectedConfigId) ?? null : null;
    const perServerPref = selectedConfigId ? (perServerPreferences[selectedConfigId] as AuthType | null) : null;
    const resolved = resolveAuthType(cfg, preferredAuthType, perServerPref, userPatConfigIds, userPasswordConfigIds, selectedConfigId);
    setAuthType(resolved);
  }, [selectedConfigId, preferredAuthType, perServerPreferences, configs, userPatConfigIds, userPasswordConfigIds]);

  // Reload sites when search changes (for site switcher)
  useEffect(() => {
    if (canSwitchSite && selectedConfigId) {
      loadSites(1, false);
    }
  }, [debouncedSiteSearch, canSwitchSite, selectedConfigId, loadSites]);

  // Handle OAuth callback redirect (?tableau_connected=1 or ?tableau_error=...)
  useEffect(() => {
    if (typeof window === 'undefined' || !isAuthenticated) return;
    const params = new URLSearchParams(window.location.search);
    const connected = params.get('tableau_connected');
    const error = params.get('tableau_error');
    const errorDetail = params.get('tableau_error_detail');
    const configIdFromUrl = params.get('tableau_config_id');
    if (connected || error || configIdFromUrl) {
      console.log('[Tableau OAuth] Callback params:', { connected, error, configIdFromUrl, configsCount: configs.length });
    }
    if (connected === '1' && configIdFromUrl) {
      if (configs.length === 0) {
        console.log('[Tableau OAuth] Waiting for configs to load before applying connection');
        return;
      }
      const config = configs.find((c) => c.id === Number(configIdFromUrl));
      console.log('[Tableau OAuth] Match check:', { configIdFromUrl, configIdNum: Number(configIdFromUrl), found: !!config, configIds: configs.map((c) => c.id) });
      if (config) {
        console.log('[Tableau OAuth] Applying connection for config:', config.id, config.name);
        setSelectedConfigId(Number(configIdFromUrl));
        setAuthType('connected_app_oauth');
        setConnectionStatus({
          connected: true,
          config,
          authResponse: { authenticated: true, server_url: config.server_url, token: '...' },
          authType: 'connected_app_oauth',
        });
        localStorage.setItem('tableau_config_id', configIdFromUrl);
        localStorage.setItem('tableau_auth_type', 'connected_app_oauth');
        localStorage.setItem('tableau_connected', 'true');
        onConnectionChange?.(true, config);
        setError(null);
      } else {
        setError('Tableau connected but configuration not found. Please try connecting again.');
      }
      const url = new URL(window.location.href);
      url.searchParams.delete('tableau_connected');
      url.searchParams.delete('tableau_config_id');
      window.history.replaceState({}, '', url.toString());
    } else if (error) {
      const msg = errorDetail
        ? `${decodeURIComponent(error)}: ${decodeURIComponent(errorDetail)}`
        : decodeURIComponent(error);
      setError(msg);
      const url = new URL(window.location.href);
      url.searchParams.delete('tableau_error');
      url.searchParams.delete('tableau_error_detail');
      window.history.replaceState({}, '', url.toString());
    }
  }, [isAuthenticated, configs, onConnectionChange]);

  const loadConfigs = async () => {
    if (!isAuthenticated) return;
    try {
      const [configsList, pats, passwords, user, perServerPrefs] = await Promise.all([
        authApi.listTableauConfigs(),
        userSettingsApi.listTableauPATs().catch(() => []),
        userSettingsApi.listTableauPasswords().catch(() => []),
        authApi.getCurrentUser().catch(() => null),
        userSettingsApi.getTableauAuthPreferences().catch(() => ({})),
      ]);
      setConfigs(configsList);
      setUserPatConfigIds(pats.map((p) => p.tableau_server_config_id));
      setUserPasswordConfigIds(passwords.map((p) => p.tableau_server_config_id));
      setPerServerPreferences(perServerPrefs as Record<number, AuthType>);
      const pref = user?.preferred_tableau_auth_type;
      if (pref && ['pat', 'connected_app', 'standard', 'connected_app_oauth'].includes(pref)) {
        setPreferredAuthType(pref as typeof preferredAuthType);
      }
      const storedConfigId = localStorage.getItem('tableau_config_id');
      const configId = storedConfigId && configsList.find((c) => c.id === Number(storedConfigId))
        ? Number(storedConfigId)
        : null;
      if (configId) setSelectedConfigId(configId);
      const found = configId ? configsList.find((c) => c.id === configId) : undefined;
      const cfg = found != null ? found : null;
      const perServerPref = configId && typeof perServerPrefs === 'object' && configId in perServerPrefs 
        ? (perServerPrefs as Record<number, AuthType>)[configId] as AuthType | null 
        : null;
      const resolved = resolveAuthType(cfg, pref as AuthType | null, perServerPref, pats.map((p) => p.tableau_server_config_id), passwords.map((p) => p.tableau_server_config_id), configId);
      setAuthType(resolved);
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

    const config = configs.find((c) => c.id === selectedConfigId);
    const hasCA = config?.has_connected_app ?? false;
    const hasOAuth = config?.has_connected_app_oauth ?? false;
    const effectiveAuthType = hasOAuth && authType === 'connected_app_oauth'
      ? 'connected_app_oauth'
      : hasCA
        ? authType
        : config?.allow_pat_auth
          ? 'pat'
          : config?.allow_standard_auth
            ? 'standard'
            : 'pat';

    if (effectiveAuthType === 'connected_app_oauth') {
      try {
        const { authorize_url } = await authApi.getOAuthAuthorizeUrl(selectedConfigId);
        localStorage.setItem('tableau_config_id', String(selectedConfigId));
        localStorage.setItem('tableau_auth_type', 'connected_app_oauth');
        window.location.href = authorize_url;
      } catch (err: unknown) {
        setError(extractErrorMessage(err, 'Failed to start OAuth flow'));
      } finally {
        setLoading(false);
      }
      return;
    }

    try {
      const authResponse = await authApi.authenticateTableau({
        config_id: selectedConfigId,
        auth_type: effectiveAuthType,
      });
      setConnectionStatus({
        connected: true,
        config,
        authResponse,
        authType: effectiveAuthType,
      });

      const canSwitchSite = effectiveAuthType === 'standard' || effectiveAuthType === 'pat';
      if (canSwitchSite && selectedConfigId) {
        setSiteSearchTerm('');
        setDebouncedSiteSearch('');
        setLoadingSites(true);
        try {
          const result = await authApi.listSites(selectedConfigId, effectiveAuthType, 50, 1);
          setSites(result.sites);
          setSitesPagination({
            pageNumber: result.pagination.page_number,
            totalAvailable: result.pagination.total_available,
          });
        } catch {
          setSites([]);
          setSitesPagination(null);
        } finally {
          setLoadingSites(false);
        }
      } else {
        setSites([]);
        setSitesPagination(null);
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
    setSitesPagination(null);
    setSiteSearchTerm('');
    setDebouncedSiteSearch('');
    localStorage.removeItem('tableau_config_id');
    localStorage.removeItem('tableau_auth_type');
    localStorage.removeItem('tableau_connected');
    localStorage.removeItem('tableau_token_expires_at');
    localStorage.removeItem('tableau_site_content_url');
    onConnectionChange?.(false);
  };

  const handleSwitchSite = async (siteContentUrl: string) => {
    if (!selectedConfigId || switchingSite) return;
    const currentUrl = sites.find((s) => s.id === connectionStatus.authResponse?.site_id)?.contentUrl ?? '';
    if (siteContentUrl === currentUrl) return;
    setSwitchingSite(true);
    setError(null);
    try {
      const authResponse = await authApi.switchSite({
        config_id: selectedConfigId,
        auth_type: (connectionStatus.authType ?? authType) as 'standard' | 'pat',
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
  const canUsePat = !!selectedConfig?.allow_pat_auth && selectedConfigId != null && userPatConfigIds.includes(selectedConfigId);
  const canUseStandard =
    !!selectedConfig?.allow_standard_auth && selectedConfigId != null && userPasswordConfigIds.includes(selectedConfigId);
  const needsPatConfig = authType === 'pat' && !canUsePat && !!selectedConfig?.allow_pat_auth;
  const needsPwdConfig = authType === 'standard' && !canUseStandard;

  const supportedAuthTypes: AuthType[] = [];
  if (selectedConfig?.has_connected_app) supportedAuthTypes.push('connected_app');
  if (selectedConfig?.has_connected_app_oauth) supportedAuthTypes.push('connected_app_oauth');
  if (selectedConfig?.allow_pat_auth) supportedAuthTypes.push('pat');
  if (selectedConfig?.allow_standard_auth) supportedAuthTypes.push('standard');
  const showAuthSelector = !connectionStatus.connected && supportedAuthTypes.length > 1;
  const selectableAuthType = supportedAuthTypes.includes(authType) ? authType : supportedAuthTypes[0] ?? 'connected_app';

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
              if (connectionStatus.connected) handleDisconnect();
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

          {showAuthSelector && (
            <Select
              value={selectableAuthType}
              onValueChange={(v) => {
                const t = v as AuthType;
                if (selectedConfigId) {
                  setPerServerPreferences((prev) => ({ ...prev, [selectedConfigId]: t }));
                  userSettingsApi.updateTableauAuthPreference(selectedConfigId, t).catch(() => {});
                }
              }}
            >
              <SelectTrigger className="w-[180px]" title="Auth method (standard/PAT allow site switching)">
                <SelectValue placeholder="Auth method" />
              </SelectTrigger>
              <SelectContent>
                {supportedAuthTypes.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t === 'standard' ? 'Username/password' : t === 'pat' ? 'PAT' : t === 'connected_app' ? 'Connected App' : 'OAuth'}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

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
              disabled={!selectedConfigId || loading || needsPatConfig || needsPwdConfig}
              size="sm"
              title={needsPatConfig ? 'Add PAT in Settings first' : needsPwdConfig ? 'Add credentials in Settings first' : 'Connect'}
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <HiOutlineLink className="h-4 w-4" />
              )}
            </Button>
          )}
        </div>
        {!connectionStatus.connected && (needsPatConfig || needsPwdConfig) && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            {needsPatConfig && (
              <Link href="/settings">
                <Button variant="outline" size="sm">Add PAT in Settings</Button>
              </Link>
            )}
            {needsPwdConfig && (
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
            <div className="space-y-2">
              <div className="relative">
                <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search sites..."
                  value={siteSearchTerm}
                  onChange={(e) => setSiteSearchTerm(e.target.value)}
                  className="h-7 pl-7 pr-7 text-xs"
                />
                {siteSearchTerm && (
                  <button
                    type="button"
                    onClick={() => setSiteSearchTerm('')}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
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
                    {loadingSites ? (
                      <div className="flex items-center justify-center py-4">
                        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                      </div>
                    ) : sites.length === 0 ? (
                      <div className="py-2 px-2 text-sm text-muted-foreground">
                        {siteSearchTerm ? 'No sites match search' : 'No sites found'}
                      </div>
                    ) : (
                      sites.map((s) => {
                        const contentUrl = s.contentUrl ?? '';
                        const value = contentUrl || '__default__';
                        return (
                          <SelectItem key={s.id ?? value} value={value}>
                            {s.name ?? s.contentUrl ?? 'Default'}
                          </SelectItem>
                        );
                      })
                    )}
                  </SelectContent>
                </Select>
                {switchingSite && (
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                )}
              </div>
              {sitesPagination && sitesPagination.totalAvailable > sites.length && (
                <div className="flex items-center gap-2">
                  <p className="text-xs text-muted-foreground">
                    Showing {sites.length} of {sitesPagination.totalAvailable} sites
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-6 text-xs"
                    disabled={loadingSites}
                    onClick={() => loadSites((sitesPagination?.pageNumber ?? 1) + 1, true)}
                  >
                    {loadingSites ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Load more'}
                  </Button>
                </div>
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
