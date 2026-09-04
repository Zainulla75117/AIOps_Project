"""Service collector — queries K8s API for service state."""

from __future__ import annotations

from kubernetes.client import ApiException

from kubernetes_agent.collectors.base import BaseCollector
from kubernetes_agent.models.snapshot import ServiceSnapshot
from kubernetes_agent.utils.logging import get_logger
from kubernetes_agent.utils.retry import retry_sync

logger = get_logger(__name__)


class ServiceCollector(BaseCollector):
    """Collects service state from the Kubernetes API."""

    @retry_sync(max_attempts=3, exceptions=(ApiException,))
    def collect(self, namespaces: list[str]) -> list[ServiceSnapshot]:
        services: list[ServiceSnapshot] = []
        for ns in namespaces:
            try:
                result = self.k8s.core_v1.list_namespaced_service(namespace=ns)
                for item in result.items:
                    services.append(self._to_snapshot(item))
            except ApiException as exc:
                if exc.status == 403:
                    logger.warning("service_collect_forbidden", namespace=ns)
                    continue
                raise
        logger.info("services_collected", count=len(services), namespaces=namespaces)
        return services

    def collect_all(self) -> list[ServiceSnapshot]:
        result = self.k8s.core_v1.list_service_for_all_namespaces()
        services = [self._to_snapshot(item) for item in result.items]
        logger.info("services_collected_all", count=len(services))
        return services

    def _to_snapshot(self, service) -> ServiceSnapshot:
        meta = service.metadata
        spec = service.spec

        ports = []
        if spec.ports:
            for port in spec.ports:
                ports.append({
                    "name": port.name,
                    "port": port.port,
                    "target_port": str(port.target_port) if port.target_port else None,
                    "protocol": port.protocol,
                    "node_port": port.node_port,
                })

        return ServiceSnapshot(
            name=meta.name,
            namespace=meta.namespace,
            type=spec.type or "ClusterIP",
            cluster_ip=spec.cluster_ip,
            ports=ports,
            selector=spec.selector or {},
            creation_timestamp=meta.creation_timestamp,
            labels=meta.labels or {},
        )
