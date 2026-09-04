"""Log collector — retrieves container logs via the K8s API."""

from __future__ import annotations

from kubernetes.client import ApiException

from kubernetes_agent.collectors.base import BaseCollector
from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.utils.logging import get_logger
from kubernetes_agent.utils.retry import retry_sync

logger = get_logger(__name__)


class LogCollector(BaseCollector):
    """Collects application/container logs from pods.

    Uses ``read_namespaced_pod_log`` to retrieve logs.  Supports fetching
    current and previous container instance logs.
    """

    def __init__(self, k8s_client, cfg: AgentConfig | None = None) -> None:
        super().__init__(k8s_client)
        self._cfg = cfg or get_config()

    def collect(self, namespaces: list[str]) -> list:
        """Not used for logs — use collect_pod_logs instead."""
        return []

    def collect_all(self) -> list:
        """Not used for logs — use collect_pod_logs instead."""
        return []

    def collect_pod_logs(
        self,
        pod_name: str,
        namespace: str,
        *,
        container: str | None = None,
        previous: bool = False,
        tail_lines: int | None = None,
        since_seconds: int | None = None,
    ) -> str:
        """Retrieve logs from a specific pod/container.

        Args:
            pod_name: Name of the pod.
            namespace: Namespace the pod is in.
            container: Specific container name (None = default container).
            previous: If True, get logs from the previously terminated instance.
            tail_lines: Number of lines from the end (default from config).
            since_seconds: Only return logs newer than this (default from config).

        Returns:
            Log text as a string.  Empty string if logs are unavailable.
        """
        tail = tail_lines or self._cfg.log_tail_lines
        since = since_seconds or self._cfg.log_since_seconds

        try:
            logs = self._read_logs(
                pod_name=pod_name,
                namespace=namespace,
                container=container,
                previous=previous,
                tail_lines=tail,
                since_seconds=since,
            )

            # Truncate to max bytes
            if len(logs.encode("utf-8", errors="replace")) > self._cfg.log_max_bytes:
                logs = logs[-self._cfg.log_max_bytes:]
                logs = "[truncated]\n" + logs

            logger.debug(
                "logs_collected",
                pod=pod_name,
                namespace=namespace,
                container=container,
                previous=previous,
                bytes=len(logs),
            )
            return logs

        except ApiException as exc:
            if exc.status == 404:
                logger.debug("pod_not_found_for_logs", pod=pod_name, namespace=namespace)
            elif exc.status == 400 and previous:
                # No previous container logs available
                logger.debug("no_previous_logs", pod=pod_name, namespace=namespace)
            else:
                logger.warning(
                    "log_collection_failed",
                    pod=pod_name,
                    namespace=namespace,
                    status=exc.status,
                    error=str(exc),
                )
            return ""

    def collect_all_container_logs(
        self,
        pod_name: str,
        namespace: str,
        container_names: list[str],
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Collect current and previous logs for all containers in a pod.

        Returns:
            Tuple of (current_logs, previous_logs) dicts keyed by container name.
        """
        current: dict[str, str] = {}
        previous: dict[str, str] = {}

        for container in container_names:
            current[container] = self.collect_pod_logs(
                pod_name=pod_name,
                namespace=namespace,
                container=container,
                previous=False,
            )
            prev_logs = self.collect_pod_logs(
                pod_name=pod_name,
                namespace=namespace,
                container=container,
                previous=True,
            )
            if prev_logs:
                previous[container] = prev_logs

        return current, previous

    @retry_sync(max_attempts=2, base_delay=0.5, exceptions=(ApiException,))
    def _read_logs(
        self,
        pod_name: str,
        namespace: str,
        container: str | None,
        previous: bool,
        tail_lines: int,
        since_seconds: int,
    ) -> str:
        """Low-level API call to read pod logs."""
        kwargs: dict = {
            "name": pod_name,
            "namespace": namespace,
            "tail_lines": tail_lines,
            "since_seconds": since_seconds,
            "timestamps": True,
            "previous": previous,
        }
        if container:
            kwargs["container"] = container

        return self.k8s.core_v1.read_namespaced_pod_log(**kwargs)
