"""Frequent restart detector.

Detects containers whose restart count exceeds a configurable threshold.
This is distinct from CrashLoopBackOff — a pod may be restarting frequently
without being in CrashLoopBackOff state at the exact moment of the scan.
"""

from __future__ import annotations

from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.detectors.base import BaseDetector
from kubernetes_agent.models.anomaly import (
    AffectedResource,
    AnomalyType,
    DetectedAnomaly,
    Severity,
)
from kubernetes_agent.models.snapshot import ClusterSnapshot


class RestartRateDetector(BaseDetector):
    """Detects containers with restart counts above a threshold."""

    def __init__(self, cfg: AgentConfig | None = None) -> None:
        self._cfg = cfg or get_config()

    @property
    def anomaly_type(self) -> AnomalyType:
        return AnomalyType.FREQUENT_RESTARTS

    def detect(self, snapshot: ClusterSnapshot) -> list[DetectedAnomaly]:
        anomalies: list[DetectedAnomaly] = []
        threshold = self._cfg.restart_threshold

        for pod in snapshot.pods:
            for cs in pod.container_statuses:
                if cs.restart_count >= threshold:
                    # Skip if already CrashLoopBackOff (handled by crash_loop detector)
                    if (
                        cs.state.state == "waiting"
                        and cs.state.reason == "CrashLoopBackOff"
                    ):
                        continue

                    severity = (
                        Severity.CRITICAL
                        if cs.restart_count >= threshold * 3
                        else Severity.WARNING
                    )

                    anomalies.append(
                        DetectedAnomaly(
                            anomaly_type=self.anomaly_type,
                            severity=severity,
                            resource=AffectedResource(
                                kind="Pod",
                                name=pod.name,
                                namespace=pod.namespace,
                            ),
                            title=(
                                f"Frequent restarts on pod {pod.namespace}/{pod.name} "
                                f"(container: {cs.name}, restarts: {cs.restart_count})"
                            ),
                            description=(
                                f"Container '{cs.name}' has restarted "
                                f"{cs.restart_count} times "
                                f"(threshold: {threshold}). "
                                f"Last termination reason: "
                                f"{cs.last_state.reason or 'unknown'}, "
                                f"exit code: {cs.last_state.exit_code}."
                            ),
                            evidence={
                                "container": cs.name,
                                "restart_count": cs.restart_count,
                                "threshold": threshold,
                                "current_state": cs.state.state,
                                "last_termination_reason": cs.last_state.reason,
                                "last_exit_code": cs.last_state.exit_code,
                            },
                        )
                    )

        return anomalies
