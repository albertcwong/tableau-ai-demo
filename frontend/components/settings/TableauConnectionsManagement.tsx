'use client';

import { useState, useEffect } from 'react';
import { authApi, userSettingsApi, type TableauConfigOption, type UserTableauPAT, type UserTableauPassword, type CreateTableauPAT, type CreateTableauPassword } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Trash2, Plus, Loader2 } from 'lucide-react';
import { extractErrorMessage } from '@/lib/utils';

type AuthType = 'connected_app' | 'connected_app_oauth' | 'pat' | 'standard';

const AUTH_OPTIONS: { value: AuthType; label: string }[] = [
  { value: 'connected_app', label: 'Connected App Direct Trust' },
  { value: 'connected_app_oauth', label: 'Connected App OAuth Trust' },
  { value: 'pat', label: 'Personal Access Token' },
  { value: 'standard', label: 'Username/Password' },
];

interface ServerConnectionCardProps {
  config: TableauConfigOption;
  preferredAuthType: AuthType | null;
  pat: UserTableauPAT | null;
  password: UserTableauPassword | null;
  onAuthTypeChange: (configId: number, authType: AuthType) => Promise<void>;
  onPatAdd: (configId: number, data: CreateTableauPAT) => Promise<void>;
  onPatDelete: (configId: number) => Promise<void>;
  onPasswordAdd: (configId: number, data: CreateTableauPassword) => Promise<void>;
  onPasswordDelete: (configId: number) => Promise<void>;
}

function ServerConnectionCard({
  config,
  preferredAuthType,
  pat,
  password,
  onAuthTypeChange,
  onPatAdd,
  onPatDelete,
  onPasswordAdd,
  onPasswordDelete,
}: ServerConnectionCardProps) {
  const [authType, setAuthType] = useState<AuthType>(preferredAuthType || 'connected_app');
  const [savingAuth, setSavingAuth] = useState(false);
  const [showPatForm, setShowPatForm] = useState(false);
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [patFormData, setPatFormData] = useState({ pat_name: '', pat_secret: '' });
  const [passwordFormData, setPasswordFormData] = useState({ tableau_username: '', password: '' });
  const [savingPat, setSavingPat] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (preferredAuthType) {
      setAuthType(preferredAuthType);
    }
  }, [preferredAuthType]);

  const handleAuthTypeChange = async (value: string) => {
    const newAuthType = value as AuthType;
    setAuthType(newAuthType);
    setSavingAuth(true);
    setError(null);
    try {
      await onAuthTypeChange(config.id, newAuthType);
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to save preference'));
      setAuthType(preferredAuthType || 'connected_app');
    } finally {
      setSavingAuth(false);
    }
  };

  const handlePatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patFormData.pat_name || !patFormData.pat_secret) {
      setError('Please fill in all fields');
      return;
    }
    setSavingPat(true);
    setError(null);
    try {
      await onPatAdd(config.id, {
        tableau_server_config_id: config.id,
        pat_name: patFormData.pat_name,
        pat_secret: patFormData.pat_secret,
      });
      setPatFormData({ pat_name: '', pat_secret: '' });
      setShowPatForm(false);
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to save PAT'));
    } finally {
      setSavingPat(false);
    }
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!passwordFormData.tableau_username || !passwordFormData.password) {
      setError('Please fill in all fields');
      return;
    }
    setSavingPassword(true);
    setError(null);
    try {
      await onPasswordAdd(config.id, {
        tableau_server_config_id: config.id,
        tableau_username: passwordFormData.tableau_username,
        password: passwordFormData.password,
      });
      setPasswordFormData({ tableau_username: '', password: '' });
      setShowPasswordForm(false);
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to save credentials'));
    } finally {
      setSavingPassword(false);
    }
  };

  const siteDisplay = config.site_id && config.site_id.trim() ? config.site_id : 'Default';

  return (
    <Card>
      <CardHeader>
        <CardTitle>{config.name}</CardTitle>
        <CardDescription>
          {config.server_url} {siteDisplay !== 'Default' && `• Site: ${siteDisplay}`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="space-y-3">
          <Label>Preferred authentication</Label>
          <RadioGroup value={authType} onValueChange={handleAuthTypeChange} disabled={savingAuth}>
            {AUTH_OPTIONS.map((opt) => {
              const isDisabled =
                (opt.value === 'connected_app' && !config.has_connected_app) ||
                (opt.value === 'connected_app_oauth' && !config.has_connected_app_oauth) ||
                (opt.value === 'pat' && !config.allow_pat_auth) ||
                (opt.value === 'standard' && !config.allow_standard_auth);
              return (
                <div key={opt.value} className="flex items-center space-x-2">
                  <RadioGroupItem value={opt.value} id={`${config.id}-${opt.value}`} disabled={isDisabled || savingAuth} />
                  <Label
                    htmlFor={`${config.id}-${opt.value}`}
                    className={`cursor-pointer font-normal ${isDisabled ? 'text-muted-foreground' : ''}`}
                  >
                    {opt.label}
                  </Label>
                </div>
              );
            })}
          </RadioGroup>
          {savingAuth && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Saving...
            </div>
          )}
        </div>

        {config.allow_pat_auth && (
          <div className="space-y-3 border-t pt-4">
            <Label>Personal Access Token</Label>
            {pat ? (
              <div className="flex items-center justify-between p-3 rounded-md border">
                <div>
                  <p className="font-medium">{pat.pat_name}</p>
                  <p className="text-sm text-muted-foreground">
                    Added {new Date(pat.created_at).toLocaleDateString()}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onPatDelete(config.id)}
                  title="Remove PAT"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ) : showPatForm ? (
              <form onSubmit={handlePatSubmit} className="space-y-3 border rounded-lg p-4">
                <div className="space-y-2">
                  <Label htmlFor={`pat-name-${config.id}`}>PAT Name</Label>
                  <Input
                    id={`pat-name-${config.id}`}
                    value={patFormData.pat_name}
                    onChange={(e) => setPatFormData({ ...patFormData, pat_name: e.target.value })}
                    placeholder="My PAT"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor={`pat-secret-${config.id}`}>PAT Secret</Label>
                  <Input
                    id={`pat-secret-${config.id}`}
                    type="password"
                    value={patFormData.pat_secret}
                    onChange={(e) => setPatFormData({ ...patFormData, pat_secret: e.target.value })}
                    placeholder="Your PAT secret"
                    required
                  />
                  <p className="text-xs text-muted-foreground">
                    Create a PAT in Tableau Server: User menu → My Account Settings → Personal Access Tokens
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button type="submit" disabled={savingPat}>
                    {savingPat ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Plus className="mr-2 h-4 w-4" />
                        Save
                      </>
                    )}
                  </Button>
                  <Button type="button" variant="outline" onClick={() => setShowPatForm(false)}>
                    Cancel
                  </Button>
                </div>
              </form>
            ) : (
              <Button onClick={() => setShowPatForm(true)} variant="outline" size="sm">
                <Plus className="mr-2 h-4 w-4" />
                Add PAT
              </Button>
            )}
          </div>
        )}

        {config.allow_standard_auth && (
          <div className="space-y-3 border-t pt-4">
            <Label>Username/Password</Label>
            {password ? (
              <div className="flex items-center justify-between p-3 rounded-md border">
                <div>
                  <p className="font-medium">{password.tableau_username}</p>
                  <p className="text-sm text-muted-foreground">
                    Added {new Date(password.created_at).toLocaleDateString()}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onPasswordDelete(config.id)}
                  title="Remove credentials"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ) : showPasswordForm ? (
              <form onSubmit={handlePasswordSubmit} className="space-y-3 border rounded-lg p-4">
                <div className="space-y-2">
                  <Label htmlFor={`password-username-${config.id}`}>Tableau username</Label>
                  <Input
                    id={`password-username-${config.id}`}
                    value={passwordFormData.tableau_username}
                    onChange={(e) => setPasswordFormData({ ...passwordFormData, tableau_username: e.target.value })}
                    placeholder="tableau_username"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor={`password-password-${config.id}`}>Password</Label>
                  <Input
                    id={`password-password-${config.id}`}
                    type="password"
                    value={passwordFormData.password}
                    onChange={(e) => setPasswordFormData({ ...passwordFormData, password: e.target.value })}
                    placeholder="Your Tableau password"
                    required
                  />
                </div>
                <div className="flex gap-2">
                  <Button type="submit" disabled={savingPassword}>
                    {savingPassword ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Plus className="mr-2 h-4 w-4" />
                        Save
                      </>
                    )}
                  </Button>
                  <Button type="button" variant="outline" onClick={() => setShowPasswordForm(false)}>
                    Cancel
                  </Button>
                </div>
              </form>
            ) : (
              <Button onClick={() => setShowPasswordForm(true)} variant="outline" size="sm">
                <Plus className="mr-2 h-4 w-4" />
                Add credentials
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function TableauConnectionsManagement() {
  const [configs, setConfigs] = useState<TableauConfigOption[]>([]);
  const [preferences, setPreferences] = useState<Record<number, string>>({});
  const [pats, setPats] = useState<UserTableauPAT[]>([]);
  const [passwords, setPasswords] = useState<UserTableauPassword[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [configsList, prefs, patsList, passwordsList] = await Promise.all([
        authApi.listTableauConfigs(),
        userSettingsApi.getTableauAuthPreferences().catch(() => ({})),
        userSettingsApi.listTableauPATs().catch(() => []),
        userSettingsApi.listTableauPasswords().catch(() => []),
      ]);
      setConfigs(configsList);
      setPreferences(prefs);
      setPats(patsList);
      setPasswords(passwordsList);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to load Tableau connections'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleAuthTypeChange = async (configId: number, authType: AuthType) => {
    await userSettingsApi.updateTableauAuthPreference(configId, authType);
    setPreferences((prev) => ({ ...prev, [configId]: authType }));
  };

  const handlePatAdd = async (configId: number, data: CreateTableauPAT) => {
    await userSettingsApi.createTableauPAT(data);
    await loadData();
  };

  const handlePatDelete = async (configId: number) => {
    if (!confirm('Remove this PAT? You will need to reconfigure it to use PAT authentication.')) return;
    await userSettingsApi.deleteTableauPAT(configId);
    await loadData();
  };

  const handlePasswordAdd = async (configId: number, data: CreateTableauPassword) => {
    await userSettingsApi.createTableauPassword(data);
    await loadData();
  };

  const handlePasswordDelete = async (configId: number) => {
    if (!confirm('Remove these credentials? You will need to reconfigure to use username/password authentication.')) return;
    await userSettingsApi.deleteTableauPassword(configId);
    await loadData();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (configs.length === 0) {
    return (
      <Alert>
        <AlertDescription>
          No Tableau server configurations available. Please contact your administrator.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      {configs.map((config) => {
        const pat = pats.find((p) => p.tableau_server_config_id === config.id) || null;
        const password = passwords.find((p) => p.tableau_server_config_id === config.id) || null;
        const preferredAuthType = (preferences[config.id] as AuthType) || null;
        return (
          <ServerConnectionCard
            key={config.id}
            config={config}
            preferredAuthType={preferredAuthType}
            pat={pat}
            password={password}
            onAuthTypeChange={handleAuthTypeChange}
            onPatAdd={handlePatAdd}
            onPatDelete={handlePatDelete}
            onPasswordAdd={handlePasswordAdd}
            onPasswordDelete={handlePasswordDelete}
          />
        );
      })}
    </div>
  );
}
