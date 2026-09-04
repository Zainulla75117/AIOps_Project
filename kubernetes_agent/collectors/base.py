"""Base collector interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from kubernetes_agent.utils.k8s_client import K8sClient
from kubernetes_agent.utils.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


class BaseCollector(ABC):
    """Abstract base class for Kubernetes resource collectors.

    Each collector is responsible for querying the K8s API for a specific
    resource type and returning a list of normalized snapshot models.
    """

    def __init__(self, k8s_client: K8sClient) -> None:
        self.k8s = k8s_client

    @abstractmethod
    def collect(self, namespaces: list[str]) -> list:
        """Collect resources from the given namespaces.

        Args:
            namespaces: List of namespace names to collect from.

        Returns:
            List of snapshot models for the collected resources.
        """
        ...

    @abstractmethod
    def collect_all(self) -> list:
        """Collect resources from all namespaces."""
        ...
