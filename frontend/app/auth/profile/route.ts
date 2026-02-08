import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

export async function GET() {
  console.log('[Auth0 Profile Route] ===== PROFILE ENDPOINT HIT =====');
  
  try {
    // Read the custom session cookie that was set in the callback handler
    const cookieStore = await cookies();
    const allCookies = cookieStore.getAll();
    console.log('[Auth0 Profile Route] All cookies:', allCookies.map(c => c.name));
    
    const sessionCookie = cookieStore.get('appSession');
    console.log('[Auth0 Profile Route] Session cookie exists:', !!sessionCookie?.value, 'length:', sessionCookie?.value?.length);
    
    if (!sessionCookie?.value) {
      // No Auth0 session - return 404 (Auth0 SDK expects this when not authenticated)
      console.log('[Auth0 Profile Route] No session cookie, returning 404');
      return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
    }
    
    try {
      // Decode the base64 session data
      const sessionData = JSON.parse(Buffer.from(sessionCookie.value, 'base64').toString());
      console.log('[Auth0 Profile Route] Session decoded successfully');
      console.log('[Auth0 Profile Route] User exists:', !!sessionData.user);
      console.log('[Auth0 Profile Route] ExpiresAt:', sessionData.expiresAt, 'Now:', Date.now());
      
      // Check if token is expired
      if (sessionData.expiresAt && Date.now() > sessionData.expiresAt) {
        // Token expired, clear the session
        console.log('[Auth0 Profile Route] Token expired, clearing session');
        cookieStore.delete('appSession');
        return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
      }
      
      // Return the user data from the session (Auth0 SDK expects user object)
      if (sessionData.user) {
        console.log('[Auth0 Profile Route] Returning user data successfully');
        return NextResponse.json(sessionData.user);
      }
      
      // No user data in session
      console.log('[Auth0 Profile Route] No user data in session, returning 404');
      return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
    } catch (parseError: any) {
      // Invalid session cookie format, clear it
      console.error('[Auth0 Profile Route] Failed to parse session cookie:', parseError?.message || parseError);
      console.error('[Auth0 Profile Route] Parse error stack:', parseError?.stack);
      cookieStore.delete('appSession');
      return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
    }
  } catch (error: any) {
    // For any errors, return 404 (Auth0 SDK expects this when not authenticated)
    console.error('[Auth0 Profile Route] Unexpected error:', error?.message || error);
    console.error('[Auth0 Profile Route] Error stack:', error?.stack);
    return NextResponse.json({ error: 'Not authenticated' }, { status: 404 });
  }
}
