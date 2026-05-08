"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from docflow.__init__ import __version__
from docflow.api.router import api_router
from docflow.db.session import init_db


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle.

    Initializes database connections on startup and cleans up on shutdown.
    """
    await init_db()
    yield


app = FastAPI(
    title="DocFlow",
    description="A production-style document ingestion pipeline for RAG and knowledge systems",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Return basic API information."""
    return {"name": "DocFlow", "version": __version__, "status": "running"}
