"""ImagePullBackOff / ErrImagePull detector.

Detects containers unable to pull their container image.
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

_IMAGE_PULL_REASONS = {"ImagePullBackOff", "ErrImagePull", "ErrImageNeverPull"}


class ImagePullDetector(BaseDetector):
    """Detects containers with image pull failures."""

    @property
    def anomaly_type(self) -> AnomalyType:
        return AnomalyType.IMAGE_PULL_ERROR

    def detect(self, snapshot: ClusterSnapshot) -> list[DetectedAnomaly]:
        anomalies: list[DetectedAnomaly] = []

        for pod in snapshot.pods:
            for cs in pod.container_statuses:
                if (
                    cs.state.state == "waiting"
                    and cs.state.reason in _IMAGE_PULL_REASONS
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
                                f"ImagePullBackOff on pod {pod.namespace}/{pod.name} "
                                f"(container: {cs.name})"
                            ),
                            description=(
                                f"Container '{cs.name}' cannot pull image '{cs.image}'. "
                                f"Reason: {cs.state.reason}. "
                                f"Message: {cs.state.message or 'none'}."
                            ),
                            evidence={
                                "container": cs.name,
                                "image": cs.image,
                                "waiting_reason": cs.state.reason,
                                "waiting_message": cs.state.message,
                            },
                        )
                    )

            # Also check init containers
            for cs in pod.init_container_statuses:
                if (
                    cs.state.state == "waiting"
                    and cs.state.reason in _IMAGE_PULL_REASONS
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
                                f"ImagePullBackOff on pod {pod.namespace}/{pod.name} "
                                f"(init container: {cs.name})"
                            ),
                            description=(
                                f"Init container '{cs.name}' cannot pull image "
                                f"'{cs.image}'. Reason: {cs.state.reason}."
                            ),
                            evidence={
                                "container": cs.name,
                                "is_init_container": True,
                                "image": cs.image,
                                "waiting_reason": cs.state.reason,
                                "waiting_message": cs.state.message,
                            },
                        )
                    )

        return anomalies
