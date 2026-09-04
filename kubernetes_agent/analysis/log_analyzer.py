"""Log analyzer — uses Gemini to find root causes in application logs."""

from __future__ import annotations

import json
from pydantic import BaseModel, Field

from kubernetes_agent.analysis.gemini_provider import GeminiProvider
from kubernetes_agent.analysis.sanitizer import LogSanitizer
from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.models.evidence import LogPattern
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Schemas for structured LLM output
# ---------------------------------------------------------------------------

class LLMLogPattern(BaseModel):
    pattern: str = Field(description="The generic error pattern, e.g., 'Connection refused to redis:6379'")
    count: int = Field(description="Approximate occurrences of this pattern")
    severity: str = Field(description="error, warning, or info")
    sample_lines: list[str] = Field(description="1-2 exact lines from the logs demonstrating this pattern")


class LLMLogAnalysis(BaseModel):
    patterns: list[LLMLogPattern] = Field(description="List of significant error or warning patterns found")
    summary: str = Field(description="One-paragraph summary of what the logs indicate went wrong")
    likely_root_cause: str | None = Field(description="The most likely root cause based purely on the logs, or null if unclear")


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class LogAnalyzer:
    """Analyzes raw container logs using Gemini to extract insights."""

    def __init__(
        self,
        provider: GeminiProvider,
        sanitizer: LogSanitizer,
        cfg: AgentConfig | None = None,
    ) -> None:
        self._provider = provider
        self._sanitizer = sanitizer
        self._cfg = cfg or get_config()

        self._system_instruction = (
            "You are a Kubernetes AIOps agent expert in debugging container failures. "
            "Your task is to analyze application and container logs. "
            "You must identify critical errors, exceptions, stack traces, and notable warnings. "
            "Ignore routine informational logs unless they provide critical context right before a crash. "
            "Be precise, factual, and strictly adhere to the requested JSON schema."
        )

    async def analyze_logs(
        self, logs: dict[str, str], pod_name: str
    ) -> tuple[list[LogPattern], str, str | None]:
        """Analyze container logs to find patterns and root cause.

        Args:
            logs: Dictionary of container_name -> log_text.
            pod_name: Name of the pod (for context).

        Returns:
            Tuple of (list of LogPattern, summary text, likely root cause text).
        """
        if not self._provider.is_available():
            logger.debug("log_analysis_skipped", reason="provider_unavailable")
            return [], "Log analysis skipped (LLM not configured).", None

        if not logs or all(not log_text.strip() for log_text in logs.values()):
            return [], "No logs available for analysis.", None

        # 1. Sanitize the logs
        sanitized_logs = self._sanitizer.sanitize_dict(logs)

        # 2. Build the prompt
        prompt = self._build_prompt(sanitized_logs, pod_name)
        
        # 3. Analyze with Gemini
        logger.info("analyzing_logs_with_llm", pod=pod_name)
        try:
            # We cast to LLMLogAnalysis because we provided the schema
            result: LLMLogAnalysis = await self._provider.analyze(
                system_instruction=self._system_instruction,
                prompt=prompt,
                schema=LLMLogAnalysis,
            ) # type: ignore
            
            # Map LLM schema back to internal domain model
            patterns = [
                LogPattern(
                    pattern=p.pattern,
                    count=p.count,
                    severity=p.severity,
                    sample_lines=p.sample_lines,
                )
                for p in result.patterns
            ]
            
            return patterns, result.summary, result.likely_root_cause

        except Exception as exc:
            logger.error("log_analysis_failed", pod=pod_name, error=str(exc))
            return [], f"Failed to analyze logs: {exc}", None

    def _build_prompt(self, sanitized_logs: dict[str, str], pod_name: str) -> str:
        """Construct the LLM prompt containing the logs."""
        prompt = f"Analyze the following logs for pod '{pod_name}'.\n\n"
        
        for container, log_text in sanitized_logs.items():
            if not log_text.strip():
                continue
                
            prompt += f"--- Container: {container} ---\n"
            prompt += f"{log_text}\n\n"
            
        prompt += (
            "Extract the key error patterns, provide a summary of the failure, "
            "and identify the likely root cause."
        )
        return prompt
