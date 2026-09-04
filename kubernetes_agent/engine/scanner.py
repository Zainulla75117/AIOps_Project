"""Periodic cluster scanner.

Coordinates the collection of cluster state, anomaly detection, and
triggers investigations for new anomalies. Persists scan results
and incident lifecycle to MongoDB.
"""

from __future__ import annotations

import asyncio
import datetime

from kubernetes_agent.collectors.deployment_collector import DeploymentCollector
from kubernetes_agent.collectors.node_collector import NodeCollector
from kubernetes_agent.collectors.pod_collector import PodCollector
from kubernetes_agent.collectors.service_collector import ServiceCollector
from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.db.repositories import IncidentRepository, ScanRepository
from kubernetes_agent.detectors.registry import DetectorRegistry
from kubernetes_agent.engine.investigation import InvestigationEngine
from kubernetes_agent.models.incident import IncidentReport
from kubernetes_agent.models.snapshot import ClusterSnapshot
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)


class Scanner:
    """Orchestrates periodic cluster health scans."""

    def __init__(
        self,
        pod_collector: PodCollector,
        deployment_collector: DeploymentCollector,
        service_collector: ServiceCollector,
        node_collector: NodeCollector,
        registry: DetectorRegistry,
        investigator: InvestigationEngine,
        cfg: AgentConfig | None = None,
        scan_repo: ScanRepository | None = None,
        incident_repo: IncidentRepository | None = None,
    ) -> None:
        self._pods = pod_collector
        self._deployments = deployment_collector
        self._services = service_collector
        self._nodes = node_collector
        
        self._registry = registry
        self._investigator = investigator
        self._cfg = cfg or get_config()
        
        # MongoDB repositories (optional — degrades gracefully)
        self._scan_repo = scan_repo
        self._incident_repo = incident_repo
        
        self._active_incidents: dict[str, IncidentReport] = {}
        
        # Statistics
        self.total_scans = 0
        self.last_scan_at: datetime.datetime | None = None
        self.last_scan_duration_ms: float | None = None

    @property
    def active_incidents(self) -> list[IncidentReport]:
        """Return list of currently active incidents."""
        return list(self._active_incidents.values())

    async def scan(self, namespaces: list[str]) -> list[IncidentReport]:
        """Perform a single scan cycle across the given namespaces.
        
        Returns:
            List of newly created or updated IncidentReports from this scan.
        """
        start_time = datetime.datetime.utcnow()
        self.total_scans += 1
        
        logger.info("scan_started", namespaces=namespaces, scan_id=self.total_scans)
        
        # 1. Collect State
        snapshot = self._collect_snapshot(namespaces)
        
        # 2. Detect Anomalies
        anomalies = self._registry.run_all(snapshot)
        
        # 3. Investigate
        new_incidents: list[IncidentReport] = []
        current_incident_keys = set()
        
        for anomaly in anomalies:
            key = anomaly.dedup_key
            current_incident_keys.add(key)
            
            if key not in self._active_incidents:
                # New anomaly detected! Investigate it.
                incident = await self._investigator.investigate(anomaly, snapshot)
                incident.scan_id = str(self.total_scans)
                self._active_incidents[key] = incident
                new_incidents.append(incident)
                
                # Persist to MongoDB
                await self._persist_incident(incident)
            else:
                # We already know about this issue.
                # In a more advanced implementation, we would update the existing
                # incident with new observations here.
                pass
                
        # 4. Resolve cleared incidents
        # If we didn't see an anomaly this scan, but we had an active incident for it,
        # it might have recovered (e.g. pod finally restarted successfully).
        resolved_keys = set(self._active_incidents.keys()) - current_incident_keys
        for key in resolved_keys:
            logger.info("incident_resolved", dedup_key=key)
            resolved_incident = self._active_incidents.pop(key)
            # Update MongoDB with resolved status
            await self._resolve_incident(resolved_incident.id)
            
        end_time = datetime.datetime.utcnow()
        self.last_scan_at = end_time
        self.last_scan_duration_ms = (end_time - start_time).total_seconds() * 1000
        snapshot.scan_duration_ms = self.last_scan_duration_ms
        
        logger.info(
            "scan_completed", 
            duration_ms=self.last_scan_duration_ms,
            anomalies_found=len(anomalies),
            new_incidents=len(new_incidents),
            active_incidents=len(self._active_incidents)
        )
        
        # 5. Persist scan summary to MongoDB
        await self._persist_scan(snapshot, anomalies, new_incidents)
        
        return new_incidents

    def _collect_snapshot(self, namespaces: list[str]) -> ClusterSnapshot:
        """Synchronously collect all resource snapshots."""
        snapshot = ClusterSnapshot(namespaces_scanned=namespaces)
        
        try:
            # We run these synchronously for simplicity, but could use ThreadPoolExecutor
            # if API latency becomes a bottleneck.
            snapshot.pods = self._pods.collect(namespaces)
            snapshot.deployments = self._deployments.collect(namespaces)
            snapshot.services = self._services.collect(namespaces)
            snapshot.nodes = self._nodes.collect_all() # Nodes are cluster-scoped
        except Exception as exc:
            logger.error("snapshot_collection_failed", error=str(exc))
            snapshot.errors.append(str(exc))
            
        return snapshot

    async def _persist_scan(
        self,
        snapshot: ClusterSnapshot,
        anomalies: list,
        new_incidents: list[IncidentReport],
    ) -> None:
        """Save scan summary to MongoDB."""
        if not self._scan_repo:
            return

        pods_running = sum(1 for p in snapshot.pods if p.phase == "Running")
        pods_pending = sum(1 for p in snapshot.pods if p.phase == "Pending")
        pods_failed = sum(1 for p in snapshot.pods if p.phase == "Failed")
        nodes_ready = sum(1 for n in snapshot.nodes if n.is_ready)
        deployments_healthy = sum(1 for d in snapshot.deployments if d.is_available)

        scan_data = {
            "scan_id": self.total_scans,
            "timestamp": self.last_scan_at,
            "duration_ms": self.last_scan_duration_ms,
            "namespaces_scanned": snapshot.namespaces_scanned,
            "counts": {
                "pods": len(snapshot.pods),
                "pods_running": pods_running,
                "pods_pending": pods_pending,
                "pods_failed": pods_failed,
                "nodes": len(snapshot.nodes),
                "nodes_ready": nodes_ready,
                "deployments": len(snapshot.deployments),
                "deployments_healthy": deployments_healthy,
                "services": len(snapshot.services),
            },
            "anomalies_detected": len(anomalies),
            "incidents_created": len(new_incidents),
            "active_incidents": len(self._active_incidents),
        }

        try:
            await self._scan_repo.save_scan(scan_data)
        except Exception as exc:
            logger.warning("scan_persist_failed", error=str(exc))

    async def _persist_incident(self, incident: IncidentReport) -> None:
        """Save a new incident to MongoDB."""
        if not self._incident_repo:
            return

        try:
            incident_data = incident.model_dump(mode="json")
            await self._incident_repo.save_incident(incident_data)
        except Exception as exc:
            logger.warning("incident_persist_failed", error=str(exc))

    async def _resolve_incident(self, incident_id: str) -> None:
        """Mark an incident as resolved in MongoDB."""
        if not self._incident_repo:
            return

        try:
            await self._incident_repo.resolve_incident(incident_id)
        except Exception as exc:
            logger.warning("incident_resolve_persist_failed", error=str(exc))
