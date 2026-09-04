"""Kubernetes API client wrapper.

Thin wrapper around the official ``kubernetes`` Python client that handles
in-cluster vs. kubeconfig loading and provides typed accessors for the
API groups we use.
"""

from __future__ import annotations

from kubernetes import client, config as k8s_config
from kubernetes.client import ApiException

from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)


class K8sClient:
    """Wrapper around the official Kubernetes Python client.

    Handles configuration loading (in-cluster or kubeconfig) and exposes
    the API objects the collectors need.  All operations are **read-only**.
    """

    def __init__(self, cfg: AgentConfig | None = None) -> None:
        self._cfg = cfg or get_config()
        self._api_client: client.ApiClient | None = None
        self._core_v1: client.CoreV1Api | None = None
        self._apps_v1: client.AppsV1Api | None = None
        self._batch_v1: client.BatchV1Api | None = None

    # ---- Lifecycle --------------------------------------------------------

    def connect(self) -> None:
        """Load K8s configuration and create API clients."""
        if self._cfg.k8s_in_cluster:
            logger.info("k8s_connect", mode="in_cluster")
            k8s_config.load_incluster_config()
        else:
            kubeconfig = self._cfg.k8s_kubeconfig
            logger.info("k8s_connect", mode="kubeconfig", path=kubeconfig)
            k8s_config.load_kube_config(config_file=kubeconfig)

        self._api_client = client.ApiClient()
        self._core_v1 = client.CoreV1Api(self._api_client)
        self._apps_v1 = client.AppsV1Api(self._api_client)
        self._batch_v1 = client.BatchV1Api(self._api_client)
        logger.info("k8s_connected")

    def close(self) -> None:
        """Close the underlying API client."""
        if self._api_client:
            self._api_client.close()
            logger.info("k8s_disconnected")

    # ---- API accessors (lazy-init safe) -----------------------------------

    @property
    def core_v1(self) -> client.CoreV1Api:
        if self._core_v1 is None:
            self.connect()
        assert self._core_v1 is not None
        return self._core_v1

    @property
    def apps_v1(self) -> client.AppsV1Api:
        if self._apps_v1 is None:
            self.connect()
        assert self._apps_v1 is not None
        return self._apps_v1

    @property
    def batch_v1(self) -> client.BatchV1Api:
        if self._batch_v1 is None:
            self.connect()
        assert self._batch_v1 is not None
        return self._batch_v1

    # ---- Health check -----------------------------------------------------

    def is_reachable(self) -> bool:
        """Return True if the K8s API server responds to a version check."""
        try:
            version_api = client.VersionApi(self._api_client)
            version_api.get_code()
            return True
        except Exception as exc:
            logger.warning("k8s_unreachable", error=str(exc))
            return False


# Module-level singleton
_client: K8sClient | None = None


def get_k8s_client() -> K8sClient:
    """Return the global K8sClient singleton."""
    global _client
    if _client is None:
        _client = K8sClient()
        _client.connect()
    return _client


def reset_k8s_client() -> None:
    """Reset the singleton (for tests)."""
    global _client
    if _client:
        _client.close()
    _client = None
