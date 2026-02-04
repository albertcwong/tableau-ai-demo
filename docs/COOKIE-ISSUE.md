# Cookie Issue Summary

## Problem
- Authentication succeeds (200 response)
- But subsequent requests fail (401) because cookies aren't being sent
- Cookies exist in browser but have `SameSite=Lax` (blocks cross-origin) or `SameSite=None` without `Secure` (browsers reject)

## Root Cause
**Mixed Content + Cookie SameSite Restrictions:**
- HTTPS pages can't load HTTP resources (mixed content blocking)
- Cookies with `SameSite=None` require `Secure` flag (HTTPS only)
- Tableau server is HTTP, so we can't use HTTPS locally without mixed content issues

## Solutions

### Solution 1: Configure Tableau Server for HTTPS (Recommended)
Enable HTTPS on your Tableau Server so everything uses HTTPS:
- Cookies can then use `SameSite=None; Secure`
- No mixed content issues
- Proper security

### Solution 2: Configure Tableau Server Cookie Settings
If HTTPS isn't possible, configure Tableau Server to:
- Set cookies with proper SameSite attributes
- Allow cookies for localhost/your domain
- May require server configuration changes

### Solution 3: Use Same Domain (Production)
Host your embedding page on the same domain as Tableau Server:
- Cookies will work with `SameSite=Lax`
- No cross-origin issues
- Best for production deployments

## Current Status
- ✅ JWT token generation works correctly
- ✅ Authentication succeeds (200 response)
- ❌ Session cookies not being sent with subsequent requests
- ❌ View fails to load due to missing session

## Next Steps
1. Check if Tableau Server supports HTTPS
2. If yes, enable HTTPS and use HTTPS URLs
3. If no, configure server cookie settings or use same-domain hosting
