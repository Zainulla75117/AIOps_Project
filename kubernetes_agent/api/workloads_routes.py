"""Workloads API routes — live K8s resource data for the dashboard.

All endpoints scope to enabled (monitored) namespaces only,
except nodes which are cluster-wide.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends

from kubernetes_agent.api.dependencies import (
    get_deployment_collector,
    get_event_collector,
    get_namespaces,
    get_node_collector,
    get_pod_collector,
    get_service_collector,
)
from kubernetes_agent.api.namespace_manager import NamespaceManager
from kubernetes_agent.collectors.deployment_collector import DeploymentCollector
from kubernetes_agent.collectors.event_collector import EventCollector
from kubernetes_agent.collectors.node_collector import NodeCollector
from kubernetes_agent.collectors.pod_collector import PodCollector
from kubernetes_agent.collectors.service_collector import ServiceCollector

router = APIRouter(prefix="/workloads", tags=["Workloads"])


def _snapshot_to_dict(obj: Any) -> dict:
    """Convert a Pydantic model to a JSON-serializable dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return dict(obj)


@router.get("/summary")
async def get_workloads_summary(
    ns_manager: NamespaceManager = Depends(get_namespaces),
    pods_coll: PodCollector = Depends(get_pod_collector),
    nodes_coll: NodeCollector = Depends(get_node_collector),
    deps_coll: DeploymentCollector = Depends(get_deployment_collector),
    svcs_coll: ServiceCollector = Depends(get_service_collector),
    events_coll: EventCollector = Depends(get_event_collector),
):
    """Aggregate workload counts and health stats."""
    namespaces = ns_manager.get_monitored_namespaces()

    # Run all collectors in threads to avoid blocking the event loop
    pods, nodes, deployments, services, events = await asyncio.gather(
        asyncio.to_thread(pods_coll.collect, namespaces),
        asyncio.to_thread(nodes_coll.collect_all),
        asyncio.to_thread(deps_coll.collect, namespaces),
        asyncio.to_thread(svcs_coll.collect, namespaces),
        asyncio.to_thread(events_coll.collect, namespaces),
    )

    pods_running = sum(1 for p in pods if p.phase == "Running")
    pods_pending = sum(1 for p in pods if p.phase == "Pending")
    pods_failed = sum(1 for p in pods if p.phase == "Failed")
    pods_succeeded = sum(1 for p in pods if p.phase == "Succeeded")

    nodes_ready = sum(1 for n in nodes if n.is_ready)
    nodes_not_ready = len(nodes) - nodes_ready

    deployments_healthy = sum(1 for d in deployments if d.is_available)
    deployments_unhealthy = len(deployments) - deployments_healthy

    events_warning = sum(1 for e in events if e.type == "Warning")
    events_normal = sum(1 for e in events if e.type == "Normal")

    return {
        "namespaces_monitored": namespaces,
        "pods": {
            "total": len(pods),
            "running": pods_running,
            "pending": pods_pending,
            "failed": pods_failed,
            "succeeded": pods_succeeded,
        },
        "nodes": {
            "total": len(nodes),
            "ready": nodes_ready,
            "not_ready": nodes_not_ready,
        },
        "deployments": {
            "total": len(deployments),
            "healthy": deployments_healthy,
            "unhealthy": deployments_unhealthy,
        },
        "services": {
            "total": len(services),
        },
        "events": {
            "total": len(events),
            "warning": events_warning,
            "normal": events_normal,
        },
    }


@router.get("/nodes")
async def get_nodes(
    nodes_coll: NodeCollector = Depends(get_node_collector),
):
    """Get all cluster nodes (cluster-scoped, not namespace-filtered)."""
    nodes = await asyncio.to_thread(nodes_coll.collect_all)
    return [_snapshot_to_dict(n) for n in nodes]


@router.get("/pods")
async def get_pods(
    ns_manager: NamespaceManager = Depends(get_namespaces),
    pods_coll: PodCollector = Depends(get_pod_collector),
):
    """Get pods from monitored namespaces."""
    namespaces = ns_manager.get_monitored_namespaces()
    pods = await asyncio.to_thread(pods_coll.collect, namespaces)
    return [_snapshot_to_dict(p) for p in pods]


@router.get("/deployments")
async def get_deployments(
    ns_manager: NamespaceManager = Depends(get_namespaces),
    deps_coll: DeploymentCollector = Depends(get_deployment_collector),
):
    """Get deployments from monitored namespaces."""
    namespaces = ns_manager.get_monitored_namespaces()
    deployments = await asyncio.to_thread(deps_coll.collect, namespaces)
    return [_snapshot_to_dict(d) for d in deployments]


@router.get("/services")
async def get_services(
    ns_manager: NamespaceManager = Depends(get_namespaces),
    svcs_coll: ServiceCollector = Depends(get_service_collector),
):
    """Get services from monitored namespaces."""
    namespaces = ns_manager.get_monitored_namespaces()
    services = await asyncio.to_thread(svcs_coll.collect, namespaces)
    return [_snapshot_to_dict(s) for s in services]


@router.get("/events")
async def get_events(
    ns_manager: NamespaceManager = Depends(get_namespaces),
    events_coll: EventCollector = Depends(get_event_collector),
    limit: int = 100,
):
    """Get recent events from monitored namespaces. Warnings pinned to top."""
    namespaces = ns_manager.get_monitored_namespaces()
    events = await asyncio.to_thread(events_coll.collect, namespaces)

    # Sort: Warning events first, then by last_timestamp descending
    events.sort(
        key=lambda e: (
            0 if e.type == "Warning" else 1,
            -(e.last_timestamp.timestamp() if e.last_timestamp else 0),
        )
    )

    return [_snapshot_to_dict(e) for e in events[:limit]]


@router.get("/pods/{namespace}/{pod_name}/logs")
async def get_pod_logs(
    namespace: str,
    pod_name: str,
    tail_lines: int = 50,
    pods_coll: PodCollector = Depends(get_pod_collector),
):
    """Get secure, masked logs for a specific pod."""
    from kubernetes_agent.utils.security import mask_sensitive_data
    
    # We fetch logs in a background thread because it's a blocking K8s API call
    raw_logs = await asyncio.to_thread(
        pods_coll.get_pod_logs, namespace, pod_name, tail_lines
    )
    
    # Apply security scrubbing before returning
    masked_logs = mask_sensitive_data(raw_logs)
    
    return {"namespace": namespace, "pod_name": pod_name, "logs": masked_logs}

