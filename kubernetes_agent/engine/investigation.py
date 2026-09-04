"""Investigation orchestrator.

Coordinates the end-to-end investigation of a detected anomaly:
1. Building evidence
2. Analyzing logs
3. Correlating signals
4. Generating the final IncidentReport
"""

from __future__ import annotations

import datetime
from uuid import uuid4

from kubernetes_agent.analysis.correlator import MultiSignalCorrelator
from kubernetes_agent.analysis.log_analyzer import LogAnalyzer
from kubernetes_agent.engine.evidence_builder import EvidenceBuilder
from kubernetes_agent.models.anomaly import DetectedAnomaly
from kubernetes_agent.models.incident import IncidentReport, IncidentStatus
from kubernetes_agent.models.snapshot import ClusterSnapshot
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)


class InvestigationEngine:
    """Orchestrates anomaly investigation."""

    def __init__(
        self,
        builder: EvidenceBuilder,
        log_analyzer: LogAnalyzer,
        correlator: MultiSignalCorrelator,
    ) -> None:
        self._builder = builder
        self._log_analyzer = log_analyzer
        self._correlator = correlator

    async def investigate(
        self, anomaly: DetectedAnomaly, snapshot: ClusterSnapshot
    ) -> IncidentReport:
        """Investigate an anomaly and return a comprehensive report."""
        start_time = datetime.datetime.utcnow()
        
        logger.info(
            "investigation_started",
            anomaly_type=anomaly.anomaly_type.value,
            resource=anomaly.resource.name,
        )

        # 1. Collect Evidence
        evidence = self._builder.build(anomaly, snapshot)

        # 2. Analyze Logs (if we have any)
        if evidence.logs or evidence.previous_logs:
            # Prefer previous logs if available (e.g. for CrashLoopBackOff)
            target_logs = evidence.previous_logs if evidence.previous_logs else evidence.logs
            
            patterns, summary, llm_root_cause = await self._log_analyzer.analyze_logs(
                logs=target_logs,
                pod_name=anomaly.resource.name,
            )
            evidence.log_patterns = patterns
            
            # Keep a small snippet for the report
            if target_logs:
                first_container = list(target_logs.keys())[0]
                snippet = target_logs[first_container].split("\n")[-10:]
                log_snippets = [f"[{first_container}] {line}" for line in snippet]
            else:
                log_snippets = []
        else:
            log_snippets = []

        # 3. Correlate Signals
        what_went_wrong, inferences, root_cause, recommendation = await self._correlator.correlate(evidence)

        # 4. Build Final Report
        end_time = datetime.datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000

        # Create evidence summary
        evidence_summary = {
            "events_analyzed": len(evidence.related_events),
            "log_patterns_found": len(evidence.log_patterns),
            "collection_errors": evidence.collection_errors,
        }

        # Determine LLM availability
        llm_available = bool(
            self._log_analyzer._provider.is_available()
        )

        report = IncidentReport(
            id=f"inc-{uuid4().hex[:8]}",
            timestamp=datetime.datetime.utcnow(),
            status=IncidentStatus.OPEN,
            severity=anomaly.severity,
            what_went_wrong=what_went_wrong or anomaly.title,
            observations=[anomaly.description], # Start with the base anomaly description
            inferences=inferences,
            root_cause=root_cause,
            affected_resources=[anomaly.resource],
            recommendation=recommendation,
            evidence_summary=evidence_summary,
            log_snippets=log_snippets,
            llm_analysis_available=llm_available,
            analysis_duration_ms=duration_ms,
        )
        
        # Add event observations
        if evidence.related_events:
            event = evidence.related_events[-1]
            report.observations.append(f"Observed recent {event.type} event: {event.reason} - {event.message}")
            
        if evidence.log_patterns:
            report.observations.append(f"Found {len(evidence.log_patterns)} recurring error patterns in logs.")

        logger.info(
            "investigation_completed",
            incident_id=report.id,
            duration_ms=duration_ms,
        )

        return report
