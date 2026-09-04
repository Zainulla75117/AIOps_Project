"""Failed deployment detector.

Detects deployments that are unable to roll out successfully.
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


class FailedDeploymentDetector(BaseDetector):
    """Detects deployments that have failed to progress."""

    @property
    def anomaly_type(self) -> AnomalyType:
        return AnomalyType.FAILED_DEPLOYMENT

    def detect(self, snapshot: ClusterSnapshot) -> list[DetectedAnomaly]:
        anomalies: list[DetectedAnomaly] = []

        for deploy in snapshot.deployments:
            # Check for ReplicaFailure condition
            has_replica_failure = any(
                c.type == "ReplicaFailure" and c.status == "True"
                for c in deploy.conditions
            )
            
            # Check for Progressing condition == False (rollout failed)
            progressing_failed = any(
                c.type == "Progressing" and c.status == "False"
                for c in deploy.conditions
            )
            
            if has_replica_failure or progressing_failed:
                # Find the reason/message
                reason = "Unknown"
                message = "Deployment failed to progress or create replicas."
                
                for c in deploy.conditions:
                    if (c.type == "ReplicaFailure" and c.status == "True") or \
                       (c.type == "Progressing" and c.status == "False"):
                        if c.reason: reason = c.reason
                        if c.message: message = c.message
                        break

                anomalies.append(
                    DetectedAnomaly(
                        anomaly_type=self.anomaly_type,
                        severity=Severity.CRITICAL,
                        resource=AffectedResource(
                            kind="Deployment",
                            name=deploy.name,
                            namespace=deploy.namespace,
                        ),
                        title=f"Failed rollout for deployment {deploy.namespace}/{deploy.name}",
                        description=f"Deployment '{deploy.name}' has failed to roll out. Reason: {reason}.",
                        evidence={
                            "replicas": deploy.replicas,
                            "ready_replicas": deploy.ready_replicas,
                            "unavailable_replicas": deploy.unavailable_replicas,
                            "condition_reason": reason,
                            "condition_message": message,
                        },
                    )
                )

        return anomalies
