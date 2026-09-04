"""Evidence package models.

An EvidencePackage is assembled during investigation. It bundles all the
signals the Investigation Engine collected for a single anomaly: the K8s
state that triggered detection, related events, and sanitized log fragments.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from kubernetes_agent.models.anomaly import DetectedAnomaly
from kubernetes_agent.models.snapshot import EventSnapshot, PodSnapshot


class LogPattern(BaseModel):
    """A notable pattern found in application logs."""

    pattern: str  # The error/exception text
    count: int = 1
    severity: str = "error"  # error, warning, info
    sample_lines: list[str] = Field(default_factory=list)  # Example log lines


class EventSummary(BaseModel):
    """Summarized Kubernetes event relevant to an investigation."""

    type: str  # Normal, Warning
    reason: str
    message: str
    count: int = 1
    source: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class EvidencePackage(BaseModel):
    """All evidence collected during an investigation of a single anomaly.

    This is the input to the LLM analyzer and the recommendation engine.
    It bundles the original detection, K8s state, events, and logs.
    """

    anomaly: DetectedAnomaly

    # K8s state context
    pod_snapshots: list[PodSnapshot] = Field(default_factory=list)
    related_events: list[EventSummary] = Field(default_factory=list)

    # Application logs
    logs: dict[str, str] = Field(default_factory=dict)  # container_name -> log text
    previous_logs: dict[str, str] = Field(default_factory=dict)  # previous instance logs
    log_patterns: list[LogPattern] = Field(default_factory=list)

    # Resource context
    resource_info: dict = Field(default_factory=dict)  # resource requests/limits, node capacity
    node_conditions: dict = Field(default_factory=dict)  # node health if relevant

    # Metadata
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    collection_errors: list[str] = Field(default_factory=list)
