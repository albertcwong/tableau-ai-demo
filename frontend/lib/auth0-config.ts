/**
 * Auth0 configuration helper for server-side route handlers.
 * Fetches Auth0 configuration from the backend API instead of environment variables.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Auth0Config {
  domain: string;
  clientId: string;
  clientSecret?: string;
  audience?: string;
  issuer?: string;
  enabled: boolean;
}

let cachedConfig: Auth0Config | null = null;
let cacheTimestamp: number = 0;
const CACHE_TTL_MS = 60000; // Cache for 60 seconds

/**
 * Fetch Auth0 configuration from backend API.
 * Uses caching to avoid excessive API calls.
 */
export async function getAuth0Config(): Promise<Auth0Config> {
  const now = Date.now();
  
  // Return cached config if still valid
  if (cachedConfig && (now - cacheTimestamp) < CACHE_TTL_MS) {
    return cachedConfig;
  }
  
  try {
    const response = await fetch(`${API_URL}/api/v1/auth/auth0-config`, {
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    if (!response.ok) {
      throw new Error(`Failed to fetch Auth0 config: ${response.statusText}`);
    }
    
    const data = await response.json();
    
    // For server-side route handlers, we also need client_secret from admin endpoint
    // But we can't access it without authentication, so we'll use env var as fallback
    const config: Auth0Config = {
      domain: data.domain || '',
      clientId: data.client_id || '',
      clientSecret: process.env.AUTH0_CLIENT_SECRET || undefined, // Fallback to env var
      audience: data.audience || undefined,
      issuer: data.issuer || undefined,
      enabled: data.enabled || false,
    };
    
    cachedConfig = config;
    cacheTimestamp = now;
    
    return config;
  } catch (error) {
    console.error('Error fetching Auth0 config:', error);
    
    // Return disabled config on error
    return {
      domain: '',
      clientId: '',
      enabled: false,
    };
  }
}

/**
 * Invalidate the Auth0 config cache (call after admin updates config).
 */
export function invalidateAuth0ConfigCache(): void {
  cachedConfig = null;
  cacheTimestamp = 0;
}
