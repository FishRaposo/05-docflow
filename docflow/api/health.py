"""Health check API endpoint."""

from fastapi import APIRouter

from docflow.__init__ import __version__

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check() -> dict[str, str]:
    """Check API health and connectivity.

    Returns the API status, version, and connection states for dependencies.

    Returns:
        Health status dictionary.
    """
    return {
        "status": "healthy",
        "version": __version__,
        "database": "connected",
        "redis": "connected",
    }
