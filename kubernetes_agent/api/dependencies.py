"""FastAPI Dependency Injection setup.

Provides access to application singletons (config, scanner, k8s client,
MongoDB repositories, collectors) for API routes.
"""

from __future__ import annotations

from typing import Generator

from kubernetes_agent.api.namespace_manager import NamespaceManager
from kubernetes_agent.collectors.deployment_collector import DeploymentCollector
from kubernetes_agent.collectors.event_collector import EventCollector
from kubernetes_agent.collectors.node_collector import NodeCollector
from kubernetes_agent.collectors.pod_collector import PodCollector
from kubernetes_agent.collectors.service_collector import ServiceCollector
from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.db.mongo_client import MongoClient
from kubernetes_agent.db.repositories import ChatRepository, IncidentRepository, ScanRepository
from kubernetes_agent.engine.scanner import Scanner
from kubernetes_agent.utils.k8s_client import K8sClient, get_k8s_client


# These will be set during application startup in main.py
_scanner_instance: Scanner | None = None
_namespace_manager_instance: NamespaceManager | None = None
_mongo_instance: MongoClient | None = None

# Collector instances
_pod_collector: PodCollector | None = None
_deployment_collector: DeploymentCollector | None = None
_service_collector: ServiceCollector | None = None
_node_collector: NodeCollector | None = None
_event_collector: EventCollector | None = None

# Repository instances (created lazily from mongo)
_chat_repo: ChatRepository | None = None
_incident_repo: IncidentRepository | None = None
_scan_repo: ScanRepository | None = None


# ---- Setters (called during startup) ----

def set_scanner(scanner: Scanner) -> None:
    """Set the global scanner instance for dependency injection."""
    global _scanner_instance
    _scanner_instance = scanner


def set_namespace_manager(manager: NamespaceManager) -> None:
    """Set the global namespace manager for dependency injection."""
    global _namespace_manager_instance
    _namespace_manager_instance = manager


def set_mongo(mongo: MongoClient) -> None:
    """Set the MongoDB client and create repository instances."""
    global _mongo_instance, _chat_repo, _incident_repo, _scan_repo
    _mongo_instance = mongo
    _chat_repo = ChatRepository(mongo)
    _incident_repo = IncidentRepository(mongo)
    _scan_repo = ScanRepository(mongo)


def set_collectors(
    pods: PodCollector,
    deployments: DeploymentCollector,
    services: ServiceCollector,
    nodes: NodeCollector,
    events: EventCollector,
) -> None:
    """Set collector instances for dependency injection."""
    global _pod_collector, _deployment_collector, _service_collector
    global _node_collector, _event_collector
    _pod_collector = pods
    _deployment_collector = deployments
    _service_collector = services
    _node_collector = nodes
    _event_collector = events


# ---- FastAPI Dependencies ----

def get_agent_config() -> AgentConfig:
    """FastAPI dependency: get application config."""
    return get_config()


def get_k8s() -> K8sClient:
    """FastAPI dependency: get Kubernetes client."""
    return get_k8s_client()


def get_scanner() -> Scanner:
    """FastAPI dependency: get the active Scanner instance."""
    if _scanner_instance is None:
        raise RuntimeError("Scanner not initialized. Is the app running?")
    return _scanner_instance


def get_namespaces() -> NamespaceManager:
    """FastAPI dependency: get the NamespaceManager instance."""
    if _namespace_manager_instance is None:
        raise RuntimeError("NamespaceManager not initialized.")
    return _namespace_manager_instance


def get_mongo() -> MongoClient:
    """FastAPI dependency: get the MongoDB client."""
    if _mongo_instance is None:
        raise RuntimeError("MongoClient not initialized.")
    return _mongo_instance


def get_chat_repo() -> ChatRepository:
    """FastAPI dependency: get the ChatRepository."""
    if _chat_repo is None:
        raise RuntimeError("ChatRepository not initialized.")
    return _chat_repo


def get_incident_repo() -> IncidentRepository:
    """FastAPI dependency: get the IncidentRepository."""
    if _incident_repo is None:
        raise RuntimeError("IncidentRepository not initialized.")
    return _incident_repo


def get_scan_repo() -> ScanRepository:
    """FastAPI dependency: get the ScanRepository."""
    if _scan_repo is None:
        raise RuntimeError("ScanRepository not initialized.")
    return _scan_repo


def get_pod_collector() -> PodCollector:
    """FastAPI dependency: get the PodCollector."""
    if _pod_collector is None:
        raise RuntimeError("PodCollector not initialized.")
    return _pod_collector


def get_deployment_collector() -> DeploymentCollector:
    """FastAPI dependency: get the DeploymentCollector."""
    if _deployment_collector is None:
        raise RuntimeError("DeploymentCollector not initialized.")
    return _deployment_collector


def get_service_collector() -> ServiceCollector:
    """FastAPI dependency: get the ServiceCollector."""
    if _service_collector is None:
        raise RuntimeError("ServiceCollector not initialized.")
    return _service_collector


def get_node_collector() -> NodeCollector:
    """FastAPI dependency: get the NodeCollector."""
    if _node_collector is None:
        raise RuntimeError("NodeCollector not initialized.")
    return _node_collector


def get_event_collector() -> EventCollector:
    """FastAPI dependency: get the EventCollector."""
    if _event_collector is None:
        raise RuntimeError("EventCollector not initialized.")
    return _event_collector
