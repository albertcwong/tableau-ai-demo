'use client';

import React, { createContext, useContext, useEffect, ReactNode, useState } from 'react';
import { useUser as useAuth0User } from '@auth0/nextjs-auth0/client';
import { authApi, UserResponse } from '@/lib/api';

interface AuthContextType {
  user: UserResponse | null;
  loading: boolean;
  login: () => void;
  logout: () => void;
  isAuthenticated: boolean;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children, oauthEnabled }: { children: ReactNode; oauthEnabled: boolean }) {
  // Always call useAuth0User hook unconditionally (required by React hooks rules)
  // Even if OAuth is disabled, the hook must be called in the same order every render
  // ConditionalAuth0Provider ensures Auth0Provider is always rendered, so the hook will work
  const auth0Result = useAuth0User();
  
  // Only use Auth0 values if OAuth is actually enabled
  const auth0User = oauthEnabled ? auth0Result.user : null;
  const auth0Error = oauthEnabled ? auth0Result.error : null;
  const auth0Loading = oauthEnabled ? auth0Result.isLoading : false;
  
  const [backendUser, setBackendUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [authConfig, setAuthConfig] = useState<{ enable_oauth_auth: boolean } | null>(null);

  // Load auth config on mount
  useEffect(() => {
    authApi.getAuthConfig()
      .then(config => {
        setAuthConfig(config);
        
        // Always check for password auth token first (admins can use password auth even when OAuth is enabled)
        const token = localStorage.getItem('auth_token');
        if (token) {
          // Try to fetch user with existing password auth token
          authApi.getCurrentUser()
            .then(user => {
              setBackendUser(user);
              setLoading(false);
            })
            .catch(() => {
              // Token invalid, clear it
              localStorage.removeItem('auth_token');
              setBackendUser(null);
              setLoading(false);
            });
        } else {
          // No password auth token, set loading to false
          // If OAuth is enabled, the second useEffect will handle Auth0 auth
          setLoading(false);
        }
      })
      .catch(() => {
        setLoading(false);
      });
  }, []);

  // Sync Auth0 user with backend user (only if OAuth is enabled)
  useEffect(() => {
    if (!oauthEnabled || !authConfig?.enable_oauth_auth) {
      return;
    }

    const syncUser = async () => {
      if (auth0Loading) {
        setLoading(true);
        return;
      }

      if (auth0Error) {
        console.error('Auth0 error:', auth0Error);
        setBackendUser(null);
        setLoading(false);
        return;
      }

      if (!auth0User) {
        setBackendUser(null);
        setLoading(false);
        return;
      }

      // User is authenticated with Auth0, fetch backend user info
      try {
        const user = await authApi.getCurrentUser();
        setBackendUser(user);
      } catch (error) {
        console.error('Failed to fetch backend user:', error);
        setBackendUser(null);
      } finally {
        setLoading(false);
      }
    };

    syncUser();
  }, [auth0User, auth0Error, auth0Loading, oauthEnabled, authConfig]);

  const login = () => {
    if (oauthEnabled && authConfig?.enable_oauth_auth) {
      // Redirect to Auth0 login
      window.location.href = '/api/auth/login';
    } else {
      // Password auth - handled by login page form
      window.location.href = '/login';
    }
  };

  const logout = async () => {
    // Check if user authenticated via Auth0 or password auth
    const hasPasswordAuthToken = !!localStorage.getItem('auth_token');
    const hasAuth0Session = oauthEnabled && authConfig?.enable_oauth_auth && !!auth0User;
    
    // Clear password auth token if it exists
    if (hasPasswordAuthToken) {
      localStorage.removeItem('auth_token');
    }
    
    // If user has Auth0 session, redirect to Auth0 logout
    if (hasAuth0Session) {
      window.location.href = '/api/auth/logout';
    } else {
      // Password auth only - just redirect to login
      window.location.href = '/login';
    }
  };

  // Determine authentication status
  // backendUser is set when either Auth0 or password auth succeeds
  // So we just need to check if backendUser exists, regardless of OAuth status
  const isAuthenticated = !!backendUser;

  return (
    <AuthContext.Provider
      value={{
        user: backendUser,
        loading,
        login,
        logout,
        isAuthenticated,
        isAdmin: backendUser?.role === 'ADMIN',
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
