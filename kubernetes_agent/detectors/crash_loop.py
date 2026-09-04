"""CrashLoopBackOff detector.

Detects containers stuck in the CrashLoopBackOff waiting state.
"""

from __future__ import annotations

from kubernetes_agent.detectors.base import BaseDetector
from kubernetes_agent.models.anomaly import (
    AffectedResource,
    AnomalyType,
    DetectedAnomaly,
    Severity,
)
from kubernetes_agent.models.snapshot import ClusterSnapshot


class CrashLoopDetector(BaseDetector):
    """Detects pods with containers in CrashLoopBackOff."""

    @property
    def anomaly_type(self) -> AnomalyType:
        return AnomalyType.CRASH_LOOP_BACKOFF

    def detect(self, snapshot: ClusterSnapshot) -> list[DetectedAnomaly]:
        anomalies: list[DetectedAnomaly] = []

        for pod in snapshot.pods:
            for cs in pod.container_statuses:
                if (
                    cs.state.state == "waiting"
                    and cs.state.reason == "CrashLoopBackOff"
                ):
                    anomalies.append(
                        DetectedAnomaly(
                            anomaly_type=self.anomaly_type,
                            severity=Severity.CRITICAL,
                            resource=AffectedResource(
                                kind="Pod",
                                name=pod.name,
                                namespace=pod.namespace,
                            ),
                            title=(
                                f"CrashLoopBackOff on pod {pod.namespace}/{pod.name} "
                                f"(container: {cs.name})"
                            ),
                            description=(
                                f"Container '{cs.name}' is in CrashLoopBackOff with "
                                f"{cs.restart_count} restarts. "
                                f"Last termination reason: "
                                f"{cs.last_state.reason or 'unknown'}, "
                                f"exit code: {cs.last_state.exit_code}."
                            ),
                            evidence={
                                "container": cs.name,
                                "restart_count": cs.restart_count,
                                "waiting_reason": cs.state.reason,
                                "waiting_message": cs.state.message,
                                "last_termination_reason": cs.last_state.reason,
                                "last_exit_code": cs.last_state.exit_code,
                                "pod_phase": pod.phase,
                            },
                        )
                    )

        return anomalies
