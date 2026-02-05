'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { AlertCircle, Server, Settings, RefreshCw } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/auth/AuthContext';

interface TableauConnectionErrorProps {
  error: string;
  onRetry?: () => void;
}

export function TableauConnectionError({ error, onRetry }: TableauConnectionErrorProps) {
  const router = useRouter();
  const { isAdmin } = useAuth();
  
  const isConfigurationError = 
    error.toLowerCase().includes('configuration') ||
    error.toLowerCase().includes('environment variables') ||
    error.toLowerCase().includes('service unavailable') ||
    error.toLowerCase().includes('503');

  return (
    <div className="flex items-center justify-center min-h-[400px] p-6">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-100 dark:bg-red-900/20 rounded-lg">
              <AlertCircle className="h-6 w-6 text-red-600 dark:text-red-400" />
            </div>
            <div>
              <CardTitle>Tableau Server Not Available</CardTitle>
              <CardDescription>
                Unable to connect to Tableau Server
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Connection Error</AlertTitle>
            <AlertDescription className="mt-2">
              {error}
            </AlertDescription>
          </Alert>

          {isConfigurationError && (
            <div className="space-y-3">
              <div className="flex items-start gap-3 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                <Server className="h-5 w-5 text-blue-600 dark:text-blue-400 mt-0.5" />
                <div className="flex-1">
                  <h3 className="font-semibold text-blue-900 dark:text-blue-100 mb-1">
                    Tableau Server Configuration Required
                  </h3>
                  <p className="text-sm text-blue-700 dark:text-blue-300">
                    {isAdmin ? (
                      <>
                        As an administrator, you can configure Tableau server connections in the{' '}
                        <strong>Admin Console</strong>. Once configured, users will be able to connect to specific
                        Tableau server/site combinations.
                      </>
                    ) : (
                      <>
                        Please contact your administrator to configure Tableau server connections.
                        Once configured, you'll be able to browse Tableau objects and interact with AI agents.
                      </>
                    )}
                  </p>
                </div>
              </div>

              {isAdmin && (
                <div className="flex gap-2">
                  <Button
                    onClick={() => router.push('/admin')}
                    className="flex items-center gap-2"
                  >
                    <Settings className="h-4 w-4" />
                    Configure Tableau Server
                  </Button>
                  {onRetry && (
                    <Button
                      variant="outline"
                      onClick={onRetry}
                      className="flex items-center gap-2"
                    >
                      <RefreshCw className="h-4 w-4" />
                      Retry Connection
                    </Button>
                  )}
                </div>
              )}
            </div>
          )}

          {!isConfigurationError && (
            <div className="space-y-3">
              <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
                <h3 className="font-semibold text-yellow-900 dark:text-yellow-100 mb-2">
                  Possible Causes
                </h3>
                <ul className="list-disc list-inside space-y-1 text-sm text-yellow-700 dark:text-yellow-300">
                  <li>Tableau server is temporarily unavailable</li>
                  <li>Network connectivity issues</li>
                  <li>Authentication credentials have expired</li>
                  <li>Server URL or site ID may be incorrect</li>
                </ul>
              </div>

              <div className="flex gap-2">
                {onRetry && (
                  <Button
                    onClick={onRetry}
                    className="flex items-center gap-2"
                  >
                    <RefreshCw className="h-4 w-4" />
                    Retry Connection
                  </Button>
                )}
                {isAdmin && (
                  <Button
                    variant="outline"
                    onClick={() => router.push('/admin')}
                    className="flex items-center gap-2"
                  >
                    <Settings className="h-4 w-4" />
                    Check Configuration
                  </Button>
                )}
              </div>
            </div>
          )}

          <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
            <p className="text-xs text-gray-500 dark:text-gray-400">
              <strong>Note:</strong> Tableau connection is optional. You can still use the AI agents
              for general queries and analysis without a Tableau connection.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
