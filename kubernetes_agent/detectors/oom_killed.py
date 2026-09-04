"""OOMKilled detector.

Detects containers terminated with OOMKilled reason or exit code 137.
"""

from __future__ import annotations

from kubernetes_agent.detectors.base import BaseDetector
from kubernetes_agent.models.anomaly import (
    AffectedResource,
    AnomalyType,
    DetectedAnomaly,
    Severity,
)
from kubernetes_agent.models.snapshot import ClusterSnapshot, ContainerStatusSnapshot


class OOMKilledDetector(BaseDetector):
    """Detects containers killed due to out-of-memory."""

    @property
    def anomaly_type(self) -> AnomalyType:
        return AnomalyType.OOM_KILLED

    def detect(self, snapshot: ClusterSnapshot) -> list[DetectedAnomaly]:
        anomalies: list[DetectedAnomaly] = []

        for pod in snapshot.pods:
            for cs in pod.container_statuses:
                if self._is_oom(cs):
                    # Determine which state has the OOM signal
                    oom_state = (
                        cs.state
                        if cs.state.reason == "OOMKilled"
                        else cs.last_state
                    )

                    # Get memory limit if available
                    memory_limit = None
                    if pod.resources and cs.name in pod.resources:
                        memory_limit = pod.resources[cs.name].limits.memory

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
                                f"OOMKilled on pod {pod.namespace}/{pod.name} "
                                f"(container: {cs.name})"
                            ),
                            description=(
                                f"Container '{cs.name}' was terminated with OOMKilled "
                                f"(exit code {oom_state.exit_code}). "
                                f"Restart count: {cs.restart_count}."
                                + (
                                    f" Memory limit: {memory_limit}."
                                    if memory_limit
                                    else ""
                                )
                            ),
                            evidence={
                                "container": cs.name,
                                "termination_reason": oom_state.reason,
                                "exit_code": oom_state.exit_code,
                                "restart_count": cs.restart_count,
                                "memory_limit": memory_limit,
                                "finished_at": (
                                    oom_state.finished_at.isoformat()
                                    if oom_state.finished_at
                                    else None
                                ),
                            },
                        )
                    )

        return anomalies

    def _is_oom(self, cs: ContainerStatusSnapshot) -> bool:
        """Check if a container was OOM-killed (current or last state)."""
        # Check current state
        if cs.state.state == "terminated" and cs.state.reason == "OOMKilled":
            return True
        if cs.state.state == "terminated" and cs.state.exit_code == 137:
            return True

        # Check last state (container may have restarted already)
        if cs.last_state.reason == "OOMKilled":
            return True
        if (
            cs.last_state.state == "terminated"
            and cs.last_state.exit_code == 137
        ):
            return True

        return False
