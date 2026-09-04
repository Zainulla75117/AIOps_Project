"""Evidence builder — collects contextual data for an anomaly."""

from __future__ import annotations

from kubernetes_agent.collectors.event_collector import EventCollector
from kubernetes_agent.collectors.log_collector import LogCollector
from kubernetes_agent.models.anomaly import DetectedAnomaly
from kubernetes_agent.models.evidence import EventSummary, EvidencePackage
from kubernetes_agent.models.snapshot import ClusterSnapshot, PodSnapshot
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)


class EvidenceBuilder:
    """Builds a complete EvidencePackage for a detected anomaly."""

    def __init__(
        self,
        event_collector: EventCollector,
        log_collector: LogCollector,
    ) -> None:
        self._events = event_collector
        self._logs = log_collector

    def build(
        self, anomaly: DetectedAnomaly, snapshot: ClusterSnapshot
    ) -> EvidencePackage:
        """Assemble all relevant evidence for the given anomaly."""
        logger.info(
            "building_evidence",
            anomaly_type=anomaly.anomaly_type.value,
            resource=f"{anomaly.resource.namespace}/{anomaly.resource.name}",
        )

        package = EvidencePackage(anomaly=anomaly)

        # 1. Attach relevant Pod snapshots
        self._attach_pod_context(package, snapshot)

        # 2. Collect related Events
        self._collect_events(package)

        # 3. Collect Logs (if applicable)
        self._collect_logs(package)

        # 4. Extract resource info
        self._extract_resource_info(package)

        return package

    def _attach_pod_context(
        self, package: EvidencePackage, snapshot: ClusterSnapshot
    ) -> None:
        """Attach the PodSnapshot(s) related to the anomaly."""
        res = package.anomaly.resource
        
        if res.kind == "Pod":
            for pod in snapshot.pods:
                if pod.name == res.name and pod.namespace == res.namespace:
                    package.pod_snapshots.append(pod)
                    break
                    
        elif res.kind == "Deployment":
            # For deployments, find pods owned by it (simplified for now,
            # proper check requires matching replicaset owner refs)
            for pod in snapshot.pods:
                if pod.namespace == res.namespace and pod.name.startswith(res.name + "-"):
                    package.pod_snapshots.append(pod)

    def _collect_events(self, package: EvidencePackage) -> None:
        """Collect Kubernetes events for the resource."""
        res = package.anomaly.resource
        
        try:
            events = self._events.collect_for_resource(
                namespace=res.namespace,
                resource_name=res.name,
            )
            
            # Summarize events
            for e in events:
                # We mostly care about Warnings, but keep Normal if it's recent
                if e.type == "Warning" or "Started" in e.reason or "Created" in e.reason:
                    package.related_events.append(
                        EventSummary(
                            type=e.type,
                            reason=e.reason,
                            message=e.message,
                            count=e.count,
                            source=e.source_component,
                            first_seen=e.first_timestamp,
                            last_seen=e.last_timestamp,
                        )
                    )
        except Exception as exc:
            package.collection_errors.append(f"Event collection failed: {exc}")

    def _collect_logs(self, package: EvidencePackage) -> None:
        """Collect logs for relevant containers."""
        # Only collect logs for Pod anomalies where a specific container is implicated,
        # or for all containers if no specific one is identified.
        if not package.pod_snapshots:
            return
            
        pod = package.pod_snapshots[0]
        target_containers = []
        
        # If the anomaly specifically named a container in evidence, use that
        if "container" in package.anomaly.evidence:
            target_containers = [package.anomaly.evidence["container"]]
        else:
            # Otherwise grab logs for all containers
            target_containers = [c.name for c in pod.container_statuses]
            
        current_logs, previous_logs = self._logs.collect_all_container_logs(
            pod_name=pod.name,
            namespace=pod.namespace,
            container_names=target_containers,
        )
        
        package.logs = current_logs
        package.previous_logs = previous_logs

    def _extract_resource_info(self, package: EvidencePackage) -> None:
        """Extract resource requests/limits into a simple structure."""
        if not package.pod_snapshots:
            return
            
        pod = package.pod_snapshots[0]
        if not pod.resources:
            return
            
        for container, res in pod.resources.items():
            package.resource_info[container] = {
                "requests": res.requests.model_dump(),
                "limits": res.limits.model_dump(),
            }
