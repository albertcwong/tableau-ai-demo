'use client';

import { useState, useEffect } from 'react';
import { authApi, type TableauConfigOption, type TableauAuthResponse } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, CheckCircle2, XCircle, Server, X } from 'lucide-react';
import { HiOutlineLink } from 'react-icons/hi';
import { FaUnlink } from 'react-icons/fa';
import { useAuth } from '@/components/auth/AuthContext';

interface TableauConnectionStatusProps {
  onConnectionChange?: (connected: boolean, config?: TableauConfigOption) => void;
}

export function TableauConnectionStatus({ onConnectionChange }: TableauConnectionStatusProps) {
  const { isAdmin } = useAuth();
  const [configs, setConfigs] = useState<TableauConfigOption[]>([]);
  const [selectedConfigId, setSelectedConfigId] = useState<number | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<{
    connected: boolean;
    config?: TableauConfigOption;
    authResponse?: TableauAuthResponse;
  }>({ connected: false });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load configs on mount
  useEffect(() => {
    loadConfigs();
    // Don't automatically restore connection state - let user explicitly connect
    // This prevents automatic API calls on page load
    // The stored config ID can be restored for UI purposes (in loadConfigs),
    // but connection state should only be set when user explicitly clicks "Connect"
  }, []);

  const loadConfigs = async () => {
    try {
      const configsList = await authApi.listTableauConfigs();
      setConfigs(configsList);
      // If there's a stored config ID, select it
      const storedConfigId = localStorage.getItem('tableau_config_id');
      if (storedConfigId && configsList.find(c => c.id === Number(storedConfigId))) {
        setSelectedConfigId(Number(storedConfigId));
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
      const authResponse = await authApi.authenticateTableau({ config_id: selectedConfigId });
      const config = configs.find(c => c.id === selectedConfigId);
      
      setConnectionStatus({
        connected: true,
        config,
        authResponse,
      });

      // Store connection state
      localStorage.setItem('tableau_config_id', String(selectedConfigId));
      localStorage.setItem('tableau_connected', 'true');
      if (authResponse.expires_at) {
        localStorage.setItem('tableau_token_expires_at', authResponse.expires_at);
      }

      onConnectionChange?.(true, config);
    } catch (err: any) {
      // Extract detailed error message from response
      let errorMessage = 'Failed to connect to Tableau server';
      if (err.response?.data) {
        // FastAPI returns errors in 'detail' field
        if (err.response.data.detail) {
          errorMessage = err.response.data.detail;
        } else if (typeof err.response.data === 'string') {
          errorMessage = err.response.data;
        } else if (err.response.data.message) {
          errorMessage = err.response.data.message;
        }
      } else if (err.message) {
        errorMessage = err.message;
      }
      setError(errorMessage);
      setConnectionStatus({ connected: false });
      onConnectionChange?.(false);
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = () => {
    setConnectionStatus({ connected: false });
    setSelectedConfigId(null);
    localStorage.removeItem('tableau_config_id');
    localStorage.removeItem('tableau_connected');
    localStorage.removeItem('tableau_token_expires_at');
    onConnectionChange?.(false);
  };

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
        <div className="flex items-center gap-2">
          <Select
            value={selectedConfigId?.toString() || ''}
            onValueChange={(value) => {
              setSelectedConfigId(Number(value));
              setError(null);
              // If currently connected, disconnect when changing config
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
      )}

      {connectionStatus.connected && connectionStatus.config && (
        <Alert className="bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800">
          <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
          <AlertDescription className="text-green-800 dark:text-green-200">
            Connected to <strong>{connectionStatus.config.name}</strong>
            {connectionStatus.authResponse?.site_id && (
              <span> (Site: {connectionStatus.authResponse.site_id})</span>
            )}
          </AlertDescription>
        </Alert>
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
