# Regression Test Plan

**Context:** Multiple changes across gateway (Endor), admin API, models, config, and frontend. Parts are breaking. This plan ensures we catch regressions systematically.

## Scope of Changes

| Area | Files | Risk |
|------|-------|------|
| **Endor** | `gateway/auth/endor.py`, `gateway/translators/endor.py`, `gateway/api.py` | High – new `verify_ssl`, token flow |
| **Admin API** | `api/admin.py` | High – provider config CRUD, `apple_endor_verify_ssl` |
| **Models** | `models/user.py` | Medium – `ProviderConfig.apple_endor_verify_ssl`, `ProviderType` |
| **Config** | `core/config.py` | Low |
| **Frontend** | `ProviderConfigManagement.tsx`, `SettingsManagement.tsx`, `lib/api.ts` | Medium |
| **Migration** | `af_add_apple_endor_verify_ssl.py` | Medium – schema change |

---

## Test Tiers

### Tier 1: Fast Unit (run first, ~30s)

Run: `cd backend && pytest tests/ -v -m "not integration" --ignore=tests/integration`

| Test File | What It Covers | Gaps |
|------------|----------------|------|
| `test_main.py` | Health, CORS | ✓ |
| `test_gateway_router.py` | Model resolution, providers | **Add:** `apple`/`endor` model resolution |
| `test_gateway_auth.py` | Direct, Salesforce, Vertex | **Add:** Endor auth (mocked) |
| `test_gateway_translators.py` | OpenAI, Salesforce, Vertex | **Add:** Endor translator |
| `test_chat_models.py` | Message, Conversation, Session | ✓ |
| `test_database.py` | DB session | ✓ |
| `test_rule_based_router.py` | Intent routing | ✓ |
| `test_prompt_registry.py` | Prompts | ✓ |
| `unit/agents/*` | Agent nodes | ✓ |

**New tests to add:**
- `test_gateway_translators.py`: EndorTranslator – `transform_request`, `normalize_response`, `_messages_to_endor_format`
- `test_gateway_auth.py`: EndorAuthenticator – `get_token` (mock httpx), `verify_ssl` passthrough
- `test_gateway_router.py`: `resolve_context("gemini-2.5-pro")` with provider=apple → `endor_a3`

---

### Tier 2: Integration (requires DB, ~1–2 min)

Run: `cd backend && pytest tests/integration/ -v`

| Test File | What It Covers | Gaps |
|------------|----------------|------|
| `test_chat_api_agents.py` | Chat flow, agents | **Verify:** Endor provider path doesn’t break |
| `test_mcp_flow.py` | MCP tools | ✓ |
| `test_multi_agent_feedback.py` | Feedback | ✓ |

**New tests to add:**
- Admin API: provider config CRUD, including `apple_endor_verify_ssl` create/update/read
- Admin API: `test_provider_config` endpoint – verify `apple_endor` config with `verify_ssl=False` works

---

### Tier 3: Migration & DB

Run before integration tests:

```bash
cd backend && alembic upgrade head
# Verify column exists
psql $DATABASE_URL -c "SELECT column_name FROM information_schema.columns WHERE table_name='provider_configs' AND column_name='apple_endor_verify_ssl';"
```

**Migration verification:**
- `provider_configs.apple_endor_verify_ssl` exists after upgrade
- Downgrade/upgrade cycle works (if using PostgreSQL)

---

### Tier 4: Smoke (manual or scripted)

1. **Backend**
   - `GET /health` → 200
   - `GET /admin/provider-configs` (auth required) → 200
   - `POST /api/chat` with mocked Tableau → 200

2. **Frontend**
   - Admin → Settings → Provider Configs: list, create `apple_endor` config with `verify_ssl` toggle
   - Chat: select Apple provider, send message (may need real Endor creds for full E2E)

3. **Endor direct** (optional, needs corp network)
   - `tmp/test.sh` – A3 token + chat completion against Endor API

---

## Execution Order

```bash
# 1. Unit tests (fast feedback)
cd backend && pytest tests/ -v -m "not integration" --ignore=tests/integration

# 2. Migration
alembic upgrade head

# 3. Integration tests
pytest tests/integration/ -v

# 4. Full suite (CI)
pytest tests/ -v
```

---

## New Test Cases (Priority)

### 1. Endor Translator (unit)

```python
# test_gateway_translators.py
def test_endor_translator_transform_request():
    """Endor request uses model_id, messages in Endor format."""
def test_endor_translator_messages_to_endor_format():
    """user/assistant → role + contents; tool_calls → tool role + tool_result."""
def test_endor_translator_normalize_response():
    """Endor response → OpenAI-compatible choices, usage."""
```

### 2. Endor Auth (unit)

```python
# test_gateway_auth.py
async def test_endor_auth_get_token_mocked():
    """Mock httpx.post to idmsac; verify token returned."""
async def test_endor_auth_verify_ssl_false():
    """verify_ssl=False passed to httpx when set on config."""
async def test_endor_auth_missing_app_id():
    """Raises ValueError when app_id or app_password missing."""
```

### 3. Admin Provider Config (integration)

```python
# test_admin_api.py (new)
def test_provider_config_create_apple_endor_with_verify_ssl(client, db_session):
    """Create apple_endor config with verify_ssl=False."""
def test_provider_config_update_verify_ssl(client, db_session):
    """Update existing config's verify_ssl."""
def test_provider_config_list_includes_verify_ssl(client, db_session):
    """List response includes apple_endor_verify_ssl for apple_endor configs."""
```

### 4. Gateway Router (unit)

```python
# test_gateway_router.py
def test_resolve_context_apple_model():
    """Apple/Endor models resolve to provider=apple, auth_type=endor_a3."""
```

---

## Regression Script

Create `scripts/regression.sh`:

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")/.."

echo "=== Tier 1: Unit tests ==="
cd backend && pytest tests/ -v -m "not integration" --ignore=tests/integration
echo "=== Tier 2: Integration tests ==="
pytest tests/integration/ -v
echo "=== Done ==="
```

---

## Frontend

- No Jest/Vitest in `package.json` – add later if needed
- Manual: Admin → Provider Configs → create/edit `apple_endor`, toggle `verify_ssl`
- `frontend/lib/validation-test.ts` – run if present

---

## Summary

| Action | Effort |
|--------|--------|
| Add Endor translator tests | ~30 min |
| Add Endor auth tests | ~30 min |
| Add admin provider-config tests | ~45 min |
| Add router apple/endor test | ~10 min |
| Run full regression | ~2 min |
| Migration verification | ~5 min |

**Total new test effort:** ~2 hours. Run existing suite first to establish baseline; add new tests incrementally.
