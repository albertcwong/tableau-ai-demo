"""Gateway API endpoints for unified LLM gateway."""
import logging
from typing import Dict, Any, Optional
import httpx
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.services.gateway.router import resolve_context, get_available_providers, get_available_models
from app.services.gateway.auth.direct import DirectAuthenticator
from app.services.gateway.auth.salesforce import SalesforceAuthenticator
from app.services.gateway.auth.vertex import VertexAuthenticator
from app.services.gateway.translators import get_translator, normalize_response, normalize_stream_chunk
from app.core.cache import check_cache_health
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gateway"])


class ChatCompletionRequest(BaseModel):
    """Chat completion request model."""
    model: str = Field(..., description="Model identifier")
    messages: list[Dict[str, str]] = Field(..., description="List of messages")
    temperature: Optional[float] = Field(None, ge=0, le=2, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens to generate")
    top_p: Optional[float] = Field(None, ge=0, le=1, description="Nucleus sampling parameter")
    stream: Optional[bool] = Field(False, description="Whether to stream the response")
    functions: Optional[list[Dict[str, Any]]] = Field(None, description="Function definitions")
    function_call: Optional[str | Dict[str, str]] = Field(None, description="Function call mode")


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    providers: list[str]
    redis_connected: bool


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Gateway health check endpoint."""
    providers = get_available_providers()
    redis_connected = check_cache_health()
    
    return HealthResponse(
        status="healthy",
        providers=providers,
        redis_connected=redis_connected
    )


@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    """
    OpenAI-compatible chat completions endpoint.
    
    Routes requests to appropriate provider based on model name.
    """
    try:
        logger.debug(f"Received chat completion request: model={request.model}, messages={len(request.messages)}, stream={request.stream}")
        # Resolve provider context
        context = resolve_context(request.model)
        
        # Get authenticator
        if context.auth_type == "direct":
            authenticator = DirectAuthenticator()
            token = await authenticator.get_token(authorization, context)
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
        if context.auth_type == "direct":
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
        logger.error(f"Provider API error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Provider API error: {e.response.text[:200]}"
        )
    except httpx.RequestError as e:
        logger.error(f"Network error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Network error connecting to provider: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal gateway error: {str(e)}"
        )


@router.get("/providers")
async def list_providers():
    """List available providers."""
    providers = get_available_providers()
    return {
        "providers": providers
    }


@router.get("/models")
async def list_models(
    provider: Optional[str] = None,
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    """
    List available models, optionally filtered by provider.
    
    If provider is specified, fetches models from the provider's API.
    Otherwise, returns models from the static mapping.
    """
    if provider:
        # Fetch models from provider's API
        try:
            # Try to fetch from API first, fallback to static mapping
            models = await fetch_models_from_provider(provider, authorization)
            logger.info(f"Fetched {len(models)} models from {provider} API")
        except Exception as e:
            logger.warning(f"Failed to fetch models from {provider} API: {e}, using static mapping")
            # Fallback to static mapping
            models = get_available_models(provider)
    else:
        # Return all models from static mapping
        models = get_available_models(provider)
    
    return {
        "models": models,
        "provider": provider
    }


async def fetch_models_from_provider(provider: str, authorization: Optional[str] = None) -> list[str]:
    """
    Fetch available models from a provider's API.
    
    Args:
        provider: Provider name (e.g., "openai", "anthropic")
        authorization: Optional Authorization header
        
    Returns:
        List of model IDs
    """
    if provider == "openai":
        return await fetch_openai_models(authorization)
    elif provider == "anthropic":
        return await fetch_anthropic_models(authorization)
    elif provider == "vertex":
        # Vertex AI models are typically static, return from mapping
        return get_available_models("vertex")
    elif provider == "salesforce":
        # Salesforce models are typically static, return from mapping
        return get_available_models("salesforce")
    elif provider == "apple":
        # Apple Endor models are typically static, return from mapping
        return get_available_models("apple")
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
    if authorization:
        headers["Authorization"] = authorization
    elif settings.OPENAI_API_KEY:
        headers["Authorization"] = f"Bearer {settings.OPENAI_API_KEY}"
    else:
        raise ValueError("OpenAI API key not configured")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Filter for chat completion models
        # Include all GPT models, o1 models, and other chat-completion capable models
        # Exclude deprecated models and non-chat models (like embeddings, fine-tuning base models)
        excluded_prefixes = ("ada-", "babbage-", "curie-", "davinci-", "text-", "embedding-", "ft:")
        excluded_suffixes = ("-deprecated", "-001", "-002")
        
        models = []
        for model in data.get("data", []):
            model_id = model["id"]
            # Skip deprecated or non-chat models
            if any(model_id.startswith(prefix) for prefix in excluded_prefixes):
                continue
            if any(model_id.endswith(suffix) for suffix in excluded_suffixes):
                continue
            # Include GPT models, o1 models, and other chat models
            if model_id.startswith(("gpt-", "o1-", "o3-")):
                models.append(model_id)
        
        # Sort and return
        return sorted(models)


async def fetch_anthropic_models(authorization: Optional[str] = None) -> list[str]:
    """Fetch models from Anthropic API."""
    # Anthropic doesn't have a public models endpoint, so we return the known models
    # If they add one in the future, we can update this
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
    ]
    return sorted(known_models)
