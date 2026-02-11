# Site Switching and Standard User/Password Auth Implementation Plan

## Executive Summary

This plan covers:
1. **Standard user/password authentication** – additional auth type alongside Connected App and PAT
2. **Site switching** – for auth types that support it (standard, PAT); Connected Apps are site-specific

## Tableau Auth Type Behavior

| Auth Type         | Site Switching      | Token Behavior                                           |
|-------------------|---------------------|----------------------------------------------------------|
| **Connected App** | Not supported       | Site-specific; JWT tied to site. Must sign in again for different site. |
| **Standard (user/pw)** | Yes (switch-site) | Multiple tokens can be active; sign-in or switch-site both work. |
| **PAT**           | Yes (switch-site)   | Only one active token; sign-in or switch-site invalidates previous. |

**Important:** `switch-site` is **Tableau Server only** – not available on Tableau Cloud.

---

## Phase 1: Standard User/Password Authentication

### 1.1 Backend – TableauClient

Add `sign_in_with_password(username, password)` to `TableauClient`:

```python
# POST /api/api-version/auth/signin
# JSON: { "credentials": { "name": "username", "password": "password", "site": { "contentUrl": "" } } }
```

- Follow same pattern as `sign_in_with_pat`
- Set `_standard_auth = True` (similar to `_pat_auth`) – no JWT refresh; user must reconnect on expiry
- Token typically valid 240 min (Server) / 120 min (Cloud)

### 1.2 Backend – Database

**TableauServerConfig:**
- Add `allow_standard_auth BOOLEAN DEFAULT false`

**UserTableauPassword** (new table, similar to UserTableauPAT):
- `id`, `user_id`, `tableau_server_config_id`, `tableau_username`, `password_encrypted` (use existing PAT encryption)
- Unique constraint on `(user_id, tableau_server_config_id)`

**Migration:** New Alembic migration for both changes.

### 1.3 Backend – API

**tableau_auth.py:**
- Extend `TableauAuthRequest` to accept `auth_type: "standard"` and optional `username`/`password` for first-time connect
- Standard auth flow: read credentials from `UserTableauPassword` (or request body for initial connect), call `sign_in_with_password`, cache token in `get_token_store("standard")`

**user_settings.py:**
- `createTableauPassword`, `deleteTableauPassword`, `listTableauPasswords` (or merge into tableau config CRUD)

**tableau.py (`get_tableau_client`):**
- Add `auth_type == "standard"` branch: check token store, else restore from `UserTableauPassword` and sign in, cache token

### 1.4 Backend – Token Store

- `TableauAuthType.STANDARD` already exists; use `memory_token_store` (same as connected_app).
- Token store factory: `"standard"` → `memory_token_store`.

### 1.5 Frontend

- **TableauConfigOption**: `allow_standard_auth?: boolean`
- **TableauConnectionStatus**: Add auth type `"standard"`; when selected, show username/password form (or prompt to add in Settings)
- **Settings**: User settings for storing Tableau credentials (username/password) per config, similar to PAT management
- Security: Passwords never stored in localStorage; only stored server-side encrypted

---

## Phase 2: Site Switching

### 2.1 TableauClient – `switch_site`

```python
async def switch_site(self, content_url: str) -> Dict[str, Any]:
    """
    Switch to another site. Tableau Server only.
    POST /api/api-version/auth/switchSite
    Body: { "site": { "contentUrl": "content-url" } }
    Header: X-Tableau-Auth: <current-token>
    Returns new token; invalidates old one.
    """
```

- Requires valid `auth_token`
- Update `self.auth_token`, `self.site_id`, `self.site_content_url` from response
- Raise `TableauAuthenticationError` if switch-site fails (e.g. 403, site not found)

### 2.2 TableauClient – List Sites

```python
async def list_sites(self) -> List[Dict[str, Any]]:
    """
    GET /api/api-version/sites (pageSize, pageNumber)
    Returns sites the user has access to.
    """
```

- Requires valid `auth_token`
- Parse response for `id`, `name`, `contentUrl`

### 2.3 Backend – API Endpoints

**tableau_auth.py:**

- `POST /tableau-auth/switch-site`
  - Body: `{ "config_id": int, "auth_type": "standard" | "pat", "site_content_url": str }`
  - Validate: auth_type must be `standard` or `pat` (not `connected_app`)
  - Get current token from token store; if no token, return 401
  - Create TableauClient with cached token, call `switch_site(content_url)`
  - Invalidate old token; store new token with updated site_id/site_content_url
  - Return `TableauAuthResponse` with new site info

- `GET /tableau-auth/sites`
  - Query params: `config_id`, `auth_type`
  - Returns list of sites user can access (for site switcher UI)
  - Use cached client or restore from credentials, then call `list_sites()`

### 2.4 Auth Type Behavior Summary

| Auth Type         | Switch-site endpoint | List sites |
|-------------------|----------------------|------------|
| connected_app      | Not allowed (return 400) | Yes (for informational UI) |
| standard           | Allowed              | Yes |
| pat                | Allowed              | Yes |

**Note:** For `connected_app`, list sites is informational only; the Connected App is tied to a config site. Switching would require a new sign-in with different site.

### 2.5 Token Store Invalidation

When calling `switch_site`:
1. Call `token_store.invalidate(user_id, config_id, auth_type)` before or immediately after `switch_site`
2. Store new `TokenEntry` with updated token and site_id/site_content_url

For PAT and standard: only one token per (user, config, auth_type). Switching replaces it.

### 2.6 Frontend

- **Site selector UI**: Dropdown or list in connection panel showing current site + "Switch site" with list of sites from `GET /tableau-auth/sites`
- **Switch site action**: Call `POST /tableau-auth/switch-site`; on success, update UI and localStorage (`tableau_site_content_url` or similar)
- **Visibility**: Only show site switcher when `auth_type` is `standard` or `pat` and server is Tableau Server (not Cloud). Optionally detect Cloud via config or API response.

---

## Phase 3: Connected App – Site Change (Re-sign-in)

Connected Apps cannot use `switch-site`. To change site for Connected App:

1. Config’s `site_id` is the default site for sign-in
2. Add optional `site_content_url` to `TableauAuthRequest` for initial connect
3. On connect: if user selects a different site, pass it in sign-in; JWT is issued for that site
4. No "switch" – user must disconnect and reconnect with desired site

Alternatively, support per-site configs or a "site override" at connect time.

---

## Implementation Order

| Step | Task | Notes |
|------|------|-------|
| 1 | Add `sign_in_with_password` to TableauClient | Mirror sign_in_with_pat |
| 2 | Add `switch_site` to TableauClient | Tableau Server only |
| 3 | Add `list_sites` to TableauClient | For site switcher UI |
| 4 | DB migration: `allow_standard_auth`, `UserTableauPassword` | |
| 5 | User settings API for standard credentials | Create/delete/list |
| 6 | tableau_auth: standard auth branch | Authenticate, cache token |
| 7 | tableau.py get_tableau_client: standard auth branch | |
| 8 | tableau_auth: POST switch-site, GET sites | |
| 9 | Frontend: standard auth in connection UI | Username/password form |
| 10 | Frontend: site switcher UI | Dropdown, switch-site call |

---

## Security Considerations

- **Passwords**: Encrypt at rest (reuse PAT encryption: `pat_encryption.py` or equivalent)
- **Transit**: Never log passwords; use HTTPS only
- **Session**: Standard tokens expire; no refresh; user must reconnect
- **Storage**: `UserTableauPassword` only; no client-side storage of passwords

---

## Edge Cases

1. **Tableau Cloud**: `switch-site` returns 405 or similar. Detect and show "Site switching not available on Tableau Cloud".
2. **PAT single-token**: Switching invalidates old token; any in-flight requests may fail. Frontend should disable actions while switching.
3. **Concurrent switch**: Use token cache lock (like `token_cache_lock`) for switch-site to avoid races.
4. **Site not found**: Return clear error from switch-site (e.g. 403, site not found).

---

## Testing

- Unit tests: `sign_in_with_password`, `switch_site`, `list_sites` with mocked httpx
- Integration tests: Real Tableau Server (if available) for standard auth and switch-site
- E2E: Connect with standard auth, list sites, switch site, verify API calls use new site
