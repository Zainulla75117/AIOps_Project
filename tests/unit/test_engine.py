"""Unit tests for the investigation engine and Gemini provider."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kubernetes_agent.analysis.correlator import MultiSignalCorrelator
from kubernetes_agent.analysis.gemini_provider import GeminiProvider
from kubernetes_agent.analysis.log_analyzer import LogAnalyzer
from kubernetes_agent.analysis.sanitizer import LogSanitizer
from kubernetes_agent.config import AgentConfig
from kubernetes_agent.engine.evidence_builder import EvidenceBuilder
from kubernetes_agent.engine.investigation import InvestigationEngine
from kubernetes_agent.models.anomaly import AffectedResource, AnomalyType, DetectedAnomaly, Severity
from kubernetes_agent.models.incident import IncidentStatus, RiskLevel
from kubernetes_agent.models.snapshot import ClusterSnapshot, PodSnapshot


@pytest.fixture
def mock_gemini():
    """Mock Gemini provider that returns a fixed JSON response."""
    provider = MagicMock(spec=GeminiProvider)
    provider.is_available.return_value = True
    
    # We mock analyze to just return a dummy response based on the schema requested
    async def mock_analyze(system_instruction, prompt, schema=None):
        if schema.__name__ == "LLMLogAnalysis":
            return schema(
                patterns=[{"pattern": "test error", "count": 1, "severity": "error", "sample_lines": ["error 123"]}],
                summary="Logs show a test error.",
                likely_root_cause="Test root cause",
            )
        elif schema.__name__ == "LLMCorrelationAnalysis":
            return schema(
                what_went_wrong="Something went wrong during test.",
                inferences=["Test inference"],
                root_cause={
                    "category": "test_category",
                    "description": "Test description",
                    "confidence": 0.9,
                    "reasoning": "Test reasoning"
                },
                recommendation={
                    "action": "Fix it",
                    "rationale": "Because it is broken",
                    "commands": ["kubectl test"],
                    "risk_level": "low",
                    "requires_restart": False,
                    "additional_investigation": []
                }
            )
        return {}
        
    provider.analyze = AsyncMock(side_effect=mock_analyze)
    return provider


@pytest.fixture
def investigation_engine(mock_gemini):
    """Investigation engine wired up with mocks."""
    cfg = AgentConfig(gemini_api_key="test")
    sanitizer = LogSanitizer(cfg)
    
    log_analyzer = LogAnalyzer(mock_gemini, sanitizer, cfg)
    correlator = MultiSignalCorrelator(mock_gemini)
    
    # Mock builder to return an empty evidence package
    builder = MagicMock(spec=EvidenceBuilder)
    
    def mock_build(anomaly, snapshot):
        from kubernetes_agent.models.evidence import EvidencePackage
        pkg = EvidencePackage(anomaly=anomaly)
        pkg.logs = {"app": "Some error happened"}
        return pkg
        
    builder.build.side_effect = mock_build
    
    return InvestigationEngine(builder, log_analyzer, correlator)


@pytest.mark.asyncio
async def test_investigation_flow(investigation_engine):
    """Test that the engine successfully orchestrates the full pipeline."""
    anomaly = DetectedAnomaly(
        anomaly_type=AnomalyType.CRASH_LOOP_BACKOFF,
        severity=Severity.CRITICAL,
        resource=AffectedResource(kind="Pod", name="test-pod", namespace="default"),
        title="Test crash",
        description="Container is crashing",
    )
    
    snapshot = ClusterSnapshot()
    
    # Run investigation
    report = await investigation_engine.investigate(anomaly, snapshot)
    
    # Verify report structure
    assert report is not None
    assert report.status == IncidentStatus.OPEN
    assert report.severity == Severity.CRITICAL
    assert report.what_went_wrong == "Something went wrong during test."
    
    # Verify correlation mapped correctly
    assert report.root_cause.category == "test_category"
    assert report.root_cause.confidence == 0.9
    
    assert report.recommendation.action == "Fix it"
    assert report.recommendation.risk_level == RiskLevel.LOW
    
    # Verify evidence summary
    assert "events_analyzed" in report.evidence_summary
    assert "log_patterns_found" in report.evidence_summary
    
    # Verify LLM analysis was used
    assert report.llm_analysis_available is True
    assert report.analysis_duration_ms > 0
    
    # Check observations include the anomaly description and log pattern observation
    assert "Container is crashing" in report.observations[0]
