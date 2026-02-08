import { Auth0Client } from '@auth0/nextjs-auth0/server';
import { NextRequest, NextResponse } from 'next/server';
import { getAuth0Config } from '@/lib/auth0-config';

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
    auth0Client = new Auth0Client({
      domain: config.domain,
      clientId: config.clientId,
      clientSecret: config.clientSecret, // Optional for SPAs, but needed for server-side token exchange
      appBaseUrl: process.env.APP_BASE_URL || process.env.AUTH0_BASE_URL || 'http://localhost:3000',
      secret: process.env.AUTH0_SECRET || '', // Cookie encryption secret (should be in env for security)
    });
    currentConfigHash = configHash;
  }
  
  return auth0Client;
}

export async function GET(req: NextRequest) {
  try {
    const client = await getAuth0Client();
    
    // The middleware method internally calls authClient.handler which routes
    // requests to the appropriate Auth0 endpoint (login, logout, callback, profile, etc.)
    // based on the path. This works for the dynamic [auth0] route.
    return client.middleware(req);
  } catch (error: any) {
    console.error('Auth0 route handler error:', error);
    
    // If Auth0 is not configured, redirect to login page with error
    if (error.message?.includes('not configured')) {
      const loginUrl = new URL('/login', req.url);
      loginUrl.searchParams.set('error', 'auth0_not_configured');
      loginUrl.searchParams.set('message', 'Auth0 authentication is not configured. Please configure Auth0 settings in the admin console.');
      return NextResponse.redirect(loginUrl);
    }
    
    // For other errors, try to redirect to login with error message
    const loginUrl = new URL('/login', req.url);
    loginUrl.searchParams.set('error', 'auth0_error');
    loginUrl.searchParams.set('message', error.message || 'Auth0 configuration error');
    return NextResponse.redirect(loginUrl);
  }
}
