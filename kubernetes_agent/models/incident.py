"""Incident report and recommendation models.

An IncidentReport is the final output of the analysis pipeline.
It clearly separates observations (facts), inferences, root cause,
and actionable recommendations.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from kubernetes_agent.models.anomaly import AffectedResource, Severity


class IncidentStatus(str, Enum):
    """Lifecycle status of an incident."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class RiskLevel(str, Enum):
    """Risk level of a recommended remediation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RootCause(BaseModel):
    """Determined root cause of an incident."""

    category: str  # e.g. "application_error", "resource_exhaustion", "configuration"
    description: str  # Natural-language explanation
    confidence: float = 0.0  # 0.0 – 1.0
    reasoning: str = ""  # Chain of reasoning from evidence to conclusion


class Recommendation(BaseModel):
    """Actionable remediation recommendation."""

    action: str  # What to do
    rationale: str  # Why this should fix it
    commands: list[str] = Field(default_factory=list)  # Suggested kubectl/YAML changes
    risk_level: RiskLevel = RiskLevel.LOW
    requires_restart: bool = False
    additional_investigation: list[str] = Field(default_factory=list)


class IncidentReport(BaseModel):
    """Complete incident analysis report.

    This is the primary artifact the agent produces. It follows a strict
    separation between observations, inferences, and recommendations so
    operators can judge the quality of the analysis.
    """

    id: str  # Unique identifier, e.g. "inc-20260903-001"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: IncidentStatus = IncidentStatus.OPEN
    severity: Severity = Severity.WARNING

    what_went_wrong: str = ""  # One-sentence summary

    # Clearly labeled sections
    observations: list[str] = Field(default_factory=list)  # FACTS — observed from K8s/logs
    inferences: list[str] = Field(default_factory=list)  # INFERENCES — derived reasoning
    root_cause: RootCause | None = None
    affected_resources: list[AffectedResource] = Field(default_factory=list)
    recommendation: Recommendation | None = None

    # Source evidence metadata (not the full package — that may be large)
    evidence_summary: dict = Field(default_factory=dict)
    log_snippets: list[str] = Field(default_factory=list)

    # Analysis metadata
    llm_analysis_available: bool = True
    analysis_duration_ms: float = 0.0
    scan_id: str | None = None
