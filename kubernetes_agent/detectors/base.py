"""Base detector interface.

Every detector is a pure function:
    Detector(ClusterSnapshot) → list[DetectedAnomaly]

Detectors must never call the K8s API directly.  They operate only
on the snapshot data provided to them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from kubernetes_agent.models.anomaly import AnomalyType, DetectedAnomaly
from kubernetes_agent.models.snapshot import ClusterSnapshot


class BaseDetector(ABC):
    """Abstract base class for anomaly detectors."""

    @abstractmethod
    def detect(self, snapshot: ClusterSnapshot) -> list[DetectedAnomaly]:
        """Analyse a cluster snapshot and return detected anomalies.

        Args:
            snapshot: Point-in-time view of cluster state.

        Returns:
            List of anomalies found.  Empty list if nothing detected.
        """
        ...

    @property
    @abstractmethod
    def anomaly_type(self) -> AnomalyType:
        """The primary anomaly type this detector identifies."""
        ...

    @property
    def name(self) -> str:
        """Human-readable detector name."""
        return self.__class__.__name__
