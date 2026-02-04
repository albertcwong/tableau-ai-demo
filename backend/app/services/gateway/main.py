"""Gateway FastAPI application entry point."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.services.gateway.api import router as gateway_router
from app.core.config import settings

logger = logging.getLogger(__name__)

# Create FastAPI app for gateway
app = FastAPI(
    title="Unified LLM Gateway",
    description="OpenAI-compatible gateway for multiple LLM providers",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Gateway can be accessed from anywhere
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include gateway router
app.include_router(gateway_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Unified LLM Gateway",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/gateway/health"
    }


if __name__ == "__main__":
    import uvicorn
    port = getattr(settings, 'GATEWAY_PORT', 8001)
    uvicorn.run(
        "app.services.gateway.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
