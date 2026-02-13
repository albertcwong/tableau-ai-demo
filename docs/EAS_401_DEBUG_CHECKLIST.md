# EAS JWT 401 Debug Checklist

When Tableau returns 401 on JWT sign-in, verify each item below.

## Resolved: 404 on metadata discovery

**Symptom:** ngrok shows `GET .well-known/oauth-authorization-server` → 404. JWT sign-in fails with 401.

**Cause:** Tableau uses **RFC 8414** OAuth 2.0 Authorization Server Metadata (`/.well-known/oauth-authorization-server`), not OIDC Discovery (`/.well-known/openid-configuration`). Both standards exist; OIDC came first, RFC 8414 (2018) generalized it for OAuth 2.0. Tableau expects the RFC 8414 endpoint.

**Fix:** Expose `/.well-known/oauth-authorization-server` returning `{"issuer":"...","jwks_uri":".../.well-known/jwks.json"}`. The backend exposes both discovery endpoints for compatibility.

## 1. EAS registration in Tableau

**Tableau must register your backend as EAS, not Auth0.** The issuer in the JWT is `BACKEND_API_URL` (your ngrok URL). Tableau fetches metadata from that URL.

- [ ] TSM: Connected Apps enabled (User Identity & Access → Connected Apps)
- [ ] Tableau Settings → Connected Apps → OAuth 2.0 Trust: Issuer URL = `BACKEND_API_URL` exactly (e.g. `https://xxx.ngrok-free.app` – no trailing slash)
- [ ] If site-level EAS (2024.2+): `aud` must be `tableau:<site_luid>`. Set `EAS_JWT_AUD=tableau:<site_luid>` in .env

## 2. Metadata reachability from Tableau Server

Tableau fetches **RFC 8414** `{issuer}/.well-known/oauth-authorization-server` (not OIDC discovery). It then fetches `jwks_uri` for JWT validation. Tableau Server must reach your backend.

- [ ] `curl -s https://YOUR_NGROK_URL/.well-known/oauth-authorization-server` returns JSON with `issuer` and `jwks_uri`
- [ ] `curl -s https://YOUR_NGROK_URL/.well-known/jwks.json` returns a `keys` array with RSA key

**Common fix:** If you see 404 for `oauth-authorization-server`, add that endpoint. Tableau uses RFC 8414 OAuth 2.0 AS Metadata, not OIDC Discovery (`openid-configuration`). The backend exposes both for compatibility.

If Tableau Server cannot reach ngrok (firewall, no outbound), use a stable public URL (e.g. deployed backend).

## 3. Issuer match

- [ ] JWT `iss` claim = `BACKEND_API_URL` (no trailing slash)
- [ ] OIDC discovery `issuer` = same
- [ ] Tableau EAS Issuer URL = same

## 4. JWT claims

| Claim | Required | Your value |
|-------|----------|------------|
| `sub` | Tableau username (case-sensitive) | `albertcwong@gmail.com` |
| `aud` | `"tableau"` (server-wide) or `tableau:<site_luid>` (site-level) | |
| `iss` | Issuer URL | `BACKEND_API_URL` |
| `exp` | Not expired, within max validity | Default 10 min |
| `jti` | Unique | UUID |
| `scp` | List type | `["tableau:content:read","tableau:views:embed"]` |

## 5. Site contentUrl

Sign-in payload: `{"credentials":{"jwt":"...","site":{"contentUrl":"..."}}}`

- [ ] Default site: `contentUrl` = `""` or `"default"` (depends on Tableau version)
- [ ] Non-default site: `contentUrl` = site's content URL (e.g. `"my-site"`)

Check Tableau Server config for `site_id` / contentUrl. If wrong, sign-in fails.

## 6. Tableau user exists

- [ ] User `albertcwong@gmail.com` exists on Tableau Server
- [ ] User has access to the target site

## 7. Manual JWT test

```bash
cd /path/to/tableau-ai-demo
./scripts/test_jwt_signin.py
# Copy the curl command from output and run it
```

If curl returns 401, the issue is JWT or Tableau config. If curl succeeds, the issue is in the OAuth flow (e.g. wrong sub from token).

## 8. Tableau error codes (from response headers/body)

Tableau may return `tableau_error_code` header. Common EAS codes:

| Code | Meaning |
|------|---------|
| 10081 | COULD_NOT_RETRIEVE_IDP_METADATA – metadata fetch failed |
| 10082 | AUTHORIZATION_SERVER_ISSUER_NOT_SPECIFIED |
| 10083 | BAD_JWT – kid missing or wrong |
| 10084 | JWT_PARSE_ERROR – aud/sub wrong |
| 10085 | COULD_NOT_FETCH_JWT_KEYS – JWKS not found |
| 10088 | RSA_KEY_SIZE_INVALID – need 2048-bit key |
| 5 | SYSTEM_USER_NOT_FOUND – sub doesn't match Tableau user |
| 16 | LOGIN_FAILED – exp or sub |

## 9. Clock skew

- [ ] JWT `exp` is within Tableau's max validity (default 10 min). Check `vizportal.oauth.external_authorization_server.max_expiration_period_in_minutes`

## 10. Key size

- [ ] RSA key is 2048 bits: `openssl rsa -in credentials/eas_jwt_key.pem -text -noout | grep "Private-Key"`
