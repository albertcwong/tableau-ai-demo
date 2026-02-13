import { NextRequest, NextResponse } from 'next/server';
import { getBaseUrl } from '@/lib/base-url';

/**
 * Redirect /api/auth/logout to /auth/logout for Auth0 logout
 * This maintains compatibility with the frontend code that uses /api/auth/logout
 */
export async function GET(req: NextRequest) {
  const baseUrl = getBaseUrl(req);
  const logoutUrl = new URL('/auth/logout', baseUrl);
  // Preserve any query parameters
  req.nextUrl.searchParams.forEach((value, key) => {
    logoutUrl.searchParams.set(key, value);
  });
  return NextResponse.redirect(logoutUrl);
}
