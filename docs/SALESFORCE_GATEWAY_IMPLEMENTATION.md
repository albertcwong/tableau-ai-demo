# Salesforce eng-ai-model-gateway Implementation Summary

Reference for implementing the fixes described in [SALESFORCE_GATEWAY_FINDINGS.md](./SALESFORCE_GATEWAY_FINDINGS.md). Apply these changes in the appropriate worktree.

---

## 1. Router: ProviderConfig-Only Mode

**File:** `backend/app/services/gateway/router.py`

**Change:** Resolve Salesforce auth and endpoint from ProviderConfig first, then fall back to env vars.

Replace the salesforce auth block:

```python
# Before:
elif provider_lower == "salesforce":
    auth_type = "direct" if settings.ENG_AI_MODEL_GW_URL else "jwt_oauth"

# After:
elif provider_lower == "salesforce":
    sf_cfg = None
    if db:
        from app.models.user import ProviderConfig
        sf_cfg = db.query(ProviderConfig).filter(
            ProviderConfig.provider_type == "salesforce",
            ProviderConfig.is_active == True,
        ).first()
    base_url = (
        sf_cfg.salesforce_models_api_url if sf_cfg and sf_cfg.salesforce_models_api_url
        else settings.ENG_AI_MODEL_GW_URL or ""
    ).rstrip("/") or None
    api_key = (sf_cfg.api_key if sf_cfg else None) or settings.ENG_AI_MODEL_GW_KEY
    auth_type = "direct" if (base_url and api_key) else "jwt_oauth"
```

In the "Add provider-specific configuration" block for salesforce, replace the direct-auth block:

```python
# Before:
if auth_type == "direct":
    base_url = settings.ENG_AI_MODEL_GW_URL.rstrip("/")
    if db:
        from app.models.user import ProviderConfig
        sf_cfg = db.query(ProviderConfig).filter(...).first()
        if sf_cfg and sf_cfg.salesforce_models_api_url:
            base_url = sf_cfg.salesforce_models_api_url.rstrip("/")
    context.endpoint = base_url

# After:
if auth_type == "direct":
    context.endpoint = base_url
```

---

## 2. Translator: Remove ENG_AI_MODEL_GW_URL Gate

**File:** `backend/app/services/gateway/translators/__init__.py`

**Change (line ~34):**

```python
# Before:
elif provider == "salesforce" and settings.ENG_AI_MODEL_GW_URL and context and context.endpoint:

# After:
elif provider == "salesforce" and context and context.endpoint:
```

---

## 3. fetch_salesforce_models: Guard Empty base_url

**File:** `backend/app/services/gateway/api.py`

**Change:** After resolving `base_url` and `verify_ssl`, add:

```python
# Before:
base_url = (cfg.salesforce_models_api_url if cfg and cfg.salesforce_models_api_url else settings.ENG_AI_MODEL_GW_URL).rstrip("/")
verify_ssl = ...

# After:
base_url = (cfg.salesforce_models_api_url if cfg and cfg.salesforce_models_api_url else settings.ENG_AI_MODEL_GW_URL or "").rstrip("/") or None
verify_ssl = cfg.salesforce_verify_ssl if cfg is not None and cfg.salesforce_verify_ssl is not None else True
if not base_url:
    raise ValueError(
        "Salesforce/eng-ai-model-gateway base URL not configured. "
        "Set salesforce_models_api_url in Admin → Provider Configs (salesforce) or ENG_AI_MODEL_GW_URL in .env."
    )
```

---

## 4. Frontend: Salesforce Form for eng-ai-model-gateway

**File:** `frontend/components/admin/ProviderConfigManagement.tsx`

**Changes:**

- **shouldShowField('api_key'):** Add `'salesforce'` to the list:
  ```typescript
  return ['openai', 'anthropic', 'salesforce'].includes(providerType);
  ```

- **api_key Input:** When provider is salesforce, set `required={false}` and add placeholder/hint. Add hint for salesforce when not editing:
  ```typescript
  placeholder={editingConfigId ? "Leave empty to keep existing key" : formData.provider_type === 'salesforce' ? "eng-ai-model-gateway API key" : ""}
  required={formData.provider_type === 'salesforce' ? false : !editingConfigId}
  ```
  And add hint: `<p>For eng-ai-model-gateway. Or use JWT fields below for Einstein Platform.</p>`

- **Validation (handleCreateConfig):** Replace salesforce validation:
  ```typescript
  } else if (formData.provider_type === 'salesforce') {
    const hasApiKey = !!formData.api_key?.trim();
    const hasJwt = !!(formData.salesforce_client_id?.trim() && formData.salesforce_private_key_path?.trim() && formData.salesforce_username?.trim());
    if (!hasApiKey && !hasJwt) {
      setError('Salesforce requires either API key (eng-ai-model-gateway) or client ID + private key path + username (Einstein JWT)');
      return;
    }
  }
  ```

- **JWT fields:** Remove `required` from client_id, private_key_path, username. Add "(Einstein JWT)" to labels.

---

## Migration

Ensure `bd_add_salesforce_verify_ssl` has been applied: `alembic upgrade head`.
