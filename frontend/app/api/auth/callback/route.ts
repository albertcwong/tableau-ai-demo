import { NextRequest, NextResponse } from 'next/server';
import { getBaseUrl } from '@/lib/base-url';

/**
 * Redirect /api/auth/callback to /auth/callback for Auth0 callback
 * This maintains compatibility with Auth0's redirect_uri configuration
 */
export async function GET(req: NextRequest) {
  const baseUrl = getBaseUrl(req);
  const callbackUrl = new URL('/auth/callback', baseUrl);
  // Preserve all query parameters (code, state, etc.)
  req.nextUrl.searchParams.forEach((value, key) => {
    callbackUrl.searchParams.set(key, value);
  });
  return NextResponse.redirect(callbackUrl);
}
