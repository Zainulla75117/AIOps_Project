"""Ingestion job progress tracker backed by MongoDB.

Stores ingestion progress in a persistent collection so the dashboard
can poll for updates that survive page refreshes and server restarts.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def create_job(db, filename: str) -> str:
    """Create a new ingestion job record. Returns the job_id."""
    job_id = str(uuid.uuid4())
    doc = {
        "_id": job_id,
        "filename": filename,
        "status": "processing",
        "total_rows": 0,
        "processed_rows": 0,
        "chunks_created": 0,
        "current_table": None,
        "error": None,
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
    }
    await db.ingestion_jobs.insert_one(doc)
    logger.info("ingestion_job_created", job_id=job_id, filename=filename)
    return job_id


async def update_progress(
    db,
    job_id: str,
    *,
    processed_rows: int | None = None,
    total_rows: int | None = None,
    chunks_created: int | None = None,
    current_table: str | None = None,
) -> None:
    """Incrementally update job progress fields."""
    update: dict[str, Any] = {"updated_at": _utcnow()}

    if processed_rows is not None:
        update["processed_rows"] = processed_rows
    if total_rows is not None:
        update["total_rows"] = total_rows
    if chunks_created is not None:
        update["chunks_created"] = chunks_created
    if current_table is not None:
        update["current_table"] = current_table

    await db.ingestion_jobs.update_one(
        {"_id": job_id},
        {"$set": update},
    )


async def mark_completed(db, job_id: str, chunks_created: int) -> None:
    """Mark a job as successfully completed."""
    await db.ingestion_jobs.update_one(
        {"_id": job_id},
        {"$set": {
            "status": "completed",
            "chunks_created": chunks_created,
            "updated_at": _utcnow(),
        }},
    )
    logger.info("ingestion_job_completed", job_id=job_id, chunks_created=chunks_created)


async def mark_failed(db, job_id: str, error: str) -> None:
    """Mark a job as failed with an error message."""
    await db.ingestion_jobs.update_one(
        {"_id": job_id},
        {"$set": {
            "status": "failed",
            "error": error,
            "updated_at": _utcnow(),
        }},
    )
    logger.error("ingestion_job_failed", job_id=job_id, error=error)


async def get_active_jobs(db) -> list[dict[str, Any]]:
    """Return all processing jobs + completed/failed within the last hour."""
    from datetime import timedelta
    one_hour_ago = _utcnow() - timedelta(hours=1)

    cursor = db.ingestion_jobs.find({
        "$or": [
            {"status": "processing"},
            {"status": {"$in": ["completed", "failed"]}, "updated_at": {"$gte": one_hour_ago}},
        ]
    }).sort("created_at", -1)

    jobs = []
    async for doc in cursor:
        doc["job_id"] = doc.pop("_id")
        # Convert datetimes to ISO strings for JSON serialization
        for key in ("created_at", "updated_at"):
            if isinstance(doc.get(key), datetime):
                doc[key] = doc[key].isoformat()
        jobs.append(doc)
    return jobs


async def get_job(db, job_id: str) -> dict[str, Any] | None:
    """Return a single job by ID."""
    doc = await db.ingestion_jobs.find_one({"_id": job_id})
    if doc is None:
        return None
    doc["job_id"] = doc.pop("_id")
    for key in ("created_at", "updated_at"):
        if isinstance(doc.get(key), datetime):
            doc[key] = doc[key].isoformat()
    return doc
