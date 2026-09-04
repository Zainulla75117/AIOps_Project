"""Anomaly detection models.

These models represent problems detected by the rule-based detection engine.
Each detector produces DetectedAnomaly instances when it finds issues in a
ClusterSnapshot.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severity levels for detected anomalies."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AnomalyType(str, Enum):
    """Known anomaly types the rule engine can detect."""

    CRASH_LOOP_BACKOFF = "crash_loop_backoff"
    IMAGE_PULL_ERROR = "image_pull_error"
    OOM_KILLED = "oom_killed"
    FREQUENT_RESTARTS = "frequent_restarts"
    FAILED_DEPLOYMENT = "failed_deployment"
    PROBE_FAILURE = "probe_failure"
    PENDING_POD = "pending_pod"
    NODE_PRESSURE = "node_pressure"
    SCHEDULING_FAILURE = "scheduling_failure"
    EVICTION = "eviction"
    RESOURCE_QUOTA_EXCEEDED = "resource_quota_exceeded"
    CONTAINER_BACKOFF = "container_backoff"


class AffectedResource(BaseModel):
    """Identifies the Kubernetes resource an anomaly is about."""

    kind: str  # Pod, Deployment, Node, etc.
    name: str
    namespace: str = ""


class DetectedAnomaly(BaseModel):
    """An anomaly found by a deterministic detector.

    These are *observed facts*, not inferences. Each one corresponds to a
    concrete signal in the Kubernetes API (a status field, an event, etc.).
    """

    anomaly_type: AnomalyType
    severity: Severity
    resource: AffectedResource
    title: str  # Human-readable one-liner, e.g. "CrashLoopBackOff on pod api-xyz"
    description: str  # Slightly more detail about what was observed
    evidence: dict = Field(default_factory=dict)  # Raw K8s fields that triggered detection
    detected_at: datetime = Field(default_factory=datetime.utcnow)

    # Deduplication key — same resource + same type = same ongoing incident
    @property
    def dedup_key(self) -> str:
        """Key used to deduplicate repeated detections of the same problem."""
        return (
            f"{self.anomaly_type.value}:"
            f"{self.resource.kind}/"
            f"{self.resource.namespace}/"
            f"{self.resource.name}"
        )
