# Model Fetching Update - Dynamic Model Lists

## Summary

Updated the model management system to fetch models from provider APIs instead of relying solely on hardcoded lists.

## Changes Made

### Backend Changes

#### 1. **Updated `/api/v1/gateway/models` Endpoint** (`backend/app/services/gateway/api.py`)
   - **Before:** Returned static model mapping only
   - **After:** Fetches models from provider APIs when possible
   - **Behavior:**
     - If `provider` is specified: Fetches from that provider's API, falls back to static mapping on error
     - If no `provider`: Fetches from all available providers' APIs, combines results
     - Falls back to static mapping if API fetch fails

#### 2. **Enhanced `fetch_models_from_provider` Function**
   - Added `fetch_vertex_models()` function for Vertex AI
   - Improved error handling and fallback logic
   - Better logging for debugging

#### 3. **Created `model_utils.py`** (`backend/app/services/gateway/model_utils.py`)
   - New utility module for model management
   - `get_default_model()` function: Dynamically selects default model
     - Prefers API-fetched models over static ones
     - Prefers newer models (gpt-4o, claude-3-5-sonnet, etc.)
     - Falls back gracefully through multiple levels

#### 4. **Updated Tool-Use Agent Nodes**
   - `get_data.py` and `summarize.py` now use `get_default_model()` instead of hardcoded "gpt-4"
   - Better fallback chain: API fetch → static mapping → hardcoded default

#### 5. **Updated Gateway Health Endpoint** (`backend/app/main.py`)
   - Added optional `include_models` parameter
   - Returns models list when requested (for frontend fallback)

### Frontend Changes

#### 1. **Updated ModelSelector Component** (`frontend/components/chat/ModelSelector.tsx`)
   - **Before:** Hardcoded fallback list of 13 models
   - **After:** 
     - Tries health endpoint with models
     - Falls back to direct models API call
     - Last resort: Minimal fallback (2-3 common models)

#### 2. **Added Health Method to gatewayApi** (`frontend/lib/api.ts`)
   - New `health()` method with optional `includeModels` parameter
   - Allows frontend to get models from health endpoint as fallback

## How It Works

### Model Fetching Flow

```
User Request → /api/v1/gateway/models
    ↓
Check if provider specified
    ↓
Yes → Fetch from provider API → Fallback to static if fails
No  → Fetch from ALL providers → Combine results → Fallback to static if all fail
    ↓
Return models list
```

### Provider-Specific Fetching

1. **OpenAI:** Fetches from `https://api.openai.com/v1/models`
   - Filters for chat-completion models (gpt-*, o1-*, o3-*)
   - Excludes deprecated and non-chat models

2. **Anthropic:** Returns known models (no public API endpoint)
   - Includes latest models: claude-3-7-sonnet-20250219, etc.

3. **Vertex AI:** Returns known models (could be enhanced to fetch from API)
   - gemini-pro, gemini-1.5-pro, gemini-1.5-flash, etc.

4. **Salesforce/Apple:** Uses static mapping (no public API)

### Default Model Selection

The `get_default_model()` function uses this priority:

1. **API-fetched models** (if available)
2. **Static mapping models** (fallback)
3. **Provider-specific defaults:**
   - OpenAI: "gpt-4"
   - Anthropic: "claude-3-5-sonnet"
   - Vertex: "gemini-1.5-pro"
4. **Universal fallback:** "gpt-4"

Within each source, prefers newer models (gpt-4o, claude-3-5-sonnet, etc.)

## Benefits

1. **Always Up-to-Date:** New models from OpenAI appear automatically
2. **No Manual Updates:** Don't need to update code when providers add models
3. **Graceful Degradation:** Falls back to static mapping if API fails
4. **Better Defaults:** Dynamically selects best default model
5. **Provider Flexibility:** Each provider can have different fetching logic

## API Changes

### GET `/api/v1/gateway/models`
- **Query Parameters:**
  - `provider` (optional): Filter by provider name
- **Response:**
  ```json
  {
    "models": ["gpt-4", "gpt-4o", "claude-3-5-sonnet", ...],
    "provider": "openai" // or null if all providers
  }
  ```

### GET `/api/v1/gateway/health`
- **Query Parameters:**
  - `include_models` (optional, default: false): Include models list
- **Response:**
  ```json
  {
    "status": "healthy",
    "service": "gateway",
    "providers": ["openai", "anthropic", ...],
    "model_count": 15,
    "enabled": true,
    "models": [...] // Only if include_models=true
  }
  ```

## Migration Notes

- **Backward Compatible:** All changes are backward compatible
- **Static Mapping Still Used:** Falls back to static mapping if API fails
- **No Breaking Changes:** Existing code continues to work
- **Performance:** API fetching adds ~100-500ms latency (cached where possible)

## Future Enhancements

1. **Caching:** Cache model lists with TTL (e.g., 1 hour)
2. **Vertex AI API:** Fetch from Vertex AI Model Garden API
3. **Model Metadata:** Include model capabilities, pricing, etc.
4. **Provider-Specific Logic:** Each provider can have custom fetching logic
5. **Webhook Updates:** Notify when new models are available

## Testing

To test the new functionality:

```bash
# Fetch all models from APIs
curl http://localhost:8000/api/v1/gateway/models

# Fetch OpenAI models only
curl http://localhost:8000/api/v1/gateway/models?provider=openai

# Health check with models
curl http://localhost:8000/api/v1/gateway/health?include_models=true
```

## Files Modified

### Backend
- `backend/app/services/gateway/api.py` - Updated models endpoint and fetching logic
- `backend/app/services/gateway/model_utils.py` - New utility module
- `backend/app/services/agents/vizql_tool_use/nodes/get_data.py` - Dynamic default model
- `backend/app/services/agents/vizql_tool_use/nodes/summarize.py` - Dynamic default model
- `backend/app/main.py` - Updated health endpoint

### Frontend
- `frontend/lib/api.ts` - Added health method
- `frontend/components/chat/ModelSelector.tsx` - Improved fallback logic
