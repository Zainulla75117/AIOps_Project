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


@router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Delete all messages in a chat session."""
    count = await chat_repo.delete_session(session_id)
    if count == 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "deleted_count": count}


@router.put("/chat/sessions/{session_id}")
async def rename_chat_session(
    session_id: str,
    body: dict,
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Rename a chat session."""
    title = body.get("title", "").strip()
    if not title:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Title is required")
    success = await chat_repo.rename_session(session_id, title)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "title": title}


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
