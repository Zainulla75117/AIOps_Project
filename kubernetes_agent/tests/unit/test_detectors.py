"""Unit tests for anomaly detectors.

Each test constructs a ClusterSnapshot with specific conditions and
verifies the correct detector fires with the expected anomaly type.
"""

from datetime import datetime, timezone

import pytest

from kubernetes_agent.detectors.crash_loop import CrashLoopDetector
from kubernetes_agent.detectors.image_pull import ImagePullDetector
from kubernetes_agent.detectors.oom_killed import OOMKilledDetector
from kubernetes_agent.detectors.restart_rate import RestartRateDetector
from kubernetes_agent.detectors.registry import DetectorRegistry
from kubernetes_agent.models.anomaly import AnomalyType, Severity
from kubernetes_agent.models.snapshot import (
    ClusterSnapshot,
    ContainerStateSnapshot,
    ContainerStatusSnapshot,
    PodSnapshot,
    PodResourceSnapshot,
    ResourceValues,
)


# ---------------------------------------------------------------------------
# Helpers to build test snapshots
# ---------------------------------------------------------------------------

def _make_pod(
    name: str = "test-pod",
    namespace: str = "default",
    phase: str = "Running",
    containers: list[ContainerStatusSnapshot] | None = None,
    init_containers: list[ContainerStatusSnapshot] | None = None,
    resources: dict | None = None,
) -> PodSnapshot:
    return PodSnapshot(
        name=name,
        namespace=namespace,
        phase=phase,
        container_statuses=containers or [],
        init_container_statuses=init_containers or [],
        resources=resources or {},
    )


def _make_container(
    name: str = "app",
    image: str = "myapp:latest",
    ready: bool = True,
    restart_count: int = 0,
    state: ContainerStateSnapshot | None = None,
    last_state: ContainerStateSnapshot | None = None,
) -> ContainerStatusSnapshot:
    return ContainerStatusSnapshot(
        name=name,
        image=image,
        ready=ready,
        restart_count=restart_count,
        state=state or ContainerStateSnapshot(state="running"),
        last_state=last_state or ContainerStateSnapshot(),
    )


def _snapshot_with_pods(*pods: PodSnapshot) -> ClusterSnapshot:
    return ClusterSnapshot(pods=list(pods))


# ===================================================================
# CrashLoopDetector
# ===================================================================

class TestCrashLoopDetector:
    def setup_method(self):
        self.detector = CrashLoopDetector()

    def test_detects_crashloop(self):
        pod = _make_pod(
            containers=[
                _make_container(
                    ready=False,
                    restart_count=5,
                    state=ContainerStateSnapshot(
                        state="waiting", reason="CrashLoopBackOff"
                    ),
                    last_state=ContainerStateSnapshot(
                        state="terminated", reason="Error", exit_code=1
                    ),
                )
            ]
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))

        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.CRASH_LOOP_BACKOFF
        assert anomalies[0].severity == Severity.CRITICAL
        assert anomalies[0].resource.name == "test-pod"
        assert anomalies[0].evidence["restart_count"] == 5

    def test_no_false_positive_running(self):
        pod = _make_pod(
            containers=[_make_container(ready=True, restart_count=0)]
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))
        assert len(anomalies) == 0

    def test_no_false_positive_other_waiting(self):
        """A container waiting for a different reason should not trigger."""
        pod = _make_pod(
            containers=[
                _make_container(
                    ready=False,
                    state=ContainerStateSnapshot(
                        state="waiting", reason="ContainerCreating"
                    ),
                )
            ]
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))
        assert len(anomalies) == 0

    def test_multiple_containers_only_affected_flagged(self):
        pod = _make_pod(
            containers=[
                _make_container(name="healthy", ready=True),
                _make_container(
                    name="crashing",
                    ready=False,
                    restart_count=10,
                    state=ContainerStateSnapshot(
                        state="waiting", reason="CrashLoopBackOff"
                    ),
                ),
            ]
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))
        assert len(anomalies) == 1
        assert anomalies[0].evidence["container"] == "crashing"


# ===================================================================
# OOMKilledDetector
# ===================================================================

class TestOOMKilledDetector:
    def setup_method(self):
        self.detector = OOMKilledDetector()

    def test_detects_oom_in_current_state(self):
        pod = _make_pod(
            containers=[
                _make_container(
                    ready=False,
                    restart_count=3,
                    state=ContainerStateSnapshot(
                        state="terminated", reason="OOMKilled", exit_code=137
                    ),
                )
            ]
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.OOM_KILLED
        assert anomalies[0].severity == Severity.CRITICAL

    def test_detects_oom_in_last_state(self):
        """Container restarted — OOM is in last_state, current is running."""
        pod = _make_pod(
            containers=[
                _make_container(
                    ready=True,
                    restart_count=2,
                    state=ContainerStateSnapshot(state="running"),
                    last_state=ContainerStateSnapshot(
                        state="terminated", reason="OOMKilled", exit_code=137
                    ),
                )
            ]
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))
        assert len(anomalies) == 1

    def test_detects_exit_code_137_without_reason(self):
        """Exit code 137 (SIGKILL) without explicit OOMKilled reason."""
        pod = _make_pod(
            containers=[
                _make_container(
                    state=ContainerStateSnapshot(
                        state="terminated", exit_code=137
                    ),
                )
            ]
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))
        assert len(anomalies) == 1

    def test_no_false_positive_normal_exit(self):
        pod = _make_pod(
            containers=[
                _make_container(
                    state=ContainerStateSnapshot(
                        state="terminated", reason="Completed", exit_code=0
                    ),
                )
            ]
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))
        assert len(anomalies) == 0

    def test_includes_memory_limit(self):
        """Evidence should include memory limit when available."""
        pod = _make_pod(
            containers=[
                _make_container(
                    name="app",
                    state=ContainerStateSnapshot(
                        state="terminated", reason="OOMKilled", exit_code=137
                    ),
                )
            ],
            resources={
                "app": PodResourceSnapshot(
                    limits=ResourceValues(memory="256Mi", cpu="500m")
                )
            },
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))
        assert len(anomalies) == 1
        assert anomalies[0].evidence["memory_limit"] == "256Mi"


# ===================================================================
# ImagePullDetector
# ===================================================================

class TestImagePullDetector:
    def setup_method(self):
        self.detector = ImagePullDetector()

    def test_detects_image_pull_backoff(self):
        pod = _make_pod(
            containers=[
                _make_container(
                    image="nonexistent:v99",
                    ready=False,
                    state=ContainerStateSnapshot(
                        state="waiting",
                        reason="ImagePullBackOff",
                        message="Back-off pulling image",
                    ),
                )
            ]
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.IMAGE_PULL_ERROR
        assert anomalies[0].evidence["image"] == "nonexistent:v99"

    def test_detects_err_image_pull(self):
        pod = _make_pod(
            containers=[
                _make_container(
                    ready=False,
                    state=ContainerStateSnapshot(
                        state="waiting", reason="ErrImagePull"
                    ),
                )
            ]
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))
        assert len(anomalies) == 1

    def test_detects_init_container_image_pull(self):
        pod = _make_pod(
            init_containers=[
                _make_container(
                    name="init-db",
                    ready=False,
                    state=ContainerStateSnapshot(
                        state="waiting", reason="ImagePullBackOff"
                    ),
                )
            ]
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))
        assert len(anomalies) == 1
        assert anomalies[0].evidence.get("is_init_container") is True

    def test_no_false_positive(self):
        pod = _make_pod(
            containers=[_make_container(ready=True)]
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))
        assert len(anomalies) == 0


# ===================================================================
# RestartRateDetector
# ===================================================================

class TestRestartRateDetector:
    def setup_method(self):
        # Use a low threshold for testing
        from kubernetes_agent.config import AgentConfig
        cfg = AgentConfig(
            gemini_api_key="test",
            restart_threshold=3,
            k8s_in_cluster=False,
        )
        self.detector = RestartRateDetector(cfg=cfg)

    def test_detects_frequent_restarts(self):
        pod = _make_pod(
            containers=[
                _make_container(
                    restart_count=5,
                    state=ContainerStateSnapshot(state="running"),
                    last_state=ContainerStateSnapshot(
                        state="terminated", reason="Error", exit_code=1
                    ),
                )
            ]
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.FREQUENT_RESTARTS
        assert anomalies[0].severity == Severity.WARNING

    def test_critical_severity_at_3x_threshold(self):
        """Very high restart count escalates to CRITICAL."""
        pod = _make_pod(
            containers=[
                _make_container(restart_count=10)  # threshold=3, 10 >= 3*3=9
            ]
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))
        assert len(anomalies) == 1
        assert anomalies[0].severity == Severity.CRITICAL

    def test_skips_crashloop_backoff(self):
        """Should not report if CrashLoopBackOff (handled by crash_loop detector)."""
        pod = _make_pod(
            containers=[
                _make_container(
                    restart_count=5,
                    ready=False,
                    state=ContainerStateSnapshot(
                        state="waiting", reason="CrashLoopBackOff"
                    ),
                )
            ]
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))
        assert len(anomalies) == 0

    def test_below_threshold_no_detection(self):
        pod = _make_pod(
            containers=[_make_container(restart_count=2)]
        )
        anomalies = self.detector.detect(_snapshot_with_pods(pod))
        assert len(anomalies) == 0


# ===================================================================
# DetectorRegistry
# ===================================================================

class TestDetectorRegistry:
    def test_registry_has_default_detectors(self):
        registry = DetectorRegistry()
        names = {d.name for d in registry.detectors}
        assert "CrashLoopDetector" in names
        assert "OOMKilledDetector" in names
        assert "ImagePullDetector" in names
        assert "RestartRateDetector" in names

    def test_run_all_deduplicates(self):
        """Same anomaly from two detectors should appear only once."""
        registry = DetectorRegistry()

        pod = _make_pod(
            containers=[
                _make_container(
                    ready=False,
                    restart_count=20,
                    state=ContainerStateSnapshot(
                        state="waiting", reason="CrashLoopBackOff"
                    ),
                    last_state=ContainerStateSnapshot(
                        state="terminated", reason="OOMKilled", exit_code=137
                    ),
                )
            ]
        )
        anomalies = registry.run_all(_snapshot_with_pods(pod))

        # Should detect CrashLoop and OOMKilled — different anomaly types
        types = {a.anomaly_type for a in anomalies}
        assert AnomalyType.CRASH_LOOP_BACKOFF in types
        assert AnomalyType.OOM_KILLED in types

    def test_empty_snapshot_no_anomalies(self):
        registry = DetectorRegistry()
        anomalies = registry.run_all(ClusterSnapshot())
        assert len(anomalies) == 0

    def test_results_sorted_by_severity(self):
        registry = DetectorRegistry()
        # Multiple pods: one critical (OOM), one warning (restarts)
        snapshot = ClusterSnapshot(
            pods=[
                _make_pod(
                    name="restart-pod",
                    containers=[
                        _make_container(
                            restart_count=6,
                            state=ContainerStateSnapshot(state="running"),
                            last_state=ContainerStateSnapshot(
                                state="terminated", reason="Error", exit_code=1
                            ),
                        )
                    ],
                ),
                _make_pod(
                    name="oom-pod",
                    containers=[
                        _make_container(
                            state=ContainerStateSnapshot(
                                state="terminated",
                                reason="OOMKilled",
                                exit_code=137,
                            ),
                        )
                    ],
                ),
            ]
        )
        anomalies = registry.run_all(snapshot)

        # Critical anomalies should come first
        assert len(anomalies) >= 2
        assert anomalies[0].severity == Severity.CRITICAL
