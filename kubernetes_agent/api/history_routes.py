"""History API routes — chat history, incidents, scan metrics from MongoDB."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from kubernetes_agent.api.dependencies import (
    get_chat_repo,
    get_incident_repo,
    get_scan_repo,
)
from kubernetes_agent.db.repositories import (
    ChatRepository,
    IncidentRepository,
    ScanRepository,
)

router = APIRouter(prefix="/history", tags=["History"])


@router.get("/chat")
async def get_chat_history(
    session_id: str | None = Query(None, description="Filter by session ID"),
    limit: int = Query(50, ge=1, le=500),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Get recent chat messages from history."""
    return await chat_repo.get_history(session_id=session_id, limit=limit)


@router.get("/chat/sessions")
async def get_chat_sessions(
    limit: int = Query(20, ge=1, le=100),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Get list of chat sessions with message counts."""
    return await chat_repo.get_sessions(limit=limit)


@router.get("/incidents")
async def get_incident_history(
    limit: int = Query(50, ge=1, le=500),
    status: str = Query("all", description="Filter: open, resolved, acknowledged, all"),
    severity: str = Query("all", description="Filter: critical, warning, info, all"),
    incident_repo: IncidentRepository = Depends(get_incident_repo),
):
    """Get incident audit trail from history."""
    return await incident_repo.get_history(
        limit=limit,
        status=status,
        severity=severity,
    )


@router.get("/incidents/{incident_id}")
async def get_incident_detail(
    incident_id: str,
    incident_repo: IncidentRepository = Depends(get_incident_repo),
):
    """Get a single incident by ID."""
    incident = await incident_repo.get_by_id(incident_id)
    if incident is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.get("/scans")
async def get_scan_history(
    limit: int = Query(100, ge=1, le=1000),
    scan_repo: ScanRepository = Depends(get_scan_repo),
):
    """Get scan history."""
    return await scan_repo.get_history(limit=limit)


@router.get("/scans/metrics")
async def get_scan_metrics(
    hours: int = Query(24, ge=1, le=168, description="Hours of metrics to return"),
    scan_repo: ScanRepository = Depends(get_scan_repo),
):
    """Get scan metrics for charting (last N hours)."""
    return await scan_repo.get_metrics(hours=hours)
