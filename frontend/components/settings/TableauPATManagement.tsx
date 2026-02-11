'use client';

import { useState, useEffect } from 'react';
import { userSettingsApi, authApi, type UserTableauPAT, type CreateTableauPAT, type TableauConfigOption } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Trash2, Plus } from 'lucide-react';

export function TableauPATManagement() {
  const [pats, setPats] = useState<UserTableauPAT[]>([]);
  const [configs, setConfigs] = useState<TableauConfigOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState<CreateTableauPAT>({
    tableau_server_config_id: 0,
    pat_name: '',
    pat_secret: '',
  });

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [patsList, configsList] = await Promise.all([
        userSettingsApi.listTableauPATs(),
        authApi.listTableauConfigs(),
      ]);
      setPats(patsList);
      setConfigs(configsList.filter((c) => c.allow_pat_auth));
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.tableau_server_config_id || !formData.pat_name || !formData.pat_secret) {
      setError('Please fill in all fields');
      return;
    }
    try {
      setError(null);
      await userSettingsApi.createTableauPAT(formData);
      setFormData({ tableau_server_config_id: 0, pat_name: '', pat_secret: '' });
      setShowAddForm(false);
      loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to save PAT');
    }
  };

  const handleDelete = async (configId: number) => {
    if (!confirm('Remove this PAT? You will need to reconfigure it to use PAT authentication.')) return;
    try {
      setError(null);
      await userSettingsApi.deleteTableauPAT(configId);
      loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to delete PAT');
    }
  };

  const availableConfigs = configs.filter(
    (c) => !pats.some((p) => p.tableau_server_config_id === c.id)
  );

  if (loading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Tableau Personal Access Tokens</CardTitle>
        <p className="text-sm text-muted-foreground">
          Manage PATs for Tableau servers that support PAT authentication. Add a PAT to connect using your own token instead of the Connected App.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {pats.length > 0 && (
          <div className="space-y-2">
            <Label>Configured PATs</Label>
            <ul className="divide-y rounded-md border">
              {pats.map((pat) => (
                <li key={pat.id} className="flex items-center justify-between p-3">
                  <div>
                    <p className="font-medium">{pat.server_name}</p>
                    <p className="text-sm text-muted-foreground">
                      PAT: {pat.pat_name} • {pat.server_url}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Added {new Date(pat.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(pat.tableau_server_config_id)}
                    title="Remove PAT"
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
              No Tableau servers have PAT authentication enabled. Ask your administrator to enable it in the Admin panel.
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
                          disabled={pats.some((p) => p.tableau_server_config_id === c.id)}
                        >
                          {c.name} {pats.some((p) => p.tableau_server_config_id === c.id) && '(already configured)'}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="pat_name">PAT Name</Label>
                  <Input
                    id="pat_name"
                    value={formData.pat_name}
                    onChange={(e) => setFormData({ ...formData, pat_name: e.target.value })}
                    placeholder="My PAT"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="pat_secret">PAT Secret</Label>
                  <Input
                    id="pat_secret"
                    type="password"
                    value={formData.pat_secret}
                    onChange={(e) => setFormData({ ...formData, pat_secret: e.target.value })}
                    placeholder="Your PAT secret"
                    required
                  />
                  <p className="text-xs text-muted-foreground">
                    Create a PAT in Tableau Server: User menu → My Account Settings → Personal Access Tokens
                  </p>
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
                <Plus className="h-4 w-4" /> Add PAT
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
