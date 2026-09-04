"""Deployment collector — queries K8s API for deployment state."""

from __future__ import annotations

from kubernetes.client import ApiException

from kubernetes_agent.collectors.base import BaseCollector
from kubernetes_agent.models.snapshot import (
    DeploymentConditionSnapshot,
    DeploymentSnapshot,
)
from kubernetes_agent.utils.logging import get_logger
from kubernetes_agent.utils.retry import retry_sync

logger = get_logger(__name__)


class DeploymentCollector(BaseCollector):
    """Collects deployment state from the Kubernetes API."""

    @retry_sync(max_attempts=3, exceptions=(ApiException,))
    def collect(self, namespaces: list[str]) -> list[DeploymentSnapshot]:
        deployments: list[DeploymentSnapshot] = []
        for ns in namespaces:
            try:
                result = self.k8s.apps_v1.list_namespaced_deployment(namespace=ns)
                for item in result.items:
                    deployments.append(self._to_snapshot(item))
            except ApiException as exc:
                if exc.status == 403:
                    logger.warning("deployment_collect_forbidden", namespace=ns)
                    continue
                raise
        logger.info("deployments_collected", count=len(deployments), namespaces=namespaces)
        return deployments

    def collect_all(self) -> list[DeploymentSnapshot]:
        result = self.k8s.apps_v1.list_deployment_for_all_namespaces()
        deployments = [self._to_snapshot(item) for item in result.items]
        logger.info("deployments_collected_all", count=len(deployments))
        return deployments

    def _to_snapshot(self, deployment) -> DeploymentSnapshot:
        meta = deployment.metadata
        spec = deployment.spec
        status = deployment.status

        conditions = []
        if status.conditions:
            for cond in status.conditions:
                conditions.append(
                    DeploymentConditionSnapshot(
                        type=cond.type,
                        status=cond.status or "Unknown",
                        reason=cond.reason,
                        message=cond.message,
                        last_transition_time=cond.last_transition_time,
                    )
                )

        strategy = None
        if spec.strategy:
            strategy = spec.strategy.type

        return DeploymentSnapshot(
            name=meta.name,
            namespace=meta.namespace,
            replicas=spec.replicas or 0,
            ready_replicas=status.ready_replicas or 0,
            available_replicas=status.available_replicas or 0,
            unavailable_replicas=status.unavailable_replicas or 0,
            updated_replicas=status.updated_replicas or 0,
            strategy=strategy,
            creation_timestamp=meta.creation_timestamp,
            labels=meta.labels or {},
            conditions=conditions,
        )
