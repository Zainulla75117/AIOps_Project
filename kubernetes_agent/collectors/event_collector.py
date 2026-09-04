"""Event collector — queries K8s API for cluster events."""

from __future__ import annotations

from kubernetes.client import ApiException

from kubernetes_agent.collectors.base import BaseCollector
from kubernetes_agent.models.snapshot import EventSnapshot
from kubernetes_agent.utils.logging import get_logger
from kubernetes_agent.utils.retry import retry_sync

logger = get_logger(__name__)


class EventCollector(BaseCollector):
    """Collects Kubernetes events (primarily Warning type)."""

    @retry_sync(max_attempts=3, exceptions=(ApiException,))
    def collect(self, namespaces: list[str]) -> list[EventSnapshot]:
        events: list[EventSnapshot] = []
        for ns in namespaces:
            try:
                result = self.k8s.core_v1.list_namespaced_event(namespace=ns)
                for item in result.items:
                    events.append(self._to_snapshot(item))
            except ApiException as exc:
                if exc.status == 403:
                    logger.warning("event_collect_forbidden", namespace=ns)
                    continue
                raise
        logger.info("events_collected", count=len(events), namespaces=namespaces)
        return events

    def collect_all(self) -> list[EventSnapshot]:
        result = self.k8s.core_v1.list_event_for_all_namespaces()
        events = [self._to_snapshot(item) for item in result.items]
        logger.info("events_collected_all", count=len(events))
        return events

    def collect_for_resource(
        self, namespace: str, resource_name: str
    ) -> list[EventSnapshot]:
        """Collect events related to a specific resource."""
        field_selector = f"involvedObject.name={resource_name}"
        try:
            result = self.k8s.core_v1.list_namespaced_event(
                namespace=namespace,
                field_selector=field_selector,
            )
            return [self._to_snapshot(item) for item in result.items]
        except ApiException as exc:
            logger.warning(
                "event_collect_for_resource_failed",
                namespace=namespace,
                resource=resource_name,
                error=str(exc),
            )
            return []

    def _to_snapshot(self, event) -> EventSnapshot:
        meta = event.metadata
        involved = event.involved_object

        return EventSnapshot(
            name=meta.name,
            namespace=meta.namespace or "",
            type=event.type or "Normal",
            reason=event.reason or "",
            message=event.message or "",
            count=event.count or 1,
            involved_kind=involved.kind or "" if involved else "",
            involved_name=involved.name or "" if involved else "",
            involved_namespace=involved.namespace or "" if involved else "",
            source_component=(
                event.source.component if event.source else None
            ),
            first_timestamp=event.first_timestamp,
            last_timestamp=event.last_timestamp,
        )
