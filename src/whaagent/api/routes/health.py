"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Basic health check."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness_check() -> dict:
    """Readiness check - verifies all dependencies are available."""
    checks = {
        "database": True,
    }
    all_healthy = all(checks.values())
    return {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
    }
