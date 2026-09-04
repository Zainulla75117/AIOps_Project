"""Detector registry — discovers and runs all detectors."""

from __future__ import annotations

from kubernetes_agent.detectors.base import BaseDetector
from kubernetes_agent.detectors.crash_loop import CrashLoopDetector
from kubernetes_agent.detectors.image_pull import ImagePullDetector
from kubernetes_agent.detectors.oom_killed import OOMKilledDetector
from kubernetes_agent.detectors.restart_rate import RestartRateDetector
from kubernetes_agent.detectors.failed_deployment import FailedDeploymentDetector
from kubernetes_agent.detectors.pending_pod import PendingPodDetector
from kubernetes_agent.detectors.node_pressure import NodePressureDetector
from kubernetes_agent.models.anomaly import DetectedAnomaly
from kubernetes_agent.models.snapshot import ClusterSnapshot
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)


class DetectorRegistry:
    """Manages and runs all anomaly detectors.

    Detectors are registered at construction time.  New detectors can also
    be added dynamically via ``register()``.
    """

    def __init__(self) -> None:
        self._detectors: list[BaseDetector] = []
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register all built-in detectors."""
        self.register(CrashLoopDetector())
        self.register(OOMKilledDetector())
        self.register(ImagePullDetector())
        self.register(RestartRateDetector())
        self.register(FailedDeploymentDetector())
        self.register(PendingPodDetector())
        self.register(NodePressureDetector())

    def register(self, detector: BaseDetector) -> None:
        """Add a detector to the registry."""
        self._detectors.append(detector)
        logger.debug("detector_registered", name=detector.name)

    def run_all(self, snapshot: ClusterSnapshot) -> list[DetectedAnomaly]:
        """Run every registered detector against the snapshot.

        Returns:
            De-duplicated list of all detected anomalies, sorted by severity.
        """
        all_anomalies: list[DetectedAnomaly] = []
        seen_keys: set[str] = set()

        for detector in self._detectors:
            try:
                anomalies = detector.detect(snapshot)
                for anomaly in anomalies:
                    if anomaly.dedup_key not in seen_keys:
                        seen_keys.add(anomaly.dedup_key)
                        all_anomalies.append(anomaly)
                logger.debug(
                    "detector_run",
                    detector=detector.name,
                    found=len(anomalies),
                )
            except Exception as exc:
                logger.error(
                    "detector_failed",
                    detector=detector.name,
                    error=str(exc),
                )

        # Sort: critical first, then warning, then info
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        all_anomalies.sort(key=lambda a: severity_order.get(a.severity.value, 9))

        logger.info(
            "detection_complete",
            total_anomalies=len(all_anomalies),
            detectors_run=len(self._detectors),
        )
        return all_anomalies

    @property
    def detectors(self) -> list[BaseDetector]:
        """List of registered detectors."""
        return list(self._detectors)
