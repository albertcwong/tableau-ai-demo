'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/auth/AuthContext';
import { authApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert } from '@/components/ui/alert';
import Image from 'next/image';
import { extractErrorMessage } from '@/lib/utils';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [authConfig, setAuthConfig] = useState<{ enable_password_auth: boolean; enable_oauth_auth: boolean } | null>(null);
  const { login, isAuthenticated, loading: authLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // Check for error in URL params (from Auth0 redirect)
    const params = new URLSearchParams(window.location.search);
    const errorParam = params.get('error');
    const messageParam = params.get('message');
    
    if (errorParam && messageParam) {
      setError(messageParam);
      // Clean up URL
      window.history.replaceState({}, '', window.location.pathname);
    }
    
    // Load auth config to determine available login methods
    authApi.getAuthConfig()
      .then(setAuthConfig)
      .catch((err) => {
        console.error('Failed to load auth config:', err);
        // Show both options when fetch fails (avoid hiding Auth0 due to transient errors)
        setAuthConfig({ enable_password_auth: true, enable_oauth_auth: true });
      });
  }, []);

  // Redirect if already authenticated
  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      const params = new URLSearchParams(window.location.search);
      const returnUrl = params.get('returnUrl');
      const target = returnUrl?.startsWith('/') ? decodeURIComponent(returnUrl) : '/';
      router.push(target);
      setLoading(false);
    }
  }, [isAuthenticated, authLoading, router]);

  if (authLoading || isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 dark:border-gray-100 mx-auto"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await authApi.login({ username, password });
      const params = new URLSearchParams(window.location.search);
      const returnUrl = params.get('returnUrl');
      const target = returnUrl?.startsWith('/') ? decodeURIComponent(returnUrl) : '/';
      window.location.href = target;
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Login failed. Please check your credentials.'));
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="flex items-center gap-3 mb-2">
            <Image
              src="/icon.png"
              alt="Tableau AI Demo Logo"
              width={32}
              height={32}
              className="w-8 h-8"
              priority
            />
            <CardTitle>Login</CardTitle>
          </div>
          <CardDescription>Enter your credentials to access the Tableau AI Demo</CardDescription>
        </CardHeader>
        <CardContent>
          {!authConfig && (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 dark:border-gray-100"></div>
            </div>
          )}
          
          {/* Always show password form - admins can always use it, regular users only if enabled */}
          {authConfig && (
            <>
              {!authConfig.enable_password_auth && (
                <Alert className="mb-4">
                  Password authentication is disabled for regular users. Admin accounts can still log in with password.
                </Alert>
              )}
              
              <form onSubmit={handleSubmit} className="space-y-4">
                {error && (
                  <Alert variant="destructive">
                    {error}
                  </Alert>
                )}
                <div className="space-y-2">
                  <Label htmlFor="username">Username</Label>
                  <Input
                    id="username"
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                    autoFocus
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? 'Logging in...' : 'Login'}
                </Button>
              </form>
            </>
          )}
          
          {authConfig?.enable_oauth_auth && (
            <div className="mt-4">
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t border-gray-300 dark:border-gray-700" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-white dark:bg-gray-900 px-2 text-gray-500 dark:text-gray-400">Or</span>
                </div>
              </div>
              <Button
                type="button"
                variant="outline"
                className="w-full mt-4 flex items-center justify-center gap-2"
                onClick={() => {
                  window.location.href = '/api/auth/login';
                }}
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  className="flex-shrink-0"
                >
                  <path
                    d="M21.98 7.448L19.62 0H4.347L2.02 7.448c-1.352 4.312.03 9.206 3.815 12.015L12.007 24l6.157-4.533c3.785-2.81 5.166-7.708 3.815-12.015zM12 13.93c-2.484 0-4.5-2.016-4.5-4.5s2.016-4.5 4.5-4.5 4.5 2.016 4.5 4.5-2.016 4.5-4.5 4.5z"
                    fill="currentColor"
                  />
                </svg>
                Login with Auth0
              </Button>
            </div>
          )}
          
          {authConfig?.enable_password_auth && (
            <div className="mt-4 text-sm text-gray-500 dark:text-gray-400">
              <p>Default admin credentials: admin / admin</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
