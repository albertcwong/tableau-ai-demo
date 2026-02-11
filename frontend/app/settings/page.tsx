'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { authApi, userSettingsApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { TableauPATManagement } from '@/components/settings/TableauPATManagement';
import { ModelSettings } from '@/components/agent-panel/ModelSettings';
import { useAuth } from '@/components/auth/AuthContext';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';

function SettingsContent() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const [user, setUser] = useState<{ username: string; role: string } | null>(null);
  const [provider, setProvider] = useState('openai');
  const [model, setModel] = useState('gpt-4');

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/');
      return;
    }
    const load = async () => {
      try {
        const userData = await authApi.getCurrentUser();
        setUser({ username: userData.username, role: userData.role });
        setProvider(userData.preferred_provider || 'openai');
        setModel(userData.preferred_model || 'gpt-4');
      } catch {
        router.push('/');
      }
    };
    load();
  }, [isAuthenticated, router]);

  const handleSavePreferences = async () => {
    try {
      await authApi.updatePreferences({ preferred_provider: provider, preferred_model: model });
    } catch (err) {
      console.error('Failed to save preferences:', err);
    }
  };

  if (!user) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }

  return (
    <div className="container max-w-4xl py-8">
      <Link href="/">
        <Button variant="ghost" className="mb-4">
          <ArrowLeft className="h-4 w-4" /> Back
        </Button>
      </Link>
      <h1 className="text-2xl font-bold mb-6">Settings</h1>
      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="tableau">Tableau Connections</TabsTrigger>
          <TabsTrigger value="preferences">AI Preferences</TabsTrigger>
        </TabsList>
        <TabsContent value="profile" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Profile</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <p><strong>Username:</strong> {user.username}</p>
              <p><strong>Role:</strong> {user.role}</p>
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="tableau" className="mt-4">
          <TableauPATManagement />
        </TabsContent>
        <TabsContent value="preferences" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>AI Preferences</CardTitle>
              <p className="text-sm text-muted-foreground">
                Default provider and model for AI conversations
              </p>
            </CardHeader>
            <CardContent>
              <ModelSettings
                provider={provider}
                model={model}
                onProviderChange={setProvider}
                onModelChange={setModel}
              />
              <Button className="mt-4" onClick={handleSavePreferences}>
                Save Preferences
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <ProtectedRoute>
      <SettingsContent />
    </ProtectedRoute>
  );
}
