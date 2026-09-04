"""Node pressure detector.

Detects memory/disk/pid pressure conditions on nodes.
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


class NodePressureDetector(BaseDetector):
    """Detects nodes experiencing resource pressure."""

    @property
    def anomaly_type(self) -> AnomalyType:
        return AnomalyType.NODE_PRESSURE

    def detect(self, snapshot: ClusterSnapshot) -> list[DetectedAnomaly]:
        anomalies: list[DetectedAnomaly] = []
        
        pressure_types = ["MemoryPressure", "DiskPressure", "PIDPressure"]

        for node in snapshot.nodes:
            for cond in node.conditions:
                if cond.type in pressure_types and cond.status == "True":
                    anomalies.append(
                        DetectedAnomaly(
                            anomaly_type=self.anomaly_type,
                            severity=Severity.WARNING,
                            resource=AffectedResource(
                                kind="Node",
                                name=node.name,
                                namespace="",  # Nodes are cluster-scoped
                            ),
                            title=f"{cond.type} on node {node.name}",
                            description=f"Node '{node.name}' is experiencing {cond.type}. Reason: {cond.reason or 'unknown'}.",
                            evidence={
                                "pressure_type": cond.type,
                                "reason": cond.reason,
                                "message": cond.message,
                                "unschedulable": node.unschedulable,
                            },
                        )
                    )

        return anomalies
