"""FastAPI application entry point."""
import logging
import logging.handlers
import time
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings, PROJECT_ROOT
from app.core.database import check_database_health
from app.core.cache import check_cache_health
from app.services.gateway.router import get_available_providers, get_available_models

# Create logs directory if it doesn't exist
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Configure logging with file rotation
LOG_FILE = LOG_DIR / "app.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5  # Keep 5 backup files

# Create formatter
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# File handler with rotation
file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE,
    maxBytes=LOG_MAX_BYTES,
    backupCount=LOG_BACKUP_COUNT,
    encoding="utf-8"
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

# Console handler (for development)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Set specific loggers to DEBUG
logging.getLogger("app.services.tableau.client").setLevel(logging.DEBUG)
logging.getLogger("app.api.tableau").setLevel(logging.DEBUG)
logging.getLogger("app.services.gateway").setLevel(logging.INFO)
logging.getLogger("app.services.ai.client").setLevel(logging.INFO)
logging.getLogger("app.api.chat").setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.info(f"Logging configured. Log file: {LOG_FILE}")
logger.info(f"Log rotation: max {LOG_MAX_BYTES / 1024 / 1024:.1f}MB, {LOG_BACKUP_COUNT} backups")

app = FastAPI(
    title="Tableau AI Demo API",
    description="AI-powered interface for interacting with Tableau",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)

# Configure CORS
cors_origins = settings.cors_origins_list
logger.info(f"CORS origins configured: {cors_origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    start_time = time.time()
    logger.info(f"Request: {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(
        f"Response: {request.method} {request.url.path} - "
        f"Status: {response.status_code} - Time: {process_time:.3f}s"
    )
    
    return response


# API versioning router
from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1", tags=["api"])


@api_router.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@api_router.get("/health/database", tags=["health"])
async def database_health_check():
    """Database health check endpoint."""
    is_healthy = check_database_health()
    if is_healthy:
        return {"status": "healthy", "service": "database"}
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "service": "database"},
        )


@api_router.get("/health/cache", tags=["health"])
async def cache_health_check():
    """Cache health check endpoint."""
    is_healthy = check_cache_health()
    if is_healthy:
        return {"status": "healthy", "service": "cache"}
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "service": "cache"},
        )


@api_router.get("/health/all", tags=["health"])
async def all_health_checks():
    """Comprehensive health check for all services."""
    db_healthy = check_database_health()
    cache_healthy = check_cache_health()
    
    all_healthy = db_healthy and cache_healthy
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": {
            "database": "healthy" if db_healthy else "unhealthy",
            "cache": "healthy" if cache_healthy else "unhealthy",
        },
    }


@api_router.get("/gateway/health", tags=["health", "gateway"])
async def gateway_health_check():
    """Gateway health check endpoint."""
    try:
        providers = get_available_providers()
        models = get_available_models()
        
        return {
            "status": "healthy",
            "service": "gateway",
            "providers": providers,
            "model_count": len(models),
            "enabled": settings.GATEWAY_ENABLED,
        }
    except Exception as e:
        logger.error(f"Gateway health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "gateway",
                "error": str(e)
            },
        )


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Tableau AI Demo API", "version": "1.0.0", "docs": "/api/v1/docs"}


# Include API router
app.include_router(api_router)

# Include Tableau API router
from app.api.tableau import router as tableau_router
app.include_router(tableau_router, prefix="/api/v1")

# Include Chat API router
from app.api.chat import router as chat_router
app.include_router(chat_router, prefix="/api/v1")

# Include Gateway API router
from app.services.gateway.api import router as gateway_router
app.include_router(gateway_router, prefix="/api/v1/gateway")

# Include Agents API router
from app.api.agents import router as agents_router
app.include_router(agents_router, prefix="/api/v1")

# Include Metrics API router
from app.api.metrics import router as metrics_router
app.include_router(metrics_router, prefix="/api/v1")

# Include Debug API router
from app.api.debug import router as debug_router
app.include_router(debug_router, prefix="/api/v1")

# Include MCP SSE endpoint and debug endpoints for web integration
try:
    from sse_starlette.sse import EventSourceResponse
    import json
    
    @app.get("/mcp/sse")
    async def mcp_sse_endpoint(request: Request):
        """
        Server-Sent Events endpoint for MCP server web integration.
        
        This allows the frontend to connect to the MCP server via SSE.
        """
        from mcp_server.server import mcp
        from fastapi.responses import Response
        
        async def event_generator():
            """Generate SSE events from MCP server."""
            try:
                # Initialize connection
                yield {
                    "event": "connected",
                    "data": json.dumps({"status": "connected", "server": mcp.name})
                }
                
                # Keep connection alive with heartbeat
                import asyncio
                while True:
                    await asyncio.sleep(30)  # Heartbeat every 30 seconds
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps({"timestamp": time.time()})
                    }
            except Exception as e:
                logger.error(f"MCP SSE error: {e}")
                yield {
                    "event": "error",
                    "data": json.dumps({"error": str(e)})
                }
        
        response = EventSourceResponse(event_generator())
        # Add CORS headers explicitly for SSE
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
        return response
    
    @app.get("/mcp/debug/tools")
    async def mcp_debug_tools():
        """
        Debug endpoint to list registered MCP tools.
        
        Useful for verifying tool registration.
        """
        from mcp_server.server import mcp
        
        tools_info = []
        try:
            # Try to get tools from FastMCP
            if hasattr(mcp, '_tools'):
                for name, tool in mcp._tools.items():
                    tools_info.append({
                        "name": name,
                        "description": getattr(tool, '__doc__', 'No description'),
                    })
            elif hasattr(mcp, 'tools'):
                # Alternative attribute name
                for name, tool in mcp.tools.items():
                    tools_info.append({
                        "name": name,
                        "description": getattr(tool, '__doc__', 'No description'),
                    })
            else:
                # Try to inspect the server object
                tools_info.append({
                    "error": "Could not find tools attribute",
                    "available_attrs": [attr for attr in dir(mcp) if not attr.startswith('__')]
                })
        except Exception as e:
            logger.error(f"Error getting tools: {e}")
            tools_info.append({"error": str(e)})
        
        return {
            "server_name": mcp.name,
            "server_version": getattr(mcp, 'version', 'unknown'),
            "tools_count": len(tools_info),
            "tools": tools_info,
        }
    
    @app.get("/mcp/debug/resources")
    async def mcp_debug_resources():
        """
        Debug endpoint to list registered MCP resources.
        """
        from mcp_server.server import mcp
        
        resources_info = []
        try:
            if hasattr(mcp, '_resources'):
                for uri, resource in mcp._resources.items():
                    resources_info.append({
                        "uri": uri,
                        "description": getattr(resource, '__doc__', 'No description'),
                    })
            elif hasattr(mcp, 'resources'):
                for uri, resource in mcp.resources.items():
                    resources_info.append({
                        "uri": uri,
                        "description": getattr(resource, '__doc__', 'No description'),
                    })
        except Exception as e:
            logger.error(f"Error getting resources: {e}")
            resources_info.append({"error": str(e)})
        
        return {
            "resources_count": len(resources_info),
            "resources": resources_info,
        }
except ImportError:
    logger.warning("sse-starlette not installed. MCP SSE endpoint not available.")
