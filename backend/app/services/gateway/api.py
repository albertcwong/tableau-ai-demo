"""Gateway API endpoints for unified LLM gateway."""
import json
import logging
from typing import Dict, Any, Optional
import httpx
from fastapi import APIRouter, HTTPException, Header, Query, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.services.gateway.router import resolve_context, get_available_models
from app.services.gateway.auth.direct import DirectAuthenticator
from app.services.gateway.auth.salesforce import SalesforceAuthenticator
from app.services.gateway.auth.vertex import VertexAuthenticator
from app.services.gateway.auth.endor import EndorAuthenticator
from app.services.gateway.translators import get_translator, normalize_response, normalize_stream_chunk
from app.core.cache import check_cache_health
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, ProviderConfig
from app.api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gateway"])


def get_configured_providers(db: Session) -> list[dict[str, str]]:
    """Return providers that have an active ProviderConfig with display names.
    
    Returns:
        List of dicts with 'provider' (normalized name) and 'name' (display name from config)
    """
    configs = db.query(ProviderConfig).filter(
        ProviderConfig.is_active == True
    ).all()
    
    # Group by provider_type, use the first config's name for each provider
    provider_map: dict[str, str] = {}
    for config in configs:
        provider_type_val = getattr(config.provider_type, "value", config.provider_type) if config.provider_type else ""
        # Normalize apple_endor -> apple
        normalized = "apple" if provider_type_val == "apple_endor" else provider_type_val
        if normalized and normalized not in provider_map:
            # Use the config's display name, or fallback to normalized provider name
            provider_map[normalized] = config.name or normalized
    
    # Convert to list of dicts sorted by provider name
    result = [{"provider": p, "name": provider_map[p]} for p in sorted(provider_map.keys())]
    return result


def _format_fetch_error(e: Exception) -> str:
    """Format exception for API response, including HTTP status and body when available."""
    if isinstance(e, httpx.HTTPStatusError):
        r = e.response
        body = (r.text[:500] + "..." if len(r.text) > 500 else r.text) if r.text else ""
        return f"{r.status_code} {r.reason_phrase or ''}: {body}".strip()
    return f"{type(e).__name__}: {e}"


class ChatCompletionRequest(BaseModel):
    """Chat completion request model."""
    model: str = Field(..., description="Model identifier")
    provider: str = Field(..., description="Provider name (e.g., 'openai', 'apple', 'vertex')")
    messages: list[Dict[str, Any]] = Field(..., description="List of messages")
    temperature: Optional[float] = Field(None, ge=0, le=2, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens to generate")
    top_p: Optional[float] = Field(None, ge=0, le=1, description="Nucleus sampling parameter")
    stream: Optional[bool] = Field(False, description="Whether to stream the response")
    functions: Optional[list[Dict[str, Any]]] = Field(None, description="Function definitions")
    function_call: Optional[str | Dict[str, str]] = Field(None, description="Function call mode")
    tools: Optional[list[Dict[str, Any]]] = Field(None, description="Tool definitions (new format)")
    tool_choice: Optional[str | Dict[str, str]] = Field(None, description="Tool choice mode")


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    providers: list[str]
    redis_connected: bool


@router.get("/endor-token")
async def get_endor_token(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Return a fresh A3 token for Endor. Frontend sends this with chat requests when provider=apple."""
    config = db.query(ProviderConfig).filter(
        ProviderConfig.provider_type == "apple_endor",
        ProviderConfig.is_active == True
    ).first()
    if not config or not config.apple_endor_app_id or not config.apple_endor_app_password:
        raise HTTPException(status_code=400, detail="Endor not configured")
    auth = EndorAuthenticator(
        app_id=config.apple_endor_app_id,
        app_password=config.apple_endor_app_password,
        other_app=config.apple_endor_other_app,
        context=config.apple_endor_context,
        one_time_token=config.apple_endor_one_time_token or False,
        db=db
    )
    token = await auth.get_token()
    return {"token": token}


@router.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """Gateway health check endpoint."""
    provider_configs = get_configured_providers(db)
    # Extract provider names for backward compatibility
    providers = [p["provider"] for p in provider_configs]
    redis_connected = check_cache_health()
    
    return HealthResponse(
        status="healthy",
        providers=providers,
        redis_connected=redis_connected
    )


@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_apple_idms_a3_token: Optional[str] = Header(None, alias="X-Apple-IDMS-A3-Token"),
    db: Session = Depends(get_db)
):
    """
    OpenAI-compatible chat completions endpoint.
    
    Routes requests to appropriate provider based on model name.
    """
    try:
        logger.info(f"Gateway received chat completion request: provider={request.provider}, model={request.model}, messages={len(request.messages)}, stream={request.stream}, has_functions={bool(request.functions)}, max_tokens={request.max_tokens}")
        # Resolve provider context
        context = resolve_context(request.model, request.provider)
        logger.info(f"Resolved context: provider={context.provider}, auth_type={context.auth_type}, model_name={context.model_name}, endpoint={context.endpoint}")
        
        # Get authenticator and token
        app_id = None  # For Endor
        if context.auth_type == "direct":
            authenticator = DirectAuthenticator()
            token = await authenticator.get_token(authorization, context, db=db)
        elif context.auth_type == "jwt_oauth":
            authenticator = SalesforceAuthenticator(
                client_id=context.client_id,
                private_key_path=context.private_key_path,
                username=context.username
            )
            token = await authenticator.get_token(authorization, context)
        elif context.auth_type == "service_account":
            authenticator = VertexAuthenticator(
                project_id=context.project_id,
                location=context.location,
                service_account_path=context.credentials_path
            )
            token = await authenticator.get_token(authorization, context)
        elif context.auth_type == "endor_a3":
            endor_config = db.query(ProviderConfig).filter(
                ProviderConfig.provider_type == "apple_endor",
                ProviderConfig.is_active == True
            ).first()
            
            if not endor_config:
                raise HTTPException(
                    status_code=400,
                    detail="Endor provider configuration not found"
                )
            
            authenticator = EndorAuthenticator(
                app_id=endor_config.apple_endor_app_id,
                app_password=endor_config.apple_endor_app_password,
                other_app=endor_config.apple_endor_other_app,
                context=endor_config.apple_endor_context,
                one_time_token=endor_config.apple_endor_one_time_token or False,
                db=db
            )
            # Use optional frontend-passed A3 token, or generate from app_id+app_password
            token = await authenticator.get_token(authorization, context, optional_a3_token=x_apple_idms_a3_token)
            app_id = authenticator.get_app_id()
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported auth type: {context.auth_type}"
            )
        
        # Get translator
        translator = get_translator(context.provider, context)
        
        # Transform request
        request_dict = request.model_dump(exclude_none=True)
        url, payload, headers = translator.transform_request(request_dict, context)
        
        # Add authorization header
        if context.auth_type == "endor_a3":
            # Endor uses custom headers - ensure we have valid values
            app_id_str = str(app_id).strip() if app_id else ""
            token_str = str(token).strip() if token else ""
            if not app_id_str or not token_str:
                raise HTTPException(
                    status_code=500,
                    detail=f"Endor auth failed: missing token or app_id (app_id={'present' if app_id_str else 'missing'}, token={'present' if token_str else 'missing'})"
                )
            headers["X-Apple-Client-App-ID"] = app_id_str
            headers["X-Apple-IDMS-A3-Token"] = token_str
            logger.info(f"Endor request: app_id={app_id_str[:8]}..., token_len={len(token_str)}")
        elif context.auth_type == "direct":
            headers["Authorization"] = f"Bearer {token}"
        else:
            headers["Authorization"] = f"Bearer {token}"
        
        # Make request to provider
        if request.stream:
            # Streaming response
            async def generate_stream():
                async with httpx.AsyncClient(timeout=60.0) as client:
                    async with client.stream(
                        "POST",
                        url,
                        json=payload,
                        headers=headers
                    ) as response:
                        response.raise_for_status()
                        
                        line_count = 0
                        chunk_count = 0
                        logger.info(f"Starting to read stream from {context.provider} provider")
                        async for line in response.aiter_lines():
                            line_count += 1
                            if not line.strip():
                                continue
                            
                            logger.info(f"Gateway received SSE line {line_count}: {line[:200]}")
                            
                            # Handle SSE format
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str.strip() == "[DONE]":
                                    logger.info("Gateway received [DONE] marker")
                                    yield "data: [DONE]\n\n"
                                    break
                                
                                try:
                                    import json
                                    chunk_data = json.loads(data_str)
                                    logger.info(f"Gateway parsed chunk {chunk_count + 1}: {json.dumps(chunk_data)[:300]}")
                                    normalized = normalize_stream_chunk(
                                        chunk_data,
                                        context.provider,
                                        context
                                    )
                                    logger.info(f"Gateway normalized chunk {chunk_count + 1}: {json.dumps(normalized)[:300]}")
                                    chunk_count += 1
                                    yield f"data: {json.dumps(normalized)}\n\n"
                                except Exception as e:
                                    logger.error(f"Error processing stream chunk: {e}", exc_info=True)
                                    continue
                            else:
                                logger.info(f"Gateway non-data line {line_count}: {line[:100]}")
                        
                        logger.info(f"Gateway stream complete: {line_count} lines processed, {chunk_count} chunks yielded")
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream"
            )
        else:
            # Non-streaming response
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                response_data = response.json()
                
                # Normalize response
                normalized = normalize_response(
                    response_data,
                    context.provider,
                    context
                )
                
                return normalized
                
    except ValueError as e:
        logger.error(f"ValueError in chat_completions: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPStatusError as e:
        error_text = e.response.text
        logger.error(f"Provider API error: {e.response.status_code} - {error_text}")
        
        # Check if it's a function calling error
        if "functions is not supported" in error_text.lower() or "function calling" in error_text.lower():
            # Try to parse the error to get model name
            try:
                import json
                error_data = json.loads(error_text)
                model_name = request.model
                error_detail = (
                    f"The model '{model_name}' does not support function calling. "
                    f"Please select a different model that supports function calling. "
                    f"Error: {error_data.get('error', {}).get('message', error_text[:200])}"
                )
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                # Expected errors when parsing error response JSON - use fallback
                logger.debug(f"Could not parse error response JSON: {e}")
                error_detail = (
                    f"The selected model '{request.model}' does not support function calling. "
                    f"Please select a different model. Error: {error_text[:200]}"
                )
            except Exception as e:
                # Log unexpected errors but use fallback
                logger.warning(f"Unexpected error parsing error response: {e}", exc_info=True)
                error_detail = (
                    f"The selected model '{request.model}' does not support function calling. "
                    f"Please select a different model. Error: {error_text[:200]}"
                )
            raise HTTPException(
                status_code=400,
                detail=error_detail
            )
        
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Provider API error: {error_text[:200]}"
        )
    except httpx.RequestError as e:
        logger.error(f"Network error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Network error connecting to provider: {str(e)}"
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Configuration error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal gateway error: {str(e)}"
        )


@router.get("/providers")
async def list_providers(db: Session = Depends(get_db)):
    """List configured providers with display names (excludes providers without active config)."""
    providers = get_configured_providers(db)
    return {"providers": providers}


@router.get("/models")
async def list_models(
    provider: Optional[str] = Query(None, description="Filter by provider name"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_apple_idms_a3_token: Optional[str] = Header(None, alias="X-Apple-IDMS-A3-Token"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List available models, optionally filtered by provider.
    
    Fetches models from provider APIs when possible, falls back to static mapping.
    Uses the user's stored API key from the database (from admin console settings).
    If no provider is specified, fetches from all available providers.
    """
    api_fetch_success = False
    fetch_error = None
    if provider:
        # Normalize provider name for database lookup (apple -> apple_endor)
        provider_db = provider.lower()
        if provider_db == "apple":
            provider_db = "apple_endor"
        
        # Get global API key for this provider from database (admin-configured)
        global_api_key = None
        provider_config = db.query(ProviderConfig).filter(
            ProviderConfig.provider_type == provider_db,
            ProviderConfig.is_active == True
        ).first()
        
        if provider_config and provider_config.api_key:
            global_api_key = provider_config.api_key
            logger.info(f"✓ Using global API key for {provider} from database (config_id={provider_config.id})")
        else:
            logger.warning(f"✗ No API key found in database for {provider}, will try authorization header or settings fallback")
        
        # Fetch models from specific provider's API
        logger.info(f"===== Fetching models for provider: {provider} =====")
        logger.info(f"Global API key from database: {global_api_key is not None}")
        logger.info(f"Authorization header present: {authorization is not None}")
        try:
            # Use global key, or fallback to authorization header
            api_key_to_use = global_api_key if global_api_key else authorization
            models = await fetch_models_from_provider(provider, api_key_to_use, db, x_apple_a3_token=x_apple_idms_a3_token)
            logger.info(f"✓ SUCCESS: Fetched {len(models)} models from {provider} API")
            logger.info(f"  Sample models: {models[:10]}")
            api_fetch_success = True
        except Exception as e:
            fetch_error = _format_fetch_error(e)
            logger.error(f"✗ FAILED: Could not fetch models from {provider} API: {fetch_error}")
            models = get_available_models(provider)
            logger.warning(f"  Falling back to {len(models)} static models for {provider}")
    else:
        # Fetch models from all available providers
        all_models = set()
        provider_configs = get_configured_providers(db)
        logger.info(f"Fetching models from {len(provider_configs)} configured providers: {[p['provider'] for p in provider_configs]}")
        
        api_fetch_success = False
        for prov_config in provider_configs:
            prov = prov_config["provider"]
            # Normalize provider name for database lookup (apple -> apple_endor)
            prov_db = prov.lower()
            if prov_db == "apple":
                prov_db = "apple_endor"
            
            # Get global API key for this provider from database (admin-configured)
            global_api_key = None
            provider_config = db.query(ProviderConfig).filter(
                ProviderConfig.provider_type == prov_db,
                ProviderConfig.is_active == True
            ).first()
            
            if provider_config and provider_config.api_key:
                global_api_key = provider_config.api_key
                logger.info(f"✓ Using global API key for {prov} from database")
            
            try:
                # Use global key, or fallback to authorization header
                api_key_to_use = global_api_key if global_api_key else authorization
                provider_models = await fetch_models_from_provider(prov, api_key_to_use, db, x_apple_a3_token=x_apple_idms_a3_token)
                all_models.update(provider_models)
                logger.info(f"✓ Fetched {len(provider_models)} models from {prov} API: {provider_models[:5]}...")
                api_fetch_success = True
            except Exception as e:
                fetch_error = f"[{prov}] {_format_fetch_error(e)}"
                logger.warning(f"✗ Failed to fetch models from {prov} API: {fetch_error}, using static mapping")
                static_models = get_available_models(prov)
                all_models.update(static_models)
        
        # If we got no models from APIs, fall back to static mapping
        if not all_models:
            logger.warning("No models fetched from APIs, using static mapping")
            all_models = set(get_available_models())
        
        models = sorted(list(all_models))
        logger.info(f"Total models returned: {len(models)} (API fetch success: {api_fetch_success})")
    
    result = {
        "models": models,
        "provider": provider,
        "source": "api" if api_fetch_success else "static",
        "count": len(models)
    }
    if fetch_error:
        result["error"] = fetch_error
    return result


async def fetch_models_from_provider(provider: str, authorization: Optional[str] = None, db: Optional[Session] = None, x_apple_a3_token: Optional[str] = None) -> list[str]:
    """
    Fetch available models from a provider's API.
    
    Args:
        provider: Provider name (e.g., "openai", "anthropic")
        authorization: Optional Authorization header
        
    Returns:
        List of model IDs
        
    Raises:
        ValueError: If API key is missing for providers that require it
        Exception: If API request fails
    """
    if provider == "openai":
        return await fetch_openai_models(authorization)
    elif provider == "anthropic":
        return await fetch_anthropic_models(authorization)
    elif provider == "vertex":
        # Try to fetch from Vertex AI API if credentials are available
        try:
            return await fetch_vertex_models(authorization)
        except Exception as e:
            logger.warning(f"Failed to fetch Vertex models from API: {e}, using static mapping")
            return get_available_models("vertex")
    elif provider == "salesforce":
        # Salesforce models are typically static, return from mapping
        # Could potentially fetch from Salesforce API in the future
        return get_available_models("salesforce")
    elif provider == "apple":
        # Fetch from Endor API - requires provider config in Admin Console
        # Optional: use X-Apple-IDMS-A3-Token from frontend if provided; else generate from app_id+app_password
        logger.info("Fetching models for Apple Endor provider")
        models = await fetch_endor_models(authorization, db, optional_a3_token=x_apple_a3_token)
        if models:
            logger.info(f"Fetched {len(models)} Endor models from API")
            return models
        # Empty response - re-raise so caller uses static fallback and logs correctly
        raise ValueError("Endor API returned no models")
    else:
        # Unknown provider, return from static mapping
        logger.warning(f"Unknown provider {provider}, using static mapping")
        return get_available_models(provider)


async def fetch_openai_models(authorization: Optional[str] = None) -> list[str]:
    """Fetch models from OpenAI API."""
    url = "https://api.openai.com/v1/models"
    headers = {
        "Content-Type": "application/json"
    }
    
    # Use provided authorization or get from settings
    # Handle both "Bearer token" format and plain token
    if authorization:
        if authorization.startswith("Bearer "):
            headers["Authorization"] = authorization
        else:
            headers["Authorization"] = f"Bearer {authorization}"
    elif settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip():
        headers["Authorization"] = f"Bearer {settings.OPENAI_API_KEY}"
    else:
        logger.warning("OpenAI API key not configured - cannot fetch models from API")
        raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY in settings or provide Authorization header.")
    
    logger.info(f"Fetching OpenAI models from {url}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            total_models = len(data.get("data", []))
            logger.info(f"OpenAI API returned {total_models} total models")
            
            # Filter for chat completion models
            # Strategy: Be inclusive - include all models except clearly non-chat ones
            # Only exclude: embeddings, audio, image, deprecated, and legacy completion models
            
            excluded_prefixes = (
                "ada-", "babbage-", "curie-", "davinci-",  # Legacy completion models (not chat)
                "text-ada-", "text-babbage-", "text-curie-", "text-davinci-",  # Legacy text completion
                "embedding-",  # Embedding models
                "ft:",  # Fine-tuned base models (not the fine-tuned model itself)
                "whisper-",  # Audio transcription models
                "tts-",  # Text-to-speech models
                "dall-e-",  # Image generation models
            )
            excluded_suffixes = ("-deprecated",)  # Only exclude explicitly deprecated
            excluded_exact = ("davinci", "curie", "babbage", "ada")  # Legacy base models only
            
            models = []
            excluded_models = []
            included_by_pattern = {"gpt": [], "o1": [], "o3": [], "other": []}
            
            for model in data.get("data", []):
                model_id = model["id"]
                model_object = model.get("object", "")
                
                # Skip excluded prefixes (clearly non-chat models)
                if any(model_id.startswith(prefix) for prefix in excluded_prefixes):
                    excluded_models.append(model_id)
                    continue
                
                # Skip excluded suffixes (deprecated)
                if any(model_id.endswith(suffix) for suffix in excluded_suffixes):
                    excluded_models.append(model_id)
                    continue
                
                # Skip exact matches (legacy base models)
                if model_id.lower() in excluded_exact:
                    excluded_models.append(model_id)
                    continue
                
                # Include the model - be inclusive!
                models.append(model_id)
                
                # Track by pattern for logging
                if model_id.startswith("gpt-"):
                    included_by_pattern["gpt"].append(model_id)
                elif model_id.startswith("o1-"):
                    included_by_pattern["o1"].append(model_id)
                elif model_id.startswith("o3-"):
                    included_by_pattern["o3"].append(model_id)
                else:
                    included_by_pattern["other"].append(model_id)
            
            logger.info(f"Filtered to {len(models)} models from OpenAI API")
            logger.info(f"  GPT models: {len(included_by_pattern['gpt'])}")
            logger.info(f"  O1 models: {len(included_by_pattern['o1'])}")
            logger.info(f"  O3 models: {len(included_by_pattern['o3'])}")
            logger.info(f"  Other models: {len(included_by_pattern['other'])}")
            if included_by_pattern["other"]:
                logger.info(f"  Other models list: {included_by_pattern['other']}")
            logger.debug(f"Excluded {len(excluded_models)} models. Sample: {excluded_models[:10]}")
            
            # Sort and return
            return sorted(models)
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI API returned error {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error fetching OpenAI models: {e}", exc_info=True)
            raise


async def fetch_anthropic_models(authorization: Optional[str] = None) -> list[str]:
    """
    Fetch models from Anthropic API.
    
    Note: Anthropic doesn't have a public models list endpoint, so we return
    known models. If they add one in the future, we can update this to fetch dynamically.
    """
    # Known Anthropic models (as of 2024)
    # These are the models that support the Messages API
    known_models = [
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        "claude-3-5-sonnet-20240620",
        "claude-3-5-haiku-20241022",
        "claude-3-opus",
        "claude-3-sonnet",
        "claude-3-haiku",
        "claude-3-5-sonnet",
        "claude-3-5-haiku",
        "claude-3-7-sonnet-20250219",  # Latest as of Feb 2025
    ]
    return sorted(known_models)


async def fetch_vertex_models(authorization: Optional[str] = None) -> list[str]:
    """
    Fetch models from Vertex AI API.
    """
    known_models = [
        "gemini-pro",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-1.5-pro-latest",
        "gemini-1.5-flash-latest",
    ]
    return sorted(known_models)


async def fetch_endor_models(authorization: Optional[str] = None, db: Optional[Session] = None, optional_a3_token: Optional[str] = None) -> list[str]:
    """
    Fetch models from Endor API.
    
    Args:
        authorization: Not used (Endor uses A3 token from config or optional_a3_token)
        db: Optional database session
        optional_a3_token: Optional A3 token from frontend; if missing, generate from app_id+app_password
        
    Returns:
        List of model IDs
        
    Raises:
        ValueError: If Endor config is missing
        Exception: If API request fails
    """
    # Get database session if not provided
    if not db:
        from app.core.database import SessionLocal
        db = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        # Get Endor config from database (Admin Console)
        provider_config = db.query(ProviderConfig).filter(
            ProviderConfig.provider_type == "apple_endor",
            ProviderConfig.is_active == True
        ).first()
        
        if not provider_config:
            all_endor = db.query(ProviderConfig).filter(
                ProviderConfig.provider_type == "apple_endor"
            ).all()
            inactive = [c for c in all_endor if not c.is_active]
            all_providers = db.query(ProviderConfig.provider_type).distinct().all()
            provider_types = [getattr(p[0], "value", p[0]) for p in all_providers]
            raise ValueError(
                "No active Endor provider config found. "
                f"apple_endor configs: {len(all_endor)} total ({len(inactive)} inactive). "
                f"Provider types in DB: {provider_types or 'none'}. "
                "Add an apple_endor config in Admin Console (Settings → Provider Configs)."
            )
        
        if not provider_config.apple_endor_app_id:
            raise ValueError("Endor App ID not configured")
        
        from app.services.gateway.auth.endor import EndorAuthenticator
        authenticator = EndorAuthenticator(
            app_id=provider_config.apple_endor_app_id,
            app_password=provider_config.apple_endor_app_password,
            other_app=provider_config.apple_endor_other_app,
            context=provider_config.apple_endor_context,
            one_time_token=provider_config.apple_endor_one_time_token or False,
            db=db
        )
        
        a3_token = await authenticator.get_token(optional_a3_token=optional_a3_token)
        app_id = authenticator.get_app_id()
        
        # Validate token and app_id before request
        app_id_str = str(app_id).strip() if app_id else ""
        token_str = str(a3_token).strip() if a3_token else ""
        if not app_id_str or not token_str:
            raise ValueError(
                f"Endor auth incomplete: app_id={'present' if app_id_str else 'missing'}, "
                f"token={'present' if token_str else 'missing'}"
            )
        
        base_url = provider_config.apple_endor_endpoint or "https://api.endor.apple.com"
        url = f"{base_url.rstrip('/')}/v2/models"
        
        headers = {
            "Accept": "application/json",
            "X-Apple-Client-App-ID": app_id_str,
            "X-Apple-IDMS-A3-Token": token_str
        }
        
        logger.info(f"Fetching Endor models from {url} (app_id={app_id_str[:8]}..., token_len={len(token_str)})")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                logger.debug(f"Endor API response structure: {type(data)}, keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
                
                # Parse models from response
                # Endor completions API expects model_id in payload. Prefer model_id over id
                # (id may be UUID; model_id is the actual completions identifier).
                models = []
                models_list = None
                if isinstance(data, dict):
                    if "models" in data:
                        models_list = data["models"]
                    elif "data" in data and isinstance(data["data"], list):
                        models_list = data["data"]
                    elif "model" in data:
                        models_list = [data["model"]] if isinstance(data["model"], (dict, str)) else data["model"]
                elif isinstance(data, list):
                    models_list = data

                if models_list:
                    if models_list and isinstance(models_list[0], dict):
                        logger.info(f"Endor first model payload keys: {list(models_list[0].keys())}")
                    for model in models_list:
                        if isinstance(model, dict):
                            # Prefer model_id (completions field) over id (may be UUID)
                            model_id = model.get("model_id") or model.get("id") or model.get("name")
                            if model_id:
                                models.append(model_id)
                        elif isinstance(model, str):
                            models.append(model)
                
                logger.info(f"Endor API returned {len(models)} models: {models}")
                if not models:
                    logger.warning(f"Endor API response parsed but no models found. Raw response: {data}")
                return sorted(models) if models else []
                
            except httpx.HTTPStatusError as e:
                error_text = e.response.text[:500] if hasattr(e.response, 'text') else str(e)
                logger.error(f"Endor API returned error {e.response.status_code}: {error_text}")
                logger.error(f"Request URL: {url}")
                raise
            except Exception as e:
                logger.error(f"Failed to fetch Endor models: {type(e).__name__}: {e}", exc_info=True)
                raise
    finally:
        if should_close:
            db.close()
