/**
 * Auth0 configuration helper for server-side route handlers.
 * Fetches Auth0 configuration from the backend API instead of environment variables.
 */

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

const FETCH_TIMEOUT_MS = 15000; // 15s - backend may be slow to start in Docker

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

  const apiPath = '/api/v1/auth/auth0-config';
  const fetchUrl =
    typeof window === 'undefined' && process.env.BACKEND_API_URL
      ? `${process.env.BACKEND_API_URL}${apiPath}` // Server-side in Docker
      : apiPath; // Client-side or dev - relative path works via rewrites

  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

      const response = await fetch(fetchUrl, {
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`Failed to fetch Auth0 config: ${response.statusText}`);
      }

      const data = await response.json();

      const config: Auth0Config = {
        domain: data.domain || '',
        clientId: data.client_id || '',
        clientSecret: process.env.AUTH0_CLIENT_SECRET || undefined,
        audience: data.audience || undefined,
        issuer: data.issuer || undefined,
        enabled: data.enabled || false,
      };

      cachedConfig = config;
      cacheTimestamp = now;
      return config;
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      const isRetryable =
        (error instanceof Error && (error.name === 'AbortError' || error.name === 'HeadersTimeoutError')) ||
        msg.includes('fetch failed') ||
        msg.includes('timeout');
      if (attempt < 2 && isRetryable) {
        await new Promise((r) => setTimeout(r, 2000));
        continue;
      }
      console.error('Error fetching Auth0 config:', error);
      return { domain: '', clientId: '', enabled: false };
    }
  }

  return { domain: '', clientId: '', enabled: false };
}

/**
 * Invalidate the Auth0 config cache (call after admin updates config).
 */
export function invalidateAuth0ConfigCache(): void {
  cachedConfig = null;
  cacheTimestamp = 0;
}
