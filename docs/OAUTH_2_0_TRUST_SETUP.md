# OAuth 2.0 Trust (Connected App) Setup Guide

This guide explains how to configure and test Tableau Connected Apps OAuth 2.0 Trust authentication. With OAuth 2.0 Trust, an External Authorization Server (EAS) such as Auth0 issues JWTs that Tableau validates; users authenticate via OAuth flow instead of Connected App Direct Trust or PAT.

## Auth Flows

| Flow | Identity Source | Config |
|------|-----------------|--------|
| OAuth 2.0 Trust | `sub` from Auth0 (configurable) | Admin: EAS JWT Sub Claim |
| Connected App (Direct Trust) | `tableau_username` from metadata | Auth0 metadata field |
| Standard | User-provided username/password | UserTableauPassword |
| PAT | User-provided token | User PAT |

## Overview

| Step | Component | Action |
|------|-----------|--------|
| 1 | Tableau Server | Register EAS in Settings > Connected Apps > OAuth 2.0 Trust |
| 2 | IdP (Auth0) | Configure OAuth app and JWT claims for Tableau |
| 3 | App | Add TableauServerConfig with EAS credentials |
| 4 | User | Select "OAuth 2.0 Trust" and click Connect |

---

## 1. Tableau Server Configuration

### Enable Connected Apps (TSM prerequisite)

Before registering an EAS, Connected Apps must be enabled in Tableau Services Manager (TSM). This establishes trust relationships between Tableau Server and external applications.

1. Sign in to **TSM** (Tableau Services Manager) as an admin
2. Go to **Configuration** → **User Identity & Access** → **Connected Apps** (or **Authorization Server** in Tableau 2023.3 and earlier)
3. Check **Enable connected apps**
4. For OAuth 2.0 Trust: select **Allow connected apps (configure at site level) and server-wide OAuth 2.0 trust (configure below)** (or **Enable OAuth access for embedded content** in older versions)
5. Click **Save Pending Changes** → **Apply Changes and Restart**

Without this step, OAuth 2.0 Trust registration in Tableau Server Settings will not work and JWT sign-in will fail with 401001.

### Register the EAS

1. Log into Tableau Server as an admin
2. Go to **Settings** → **Connected Apps** → **OAuth 2.0 Trust**
3. Click **Add**
4. Enter the **Issuer URL** of your IdP (e.g. `https://your-tenant.auth0.com/`)
5. Save

**Note:** For Tableau Cloud, the `aud` claim must be `tableau:<site_luid>`. For Tableau Server, `aud` is simply `"tableau"` (no site LUID). This app targets Tableau Server.

---

## 2. IdP (Auth0) Configuration

### Create an Application

1. In Auth0 Dashboard: **Applications** → **Applications** → **Create Application**
2. Type: **Regular Web Application** (or Machine to Machine if server-side only)
3. Note the **Client ID** and **Client Secret**

### Configure Application Settings

- **Allowed Callback URLs**:
  ```
  https://your-backend.example.com/api/v1/tableau-auth/oauth/callback
  ```
  For local dev: `http://localhost:8000/api/v1/tableau-auth/oauth/callback`

- **Allowed Logout URLs**: Optional

### Configure JWT Claims for Tableau

Tableau expects these claims in the JWT (typically the `id_token`):

| Claim | Description | Example |
|-------|-------------|---------|
| `sub` | User identifier (email or username) | `user@example.com` |
| `aud` | Audience – **must** be `"tableau"` for Tableau Server (case-sensitive) | `tableau` |
| `scp` | Scopes | `["tableau:content:read","tableau:views:embed","tableau:viz_data_service:read"]` – see scope notes below |
| `iss` | Issuer URL | `https://your-tenant.auth0.com/` |
| `exp` | Expiration (Unix timestamp) | `1734123456` |
| `jti` | Unique token ID | `uuid` |

**Scope notes:**
- `tableau:content:read` – Metadata API / REST API authorization
- `tableau:views:embed` – Embed views in web apps
- `tableau:viz_data_service:read` – Query VizQL Data Service (datasource queries)

### Auth0 Action to Add Tableau Claims

Auth0 Actions run globally for all applications. Use `event.client.client_id` to add Tableau claims only when the login is for your Tableau OAuth app, so the `aud` claim does not conflict with other applications.

Create or update an Auth0 **Action** (Login / Post Login):

1. **Actions** → **Flows** → **Login** → **+ Create Action** (or edit existing)
2. Name: "Add Tableau Claims to Token"
3. Add code:

```javascript
exports.onExecutePostLogin = async (event, api) => {
  const namespace = 'https://tableau-ai-demo-api';
  
  // Extract tableau_username from app_metadata or user_metadata
  const tableauUsername =
    event.user.app_metadata?.tableau_username ||
    event.user.user_metadata?.tableau_username;
  
  if (tableauUsername) {
    api.idToken.setCustomClaim(`${namespace}/tableau_username`, tableauUsername);
    api.accessToken.setCustomClaim(`${namespace}/tableau_username`, tableauUsername);
  }

  // OAuth 2.0 Trust claims – only for the Tableau OAuth app
  const TABLEAU_CLIENT_ID = 'YOUR_TABLEAU_OAUTH_APP_CLIENT_ID'; // from Auth0 Applications
  if (event.client?.client_id === TABLEAU_CLIENT_ID) {
    api.idToken.setCustomClaim('aud', 'tableau');
    api.idToken.setCustomClaim('scp', ['tableau:content:read', 'tableau:views:embed', 'tableau:viz_data_service:read']);
    // sub: read from sub_claim param (passed by app in authorize URL). Admin configurable.
    const subClaim = event.transaction?.request?.query?.sub_claim || 'email';
    let subValue = null;
    if (subClaim === 'email') subValue = event.user.email;
    else if (subClaim === 'tableau_username') subValue = event.user.app_metadata?.tableau_username || event.user.user_metadata?.tableau_username;
    else if (subClaim === 'name') subValue = event.user.name;
    else if (subClaim === 'sub') { /* don't override – use Auth0 default */ }
    else subValue = event.user[subClaim] || event.user.user_metadata?.[subClaim] || event.user.app_metadata?.[subClaim];
    if (subValue) api.idToken.setCustomClaim('sub', String(subValue));
  }
};
```

4. Replace `YOUR_TABLEAU_OAUTH_APP_CLIENT_ID` with the Client ID of your Tableau OAuth application (from Auth0 Dashboard → Applications)
5. Add the Action to the Login flow
6. Ensure **OpenID Connect** scopes include `openid`, `profile`, `email` so Auth0 returns an `id_token`

**Note:** The app passes `sub_claim` in the authorize URL. The Action reads it from `event.transaction.request.query.sub_claim`. If Auth0 strips unknown params, the Action falls back to `email`.

### Auth0 Limitation: Cannot Override `aud` or `sub`

Auth0 **does not allow** overriding standard claims (`aud`, `sub`, `iss`, `exp`, etc.) in Actions. `api.idToken.setCustomClaim('aud', 'tableau')` is silently ignored. If you see JWT `aud=8WInog...` (Auth0 client ID) in logs, the Action cannot fix it.

**Workaround: Backend-constructed JWT**

When `EAS_JWT_KEY_PATH` is set, the backend constructs and signs the JWT after Auth0 verifies the user. Tableau must register the *backend* as the EAS (not Auth0):

1. Generate an RSA key: `openssl genrsa -out backend/credentials/eas_jwt_key.pem 2048`
2. Set in `.env`: `EAS_JWT_KEY_PATH=backend/credentials/eas_jwt_key.pem`
3. In Tableau: **Settings** → **Connected Apps** → **OAuth 2.0 Trust** → **Add**
   - **Issuer URL**: `{BACKEND_API_URL}` (e.g. `http://localhost:8000` or `https://your-backend.com`)
4. The backend exposes metadata and JWKS for Tableau to discover and validate signatures (see [EAS metadata discovery](#eas-metadata-discovery) below)

**Note:** Tableau Server must be able to reach `BACKEND_API_URL` to fetch metadata and JWKS. For local dev, use a tunnel (e.g. ngrok) or ensure Tableau can reach your backend.

#### EAS metadata discovery

Tableau fetches authorization server metadata to obtain `jwks_uri` for JWT validation. Two discovery standards exist; **Tableau uses RFC 8414** (`/.well-known/oauth-authorization-server`), so the backend must expose it:

| Endpoint | Standard | Notes |
|----------|----------|-------|
| `/.well-known/oauth-authorization-server` | RFC 8414 (OAuth 2.0 AS Metadata, 2018) | **Required** – Tableau fetches this |
| `/.well-known/openid-configuration` | OIDC Discovery (OpenID Connect) | Optional – some clients use this |
| `/.well-known/jwks.json` | JWKS (RFC 7517) | Required – public keys for JWT validation |

**Why both discovery endpoints?** OIDC Discovery (`openid-configuration`) predates RFC 8414. RFC 8414 generalized that pattern for OAuth 2.0 authorization servers. They return equivalent metadata (`issuer`, `jwks_uri`). The backend exposes both for compatibility; Tableau specifically requires `oauth-authorization-server`. If you see 404 for that path, JWT sign-in will fail with 401.

### Local dev: Expose EAS with ngrok

When Tableau Server is remote (e.g. EC2) and your backend runs locally, Tableau cannot reach `localhost`. Use ngrok to expose your backend:

1. **Install ngrok**: `brew install ngrok` (macOS) or download from [ngrok.com](https://ngrok.com)

2. **Start your backend** on port 8000:
   ```bash
   cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. **Start ngrok** in another terminal:
   ```bash
   ./scripts/ngrok-eas.sh
   # or: ngrok http 8000
   ```
   Copy the HTTPS URL (e.g. `https://abc123.ngrok-free.app`). Free tier URLs change each run; paid plans support static subdomains.

4. **Update `.env`**:
   ```bash
   BACKEND_API_URL=https://abc123.ngrok-free.app
   ```
   Restart the backend so it picks up the new value.

5. **Auth0** – Add the callback URL:
   ```
   https://abc123.ngrok-free.app/api/v1/tableau-auth/oauth/callback
   ```
   (Auth0 Dashboard → Applications → Your Tableau OAuth App → Allowed Callback URLs)

6. **Tableau** – Register the EAS:
   - Settings → Connected Apps → OAuth 2.0 Trust → Add
   - **Issuer URL**: `https://abc123.ngrok-free.app` (no trailing slash)

7. **CORS** – Ensure ngrok URL is allowed. In `.env`:
   ```bash
   CORS_ORIGINS=http://localhost:3000,https://localhost:3000,https://abc123.ngrok-free.app
   ```

**Free tier:** The ngrok URL changes when you restart ngrok. Re-run steps 4–6 with the new URL.

### Alternative: Auth0 Rules (Legacy)

If using Rules instead of Actions, add claims to `idToken` in the same way. Ensure the Rule runs in the Login flow.

---

## 3. Application Configuration

### Environment Variables

In `.env` or deployment config:

```bash
# OAuth callback – must match Auth0 Allowed Callback URLs
BACKEND_API_URL=https://your-backend.example.com

# Frontend URL for redirect after OAuth (success/error)
TABLEAU_OAUTH_FRONTEND_REDIRECT=https://your-frontend.example.com
```

For local dev:

```bash
BACKEND_API_URL=http://localhost:8000
TABLEAU_OAUTH_FRONTEND_REDIRECT=http://localhost:3000
```

### Admin Panel: Create Tableau Config

1. Log in as admin
2. Go to **Admin Console** → **Tableau Configurations**
3. Create or edit a configuration
4. Enable **Allow OAuth 2.0 Trust (EAS-issued JWT)**
5. Fill in:
   - **EAS Issuer URL**: `https://your-tenant.auth0.com/` (trailing slash optional)
   - **EAS Client ID**: Auth0 application Client ID
   - **EAS Client Secret**: Auth0 application Client Secret
   - **EAS JWT Sub Claim**: `email` (default for Tableau OIDC), `tableau_username`, `name`, or `sub` (Auth0 default)
6. **EAS Authorization Endpoint** and **EAS Token Endpoint** are optional – they are auto-discovered from `/.well-known/openid-configuration` if omitted

### Redirect URI in Auth0

The callback URL used by the app is:

```
{BACKEND_API_URL}/api/v1/tableau-auth/oauth/callback
```

Add this exact URL to Auth0 **Allowed Callback URLs**.

---

## 4. Testing the Flow

### Prerequisites

- Migration applied: `alembic upgrade head`
- Redis running (for OAuth state)
- Backend and frontend running

### Test Steps

1. **Configure**: Complete Tableau, Auth0, and App configuration above
2. **Select server**: In the Explorer, choose the Tableau config with OAuth 2.0 Trust enabled
3. **Select auth type**: Choose **OAuth 2.0 Trust** from the auth dropdown
4. **Connect**: Click Connect – you are redirected to Auth0
5. **Sign in**: Sign in at Auth0 (or create account)
6. **Callback**: Auth0 redirects back to the app; the app exchanges the code for tokens, signs in to Tableau with the JWT, and redirects to the frontend with `?tableau_connected=1`
7. **Verify**: You should see "Connected" and be able to use chat, datasources, etc.

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `invalid_state` | Redis unavailable or state expired | Ensure Redis is running; try again within 10 minutes |
| `token_exchange_failed` | Wrong client secret, invalid code | Verify EAS client secret; ensure callback URL matches exactly |
| `tableau_signin_failed` (401001) | JWT rejected by Tableau | See "JWT / 401001" below |
| `auth0_aud_not_tableau` | Auth0 cannot set aud (restricted) | Use backend JWT: set `EAS_JWT_KEY_PATH` and register backend as EAS in Tableau |
| No "OAuth 2.0 Trust" option | Config not set up | Enable `allow_connected_app_oauth` and set EAS fields in Admin |
| Redirect loops | Callback URL mismatch | Align Auth0 callback URL with `BACKEND_API_URL` |

**JWT / 401001 ("Error signing in to Tableau Server")**

Check backend logs for `JWT claims for Tableau:` – the logged values show what Tableau receives.

| Required | Value | Notes |
|----------|-------|-------|
| `aud` | `"tableau"` | Exact string, case-sensitive. Auth0 default is client_id – override in Action |
| `sub` | User identity (configurable) | Admin sets **EAS JWT Sub Claim** (e.g. `email` for OIDC, `tableau_username` for direct mapping). Auth0 default is `google-oauth2|123...` – override in Action |
| `scp` | `["tableau:content:read","tableau:views:embed","tableau:viz_data_service:read"]` | Must be a list, not string |
| `iss` | EAS issuer URL | Must match URL registered in Tableau (Settings > Connected Apps > OAuth 2.0 Trust) |
| `jti` | Unique ID | Auth0 usually adds this |

Also verify:
- **EAS registered in Tableau**: Settings > Connected Apps > OAuth 2.0 Trust – Issuer URL must match JWT `iss`
- **User exists**: `sub` must be a Tableau Server username that exists on the site
- **Clock sync**: Server clocks in UTC; drift can cause validation failure

### Inspecting the JWT

Decode the `id_token` at [jwt.io](https://jwt.io) to confirm:

- `aud` is `"tableau"` (for Tableau Server)
- `scp` includes `tableau:content:read`, `tableau:views:embed`, and `tableau:viz_data_service:read` (for VizQL Data Service querying)
- `iss` matches your EAS issuer URL
- `exp` is in the future

---

## References

- [Tableau Connected Apps](https://help.tableau.com/current/server/en-us/connected_apps.htm)
- [Auth0 Actions](https://auth0.com/docs/customize/actions)
- [Auth0 Custom Claims](https://auth0.com/docs/secure/tokens/json-web-tokens/create-custom-claims)
