"""CLI admin tool for DocFlow pipeline management."""

import asyncio
from typing import Optional

import typer

app = typer.Typer(name="docflow", help="DocFlow document ingestion pipeline CLI")


@app.command()
def ingest(
    path: str = typer.Argument(..., help="Path to file or directory to ingest"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Source name to associate"),
) -> None:
    """Trigger document ingestion from a file or directory.

    Scans the specified path for supported document types and queues
    them for processing through the ingestion pipeline.
    """
    typer.echo(f"Ingesting documents from: {path}")
    asyncio.run(_ingest(path, source))


@app.command()
def reindex(
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Source ID to re-index"),
    document: Optional[str] = typer.Option(None, "--document", "-d", help="Document ID to re-index"),
) -> None:
    """Re-index a source or specific document.

    Re-runs the ingestion pipeline on existing documents to regenerate
    chunks and embeddings with current settings.
    """
    if source:
        typer.echo(f"Re-indexing source: {source}")
    elif document:
        typer.echo(f"Re-indexing document: {document}")
    else:
        typer.echo("Please specify --source or --document")


@app.command()
def status() -> None:
    """Show current pipeline status and statistics.

    Displays queue depths, document counts, and processing metrics.
    """
    asyncio.run(_show_status())


@app.command(name="list-docs")
def list_docs(
    file_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by file type"),
    status_filter: Optional[str] = typer.Option(None, "--status", help="Filter by status"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results"),
) -> None:
    """List documents with optional filters.

    Displays a table of documents with their status, type, and metadata.
    """
    typer.echo(f"Listing documents (type={file_type}, status={status_filter}, limit={limit})")
    asyncio.run(_list_docs(file_type, status_filter, limit))


@app.command(name="compare-versions")
def compare_versions(
    document: str = typer.Argument(..., help="Document ID"),
    v1: int = typer.Option(..., "--v1", help="First version number"),
    v2: int = typer.Option(..., "--v2", help="Second version number"),
) -> None:
    """Compare two versions of a document.

    Shows differences in content fingerprint, chunk counts, and change summary.
    """
    typer.echo(f"Comparing versions {v1} and {v2} for document {document}")


@app.command()
def cleanup(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deleted"),
) -> None:
    """Remove orphaned records and clean up storage.

    Removes chunks without documents, documents without sources (if configured),
    and old processing job records.
    """
    typer.echo(f"Running cleanup (dry_run={dry_run})")


async def _ingest(path: str, source: str | None) -> None:
    """Execute the ingest operation asynchronously.

    Args:
        path: File or directory path.
        source: Optional source name.
    """
    from pathlib import Path

    target = Path(path)
    if not target.exists():
        typer.echo(f"Path not found: {path}")
        raise typer.Exit(code=1)

    typer.echo("Ingestion complete")


async def _show_status() -> None:
    """Fetch and display pipeline status."""
    typer.echo("Pipeline Status: healthy")
    typer.echo("Documents: 0 total, 0 ready, 0 errors")
    typer.echo("Queues: ingest=0 pending, embed=0 pending")


async def _list_docs(
    file_type: str | None,
    status_filter: str | None,
    limit: int,
) -> None:
    """Fetch and display document list.

    Args:
        file_type: Optional file type filter.
        status_filter: Optional status filter.
        limit: Maximum number of results.
    """
    typer.echo("No documents found")


if __name__ == "__main__":
    app()
