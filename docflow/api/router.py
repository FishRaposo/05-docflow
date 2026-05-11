"""API router aggregation."""

from fastapi import APIRouter

from docflow.api.health import router as health_router
from docflow.api.sources import router as sources_router
from docflow.api.documents import router as documents_router
from docflow.api.pipeline import router as pipeline_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(sources_router)
api_router.include_router(documents_router)
api_router.include_router(pipeline_router)

__all__ = ["api_router"]
