# Single Sign-On (SSO) Architecture

## MVP Demo Approach (Current Implementation)

This document describes a **simplified MVP implementation** for Auth0 SSO integration suitable for demo purposes. The approach prioritizes simplicity and ease of understanding over advanced security features.

### Key MVP Design Decisions

1. **OAuth 2.0** (not 2.1) - Standard authorization code flow with PKCE
2. **Single Token Flow** - Same Auth0 access token used across all services
3. **Pre-registered Clients** - Frontend SPA registered manually in Auth0 dashboard
4. **No Token Exchange** - Services use the same user token directly
5. **Tableau via Connected Apps** - Continues using existing JWT approach (no Auth0 integration)

### Simple Token Flow

```
1. User logs in via Frontend → Auth0
2. Auth0 returns access token (JWT)
3. Frontend stores token, passes to Backend and MCP Server
4. Backend validates token, maps Auth0 user to Tableau credentials
5. MCP Server validates token, calls Backend API with same token
6. Tableau: No changes (Backend uses existing Connected Apps JWT)
```

### Future Enhancements (Post-MVP)

The following features are deferred for future implementation:
- OAuth 2.1 compliance (mandatory PKCE already used)
- Token Exchange (RFC 8693) for better security
- Token Vault for third-party API integration
- CIMD/DCR for dynamic client registration
- Fine-grained scope management
- Direct Tableau Auth0 integration (SAML/OAuth)

---

## Overview

This document outlines the recommended SSO architecture for integrating Auth0 (or similar IdP) across all services:
- Frontend App (Next.js)
- Backend API (FastAPI)
- Tableau Server
- MCP Server

**Important Note on MCP Server Deployment:**

The MCP server can be deployed in two modes with different authentication requirements:

1. **SSE Transport (Web Integration)**: Runs as part of the backend API, accepts HTTP requests with Authorization headers containing backend-issued JWT tokens.

2. **stdio Transport (IDE Integration)**: Runs as a standalone subprocess spawned by IDE tools (Cursor, VS Code), communicates via stdin/stdout. Requires token injection via environment variables since there are no HTTP headers.

See the [MCP Server section](#4-mcp-server) for detailed configuration options for each mode.

## Architecture Diagram (MVP)

```
┌─────────────────┐
│   Auth0 (IdP)   │
│  - User Login   │
│  - JWT Issuance │
└────────┬────────┘
         │
         │ OAuth 2.0 Authorization Code Flow
         │
    ┌────┴────┐
    │Frontend │ (Next.js)
    │  (Web)  │
    └────┬────┘
         │
         │ Pass Auth0 Token (Bearer)
         │
    ┌────┴────┬──────────────┐
    │         │              │
    ▼         ▼              ▼
┌────────┐ ┌──────────┐ ┌──────────┐
│Backend │ │ Tableau  │ │   MCP    │
│  API   │ │  Server  │ │  Server  │
│(FastAPI│ │(Connected│ │(FastMCP) │
│        │ │  Apps)   │ │          │
└────────┘ └──────────┘ └──────────┘
    │                       │
    │                       │
    └───────────────────────┘
     Backend API calls
```

**Token Flow:**
1. Frontend authenticates user with Auth0
2. Frontend receives Auth0 access token (JWT)
3. Frontend passes token to Backend API in Authorization header
4. Frontend passes token to MCP Server (via environment variable for stdio)
5. Backend validates Auth0 token and maps user to Tableau credentials
6. MCP Server validates Auth0 token and calls Backend API with same token
7. Tableau continues using existing Connected Apps JWT (no Auth0 integration)

## Recommended Architecture (MVP)

### Simple Auth0 Integration

**Flow:**
1. User logs in via Auth0 (redirect to Auth0 login page)
2. Auth0 returns access token (JWT) via authorization code flow with PKCE
3. Frontend stores Auth0 token securely
4. Frontend passes Auth0 token to Backend API in Authorization header
5. Backend validates Auth0 token (RS256 signature verification via JWKS)
6. Backend maps Auth0 user to internal User model (auto-provisioning on first login)
7. Backend uses existing Tableau Connected Apps JWT (no Auth0 integration needed)
8. MCP Server validates Auth0 token from environment variable and calls Backend API

**Key Characteristics:**
- Single Auth0 token shared across Frontend, Backend, and MCP Server
- No token exchange - same token used everywhere
- Pre-registered SPA client in Auth0 dashboard
- Tableau continues with existing Connected Apps approach
- Simple user mapping: Auth0 `sub` claim → internal User record

**Pros:**
- Simple to understand and implement
- Centralized authentication
- Industry-standard OAuth 2.0 / OIDC
- Supports multiple identity providers (Google, Microsoft, etc.)
- Built-in MFA support
- Token refresh handling via Auth0 SDK

**Cons:**
- Requires Auth0 subscription
- Token validation complexity (RS256 vs HS256)
- Need to sync users between Auth0 and internal database
- Same token used everywhere (less secure than token exchange)

## Implementation Details

### 1. Frontend App (Next.js)

**Changes Required:**
- Replace username/password login with Auth0 SDK
- Implement Auth0 callback handler
- Store Auth0 tokens securely (httpOnly cookies recommended)
- Add token refresh logic
- Update API client to send Auth0 tokens

**Key Components:**
- `@auth0/nextjs-auth0` SDK
- Auth0 callback route (`/api/auth/callback`)
- Token refresh middleware
- Protected route wrapper

### 2. Backend API (FastAPI)

**Changes Required:**
- Add Auth0 JWT validation middleware
- Map Auth0 users to internal User model
- Sync Auth0 user attributes (email, name, etc.)
- Support both Auth0 tokens and internal tokens (during migration)
- Update `get_current_user` dependency to validate Auth0 tokens

**Key Components:**
- Auth0 JWT verification (using public keys)
- User sync service (Auth0 → Database)
- Token validation middleware
- User mapping logic

**Token Validation:**
```python
# Validate Auth0 JWT token
# 1. Verify signature using Auth0 public keys
# 2. Check expiration
# 3. Validate issuer (iss) and audience (aud)
# 4. Map Auth0 user_id to internal User model
```

### 3. Tableau Server

**Options:**

**Option A: SAML SSO (if Tableau supports)**
- Configure Tableau Server to use Auth0 as SAML IdP
- Users authenticate via Auth0, redirected to Tableau
- Tableau validates SAML assertion

**Option B: Continue with Connected Apps + User Mapping (Current)**
- Keep existing Connected Apps JWT authentication
- Map Auth0 users to Tableau usernames via `UserTableauServerMapping`
- Backend generates Tableau JWT using mapped username
- No changes to Tableau Server configuration

**Recommendation:** Option B (simpler, no Tableau reconfiguration needed)

### 4. MCP Server

The MCP server can be deployed in two modes, each requiring different authentication approaches:

#### Option A: Integrated with Backend API (SSE Transport)

**Use Case:** Web frontend integration via HTTP/SSE

**Changes Required:**
- Accept backend-issued JWT tokens (same as backend API)
- Validate tokens using backend's SECRET_KEY
- Extract user_id from token to identify user context

**Implementation:**
- Add token validation middleware for HTTP requests
- Extract user context from Authorization header
- Pass user context to MCP tools
- Token passed via HTTP headers: `Authorization: Bearer <token>`

**Token Flow:**
```
1. Frontend → Backend API: Authenticate with Auth0 token
2. Backend → Frontend: Return backend-issued JWT token
3. Frontend → MCP Server (SSE): Connect with backend JWT token in header
4. MCP Server validates token using backend SECRET_KEY
5. MCP Server extracts user_id and processes requests
```

#### Option B: Standalone with IDE Tools (stdio Transport) - **Recommended for IDE Integration**

**Use Case:** Direct integration with IDEs like Cursor or VS Code

**How it works:**
- IDE spawns MCP server as subprocess
- Communication via stdin/stdout (no HTTP)
- Runs on-demand when IDE connects
- No network port required

**Authentication Approach:**

Since the MCP server runs as a standalone process without HTTP headers, it uses **local credential storage** with optional SSO token injection:

**Option B1: Direct Auth0 Token Injection (Recommended)**

The IDE can inject Auth0 tokens via environment variables or MCP config:

```json
{
  "mcpServers": {
    "tableau-analyst-agent": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "PYTHONPATH": "/path/to/backend",
        "AUTH0_ACCESS_TOKEN": "<token-from-ide>",
        "AUTH0_DOMAIN": "your-tenant.auth0.com",
        "BACKEND_API_URL": "https://your-api.com",
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

**MCP Server Implementation:**
- Read Auth0 token from environment variable
- Validate token with Auth0 public keys (or validate via backend API)
- Map Auth0 user to internal User model via backend API
- Store user context for tool execution

**Option B2: Backend Token Exchange**

IDE obtains backend token and injects it:

```json
{
  "mcpServers": {
    "tableau-analyst-agent": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "PYTHONPATH": "/path/to/backend",
        "BACKEND_TOKEN": "<backend-jwt-token>",
        "BACKEND_API_URL": "https://your-api.com",
        "BACKEND_SECRET_KEY": "<shared-secret>",
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

**MCP Server Implementation:**
- Read backend token from environment variable
- Validate token using shared SECRET_KEY
- Extract user_id from token
- Query backend API or database for user context

**Option B3: Per-User Credential Storage (Current Approach)**

Users authenticate directly with Tableau via MCP tools:

**Flow:**
1. User opens IDE (Cursor/VS Code)
2. IDE spawns MCP server process
3. User calls `auth_tableau_signin` MCP tool with credentials
4. MCP server stores encrypted credentials locally
5. Subsequent operations use stored credentials

**Pros:**
- No SSO integration needed
- Works offline
- User controls their own credentials

**Cons:**
- Users must manage Tableau credentials separately
- Not integrated with SSO flow
- Credentials stored per-machine

**Recommendation for IDE Integration:**

For IDE tools, **Option B1 (Direct Auth0 Token Injection)** provides the best SSO experience:

1. IDE extension obtains Auth0 token (via OAuth flow or user login)
2. IDE injects token into MCP server environment
3. MCP server validates token and maps to user
4. MCP tools execute with user context
5. Tableau operations use user's mapped Tableau credentials from backend

**Implementation Requirements:**

```python
# In MCP server startup
import os
from app.core.auth import validate_auth0_token, get_user_from_auth0_token

# Read token from environment
auth0_token = os.getenv("AUTH0_ACCESS_TOKEN")
if auth0_token:
    # Validate token
    claims = validate_auth0_token(auth0_token)
    # Map to internal user
    user = get_user_from_auth0_token(claims)
    # Store user context for tools
    set_current_user(user)
```

## Token Flow

### Authentication Flow

```
1. User → Frontend: Navigate to login
2. Frontend → Auth0: Redirect to Auth0 login
3. User → Auth0: Enter credentials
4. Auth0 → Frontend: Redirect with authorization code
5. Frontend → Auth0: Exchange code for tokens (ID token + Access token)
6. Frontend → Backend: Send Auth0 access token
7. Backend → Auth0: Validate token (verify signature, check claims)
8. Backend → Database: Lookup/sync user from Auth0 user_id
9. Backend → Frontend: Return user info + backend session token (optional)
```

### API Request Flow

```
1. Frontend → Backend API: Request with Auth0 token in Authorization header
2. Backend validates Auth0 token
3. Backend maps Auth0 user to internal User model
4. Backend processes request with user context
5. Backend → Tableau: Generate Tableau JWT using mapped username
6. Backend → Frontend: Return response
```

## Database Schema Changes

### User Model Updates

```python
class User(Base):
    # Existing fields...
    
    # Auth0 integration
    auth0_user_id = Column(String(255), unique=True, nullable=True, index=True)
    auth0_email = Column(String(255), nullable=True)
    auth0_name = Column(String(255), nullable=True)
    auth_provider = Column(String(50), nullable=True)  # 'auth0', 'local', 'google', etc.
    last_synced_at = Column(DateTime, nullable=True)
```

### User Sync Strategy

1. **On First Login:**
   - Create user record with Auth0 user_id
   - Sync email, name from Auth0 profile
   - Set default role (USER)

2. **On Subsequent Logins:**
   - Update user attributes if changed in Auth0
   - Update last_synced_at timestamp

3. **User Mapping:**
   - Use `auth0_user_id` as primary identifier
   - Keep `username` for backward compatibility
   - Map Auth0 email to username if needed

## Configuration

### Auth0 Application Setup

1. Create Auth0 Application (Single Page Application)
2. Configure:
   - Allowed Callback URLs: `http://localhost:3000/api/auth/callback, https://yourdomain.com/api/auth/callback`
   - Allowed Logout URLs: `http://localhost:3000, https://yourdomain.com`
   - Allowed Web Origins: `http://localhost:3000, https://yourdomain.com`
   - Token Endpoint Auth Method: `None` (for SPA)

3. Configure API:
   - Identifier: `https://your-api.com`
   - Enable RBAC (if using roles)
   - Add scopes: `read:users`, `read:admin` (optional)

### Environment Variables (MVP)

#### Backend API

```bash
# Auth0 Configuration
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_AUDIENCE=https://tableau-ai-demo-api
AUTH0_ISSUER=https://your-tenant.auth0.com/

# Backend API URL (for MCP Server)
BACKEND_API_URL=http://localhost:8000

# Existing Tableau config (no changes)
TABLEAU_SERVER_URL=https://tableau.example.com
TABLEAU_CLIENT_ID=...
TABLEAU_CLIENT_SECRET=...
```

#### Frontend

```bash
# Auth0 Configuration
AUTH0_SECRET=<32-byte-secret>  # Generate with: openssl rand -hex 32
AUTH0_BASE_URL=http://localhost:3000
AUTH0_ISSUER_BASE_URL=https://your-tenant.auth0.com
AUTH0_CLIENT_ID=<spa-client-id>  # From Auth0 dashboard
AUTH0_AUDIENCE=https://tableau-ai-demo-api
```

**Note:** `AUTH0_CLIENT_SECRET` is not needed for Single Page Applications (SPA).

#### MCP Server (IDE Integration)

**For stdio transport (IDE tools like Cursor):**

The MCP server configuration is set in the IDE's MCP config file (`~/.cursor/mcp-config.json` or VS Code settings). Environment variables are injected by the IDE.

**Option 1: Auth0 Token Injection (Recommended)**

```json
{
  "mcpServers": {
    "tableau-analyst-agent": {
      "command": "/path/to/backend/venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "PYTHONPATH": "/path/to/backend",
        "MCP_TRANSPORT": "stdio",
        "AUTH0_DOMAIN": "your-tenant.auth0.com",
        "AUTH0_AUDIENCE": "https://your-api.com",
        "AUTH0_ACCESS_TOKEN": "${AUTH0_TOKEN}",  // IDE injects token here
        "BACKEND_API_URL": "https://your-api.com",
        "DATABASE_URL": "postgresql://user:pass@host:5432/db"
      }
    }
  }
}
```

**Option 2: Backend Token Injection**

```json
{
  "mcpServers": {
    "tableau-analyst-agent": {
      "command": "/path/to/backend/venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "PYTHONPATH": "/path/to/backend",
        "MCP_TRANSPORT": "stdio",
        "BACKEND_TOKEN": "${BACKEND_JWT_TOKEN}",  // IDE injects backend token
        "BACKEND_API_URL": "https://your-api.com",
        "BACKEND_SECRET_KEY": "your-secret-key",  // Shared secret for validation
        "DATABASE_URL": "postgresql://user:pass@host:5432/db"
      }
    }
  }
}
```

**Option 3: No SSO (Current - Direct Tableau Auth)**

```json
{
  "mcpServers": {
    "tableau-analyst-agent": {
      "command": "/path/to/backend/venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "PYTHONPATH": "/path/to/backend",
        "MCP_TRANSPORT": "stdio",
        "DATABASE_URL": "postgresql://user:pass@host:5432/db",
        "TABLEAU_SERVER_URL": "https://tableau.example.com",
        "TABLEAU_CLIENT_ID": "optional-default",
        "TABLEAU_CLIENT_SECRET": "optional-default"
      }
    }
  }
}
```

**Note:** In Option 3, users authenticate via MCP tools (`auth_tableau_signin`) and credentials are stored locally encrypted.

### IDE Extension Requirements

For SSO integration with IDE tools, the IDE extension (Cursor/VS Code) needs to:

1. **Obtain Auth0 Token:**
   - Implement OAuth 2.0 Authorization Code flow
   - Store token securely (OS keychain/credential store)
   - Refresh token when expired

2. **Inject Token into MCP Server:**
   - Read token from secure storage
   - Inject as environment variable when spawning MCP server process
   - Update token when refreshed

3. **Token Refresh:**
   - Monitor token expiration
   - Refresh via Auth0 token endpoint
   - Restart MCP server with new token (or implement token update mechanism)

**Example IDE Extension Flow:**

```javascript
// Pseudo-code for IDE extension
async function startMCPServer() {
  // Get Auth0 token (from keychain or OAuth flow)
  const auth0Token = await getAuth0Token();
  
  // Spawn MCP server with token in environment
  const mcpProcess = spawn('python', ['-m', 'mcp_server.server'], {
    env: {
      ...process.env,
      AUTH0_ACCESS_TOKEN: auth0Token,
      AUTH0_DOMAIN: 'your-tenant.auth0.com',
      BACKEND_API_URL: 'https://your-api.com'
    }
  });
  
  // Monitor token expiration and refresh
  setInterval(async () => {
    if (await isTokenExpired(auth0Token)) {
      const newToken = await refreshAuth0Token();
      // Update MCP server environment or restart
    }
  }, 60000); // Check every minute
}
```

## Migration Strategy

### Phase 1: Add Auth0 Support (Parallel)
- Implement Auth0 authentication alongside existing system
- Users can choose Auth0 or username/password
- Sync Auth0 users to database

### Phase 2: Migrate Users
- Encourage users to migrate to Auth0
- Provide migration tool/instructions
- Keep username/password as fallback

### Phase 3: Enforce Auth0 (Optional)
- Disable username/password login
- Require all users to use Auth0
- Remove local password storage

## Security Considerations

1. **Token Storage:**
   - Use httpOnly cookies instead of localStorage (more secure)
   - Implement CSRF protection
   - Set secure cookie flags in production

2. **Token Validation:**
   - Always validate token signature
   - Check token expiration
   - Validate issuer and audience
   - Implement token refresh

3. **User Mapping:**
   - Verify Auth0 user_id is unique
   - Handle user deletion in Auth0
   - Sync user attributes securely

4. **Tableau Integration:**
   - Keep Tableau credentials secure
   - Use user mapping table for username translation
   - Rotate Tableau Connected App secrets regularly

## Alternative: Self-Hosted OIDC Provider

If you prefer not to use Auth0, consider:
- **Keycloak** (open-source)
- **Ory Hydra** (open-source)
- **AWS Cognito** (if using AWS)
- **Azure AD** (if using Microsoft ecosystem)

Same architecture applies, just different IdP.

## Implementation Checklist

### Backend
- [ ] Install Auth0 JWT validation library using `uv`: `uv add python-jose[cryptography]` or `uv add PyJWT`
- [ ] Add Auth0 configuration to settings
- [ ] Create Auth0 token validation middleware
- [ ] Update `get_current_user` to support Auth0 tokens
- [ ] Add user sync service (Auth0 → Database)
- [ ] Add `auth0_user_id` column to User model
- [ ] Create migration for user schema changes
- [ ] Add Auth0 user sync endpoint (webhook or scheduled job)

### Frontend
- [ ] Install `@auth0/nextjs-auth0` SDK
- [ ] Configure Auth0 provider
- [ ] Replace login form with Auth0 redirect
- [ ] Implement callback handler
- [ ] Update API client to send Auth0 tokens
- [ ] Add token refresh logic
- [ ] Update AuthContext to use Auth0

### Tableau
- [ ] Keep existing Connected Apps configuration
- [ ] Ensure user mapping table supports Auth0 users
- [ ] Update user mapping UI to show Auth0 email/name

### MCP Server

#### SSE Transport (Web Integration)
- [ ] Add HTTP token validation middleware
- [ ] Extract user context from Authorization header
- [ ] Update tools to use user context
- [ ] Add CORS configuration for frontend access

#### stdio Transport (IDE Integration)
- [ ] Add Auth0 token validation from environment variables
- [ ] Implement user context extraction from Auth0 token
- [ ] Add backend API client for user mapping (Auth0 → internal user)
- [ ] Update MCP server startup to read and validate tokens
- [ ] Add token refresh mechanism (or document IDE extension requirements)
- [ ] Update tools to use user context from environment
- [ ] Document IDE configuration requirements
- [ ] Create example MCP config files for Cursor/VS Code

## Testing

1. **Unit Tests:**
   - Auth0 token validation
   - User sync logic
   - Token refresh
   - MCP server token extraction from environment

2. **Integration Tests:**
   - Full Auth0 login flow
   - API requests with Auth0 tokens
   - User mapping to Tableau
   - MCP server startup with injected tokens
   - MCP tool execution with user context

3. **E2E Tests:**
   - Complete user journey (login → use app → access Tableau)
   - IDE integration: Token injection → MCP server → Tool execution
   - Token refresh flow in IDE context

4. **IDE Integration Tests:**
   - MCP server spawns with environment variables
   - Token validation on startup
   - User context available to tools
   - Tableau operations use mapped credentials
   - Token expiration handling

## Troubleshooting

### Error: "Client is not authorized to access resource server"

This error occurs during the token exchange when your Auth0 application is not properly authorized to access the Custom API (audience).

**For Custom APIs (not Machine to Machine APIs):**

1. **Verify Client Grant Configuration:**
   - Log into Auth0 Dashboard
   - Go to **Applications** → **APIs**
   - Click on your Custom API (matching your audience value, e.g., `https://tableau-ai-demo-api`)
   - Go to the **"Application Access"** tab (NOT "Machine to Machine Applications")
   - Find your application in the list
   - Ensure it's **enabled** (toggle should be ON)
   - Verify the **scopes** enabled in the Client Grant match what you're requesting

2. **Check API Scopes:**
   - In the same API settings, check if your API has scopes defined
   - If your API has **NO scopes defined**: You can request the audience without API scopes (just `openid profile email`)
   - If your API **HAS scopes defined**: You must request at least one scope that's enabled in your Client Grant
   - Update `frontend/app/auth/[auth0]/route.ts` to include the API scopes in the `scope` parameter

3. **Verify Application Type:**
   - Go to **Applications** → Your application
   - Ensure **Application Type** is "Regular Web Application" (NOT "Single Page Application" or "Machine to Machine")
   - Verify **Allowed Callback URLs** includes: `http://localhost:3000/api/auth/callback`
   - Verify **Allowed Logout URLs** includes: `http://localhost:3000/login`

4. **Check Scope Configuration:**
   - The scopes requested in your authorization request must match what's enabled in the Client Grant
   - Example: If your Client Grant has `read` and `write` scopes enabled, request `openid profile email read write`
   - If your API has no scopes, just request `openid profile email`

**Common Issues:**
- Requesting scopes that aren't enabled in the Client Grant
- Application type is wrong (SPA instead of Regular Web Application)
- Client Grant exists but is disabled
- Scopes mismatch between what's requested and what's authorized

### Error: "Invalid state parameter"

This error indicates a CSRF protection failure during the OAuth callback.

**Possible Causes:**
- Cookie not being set/read correctly (check browser settings, HTTPS in production)
- State cookie expired (OAuth flow took longer than 10 minutes)
- Multiple login attempts in parallel

**Solution:**
- Ensure cookies are enabled in the browser
- Check that `sameSite` cookie settings are appropriate for your deployment
- In production, ensure `secure: true` is set for cookies (requires HTTPS)

### Token Exchange Improvements

The current implementation includes the following security enhancements:
- **PKCE (Proof Key for Code Exchange)**: Prevents authorization code interception attacks
- **Client Secret**: Added to token exchange for confidential clients (server-side apps)
- **State Parameter**: CSRF protection for OAuth flow
- **Better Error Messages**: Detailed error descriptions from Auth0 are logged and displayed

## References

- [Auth0 Next.js SDK](https://auth0.com/docs/quickstart/webapp/nextjs)
- [FastAPI Auth0 Integration](https://auth0.com/docs/quickstart/backend/python)
- [OAuth 2.0 / OIDC Specification](https://oauth.net/2/)
- [Tableau SAML Configuration](https://help.tableau.com/current/server/en-us/saml_config.htm)
- [Auth0 Authorization Code Flow](https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow)
- [Auth0 API Authorization](https://auth0.com/docs/get-started/apis/api-authorization)
