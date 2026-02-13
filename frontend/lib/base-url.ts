/**
 * Get the base URL for the application.
 * Prefers environment variables over request parsing to avoid 0.0.0.0 and port 3002 issues in Docker.
 */
import { NextRequest } from 'next/server';

export function getBaseUrl(req: NextRequest): string {
  // Prefer environment variables (most reliable)
  const appBaseUrl = process.env.APP_BASE_URL || process.env.AUTH0_BASE_URL;
  if (appBaseUrl) {
    return appBaseUrl;
  }

  // Fall back to parsing request headers (Host header is more reliable than req.url)
  const host = req.headers.get('host') || req.headers.get('x-forwarded-host');
  const protocol =
    req.headers.get('x-forwarded-proto') ||
    (req.url.startsWith('https') ? 'https' : 'http');

  if (host) {
    // Normalize hostname: replace 0.0.0.0 with localhost
    let hostname = host.split(':')[0];
    if (hostname === '0.0.0.0') {
      hostname = 'localhost';
    }

    // Get port from host header or use defaults
    const portMatch = host.match(/:(\d+)$/);
    let port = portMatch ? portMatch[1] : null;

    // Use correct external port (3000 for HTTPS, 3001 for HTTP) instead of internal port 3002
    if (!port || port === '3002') {
      port = protocol === 'https' ? '3000' : '3001';
    }

    return `${protocol}://${hostname}:${port}`;
  }

  // Last resort: parse req.url (least reliable)
  const requestUrl = new URL(req.url);
  let hostname = requestUrl.hostname;
  if (hostname === '0.0.0.0') {
    hostname = 'localhost';
  }
  let port = requestUrl.port;
  if (!port || port === '3002') {
    port = requestUrl.protocol === 'https:' ? '3000' : '3001';
  }
  return `${requestUrl.protocol}//${hostname}:${port}`;
}
