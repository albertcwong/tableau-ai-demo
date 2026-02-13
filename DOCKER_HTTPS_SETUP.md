# Docker HTTPS Setup

This guide explains how to set up HTTPS for the frontend when running in Docker.

## Quick Setup

1. **Generate SSL certificates (optional, but recommended):**
   ```bash
   cd frontend
   ./generate-cert.sh
   ```
   Note: If certificates don't exist, the server will automatically use HTTP on port 3001.
   
   **Important**: The certificate includes SANs (Subject Alternative Names) for:
   - `localhost`
   - `*.localhost`
   - `127.0.0.1`
   - `::1`
   
   This ensures the certificate works regardless of how you access the site.

2. **Rebuild and start Docker containers:**
   ```bash
   docker-compose down
   docker-compose build frontend
   docker-compose up -d
   ```
   
   If you get "Cannot find module" errors, make sure to rebuild:
   ```bash
   docker-compose build --no-cache frontend
   ```

3. **Access the frontend:**
   - HTTPS: `https://localhost:3000` (if certificates are provided)
   - HTTP fallback: `http://localhost:3001` (always available)
   
   **Important**: Do NOT use `0.0.0.0` or port `3002` - these are internal Docker addresses.
   Always use `localhost` with ports `3000` (HTTPS) or `3001` (HTTP).

4. **Trust the certificate in your browser:**
   - macOS: Open Keychain Access → Import `frontend/localhost.pem` → Set to "Always Trust"
   - Chrome/Edge: `chrome://settings/certificates` → Authorities → Import `frontend/localhost.pem`
   - Firefox: Preferences → Privacy → Certificates → View Certificates → Authorities → Import

## Troubleshooting Infinite Loop

If the frontend loads in an infinite loop, check:

1. **Backend is accessible:**
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

2. **Check frontend logs:**
   ```bash
   docker-compose logs -f frontend
   ```
   Look for:
   - "Standalone server started on port 3002"
   - "HTTPS server ready" or "HTTPS server skipped"
   - "HTTP server ready"

3. **Check browser console** (F12 → Console tab):
   - Look for CORS errors
   - Check Network tab for failed API requests
   - Look for authentication redirect loops

4. **Common issues:**
   - **CORS errors**: Make sure `CORS_ORIGINS` in backend `.env` includes `https://localhost:3000` and `http://localhost:3001`
   - **Auth redirect loop**: Check Auth0 configuration or disable OAuth if not needed
   - **API connection failure**: Verify `NEXT_PUBLIC_API_URL` is correct (default: `http://localhost:8000`)
   - **Module not found errors**: Rebuild the frontend container: `docker-compose build frontend`

5. **If certificates are missing:**
   - The server will automatically fall back to HTTP on port 3001
   - Access via `http://localhost:3001`
   - Generate certificates with `cd frontend && ./generate-cert.sh` and restart

6. **Debug steps:**
   ```bash
   # Check if containers are running
   docker-compose ps
   
   # Check frontend logs
   docker-compose logs frontend
   
   # Check backend logs
   docker-compose logs backend
   
   # Restart frontend
   docker-compose restart frontend
   ```

## Architecture

The HTTPS setup uses a proxy pattern:
- Next.js standalone server runs on internal port 3002
- `server-https.js` creates HTTPS (3000) and HTTP (3001) servers that proxy to the standalone server
- SSL certificates are mounted as volumes from `frontend/localhost-key.pem` and `frontend/localhost.pem`

## Production Setup

For production, use proper SSL certificates from a CA (Let's Encrypt, etc.) and configure a reverse proxy (nginx, Traefik) to handle SSL termination.
