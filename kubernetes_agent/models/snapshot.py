"""Cluster state snapshot models.

These models represent a normalized, point-in-time view of Kubernetes resources.
Each collector produces one of these snapshot types, and the ClusterSnapshot
aggregates them into a single coherent view used by the detection layer.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Container state models
# ---------------------------------------------------------------------------

class ContainerStateSnapshot(BaseModel):
    """Normalized representation of a container's current or last state."""

    state: str = "unknown"  # "running", "waiting", "terminated", "unknown"
    reason: str | None = None  # e.g. "CrashLoopBackOff", "OOMKilled"
    message: str | None = None
    exit_code: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ContainerStatusSnapshot(BaseModel):
    """Status of a single container within a pod."""

    name: str
    image: str = ""
    ready: bool = False
    restart_count: int = 0
    state: ContainerStateSnapshot = Field(default_factory=ContainerStateSnapshot)
    last_state: ContainerStateSnapshot = Field(default_factory=ContainerStateSnapshot)


# ---------------------------------------------------------------------------
# Pod models
# ---------------------------------------------------------------------------

class PodConditionSnapshot(BaseModel):
    """A single condition on a pod (Ready, Initialized, etc.)."""

    type: str
    status: str  # "True", "False", "Unknown"
    reason: str | None = None
    message: str | None = None
    last_transition_time: datetime | None = None


class ResourceValues(BaseModel):
    """CPU and memory resource values."""

    cpu: str | None = None
    memory: str | None = None


class PodResourceSnapshot(BaseModel):
    """Resource requests and limits for a pod container."""

    requests: ResourceValues = Field(default_factory=ResourceValues)
    limits: ResourceValues = Field(default_factory=ResourceValues)


class PodSnapshot(BaseModel):
    """Normalized snapshot of a Kubernetes Pod."""

    name: str
    namespace: str
    phase: str = "Unknown"  # Running, Pending, Succeeded, Failed, Unknown
    node_name: str | None = None
    qos_class: str | None = None  # Guaranteed, Burstable, BestEffort
    creation_timestamp: datetime | None = None
    deletion_timestamp: datetime | None = None

    # Owner reference (usually a ReplicaSet or Job)
    owner_kind: str | None = None
    owner_name: str | None = None

    labels: dict[str, str] = Field(default_factory=dict)
    container_statuses: list[ContainerStatusSnapshot] = Field(default_factory=list)
    init_container_statuses: list[ContainerStatusSnapshot] = Field(default_factory=list)
    conditions: list[PodConditionSnapshot] = Field(default_factory=list)
    resources: dict[str, PodResourceSnapshot] = Field(default_factory=dict)

    # Status reason (e.g. "Evicted")
    status_reason: str | None = None
    status_message: str | None = None

    @property
    def total_restarts(self) -> int:
        """Sum of restart counts across all containers."""
        return sum(c.restart_count for c in self.container_statuses)

    @property
    def is_ready(self) -> bool:
        """Whether all containers are ready."""
        if not self.container_statuses:
            return False
        return all(c.ready for c in self.container_statuses)


# ---------------------------------------------------------------------------
# Deployment models
# ---------------------------------------------------------------------------

class DeploymentConditionSnapshot(BaseModel):
    """A single condition on a deployment."""

    type: str  # Available, Progressing, ReplicaFailure
    status: str  # "True", "False", "Unknown"
    reason: str | None = None
    message: str | None = None
    last_transition_time: datetime | None = None


class DeploymentSnapshot(BaseModel):
    """Normalized snapshot of a Kubernetes Deployment."""

    name: str
    namespace: str
    replicas: int = 0
    ready_replicas: int = 0
    available_replicas: int = 0
    unavailable_replicas: int = 0
    updated_replicas: int = 0
    strategy: str | None = None  # RollingUpdate, Recreate
    creation_timestamp: datetime | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    conditions: list[DeploymentConditionSnapshot] = Field(default_factory=list)

    @property
    def is_available(self) -> bool:
        """Whether the deployment has the Available condition True."""
        return any(
            c.type == "Available" and c.status == "True" for c in self.conditions
        )

    @property
    def is_progressing(self) -> bool:
        """Whether the deployment is currently rolling out."""
        return any(
            c.type == "Progressing" and c.status == "True" for c in self.conditions
        )


# ---------------------------------------------------------------------------
# Service models
# ---------------------------------------------------------------------------

class ServiceSnapshot(BaseModel):
    """Normalized snapshot of a Kubernetes Service."""

    name: str
    namespace: str
    type: str = "ClusterIP"  # ClusterIP, NodePort, LoadBalancer, ExternalName
    cluster_ip: str | None = None
    ports: list[dict] = Field(default_factory=list)
    selector: dict[str, str] = Field(default_factory=dict)
    creation_timestamp: datetime | None = None
    labels: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Node models
# ---------------------------------------------------------------------------

class NodeConditionSnapshot(BaseModel):
    """A single condition on a node (Ready, MemoryPressure, etc.)."""

    type: str
    status: str  # "True", "False", "Unknown"
    reason: str | None = None
    message: str | None = None
    last_transition_time: datetime | None = None


class NodeSnapshot(BaseModel):
    """Normalized snapshot of a Kubernetes Node."""

    name: str
    labels: dict[str, str] = Field(default_factory=dict)
    conditions: list[NodeConditionSnapshot] = Field(default_factory=list)

    # Capacity
    capacity_cpu: str | None = None
    capacity_memory: str | None = None
    capacity_pods: str | None = None

    # Allocatable
    allocatable_cpu: str | None = None
    allocatable_memory: str | None = None
    allocatable_pods: str | None = None

    # Info
    kubelet_version: str | None = None
    os_image: str | None = None
    container_runtime: str | None = None

    unschedulable: bool = False
    taints: list[dict] = Field(default_factory=list)
    creation_timestamp: datetime | None = None

    @property
    def is_ready(self) -> bool:
        return any(
            c.type == "Ready" and c.status == "True" for c in self.conditions
        )

    @property
    def has_memory_pressure(self) -> bool:
        return any(
            c.type == "MemoryPressure" and c.status == "True" for c in self.conditions
        )

    @property
    def has_disk_pressure(self) -> bool:
        return any(
            c.type == "DiskPressure" and c.status == "True" for c in self.conditions
        )

    @property
    def has_pid_pressure(self) -> bool:
        return any(
            c.type == "PIDPressure" and c.status == "True" for c in self.conditions
        )


# ---------------------------------------------------------------------------
# Event models
# ---------------------------------------------------------------------------

class EventSnapshot(BaseModel):
    """Normalized snapshot of a Kubernetes Event."""

    name: str
    namespace: str
    type: str = "Normal"  # Normal, Warning
    reason: str = ""
    message: str = ""
    count: int = 1

    # The resource this event is about
    involved_kind: str = ""
    involved_name: str = ""
    involved_namespace: str = ""

    source_component: str | None = None
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None


# ---------------------------------------------------------------------------
# Aggregate cluster snapshot
# ---------------------------------------------------------------------------

class ClusterSnapshot(BaseModel):
    """Complete point-in-time view of the cluster state.

    This is the primary input to the detection layer. One of these is
    produced per scan cycle by aggregating all collector outputs.
    """

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    pods: list[PodSnapshot] = Field(default_factory=list)
    deployments: list[DeploymentSnapshot] = Field(default_factory=list)
    services: list[ServiceSnapshot] = Field(default_factory=list)
    nodes: list[NodeSnapshot] = Field(default_factory=list)
    events: list[EventSnapshot] = Field(default_factory=list)

    # Metadata
    namespaces_scanned: list[str] = Field(default_factory=list)
    scan_duration_ms: float = 0.0
    errors: list[str] = Field(default_factory=list)
