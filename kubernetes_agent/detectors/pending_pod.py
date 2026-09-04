"""Pending pod detector.

Detects pods stuck in Pending state for too long.
"""

from __future__ import annotations

import datetime

from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.detectors.base import BaseDetector
from kubernetes_agent.models.anomaly import (
    AffectedResource,
    AnomalyType,
    DetectedAnomaly,
    Severity,
)
from kubernetes_agent.models.snapshot import ClusterSnapshot


class PendingPodDetector(BaseDetector):
    """Detects pods stuck in Pending phase."""

    def __init__(self, cfg: AgentConfig | None = None) -> None:
        self._cfg = cfg or get_config()

    @property
    def anomaly_type(self) -> AnomalyType:
        return AnomalyType.PENDING_POD

    def detect(self, snapshot: ClusterSnapshot) -> list[DetectedAnomaly]:
        anomalies: list[DetectedAnomaly] = []
        now = datetime.datetime.now(datetime.UTC)
        threshold_seconds = self._cfg.pending_threshold_seconds

        for pod in snapshot.pods:
            if pod.phase == "Pending":
                # Check if it's actually stuck, or just created 2 seconds ago
                stuck_duration = 0.0
                if pod.creation_timestamp:
                    stuck_duration = (now - pod.creation_timestamp).total_seconds()
                    
                if stuck_duration >= threshold_seconds:
                    
                    # Determine reason if possible
                    reason = pod.status_reason or "Unknown"
                    message = pod.status_message or "Pod is stuck in Pending state."
                    
                    # Check conditions for scheduling failures
                    for cond in pod.conditions:
                        if cond.type == "PodScheduled" and cond.status == "False":
                            reason = cond.reason or reason
                            message = cond.message or message
                            break

                    anomalies.append(
                        DetectedAnomaly(
                            anomaly_type=self.anomaly_type,
                            severity=Severity.WARNING,
                            resource=AffectedResource(
                                kind="Pod",
                                name=pod.name,
                                namespace=pod.namespace,
                            ),
                            title=f"Pod {pod.namespace}/{pod.name} stuck in Pending",
                            description=f"Pod '{pod.name}' has been Pending for {int(stuck_duration)} seconds. Reason: {reason}.",
                            evidence={
                                "duration_seconds": int(stuck_duration),
                                "threshold": threshold_seconds,
                                "reason": reason,
                                "message": message,
                            },
                        )
                    )

        return anomalies
