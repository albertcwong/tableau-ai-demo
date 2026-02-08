import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { getAuth0Config } from '@/lib/auth0-config';

export async function GET() {
  try {
    // Check config first
    const config = await getAuth0Config();
    
    // If Auth0 is not configured, return 404 (Auth0 SDK expects this when not authenticated)
    if (!config.enabled || !config.domain || !config.clientId) {
      return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
    }
    
    // Read the custom session cookie that was set in the callback handler
    const cookieStore = await cookies();
    const sessionCookie = cookieStore.get('appSession');
    
    if (!sessionCookie?.value) {
      // No Auth0 session - return 404 (Auth0 SDK expects this when not authenticated)
      return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
    }
    
    try {
      // Decode the base64 session data
      const sessionData = JSON.parse(Buffer.from(sessionCookie.value, 'base64').toString());
      
      // Check if token is expired
      if (sessionData.expiresAt && Date.now() > sessionData.expiresAt) {
        // Token expired, clear the session
        cookieStore.delete('appSession');
        return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
      }
      
      // Return the user data from the session (Auth0 SDK expects user object)
      if (sessionData.user) {
        return NextResponse.json(sessionData.user);
      }
      
      // No user data in session
      return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
    } catch (parseError) {
      // Invalid session cookie format, clear it
      console.error('[Auth0 Profile] Failed to parse session cookie:', parseError);
      cookieStore.delete('appSession');
      return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
    }
  } catch (error: any) {
    // For any errors, return 404 (Auth0 SDK expects this when not authenticated)
    console.error('[Auth0 Profile] Error:', error);
    return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
  }
}
