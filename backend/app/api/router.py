"""API router aggregation — mounts all sub-routers."""

from fastapi import APIRouter

from app.api.tasks import router as tasks_router

api_router = APIRouter(prefix="/api")
api_router.include_router(tasks_router)


@api_router.get("/health")
async def health_check():
    """Liveness/readiness check."""
    return {"status": "ok", "service": "ai-browser-assistant"}
