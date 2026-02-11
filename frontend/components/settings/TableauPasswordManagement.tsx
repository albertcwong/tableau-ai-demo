'use client';

import { useState, useEffect } from 'react';
import {
  userSettingsApi,
  authApi,
  type UserTableauPassword,
  type CreateTableauPassword,
  type TableauConfigOption,
} from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Trash2, Plus } from 'lucide-react';

export function TableauPasswordManagement() {
  const [passwords, setPasswords] = useState<UserTableauPassword[]>([]);
  const [configs, setConfigs] = useState<TableauConfigOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState<CreateTableauPassword>({
    tableau_server_config_id: 0,
    tableau_username: '',
    password: '',
  });

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [passwordsList, configsList] = await Promise.all([
        userSettingsApi.listTableauPasswords(),
        authApi.listTableauConfigs(),
      ]);
      setPasswords(passwordsList);
      setConfigs(configsList.filter((c) => c.allow_standard_auth));
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail ||
          (err as { message?: string })?.message ||
          'Failed to load data'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.tableau_server_config_id || !formData.tableau_username || !formData.password) {
      setError('Please fill in all fields');
      return;
    }
    try {
      setError(null);
      await userSettingsApi.createTableauPassword(formData);
      setFormData({ tableau_server_config_id: 0, tableau_username: '', password: '' });
      setShowAddForm(false);
      loadData();
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail ||
          (err as { message?: string })?.message ||
          'Failed to save credentials'
      );
    }
  };

  const handleDelete = async (configId: number) => {
    if (!confirm('Remove these credentials? You will need to reconfigure to use username/password authentication.'))
      return;
    try {
      setError(null);
      await userSettingsApi.deleteTableauPassword(configId);
      loadData();
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail ||
          (err as { message?: string })?.message ||
          'Failed to delete credentials'
      );
    }
  };

  const availableConfigs = configs.filter(
    (c) => !passwords.some((p) => p.tableau_server_config_id === c.id)
  );

  if (loading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Tableau Username/Password</CardTitle>
        <p className="text-sm text-muted-foreground">
          Manage credentials for Tableau servers that support standard authentication. Add credentials to connect
          using username and password.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {passwords.length > 0 && (
          <div className="space-y-2">
            <Label>Configured credentials</Label>
            <ul className="divide-y rounded-md border">
              {passwords.map((pw) => (
                <li key={pw.id} className="flex items-center justify-between p-3">
                  <div>
                    <p className="font-medium">{pw.server_name}</p>
                    <p className="text-sm text-muted-foreground">
                      User: {pw.tableau_username} • {pw.server_url}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Added {new Date(pw.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(pw.tableau_server_config_id)}
                    title="Remove credentials"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {configs.length === 0 && (
          <Alert>
            <AlertDescription>
              No Tableau servers have standard authentication enabled. Ask your administrator to enable it in the
              Admin panel.
            </AlertDescription>
          </Alert>
        )}
        {configs.length > 0 && (
          <>
            {showAddForm ? (
              <form onSubmit={handleSubmit} className="space-y-4 border rounded-lg p-4">
                <div className="space-y-2">
                  <Label>Server</Label>
                  <Select
                    value={formData.tableau_server_config_id?.toString() || ''}
                    onValueChange={(v) =>
                      setFormData({ ...formData, tableau_server_config_id: parseInt(v) })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select server" />
                    </SelectTrigger>
                    <SelectContent>
                      {configs.map((c) => (
                        <SelectItem
                          key={c.id}
                          value={c.id.toString()}
                          disabled={passwords.some((p) => p.tableau_server_config_id === c.id)}
                        >
                          {c.name}{' '}
                          {passwords.some((p) => p.tableau_server_config_id === c.id) && '(already configured)'}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="tableau_username">Tableau username</Label>
                  <Input
                    id="tableau_username"
                    value={formData.tableau_username}
                    onChange={(e) => setFormData({ ...formData, tableau_username: e.target.value })}
                    placeholder="tableau_username"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    placeholder="Your Tableau password"
                    required
                  />
                </div>
                <div className="flex gap-2">
                  <Button type="submit">
                    <Plus className="h-4 w-4" /> Save
                  </Button>
                  <Button type="button" variant="outline" onClick={() => setShowAddForm(false)}>
                    Cancel
                  </Button>
                </div>
              </form>
            ) : (
              <Button onClick={() => setShowAddForm(true)} disabled={availableConfigs.length === 0}>
                <Plus className="h-4 w-4" /> Add credentials
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
