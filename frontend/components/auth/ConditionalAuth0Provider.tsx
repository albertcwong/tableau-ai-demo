'use client';

import { useEffect, useState, ReactNode } from 'react';
import { Auth0Provider } from '@auth0/nextjs-auth0/client';
import { AuthProvider } from './AuthContext';
import { authApi } from '@/lib/api';

/**
 * Conditionally wraps children with Auth0Provider only if OAuth is enabled.
 * This prevents Auth0 SDK from making unnecessary requests when OAuth is disabled.
 * AuthProvider is always rendered to ensure useAuth hook works.
 */
export function ConditionalAuth0Provider({ children }: { children: ReactNode }) {
  const [oauthEnabled, setOauthEnabled] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if OAuth is enabled
    authApi.getAuthConfig()
      .then(config => {
        setOauthEnabled(config.enable_oauth_auth || false);
        setLoading(false);
      })
      .catch(() => {
        // On error, assume OAuth is disabled
        setOauthEnabled(false);
        setLoading(false);
      });
  }, []);

  // Always render Auth0Provider so useAuth0User hook works (React hooks rules)
  // When OAuth is disabled, AuthProvider will ignore Auth0 results
  return (
    <Auth0Provider>
      <AuthProvider oauthEnabled={oauthEnabled && !loading}>
        {children}
      </AuthProvider>
    </Auth0Provider>
  );
}
