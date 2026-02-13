import { Auth0Client } from '@auth0/nextjs-auth0/server';
import { NextRequest, NextResponse } from 'next/server';
import { getAuth0Config } from '@/lib/auth0-config';
import { getBaseUrl } from '@/lib/base-url';

// Cache Auth0Client instances per config (invalidate when config changes)
let auth0Client: Auth0Client | null = null;
let currentConfigHash: string = '';

function getConfigHash(config: { domain: string; clientId: string }): string {
  return `${config.domain}:${config.clientId}`;
}

async function getAuth0Client(): Promise<Auth0Client> {
  const config = await getAuth0Config();
  
  if (!config.enabled || !config.domain || !config.clientId) {
    throw new Error('Auth0 is not configured. Please configure it in the admin console.');
  }
  
  const configHash = getConfigHash(config);
  
  // Create new client if config changed or client doesn't exist
  if (!auth0Client || currentConfigHash !== configHash) {
    // Determine base URL - use environment variable or default to localhost
    // In Docker, this should be set to the external URL (https://localhost:3000)
    let appBaseUrl = process.env.APP_BASE_URL || process.env.AUTH0_BASE_URL;
    if (!appBaseUrl) {
      // Default based on protocol - HTTPS on 3000, HTTP on 3001
      const protocol = process.env.NODE_ENV === 'production' ? 'https' : 'http';
      const port = protocol === 'https' ? '3000' : '3001';
      appBaseUrl = `${protocol}://localhost:${port}`;
    }
    
    auth0Client = new Auth0Client({
      domain: config.domain,
      clientId: config.clientId,
      clientSecret: config.clientSecret, // Optional for SPAs, but needed for server-side token exchange
      appBaseUrl: appBaseUrl,
      secret: process.env.AUTH0_SECRET || '', // Cookie encryption secret (should be in env for security)
    });
    currentConfigHash = configHash;
  }
  
  return auth0Client;
}

export async function GET(req: NextRequest) {
  try {
    const client = await getAuth0Client();
    const url = new URL(req.url);
    
    // Handle logout specially to ensure correct returnTo URL
    if (url.pathname === '/auth/logout') {
      // Get Auth0 config for logout URL
      const config = await getAuth0Config();

      const baseUrl = getBaseUrl(req);
      const loginUrl = `${baseUrl}/login`;
      
      // Clear local session cookie
      const response = NextResponse.redirect(loginUrl);
      response.cookies.delete('appSession');
      
      if (!config.enabled || !config.domain || !config.clientId) {
        // Auth0 not configured, just redirect to login
        return response;
      }
      
      // Construct returnTo URL using the base URL
      // Add logout parameter to prevent auto-login on redirect
      const returnTo = new URL('/login', baseUrl);
      returnTo.searchParams.set('logout', 'true');
      
      // Build Auth0 logout URL with returnTo parameter
      const auth0LogoutUrl = new URL(`https://${config.domain}/v2/logout`);
      auth0LogoutUrl.searchParams.set('client_id', config.clientId);
      auth0LogoutUrl.searchParams.set('returnTo', returnTo.toString());
      
      // Redirect to Auth0 logout
      // If Auth0 rejects it (400 error), the user will see an error page
      // But the session is already cleared locally, so they can navigate to /login manually
      return NextResponse.redirect(auth0LogoutUrl.toString());
    }
    
    // For all other routes, use the standard middleware
    return client.middleware(req);
  } catch (error: any) {
    console.error('Auth0 route handler error:', error);

    const baseUrl = getBaseUrl(req);

    // If Auth0 is not configured, redirect to login page with error
    if (error.message?.includes('not configured')) {
      const loginUrl = new URL('/login', baseUrl);
      loginUrl.searchParams.set('error', 'auth0_not_configured');
      loginUrl.searchParams.set('message', 'Auth0 authentication is not configured. Please configure Auth0 settings in the admin console.');
      return NextResponse.redirect(loginUrl);
    }

    // For other errors, try to redirect to login with error message
    const loginUrl = new URL('/login', baseUrl);
    loginUrl.searchParams.set('error', 'auth0_error');
    loginUrl.searchParams.set('message', error.message || 'Auth0 configuration error');
    return NextResponse.redirect(loginUrl);
  }
}
