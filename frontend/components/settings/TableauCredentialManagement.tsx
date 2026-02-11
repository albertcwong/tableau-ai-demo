'use client';

import { useState, useEffect } from 'react';
import type { TableauConfigOption } from '@/lib/api';
import { authApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Trash2, Plus } from 'lucide-react';
import { extractErrorMessage } from '@/lib/utils';

export interface CredentialItem {
  id: number;
  tableau_server_config_id: number;
  server_name: string;
  server_url: string;
  created_at: string;
}

export interface CredentialConfig<T extends CredentialItem, C extends { tableau_server_config_id: number }> {
  title: string;
  description: string;
  listLabel: string;
  addLabel: string;
  emptyConfigMessage: string;
  deleteConfirm: string;
  configFilter: (c: TableauConfigOption) => boolean;
  listApi: () => Promise<T[]>;
  createApi: (data: C) => Promise<T>;
  deleteApi: (configId: number) => Promise<void>;
  displayField: keyof T;
  formFields: Array<{
    key: string;
    label: string;
    placeholder: string;
    type?: string;
    hint?: string;
  }>;
  getInitialForm: () => C;
}

export function TableauCredentialManagement<
  T extends CredentialItem,
  C extends { tableau_server_config_id: number },
>({
  config,
}: {
  config: CredentialConfig<T, C>;
}) {
  const [items, setItems] = useState<T[]>([]);
  const [configs, setConfigs] = useState<TableauConfigOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState<C>(config.getInitialForm());

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [itemsList, configsList] = await Promise.all([
        config.listApi(),
        authApi.listTableauConfigs(),
      ]);
      setItems(itemsList);
      setConfigs(configsList.filter(config.configFilter));
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to load data'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const required = [formData.tableau_server_config_id, ...config.formFields.map((f) => (formData as Record<string, unknown>)[f.key as string])];
    if (required.some((v) => !v)) {
      setError('Please fill in all fields');
      return;
    }
    try {
      setError(null);
      await config.createApi(formData);
      setFormData(config.getInitialForm());
      setShowAddForm(false);
      loadData();
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to save'));
    }
  };

  const handleDelete = async (configId: number) => {
    if (!confirm(config.deleteConfirm)) return;
    try {
      setError(null);
      await config.deleteApi(configId);
      loadData();
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to delete'));
    }
  };

  const availableConfigs = configs.filter((c) => !items.some((p) => p.tableau_server_config_id === c.id));

  if (loading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{config.title}</CardTitle>
        <p className="text-sm text-muted-foreground">{config.description}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {items.length > 0 && (
          <div className="space-y-2">
            <Label>{config.listLabel}</Label>
            <ul className="divide-y rounded-md border">
              {items.map((item) => (
                <li key={item.id} className="flex items-center justify-between p-3">
                  <div>
                    <p className="font-medium">{item.server_name}</p>
                    <p className="text-sm text-muted-foreground">
                      {String((item as Record<string, unknown>)[config.displayField as string])} • {item.server_url}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Added {new Date(item.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(item.tableau_server_config_id)}
                    title="Remove"
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
            <AlertDescription>{config.emptyConfigMessage}</AlertDescription>
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
                      setFormData({ ...formData, tableau_server_config_id: parseInt(v) } as C)
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
                          disabled={items.some((p) => p.tableau_server_config_id === c.id)}
                        >
                          {c.name}{' '}
                          {items.some((p) => p.tableau_server_config_id === c.id) && '(already configured)'}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {config.formFields.map((f) => (
                  <div key={String(f.key)} className="space-y-2">
                    <Label htmlFor={String(f.key)}>{f.label}</Label>
                    <Input
                      id={String(f.key)}
                      type={f.type || 'text'}
                      value={String((formData as Record<string, unknown>)[f.key as string] ?? '')}
                      onChange={(e) =>
                        setFormData({ ...formData, [f.key]: e.target.value } as C)
                      }
                      placeholder={f.placeholder}
                      required
                    />
                    {f.hint && <p className="text-xs text-muted-foreground">{f.hint}</p>}
                  </div>
                ))}
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
                <Plus className="h-4 w-4" /> {config.addLabel}
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
