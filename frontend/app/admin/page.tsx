'use client';

import { useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAuth } from '@/components/auth/AuthContext';
import { authApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { UserManagement } from '@/components/admin/UserManagement';
import { TableauConfigManagement } from '@/components/admin/TableauConfigManagement';
import { ProviderConfigManagement } from '@/components/admin/ProviderConfigManagement';
import { FeedbackManagement } from '@/components/admin/FeedbackManagement';
import { Home, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';

function AdminDashboardContent() {
  const router = useRouter();
  const pathname = usePathname();
  const { user, logout, isAdmin } = useAuth();
  const [loading, setLoading] = useState(true);

  // Admin page is standalone, no redirect needed
  useEffect(() => {
    setLoading(false);
  }, []);

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 dark:border-gray-100 mx-auto"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
      {/* Header */}
      <header className="shrink-0 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Logo placeholder - blank for now */}
              <div className="w-8 h-8"></div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                Tableau AI
              </h1>
            </div>
            <div className="flex items-center gap-2">
              {/* Navigation Tabs */}
              <div className="flex items-center gap-1 mr-4">
                <Link href="/">
                  <Button
                    variant={pathname === '/' ? 'default' : 'ghost'}
                    size="sm"
                    className="flex items-center gap-2"
                  >
                    <Home className="h-4 w-4" />
                    Home
                  </Button>
                </Link>
                {isAdmin && (
                  <Link href="/admin">
                    <Button
                      variant={pathname === '/admin' ? 'default' : 'ghost'}
                      size="sm"
                      className="flex items-center gap-2"
                    >
                      <Settings className="h-4 w-4" />
                      Admin Console
                    </Button>
                  </Link>
                )}
              </div>
              {user && (
                <span className="text-sm text-gray-600 dark:text-gray-400 mr-2">
                  {user.username} ({user.role})
                </span>
              )}
              <Button variant="outline" size="sm" onClick={handleLogout}>
                {user ? 'Logout' : 'Login'}
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 container mx-auto px-4 py-8">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Admin Console</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Manage users, Tableau server configurations, AI provider configurations, and view feedback
          </p>
        </div>

        <Tabs defaultValue="users" className="space-y-4">
          <TabsList>
            <TabsTrigger value="users">Users</TabsTrigger>
            <TabsTrigger value="tableau">Tableau Connected Apps</TabsTrigger>
            <TabsTrigger value="providers">Providers</TabsTrigger>
            <TabsTrigger value="feedback">Feedback</TabsTrigger>
          </TabsList>
          
          <TabsContent value="users">
            <Card>
              <CardHeader>
                <CardTitle>Users</CardTitle>
                <CardDescription>
                  Add, edit, and manage system users
                </CardDescription>
              </CardHeader>
              <CardContent>
                <UserManagement />
              </CardContent>
            </Card>
          </TabsContent>
          
          <TabsContent value="tableau">
            <Card>
              <CardHeader>
                <CardTitle>Tableau Server Configurations</CardTitle>
                <CardDescription>
                  Manage Tableau server and site configurations for Connected App authentication
                </CardDescription>
              </CardHeader>
              <CardContent>
                <TableauConfigManagement />
              </CardContent>
            </Card>
          </TabsContent>
          
          <TabsContent value="providers">
            <Card>
              <CardHeader>
                <CardTitle>Providers</CardTitle>
                <CardDescription>
                  Manage AI provider configurations (OpenAI, Anthropic, Salesforce, Vertex AI, Apple Endor)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ProviderConfigManagement />
              </CardContent>
            </Card>
          </TabsContent>
          
          <TabsContent value="feedback">
            <Card>
              <CardHeader>
                <CardTitle>Message Feedback</CardTitle>
                <CardDescription>
                  View and analyze user feedback on AI responses (thumbs up/down)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <FeedbackManagement />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

export default function AdminDashboard() {
  return (
    <ProtectedRoute>
      <AdminDashboardContent />
    </ProtectedRoute>
  );
}
