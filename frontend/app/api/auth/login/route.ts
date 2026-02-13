import { NextRequest, NextResponse } from 'next/server';
import { getBaseUrl } from '@/lib/base-url';

/**
 * Redirect /api/auth/login to /auth/login for Auth0 authentication
 * This maintains compatibility with the frontend code that uses /api/auth/login
 */
export async function GET(req: NextRequest) {
  const baseUrl = getBaseUrl(req);
  const authUrl = new URL('/auth/login', baseUrl);
  // Preserve any query parameters
  req.nextUrl.searchParams.forEach((value, key) => {
    authUrl.searchParams.set(key, value);
  });
  return NextResponse.redirect(authUrl);
}
