'use client';

import { useState, useEffect, useCallback } from 'react';
import { adminApi, AgentVersionResponse, AgentSettingsResponse, AgentSettingsUpdate } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert } from '@/components/ui/alert';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, Save, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';
import { extractErrorMessage } from '@/lib/utils';

export function AgentManagement() {
  const [agents, setAgents] = useState<Record<string, AgentVersionResponse[]>>({});
  const [settings, setSettings] = useState<Record<string, AgentSettingsResponse>>({});
  const [systemPrompts, setSystemPrompts] = useState<Record<string, string>>({});
  const [promptLoading, setPromptLoading] = useState<Record<string, boolean>>({});
  const [promptExpanded, setPromptExpanded] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [editingSettings, setEditingSettings] = useState<Record<string, AgentSettingsUpdate>>({});

  const loadSystemPrompt = useCallback(async (agentName: string, version: string) => {
    setPromptLoading((prev) => ({ ...prev, [agentName]: true }));
    try {
      const { content } = await adminApi.getAgentSystemPrompt(agentName, version);
      setSystemPrompts((prev) => ({ ...prev, [agentName]: content }));
    } catch {
      setSystemPrompts((prev) => ({ ...prev, [agentName]: '(Failed to load)' }));
    } finally {
      setPromptLoading((prev) => ({ ...prev, [agentName]: false }));
    }
  }, []);

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    try {
      setLoading(true);
      setError(null);
      setSuccess(null);
      const agentsData = await adminApi.listAgents();
      setAgents(agentsData);

      const settingsData: Record<string, AgentSettingsResponse> = {};
      for (const agentName of Object.keys(agentsData)) {
        try {
          const agentSettings = await adminApi.getAgentSettings(agentName);
          settingsData[agentName] = agentSettings;
        } catch (err) {
          console.warn(`No settings for agent ${agentName}:`, err);
        }
      }
      setSettings(settingsData);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to load agent configurations'));
    } finally {
      setLoading(false);
    }
  };

  const handleSetActive = async (agentName: string, version: string) => {
    try {
      setSaving(`${agentName}-${version}`);
      setError(null);
      setSuccess(null);

      await adminApi.setActiveVersion(agentName, version);

      await loadAgents();
      setSystemPrompts((prev) => {
        const next = { ...prev };
        delete next[agentName];
        return next;
      });
      setSuccess(`Active version set to ${version} for ${agentName}`);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to set active version'));
    } finally {
      setSaving(null);
    }
  };

  const handleUpdateSettings = async (agentName: string) => {
    try {
      setSaving(`${agentName}-settings`);
      setError(null);
      setSuccess(null);
      
      const update = editingSettings[agentName];
      if (!update) {
        return;
      }
      
      await adminApi.updateAgentSettings(agentName, update);
      
      await loadAgents();
      setSuccess(`Settings updated for ${agentName}`);
      setEditingSettings(prev => {
        const next = { ...prev };
        delete next[agentName];
        return next;
      });
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to update settings'));
    } finally {
      setSaving(null);
    }
  };

  const handleSettingsChange = (agentName: string, field: 'max_build_retries' | 'max_execution_retries', value: string) => {
    const numValue = value === '' ? undefined : parseInt(value, 10);
    if (numValue !== undefined && (isNaN(numValue) || numValue < 1 || numValue > 10)) {
      return; // Invalid value
    }
    
    setEditingSettings(prev => ({
      ...prev,
      [agentName]: {
        ...prev[agentName],
        [field]: numValue
      }
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
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

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Agent Versions</h2>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Select which version is used in chat
          </p>
        </div>
        <Button onClick={loadAgents} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {Object.entries(agents).map(([agentName, versions]) => {
        const agentSettings = settings[agentName];
        const editingAgentSettings = editingSettings[agentName];
        const currentSettings = editingAgentSettings || agentSettings;
        
        return (
          <Card key={agentName}>
            <CardHeader>
              <CardTitle className="capitalize">{agentName} Agent</CardTitle>
              <CardDescription>
                Manage versions and settings for the {agentName} agent
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Version selector */}
              <div>
                <h3 className="text-sm font-medium mb-3">Active version</h3>
                <div className="space-y-2">
                  {versions.map((version) => {
                    const isActive = version.is_default;
                    const isSaving = saving === `${agentName}-${version.version}`;
                    return (
                      <div
                        key={version.version}
                        className="flex items-center justify-between p-3 border rounded-lg bg-gray-50 dark:bg-gray-800"
                      >
                        <label className="flex items-center gap-3 flex-1 cursor-pointer">
                          <input
                            type="radio"
                            name={`agent-${agentName}`}
                            checked={isActive}
                            onChange={() => !isActive && handleSetActive(agentName, version.version)}
                            disabled={isSaving}
                            className="h-4 w-4"
                          />
                          <div>
                            <span className="font-medium">{version.version}</span>
                            {version.description && (
                              <span className="ml-2 text-sm text-gray-600 dark:text-gray-400">
                                {version.description}
                              </span>
                            )}
                          </div>
                        </label>
                        {isActive && (
                          <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded">
                            Active
                          </span>
                        )}
                        {isSaving && (
                          <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Settings (for VizQL) */}
              {agentName === 'vizql' && agentSettings && (
                <div className="border-t pt-4">
                  <h3 className="text-sm font-medium mb-3">Retry Settings</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor={`build-retries-${agentName}`}>
                        Max Build Retries
                      </Label>
                      <Input
                        id={`build-retries-${agentName}`}
                        type="number"
                        min="1"
                        max="10"
                        value={currentSettings?.max_build_retries?.toString() || ''}
                        onChange={(e) => handleSettingsChange(agentName, 'max_build_retries', e.target.value)}
                        placeholder="3"
                        className="mt-1"
                      />
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        Maximum query build/refinement attempts
                      </p>
                    </div>
                    <div>
                      <Label htmlFor={`execution-retries-${agentName}`}>
                        Max Execution Retries
                      </Label>
                      <Input
                        id={`execution-retries-${agentName}`}
                        type="number"
                        min="1"
                        max="10"
                        value={currentSettings?.max_execution_retries?.toString() || ''}
                        onChange={(e) => handleSettingsChange(agentName, 'max_execution_retries', e.target.value)}
                        placeholder="3"
                        className="mt-1"
                      />
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        Maximum execution retry attempts
                      </p>
                    </div>
                  </div>
                  {editingAgentSettings && (
                    <div className="mt-4">
                      <Button
                        onClick={() => handleUpdateSettings(agentName)}
                        disabled={saving === `${agentName}-settings`}
                        size="sm"
                      >
                        {saving === `${agentName}-settings` ? (
                          <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          <>
                            <Save className="h-4 w-4 mr-2" />
                            Save Settings
                          </>
                        )}
                      </Button>
                      <Button
                        onClick={() => {
                          setEditingSettings(prev => {
                            const next = { ...prev };
                            delete next[agentName];
                            return next;
                          });
                        }}
                        variant="outline"
                        size="sm"
                        className="ml-2"
                      >
                        Cancel
                      </Button>
                    </div>
                  )}
                </div>
              )}

              {/* System prompt (read-only) for active version */}
              {(() => {
                const activeVersion = versions.find((v) => v.is_default);
                if (!activeVersion) return null;
                const isExpanded = promptExpanded[agentName] ?? false;
                const promptContent = systemPrompts[agentName];
                const isLoading = promptLoading[agentName];
                return (
                  <div className="border-t pt-4">
                    <button
                      type="button"
                      onClick={() => {
                        const willExpand = !(promptExpanded[agentName] ?? false);
                        setPromptExpanded((prev) => ({ ...prev, [agentName]: willExpand }));
                        if (willExpand && !promptContent && !isLoading) {
                          loadSystemPrompt(agentName, activeVersion.version);
                        }
                      }}
                      className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100"
                    >
                      {isExpanded ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                      System prompt ({activeVersion.version})
                    </button>
                    {isExpanded && (
                      <div className="mt-2">
                        {isLoading ? (
                          <div className="flex items-center gap-2 py-4 text-sm text-gray-500">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Loading...
                          </div>
                        ) : (
                          <textarea
                            readOnly
                            value={promptContent ?? ''}
                            rows={12}
                            className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-3 font-mono text-xs text-gray-700 dark:text-gray-300 resize-y"
                          />
                        )}
                      </div>
                    )}
                  </div>
                );
              })()}
            </CardContent>
          </Card>
        );
      })}

      {Object.keys(agents).length === 0 && (
        <Alert>
          No agents found. Agents will be created automatically during migration.
        </Alert>
      )}
    </div>
  );
}
