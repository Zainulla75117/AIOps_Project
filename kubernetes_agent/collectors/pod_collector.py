"""Pod collector — queries K8s API for pod state and normalizes into PodSnapshot models."""

from __future__ import annotations

from kubernetes.client import ApiException

from kubernetes_agent.collectors.base import BaseCollector
from kubernetes_agent.models.snapshot import (
    ContainerStateSnapshot,
    ContainerStatusSnapshot,
    PodConditionSnapshot,
    PodResourceSnapshot,
    PodSnapshot,
    ResourceValues,
)
from kubernetes_agent.utils.logging import get_logger
from kubernetes_agent.utils.retry import retry_sync

logger = get_logger(__name__)


class PodCollector(BaseCollector):
    """Collects pod state from the Kubernetes API."""

    @retry_sync(max_attempts=3, exceptions=(ApiException,))
    def collect(self, namespaces: list[str]) -> list[PodSnapshot]:
        """Collect pods from specific namespaces."""
        pods: list[PodSnapshot] = []
        for ns in namespaces:
            try:
                result = self.k8s.core_v1.list_namespaced_pod(namespace=ns)
                for item in result.items:
                    pods.append(self._to_snapshot(item))
            except ApiException as exc:
                if exc.status == 403:
                    logger.warning("pod_collect_forbidden", namespace=ns)
                    continue
                raise
        logger.info("pods_collected", count=len(pods), namespaces=namespaces)
        return pods

    def collect_all(self) -> list[PodSnapshot]:
        """Collect pods from all namespaces."""
        result = self.k8s.core_v1.list_pod_for_all_namespaces()
        pods = [self._to_snapshot(item) for item in result.items]
        logger.info("pods_collected_all", count=len(pods))
        return pods

    @retry_sync(max_attempts=3, exceptions=(ApiException,))
    def get_pod_logs(self, namespace: str, pod_name: str, tail_lines: int = 50) -> str:
        """Fetch recent logs for a specific pod (all containers)."""
        try:
            # We fetch logs for all containers in the pod, combining them
            # if there are multiple, but the python client requires specifying the container
            # or it defaults to the first one. For simplicity, we just grab the default.
            logs = self.k8s.core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=tail_lines,
                timestamps=True,
            )
            return logs
        except ApiException as exc:
            logger.warning("pod_log_fetch_failed", namespace=namespace, pod=pod_name, error=str(exc))
            return f"<Error fetching logs: {exc.reason}>"

    # ---- Internal helpers -------------------------------------------------

    def _to_snapshot(self, pod) -> PodSnapshot:
        """Convert a V1Pod API object to a PodSnapshot."""
        meta = pod.metadata
        status = pod.status
        spec = pod.spec

        # Owner reference
        owner_kind = None
        owner_name = None
        if meta.owner_references:
            owner = meta.owner_references[0]
            owner_kind = owner.kind
            owner_name = owner.name

        # Container statuses
        container_statuses = self._extract_container_statuses(
            status.container_statuses
        )
        init_container_statuses = self._extract_container_statuses(
            status.init_container_statuses
        )

        # Conditions
        conditions = []
        if status.conditions:
            for cond in status.conditions:
                conditions.append(
                    PodConditionSnapshot(
                        type=cond.type,
                        status=cond.status or "Unknown",
                        reason=cond.reason,
                        message=cond.message,
                        last_transition_time=cond.last_transition_time,
                    )
                )

        # Resource requests/limits per container
        resources = {}
        if spec.containers:
            for container in spec.containers:
                res = container.resources
                if res:
                    resources[container.name] = PodResourceSnapshot(
                        requests=ResourceValues(
                            cpu=self._get_resource(res.requests, "cpu"),
                            memory=self._get_resource(res.requests, "memory"),
                        ),
                        limits=ResourceValues(
                            cpu=self._get_resource(res.limits, "cpu"),
                            memory=self._get_resource(res.limits, "memory"),
                        ),
                    )

        return PodSnapshot(
            name=meta.name,
            namespace=meta.namespace,
            phase=status.phase or "Unknown",
            node_name=spec.node_name,
            qos_class=status.qos_class,
            creation_timestamp=meta.creation_timestamp,
            deletion_timestamp=meta.deletion_timestamp,
            owner_kind=owner_kind,
            owner_name=owner_name,
            labels=meta.labels or {},
            container_statuses=container_statuses,
            init_container_statuses=init_container_statuses,
            conditions=conditions,
            resources=resources,
            status_reason=status.reason,
            status_message=status.message,
        )

    def _extract_container_statuses(
        self, statuses: list | None
    ) -> list[ContainerStatusSnapshot]:
        """Convert V1ContainerStatus list to ContainerStatusSnapshot list."""
        if not statuses:
            return []

        result = []
        for cs in statuses:
            state = self._extract_state(cs.state)
            last_state = self._extract_state(cs.last_state)
            result.append(
                ContainerStatusSnapshot(
                    name=cs.name,
                    image=cs.image or "",
                    ready=cs.ready or False,
                    restart_count=cs.restart_count or 0,
                    state=state,
                    last_state=last_state,
                )
            )
        return result

    def _extract_state(self, state) -> ContainerStateSnapshot:
        """Extract running/waiting/terminated state into a flat model."""
        if state is None:
            return ContainerStateSnapshot()

        if state.running:
            return ContainerStateSnapshot(
                state="running",
                started_at=state.running.started_at,
            )
        elif state.waiting:
            return ContainerStateSnapshot(
                state="waiting",
                reason=state.waiting.reason,
                message=state.waiting.message,
            )
        elif state.terminated:
            t = state.terminated
            return ContainerStateSnapshot(
                state="terminated",
                reason=t.reason,
                message=t.message,
                exit_code=t.exit_code,
                started_at=t.started_at,
                finished_at=t.finished_at,
            )
        return ContainerStateSnapshot()

    def _get_resource(self, resource_dict: dict | None, key: str) -> str | None:
        """Safely get a resource value from a dict."""
        if resource_dict and key in resource_dict:
            return str(resource_dict[key])
        return None
