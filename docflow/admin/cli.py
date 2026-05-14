"""CLI admin tool for DocFlow pipeline management."""

import asyncio
import uuid as uuid_mod
from typing import Optional

import typer
from sqlalchemy import func, select

from docflow.config import settings
from docflow.db import async_session
from docflow.db.models import Chunk, Document, ProcessingJob
from docflow.processing.versioning import VersioningService
from docflow.queue.dlq import DeadLetterQueue
from docflow.queue.redis_queue import RedisQueue

app = typer.Typer(name="docflow", help="DocFlow document ingestion pipeline CLI")


@app.command()
def ingest(
    path: str = typer.Argument(..., help="Path to file or directory to ingest"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Source name to associate"),
) -> None:
    """Trigger document ingestion from a file or directory."""
    asyncio.run(_ingest(path, source))


@app.command()
def reindex(
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Source ID to re-index"),
    document: Optional[str] = typer.Option(None, "--document", "-d", help="Document ID to re-index"),
) -> None:
    """Re-index a source or specific document."""
    asyncio.run(_reindex(source, document))


@app.command()
def status() -> None:
    """Show current pipeline status and statistics."""
    asyncio.run(_show_status())


@app.command(name="list-docs")
def list_docs(
    file_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by file type"),
    status_filter: Optional[str] = typer.Option(None, "--status", help="Filter by status"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results"),
) -> None:
    """List documents with optional filters."""
    asyncio.run(_list_docs(file_type, status_filter, limit))


@app.command(name="compare-versions")
def compare_versions(
    document: str = typer.Argument(..., help="Document ID"),
    v1: int = typer.Option(..., "--v1", help="First version number"),
    v2: int = typer.Option(..., "--v2", help="Second version number"),
) -> None:
    """Compare two versions of a document."""
    asyncio.run(_compare(document, v1, v2))


@app.command()
def cleanup(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deleted"),
) -> None:
    """Remove orphaned records and clean up storage."""
    asyncio.run(_cleanup(dry_run))


async def _ingest(path: str, source: str | None) -> None:
    """Scan path for documents and enqueue for processing."""
    from pathlib import Path

    import uuid as uuid_mod

    target = Path(path)
    if not target.exists():
        typer.echo(f"Path not found: {path}")
        raise typer.Exit(code=1)

    supported = {"md", "pdf", "html", "htm", "docx", "csv", "txt"}

    files_to_ingest: list[Path] = []
    if target.is_file():
        files_to_ingest.append(target)
    else:
        for f in target.rglob("*"):
            if f.is_file() and f.suffix.lstrip(".").lower() in supported:
                files_to_ingest.append(f)

    if not files_to_ingest:
        typer.echo("No supported files found")
        raise typer.Exit(code=0)

    async with async_session() as session:
        queue = RedisQueue()
        await queue.connect()

        try:
            for file_path in files_to_ingest:
                ext = file_path.suffix.lstrip(".").lower()
                doc = Document(
                    title=file_path.name,
                    file_path=str(file_path),
                    file_type=ext,
                    status="pending",
                )
                session.add(doc)
                await session.commit()
                await session.refresh(doc)

                await queue.enqueue(
                    f"{settings.QUEUE_NAME}:ingest",
                    {"document_id": str(doc.id)},
                )
                typer.echo(f"Queued: {file_path.name}")
        finally:
            await queue.disconnect()

    typer.echo(f"Ingestion complete: {len(files_to_ingest)} documents queued")


async def _reindex(source: str | None, document: str | None) -> None:
    """Re-index a source or document by resetting status and enqueueing."""
    async with async_session() as session:
        queue = RedisQueue()
        await queue.connect()

        try:
            if source:
                result = await session.execute(
                    select(Document).where(Document.source_id == source)
                )
                docs = result.scalars().all()
                for doc in docs:
                    doc.status = "pending"
                    await queue.enqueue(
                        f"{settings.QUEUE_NAME}:ingest",
                        {"document_id": str(doc.id)},
                    )
                await session.commit()
                typer.echo(f"Re-indexing {len(docs)} documents from source {source}")

            elif document:
                result = await session.execute(
                    select(Document).where(Document.id == document)
                )
                doc = result.scalar_one_or_none()
                if doc is None:
                    typer.echo(f"Document not found: {document}")
                    raise typer.Exit(code=1)
                doc.status = "pending"
                await session.commit()
                await queue.enqueue(
                    f"{settings.QUEUE_NAME}:ingest",
                    {"document_id": str(doc.id)},
                )
                typer.echo(f"Re-indexing document: {doc.title}")

            else:
                typer.echo("Please specify --source or --document")
                raise typer.Exit(code=1)
        finally:
            await queue.disconnect()


async def _show_status() -> None:
    """Fetch and display pipeline status."""
    async with async_session() as session:
        total = (await session.execute(select(func.count()).select_from(Document))).scalar() or 0
        ready = (
            await session.execute(select(func.count()).where(Document.status == "ready"))
        ).scalar() or 0
        error = (
            await session.execute(select(func.count()).where(Document.status == "error"))
        ).scalar() or 0
        processing = (
            await session.execute(select(func.count()).where(Document.status == "processing"))
        ).scalar() or 0
        pending = (
            await session.execute(select(func.count()).where(Document.status == "pending"))
        ).scalar() or 0

        queue = RedisQueue()
        await queue.connect()
        try:
            ingest_depth = await queue.get_queue_length(f"{settings.QUEUE_NAME}:ingest")
            embed_depth = await queue.get_queue_length(f"{settings.QUEUE_NAME}:embed")
        finally:
            await queue.disconnect()

        typer.echo(f"Pipeline Status")
        typer.echo(f"  Documents: {total} total, {ready} ready, {processing} processing, {pending} pending, {error} errors")
        typer.echo(f"  Queues: ingest={ingest_depth}, embed={embed_depth}")


async def _list_docs(
    file_type: str | None,
    status_filter: str | None,
    limit: int,
) -> None:
    """Fetch and display document list."""
    async with async_session() as session:
        query = select(Document)
        if file_type:
            query = query.where(Document.file_type == file_type)
        if status_filter:
            query = query.where(Document.status == status_filter)
        query = query.limit(limit)

        result = await session.execute(query)
        docs = result.scalars().all()

        if not docs:
            typer.echo("No documents found")
            return

        typer.echo(f"{'ID':<38} {'Title':<40} {'Type':<6} {'Status':<12} {'Version':<8}")
        typer.echo("-" * 110)
        for doc in docs:
            typer.echo(f"{str(doc.id):<38} {doc.title[:38]:<40} {doc.file_type:<6} {doc.status:<12} {doc.version:<8}")


async def _compare(document: str, v1: int, v2: int) -> None:
    """Compare two versions of a document."""
    versioner = VersioningService()
    try:
        async with async_session() as session:
            diff = await versioner.compare_versions(uuid_mod.UUID(document), v1, v2, session)
            typer.echo(f"Comparing versions {v1} and {v2} for document {document}")
            typer.echo(f"  Fingerprint changed: {diff.fingerprint_changed}")
            typer.echo(f"  Chunks added: {diff.chunks_added}")
            typer.echo(f"  Chunks removed: {diff.chunks_removed}")
            typer.echo(f"  Summary: {diff.summary}")
    except ValueError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(code=1)


async def _cleanup(dry_run: bool) -> None:
    """Remove orphaned records and clean up storage."""
    async with async_session() as session:
        # Find orphaned chunks (chunks whose document no longer exists)
        orphaned_chunks = await session.execute(
            select(Chunk).outerjoin(Document, Chunk.document_id == Document.id).where(Document.id.is_(None))
        )
        orphaned = orphaned_chunks.scalars().all()

        # Find old processing jobs (completed > 30 days ago)
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        old_jobs = await session.execute(
            select(ProcessingJob).where(
                ProcessingJob.status.in_(["completed", "error"]),
                ProcessingJob.completed_at < cutoff,
            )
        )
        old_job_records = old_jobs.scalars().all()

        if dry_run:
            typer.echo(f"Would delete {len(orphaned)} orphaned chunks")
            typer.echo(f"Would delete {len(old_job_records)} old processing jobs")
        else:
            for chunk in orphaned:
                await session.delete(chunk)
            for job in old_job_records:
                await session.delete(job)
            await session.commit()
            typer.echo(f"Deleted {len(orphaned)} orphaned chunks, {len(old_job_records)} old processing jobs")


@app.command()
def dlq(
    action: str = typer.Argument(..., help="Action: list, retry, clear"),
    dlq_id: Optional[str] = typer.Option(None, "--id", "-i", help="DLQ entry ID to retry"),
) -> None:
    """Manage the Dead Letter Queue."""
    asyncio.run(_dlq(action, dlq_id))


async def _dlq(action: str, dlq_id: str | None) -> None:
    import redis.asyncio as aioredis

    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        dlq_instance = DeadLetterQueue(redis_client)
        if action == "list":
            entries = await dlq_instance.list_entries()
            if not entries:
                typer.echo("DLQ is empty")
                return
            typer.echo(f"{'ID':<38} {'Queue':<25} {'Error':<50} {'Timestamp'}")
            typer.echo("-" * 130)
            for entry in entries:
                ts = entry.get("timestamp", "")[:19]
                err = entry.get("error", "")[:48]
                typer.echo(f"{entry.get('id', ''):<38} {entry.get('queue', ''):<25} {err:<50} {ts}")
        elif action == "retry":
            if dlq_id is None:
                typer.echo("Please provide --id for retry")
                raise typer.Exit(code=1)
            success = await dlq_instance.retry(dlq_id)
            if success:
                typer.echo(f"DLQ entry {dlq_id} requeued successfully")
            else:
                typer.echo(f"DLQ entry {dlq_id} not found")
                raise typer.Exit(code=1)
        elif action == "clear":
            count = await dlq_instance.clear()
            typer.echo(f"Cleared DLQ ({count} key(s) removed)")
        else:
            typer.echo(f"Unknown action: {action}. Use list, retry, or clear.")
            raise typer.Exit(code=1)
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    app()
