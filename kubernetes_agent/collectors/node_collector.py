"""Node collector — queries K8s API for node state."""

from __future__ import annotations

from kubernetes.client import ApiException

from kubernetes_agent.collectors.base import BaseCollector
from kubernetes_agent.models.snapshot import NodeConditionSnapshot, NodeSnapshot
from kubernetes_agent.utils.logging import get_logger
from kubernetes_agent.utils.retry import retry_sync

logger = get_logger(__name__)


class NodeCollector(BaseCollector):
    """Collects node state from the Kubernetes API."""

    def collect(self, namespaces: list[str]) -> list[NodeSnapshot]:
        """Nodes are cluster-scoped — namespaces parameter is ignored."""
        return self.collect_all()

    @retry_sync(max_attempts=3, exceptions=(ApiException,))
    def collect_all(self) -> list[NodeSnapshot]:
        result = self.k8s.core_v1.list_node()
        nodes = [self._to_snapshot(item) for item in result.items]
        logger.info("nodes_collected", count=len(nodes))
        return nodes

    def _to_snapshot(self, node) -> NodeSnapshot:
        meta = node.metadata
        status = node.status
        spec = node.spec

        conditions = []
        if status.conditions:
            for cond in status.conditions:
                conditions.append(
                    NodeConditionSnapshot(
                        type=cond.type,
                        status=cond.status or "Unknown",
                        reason=cond.reason,
                        message=cond.message,
                        last_transition_time=cond.last_transition_time,
                    )
                )

        capacity = status.capacity or {}
        allocatable = status.allocatable or {}

        taints = []
        if spec.taints:
            for taint in spec.taints:
                taints.append({
                    "key": taint.key,
                    "value": taint.value,
                    "effect": taint.effect,
                })

        node_info = status.node_info

        return NodeSnapshot(
            name=meta.name,
            labels=meta.labels or {},
            conditions=conditions,
            capacity_cpu=capacity.get("cpu"),
            capacity_memory=capacity.get("memory"),
            capacity_pods=capacity.get("pods"),
            allocatable_cpu=allocatable.get("cpu"),
            allocatable_memory=allocatable.get("memory"),
            allocatable_pods=allocatable.get("pods"),
            kubelet_version=node_info.kubelet_version if node_info else None,
            os_image=node_info.os_image if node_info else None,
            container_runtime=node_info.container_runtime_version if node_info else None,
            unschedulable=spec.unschedulable or False,
            taints=taints,
            creation_timestamp=meta.creation_timestamp,
        )
