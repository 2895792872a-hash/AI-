"""FastAPI application entry point.

Sets up CORS, logging, lifespan (Redis connect/disconnect), and mounts routes.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.core.logging import setup_logging, logger


# ── Lifespan ─────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init logging, connect Redis. Shutdown: close Redis."""
    setup_logging()
    logger.info("AI Browser Assistant starting on %s:%s", settings.api_host, settings.api_port)

    # Pre-connect Redis on startup (best-effort)
    try:
        from app.services.redis_service import get_redis
        await get_redis()
    except Exception:
        logger.warning("Redis not available — running without persistence")

    yield

    # Shutdown
    try:
        from app.services.redis_service import close_redis
        await close_redis()
    except Exception:
        pass
    logger.info("AI Browser Assistant shut down")


# ── App ──────────────────────────────────────────────────────


app = FastAPI(
    title="AI Browser Automation Assistant",
    description=(
        "A four-stage AI Agent that automates browser tasks using Claude API, "
        "LangGraph, and Playwright. Supports web search, form filling, and "
        "content extraction with real-time SSE progress streaming."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(o) for o in settings.cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(api_router)


# ── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
