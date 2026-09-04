"""Multi-signal Correlator — correlates Kubernetes state and logs to determine root cause."""

from __future__ import annotations

from pydantic import BaseModel, Field

from kubernetes_agent.analysis.gemini_provider import GeminiProvider
from kubernetes_agent.models.evidence import EvidencePackage
from kubernetes_agent.models.incident import Recommendation, RiskLevel, RootCause
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Schemas for structured LLM output
# ---------------------------------------------------------------------------

class LLMRecommendation(BaseModel):
    action: str = Field(description="The primary action to take (e.g., 'Increase memory limits')")
    rationale: str = Field(description="Why this action will resolve the issue")
    commands: list[str] = Field(description="Specific kubectl or YAML edits to apply, if any")
    risk_level: str = Field(description="low, medium, or high")
    requires_restart: bool = Field(description="True if the action involves restarting the pod/deployment")
    additional_investigation: list[str] = Field(description="Things the user should check manually")


class LLMRootCause(BaseModel):
    category: str = Field(description="General category (e.g., application_error, configuration, resource_exhaustion)")
    description: str = Field(description="Detailed explanation of the root cause")
    confidence: float = Field(description="0.0 to 1.0 rating of how confident you are in this root cause")
    reasoning: str = Field(description="Chain of reasoning connecting the evidence to this conclusion")


class LLMCorrelationAnalysis(BaseModel):
    what_went_wrong: str = Field(description="One-sentence summary of the incident")
    inferences: list[str] = Field(description="List of factual inferences derived from the evidence")
    root_cause: LLMRootCause = Field(description="The determined root cause")
    recommendation: LLMRecommendation = Field(description="Actionable remediation recommendation")


# ---------------------------------------------------------------------------
# Correlator
# ---------------------------------------------------------------------------

class MultiSignalCorrelator:
    """Correlates logs, events, and K8s state to find root cause and recommend fixes."""

    def __init__(self, provider: GeminiProvider) -> None:
        self._provider = provider
        
        self._system_instruction = (
            "You are a Kubernetes AIOps Incident Commander. "
            "Your job is to correlate multiple signals (Kubernetes resource state, events, "
            "and application log patterns) to determine the definitive root cause of a failure. "
            "Provide highly specific, actionable remediation recommendations. "
            "Do not suggest generic troubleshooting steps if the root cause is clear. "
            "Return your analysis strictly adhering to the requested JSON schema."
        )

    async def correlate(
        self, evidence: EvidencePackage
    ) -> tuple[str, list[str], RootCause, Recommendation]:
        """Correlate evidence package and generate final analysis.

        Args:
            evidence: The complete evidence package for an anomaly.

        Returns:
            Tuple of (what_went_wrong, inferences, root_cause, recommendation).
        """
        if not self._provider.is_available():
            logger.debug("correlation_skipped", reason="provider_unavailable")
            return self._generate_fallback(evidence)

        prompt = self._build_prompt(evidence)
        logger.info(
            "correlating_evidence_with_llm",
            anomaly_type=evidence.anomaly.anomaly_type.value,
            resource=evidence.anomaly.resource.name,
        )

        try:
            result: LLMCorrelationAnalysis = await self._provider.analyze(
                system_instruction=self._system_instruction,
                prompt=prompt,
                schema=LLMCorrelationAnalysis,
            ) # type: ignore

            # Map LLM schema back to domain models
            root_cause = RootCause(
                category=result.root_cause.category,
                description=result.root_cause.description,
                confidence=result.root_cause.confidence,
                reasoning=result.root_cause.reasoning,
            )
            
            risk_level_map = {
                "low": RiskLevel.LOW,
                "medium": RiskLevel.MEDIUM,
                "high": RiskLevel.HIGH,
            }

            recommendation = Recommendation(
                action=result.recommendation.action,
                rationale=result.recommendation.rationale,
                commands=result.recommendation.commands,
                risk_level=risk_level_map.get(
                    result.recommendation.risk_level.lower(), RiskLevel.MEDIUM
                ),
                requires_restart=result.recommendation.requires_restart,
                additional_investigation=result.recommendation.additional_investigation,
            )

            return (
                result.what_went_wrong,
                result.inferences,
                root_cause,
                recommendation,
            )

        except Exception as exc:
            logger.error("correlation_failed", error=str(exc))
            return self._generate_fallback(evidence)

    def _build_prompt(self, evidence: EvidencePackage) -> str:
        """Construct the correlation prompt from the evidence package."""
        anomaly = evidence.anomaly
        
        prompt = (
            f"Analyze the following Kubernetes incident.\n\n"
            f"### Primary Anomaly Detected\n"
            f"- Type: {anomaly.anomaly_type.value}\n"
            f"- Resource: {anomaly.resource.kind} {anomaly.resource.namespace}/{anomaly.resource.name}\n"
            f"- Description: {anomaly.description}\n"
            f"- Evidence: {anomaly.evidence}\n\n"
        )
        
        if evidence.resource_info:
            prompt += f"### Resource Context\n{evidence.resource_info}\n\n"
            
        if evidence.related_events:
            prompt += "### Related Kubernetes Events\n"
            for event in evidence.related_events:
                prompt += f"- [{event.type}] {event.reason}: {event.message} ({event.count}x)\n"
            prompt += "\n"
            
        if evidence.log_patterns:
            prompt += "### Extracted Log Patterns\n"
            for pattern in evidence.log_patterns:
                prompt += f"- [{pattern.severity.upper()}] ({pattern.count}x): {pattern.pattern}\n"
                for line in pattern.sample_lines:
                    prompt += f"    Sample: {line}\n"
            prompt += "\n"
            
        prompt += (
            "Determine the root cause by correlating the K8s state/events with the log patterns. "
            "Provide a concrete recommendation to fix it."
        )
        return prompt

    def _generate_fallback(self, evidence: EvidencePackage) -> tuple:
        """Generate a basic, rule-based response when the LLM is unavailable."""
        anomaly = evidence.anomaly
        
        root_cause = RootCause(
            category="unknown",
            description=f"A {anomaly.anomaly_type.value} was detected, but detailed analysis requires LLM configuration.",
            confidence=0.5,
            reasoning="Rule-based detection fired, but advanced correlation is disabled.",
        )
        
        recommendation = Recommendation(
            action="Investigate the resource manually.",
            rationale="Automated recommendation requires LLM configuration.",
            commands=[
                f"kubectl describe {anomaly.resource.kind.lower()} {anomaly.resource.name} -n {anomaly.resource.namespace}",
                f"kubectl logs {anomaly.resource.name} -n {anomaly.resource.namespace}"
            ],
            risk_level=RiskLevel.LOW,
            requires_restart=False,
            additional_investigation=["Review logs", "Check events"],
        )
        
        return (
            anomaly.title,
            [anomaly.description],
            root_cause,
            recommendation,
        )
