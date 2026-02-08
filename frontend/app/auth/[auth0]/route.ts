import { Auth0Client } from '@auth0/nextjs-auth0/server';
import { NextRequest, NextResponse } from 'next/server';
import { getAuth0Config } from '@/lib/auth0-config';
import { cookies } from 'next/headers';
import crypto from 'crypto';

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
  
  // Get AUTH0_SECRET from environment (should be set in .env.local)
  const secret = process.env.AUTH0_SECRET || '';
  if (!secret) {
    throw new Error('AUTH0_SECRET environment variable is not set. Please set it in your .env.local file.');
  }
  
  // Create new client if config changed or client doesn't exist
  if (!auth0Client || currentConfigHash !== configHash) {
    auth0Client = new Auth0Client({
      domain: config.domain,
      clientId: config.clientId,
      clientSecret: config.clientSecret, // Optional for SPAs, but needed for server-side token exchange
      appBaseUrl: process.env.APP_BASE_URL || process.env.AUTH0_BASE_URL || 'http://localhost:3000',
      secret: secret,
    });
    currentConfigHash = configHash;
  }
  
  return auth0Client;
}

export async function GET(req: NextRequest) {
  const pathname = req.nextUrl.pathname;
  const route = pathname.split('/').pop(); // Get the [auth0] parameter
  console.log('[Auth0 Dynamic Route] Request:', pathname, 'route:', route);
  
  try {
    const config = await getAuth0Config();
    console.log('[Auth0 Dynamic Route] Config enabled:', config.enabled, 'domain:', config.domain);
    
    // If Auth0 is not configured, return appropriate responses based on the route
    if (!config.enabled || !config.domain || !config.clientId) {
      console.log('[Auth0 Dynamic Route] Auth0 not configured');
      // For profile endpoint, return 404 (Auth0 SDK expects this when not authenticated)
      if (route === 'profile') {
        console.log('[Auth0 Dynamic Route] Profile route, Auth0 not configured, returning 404');
        return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
      }
      
      // For login endpoint, redirect to login page with message
      if (route === 'login') {
        const loginUrl = new URL('/login', req.url);
        loginUrl.searchParams.set('error', 'auth0_not_configured');
        loginUrl.searchParams.set('message', 'Auth0 authentication is not configured. Please configure Auth0 settings in the admin console.');
        return NextResponse.redirect(loginUrl);
      }
      
      // For other routes, return 404
      return NextResponse.json({ error: 'Auth0 not configured' }, { status: 404 });
    }
    
    const client = await getAuth0Client();
    
    // Handle different routes
    if (route === 'login') {
      // Manual OAuth 2.0 Authorization Code flow with PKCE
      // Generate PKCE code verifier and challenge
      const codeVerifier = crypto.randomBytes(32).toString('base64url');
      const codeChallenge = crypto
        .createHash('sha256')
        .update(codeVerifier)
        .digest('base64url');
      
      // Store code verifier in httpOnly cookie for later use in callback
      const cookieStore = await cookies();
      cookieStore.set('auth0_code_verifier', codeVerifier, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        maxAge: 600, // 10 minutes
        path: '/',
      });
      
      // Build authorization URL
      // Use /api/auth/callback which redirects to /auth/callback
      // This maintains compatibility with Auth0 configuration
      // Get base URL from request to ensure it matches the actual URL being used
      const requestUrl = new URL(req.url);
      const baseUrl = `${requestUrl.protocol}//${requestUrl.host}`;
      const callbackUrl = `${baseUrl}/api/auth/callback`;
      
      const state = crypto.randomBytes(16).toString('base64url');
      
      // Store state in cookie for CSRF protection
      cookieStore.set('auth0_state', state, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        maxAge: 600,
        path: '/',
      });
      
      // Build scope parameter
      // For Custom APIs with Client Grants:
      // - If your API has NO scopes defined: just use OIDC scopes
      // - If your API HAS scopes defined: you must request at least one scope that's authorized in the Client Grant
      // The scopes requested here must match what's enabled in your Client Grant configuration
      let scope = 'openid profile email';
      
      // Note: If your Custom API has scopes defined, uncomment and add them here:
      // Example: scope = 'openid profile email read write';
      // The scopes must match what's enabled in your Client Grant in Auth0 Dashboard
      
      // Log for debugging (remove in production)
      console.log('[Auth0 Login] Callback URL:', callbackUrl);
      console.log('[Auth0 Login] Audience:', config.audience);
      console.log('[Auth0 Login] Scopes:', scope);
      
      const authParams = new URLSearchParams({
        response_type: 'code',
        client_id: config.clientId,
        redirect_uri: callbackUrl,
        scope: scope,
        code_challenge: codeChallenge,
        code_challenge_method: 'S256',
        state: state,
      });
      
      if (config.audience) {
        authParams.append('audience', config.audience);
      }
      
      const authUrl = `https://${config.domain}/authorize?${authParams.toString()}`;
      return NextResponse.redirect(authUrl);
    } else if (route === 'callback') {
      // Handle OAuth callback - exchange authorization code for tokens
      const searchParams = req.nextUrl.searchParams;
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const error = searchParams.get('error');
      
      // Check for errors from Auth0
      if (error) {
        const loginUrl = new URL('/login', req.url);
        loginUrl.searchParams.set('error', 'auth0_error');
        loginUrl.searchParams.set('message', searchParams.get('error_description') || 'Auth0 authentication failed');
        return NextResponse.redirect(loginUrl);
      }
      
      if (!code || !state) {
        const loginUrl = new URL('/login', req.url);
        loginUrl.searchParams.set('error', 'auth0_error');
        loginUrl.searchParams.set('message', 'Missing authorization code or state');
        return NextResponse.redirect(loginUrl);
      }
      
      // Verify state (CSRF protection)
      const cookieStore = await cookies();
      const storedState = cookieStore.get('auth0_state')?.value;
      const codeVerifier = cookieStore.get('auth0_code_verifier')?.value;
      
      if (!storedState || storedState !== state) {
        const loginUrl = new URL('/login', req.url);
        loginUrl.searchParams.set('error', 'auth0_error');
        loginUrl.searchParams.set('message', 'Invalid state parameter');
        return NextResponse.redirect(loginUrl);
      }
      
      if (!codeVerifier) {
        const loginUrl = new URL('/login', req.url);
        loginUrl.searchParams.set('error', 'auth0_error');
        loginUrl.searchParams.set('message', 'Missing code verifier');
        return NextResponse.redirect(loginUrl);
      }
      
      // Exchange authorization code for tokens
      // Use /api/auth/callback which is what Auth0 redirects to
      // Get base URL from request to ensure it matches
      const requestUrl = new URL(req.url);
      const baseUrl = `${requestUrl.protocol}//${requestUrl.host}`;
      const callbackUrl = `${baseUrl}/api/auth/callback`;
      
      try {
        // Build token request body
        const tokenRequestBody: any = {
          grant_type: 'authorization_code',
          client_id: config.clientId,
          code: code,
          redirect_uri: callbackUrl,
          code_verifier: codeVerifier,
        };
        
        // Include client_secret for confidential clients (server-side apps)
        // This is optional when using PKCE but adds extra security
        if (config.clientSecret) {
          tokenRequestBody.client_secret = config.clientSecret;
        }
        
        const tokenResponse = await fetch(`https://${config.domain}/oauth/token`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(tokenRequestBody),
        });
        
        if (!tokenResponse.ok) {
          const errorData = await tokenResponse.json().catch(() => ({}));
          const errorMsg = errorData.error_description || errorData.error || tokenResponse.statusText;
          console.error('Token exchange error:', {
            status: tokenResponse.status,
            statusText: tokenResponse.statusText,
            error: errorData,
            audience: config.audience,
            clientId: config.clientId,
          });
          
          // Provide helpful error message for common issues
          if (errorMsg?.includes('not authorized') || errorMsg?.includes('access resource server')) {
            throw new Error(
              `Token exchange failed: ${errorMsg}\n\n` +
              `Troubleshooting:\n` +
              `1. Go to Auth0 Dashboard → APIs → ${config.audience || 'your API'}\n` +
              `2. Click "Application Access" tab\n` +
              `3. Verify your application (${config.clientId}) is listed and enabled\n` +
              `4. If your API has scopes defined, ensure the requested scopes match what's enabled in the Client Grant\n` +
              `5. Check that your application type is "Regular Web Application" (not "Single Page Application" or "Machine to Machine")`
            );
          }
          
          throw new Error(`Token exchange failed: ${errorMsg}`);
        }
        
        const tokens = await tokenResponse.json();
        
        // Store session using Auth0 SDK's expected format
        // The SDK expects an encrypted session cookie named 'appSession'
        // We'll use the SDK's internal encryption if available, or store manually
        const sessionData = {
          user: tokens.id_token ? JSON.parse(Buffer.from(tokens.id_token.split('.')[1], 'base64').toString()) : {},
          accessToken: tokens.access_token,
          idToken: tokens.id_token,
          refreshToken: tokens.refresh_token,
          expiresAt: Date.now() + (tokens.expires_in * 1000),
        };
        
        console.log('[Auth0 Callback] Token exchange successful, storing session');
        console.log('[Auth0 Callback] Access token length:', tokens.access_token?.length || 0);
        console.log('[Auth0 Callback] Token expires in:', tokens.expires_in, 'seconds');
        
        // Try to use the SDK's session management
        // Note: This is a workaround since handleCallback doesn't work in App Router
        // In a production app, you'd want to use the SDK's proper session encryption
        const sessionCookie = Buffer.from(JSON.stringify(sessionData)).toString('base64');
        cookieStore.set('appSession', sessionCookie, {
          httpOnly: true,
          secure: process.env.NODE_ENV === 'production',
          sameSite: 'lax',
          maxAge: tokens.expires_in || 86400,
          path: '/',
        });
        
        console.log('[Auth0 Callback] Session cookie set, redirecting to home');
        
        // Clean up PKCE cookies
        cookieStore.delete('auth0_code_verifier');
        cookieStore.delete('auth0_state');
        
        // Redirect to home page
        return NextResponse.redirect(new URL('/', req.url));
      } catch (error: any) {
        console.error('Token exchange error:', error);
        const loginUrl = new URL('/login', req.url);
        loginUrl.searchParams.set('error', 'auth0_error');
        loginUrl.searchParams.set('message', error.message || 'Failed to exchange authorization code');
        return NextResponse.redirect(loginUrl);
      }
    } else if (route === 'logout') {
      // Check if there's actually an Auth0 session before trying to logout
      try {
        const cookieStore = await cookies();
        const sessionCookie = cookieStore.get('appSession');
        
        if (sessionCookie?.value) {
          // User has Auth0 session, perform Auth0 logout
          // Clear the session cookie
          cookieStore.delete('appSession');
          
          // Build Auth0 logout URL
          const returnTo = encodeURIComponent(new URL('/login', req.url).toString());
          const logoutUrl = `https://${config.domain}/v2/logout?client_id=${config.clientId}&returnTo=${returnTo}`;
          return NextResponse.redirect(logoutUrl);
        } else {
          // No Auth0 session, just redirect to login
          return NextResponse.redirect(new URL('/login', req.url));
        }
      } catch {
        // Error checking session, just redirect to login
        return NextResponse.redirect(new URL('/login', req.url));
      }
    } else if (route === 'profile') {
      // For profile, check if user is authenticated using our custom session format
      console.log('[Auth0 Dynamic Route] Profile route handler executing');
      try {
        const cookieStore = await cookies();
        const sessionCookie = cookieStore.get('appSession');
        
        console.log('[Auth0 Profile] Session cookie exists:', !!sessionCookie?.value);
        
        if (!sessionCookie?.value) {
          console.log('[Auth0 Profile] No session cookie, returning 404');
          return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
        }
        
        // Decode the session data
        const sessionData = JSON.parse(Buffer.from(sessionCookie.value, 'base64').toString());
        
        console.log('[Auth0 Profile] Session data decoded, user exists:', !!sessionData.user);
        
        // Check if token is expired
        if (sessionData.expiresAt && Date.now() > sessionData.expiresAt) {
          console.log('[Auth0 Profile] Token expired');
          cookieStore.delete('appSession');
          return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
        }
        
        // Return the user data from the session
        if (sessionData.user) {
          console.log('[Auth0 Profile] Returning user data');
          return NextResponse.json(sessionData.user);
        }
        
        console.log('[Auth0 Profile] No user data in session');
        return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
      } catch (error) {
        console.error('[Auth0 Profile] Error reading session:', error);
        return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
      }
    }
    
    // Unknown route
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  } catch (error: any) {
    console.error('Auth0 route handler error:', error);
    
    // For profile endpoint, return 404 (Auth0 SDK expects this when not authenticated)
    const route = req.nextUrl.pathname.split('/').pop();
    if (route === 'profile') {
      return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
    }
    
    // For other errors, redirect to login page with error message
    const loginUrl = new URL('/login', req.url);
    loginUrl.searchParams.set('error', 'auth0_error');
    loginUrl.searchParams.set('message', error.message || 'Auth0 configuration error');
    return NextResponse.redirect(loginUrl);
  }
}
