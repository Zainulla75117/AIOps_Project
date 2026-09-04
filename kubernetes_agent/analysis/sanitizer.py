"""Log sanitizer — redacts sensitive data from logs before LLM analysis.

This is a **critical security component**.  Application logs frequently
contain API keys, tokens, passwords, connection strings, JWTs, PII, and
internal infrastructure details.  This module redacts those patterns before
any log data is sent to an external LLM provider.
"""

from __future__ import annotations

import re

from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)

# Placeholder that replaces redacted content
_REDACTED = "[REDACTED]"


class LogSanitizer:
    """Redacts sensitive patterns from log text.

    Uses a configurable list of regex patterns.  Patterns are compiled
    once at construction time for performance.
    """

    def __init__(self, cfg: AgentConfig | None = None) -> None:
        self._cfg = cfg or get_config()
        self._patterns: list[re.Pattern] = []
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns from config."""
        for pattern_str in self._cfg.redact_patterns:
            try:
                self._patterns.append(re.compile(pattern_str))
            except re.error as exc:
                logger.warning(
                    "sanitizer_invalid_pattern",
                    pattern=pattern_str,
                    error=str(exc),
                )

    def sanitize(self, text: str) -> str:
        """Redact sensitive patterns from the given text.

        Args:
            text: Raw log text.

        Returns:
            Sanitized log text with sensitive values replaced by [REDACTED].
        """
        if not self._cfg.sanitize_logs:
            return text

        result = text
        redaction_count = 0

        for pattern in self._patterns:
            matches = pattern.findall(result)
            if matches:
                redaction_count += len(matches)
                result = pattern.sub(_REDACTED, result)

        if redaction_count > 0:
            logger.debug(
                "logs_sanitized",
                redactions=redaction_count,
                original_length=len(text),
                sanitized_length=len(result),
            )

        return result

    def sanitize_dict(self, logs: dict[str, str]) -> dict[str, str]:
        """Sanitize all values in a container_name -> log_text dict."""
        return {name: self.sanitize(text) for name, text in logs.items()}
