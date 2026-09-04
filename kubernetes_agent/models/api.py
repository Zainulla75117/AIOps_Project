"""API request and response models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Namespace settings
# ---------------------------------------------------------------------------

class NamespacePermission(BaseModel):
    """Permission state for a single namespace."""

    name: str
    enabled: bool = False
    is_system: bool = False
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    enabled_at: datetime | None = None
    disabled_at: datetime | None = None


class NamespaceSettings(BaseModel):
    """All namespace permission settings."""

    namespaces: dict[str, NamespacePermission] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class NamespaceToggleRequest(BaseModel):
    """Request body for toggling a single namespace."""

    enabled: bool


class NamespaceBulkUpdateRequest(BaseModel):
    """Request body for bulk-updating namespace permissions."""

    namespaces: dict[str, bool]  # namespace_name -> enabled


# ---------------------------------------------------------------------------
# Agent status
# ---------------------------------------------------------------------------

class AgentStatusResponse(BaseModel):
    """Response for GET /api/v1/status."""

    agent_version: str
    uptime_seconds: float
    last_scan_at: datetime | None = None
    last_scan_duration_ms: float | None = None
    total_scans: int = 0
    active_incidents: int = 0
    monitored_namespaces: list[str] = Field(default_factory=list)
    gemini_available: bool = False


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

class ScanTriggerResponse(BaseModel):
    """Response for POST /api/v1/scan."""

    scan_id: str
    status: str = "started"
    message: str = ""


class ScanHistoryEntry(BaseModel):
    """A single past scan summary."""

    scan_id: str
    started_at: datetime
    duration_ms: float
    namespaces_scanned: list[str] = Field(default_factory=list)
    anomalies_detected: int = 0
    incidents_created: int = 0


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Request for the LLM chat."""
    query: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Response from the LLM chat."""
    reply: str


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Standard error response body."""

    error: str
    detail: str | None = None
