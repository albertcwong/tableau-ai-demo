import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { getAuth0Config } from '@/lib/auth0-config';

export async function GET() {
  try {
    // Check config first
    const config = await getAuth0Config();
    
    // If Auth0 is not configured, return null token (not an error)
    // This allows the frontend to fall back to password auth
    if (!config.enabled || !config.domain || !config.clientId) {
      return NextResponse.json({ token: null, configured: false }, { status: 200 });
    }
    
    // Read the custom session cookie that was set in the callback handler
    const cookieStore = await cookies();
    const allCookies = cookieStore.getAll();
    console.log('[Auth0 Token] All cookies:', allCookies.map(c => c.name));
    const sessionCookie = cookieStore.get('appSession');
    console.log('[Auth0 Token] Session cookie exists:', !!sessionCookie?.value);
    
    if (!sessionCookie?.value) {
      // No Auth0 session - return 200 with null token (not an error)
      // This allows the frontend to fall back to password auth
      return NextResponse.json({ token: null, configured: true }, { status: 200 });
    }
    
    try {
      // Decode the base64 session data
      const sessionData = JSON.parse(Buffer.from(sessionCookie.value, 'base64').toString());
      
      // Check if token is expired
      if (sessionData.expiresAt && Date.now() > sessionData.expiresAt) {
        // Token expired, clear the session
        console.log('[Auth0 Token] Token expired, clearing session');
        cookieStore.delete('appSession');
        return NextResponse.json({ token: null, configured: true }, { status: 200 });
      }
      
      // Return the access token
      if (sessionData.accessToken) {
        console.log('[Auth0 Token] Returning access token (length:', sessionData.accessToken.length, ')');
        return NextResponse.json({ token: sessionData.accessToken });
      }
      
      // No access token in session
      console.log('[Auth0 Token] No access token in session data');
      return NextResponse.json({ token: null, configured: true }, { status: 200 });
    } catch (parseError) {
      // Invalid session cookie format, clear it
      console.error('[Auth0 Token] Failed to parse session cookie:', parseError);
      cookieStore.delete('appSession');
      return NextResponse.json({ token: null, configured: true }, { status: 200 });
    }
  } catch (error: any) {
    // If Auth0 is not configured, return null token (not an error)
    if (error.message?.includes('not configured')) {
      return NextResponse.json({ token: null, configured: false }, { status: 200 });
    }
    
    // For other errors, return 200 with null token (not an error)
    // This allows the frontend to fall back to password auth
    console.error('Error getting Auth0 token:', error);
    return NextResponse.json({ token: null, configured: true }, { status: 200 });
  }
}
