"""Unit tests for the log sanitizer."""

import pytest

from kubernetes_agent.analysis.sanitizer import LogSanitizer
from kubernetes_agent.config import AgentConfig


def _make_sanitizer(**kwargs) -> LogSanitizer:
    cfg = AgentConfig(
        gemini_api_key="test",
        k8s_in_cluster=False,
        **kwargs,
    )
    return LogSanitizer(cfg=cfg)


class TestLogSanitizer:
    def test_redacts_api_key(self):
        sanitizer = _make_sanitizer()
        log = 'Connecting with api_key: sk-abc123xyz456789012'
        result = sanitizer.sanitize(log)
        assert "sk-abc123xyz456789012" not in result
        assert "[REDACTED]" in result

    def test_redacts_bearer_token(self):
        sanitizer = _make_sanitizer()
        log = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature"
        result = sanitizer.sanitize(log)
        assert "eyJhbGci" not in result
        assert "[REDACTED]" in result

    def test_redacts_jwt(self):
        sanitizer = _make_sanitizer()
        log = "token=eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature123"
        result = sanitizer.sanitize(log)
        assert "eyJhbGci" not in result

    def test_redacts_connection_string(self):
        sanitizer = _make_sanitizer()
        log = "Connecting to postgresql://admin:s3cret@db.internal:5432/mydb"
        result = sanitizer.sanitize(log)
        assert "s3cret" not in result
        assert "[REDACTED]" in result

    def test_redacts_password_field(self):
        sanitizer = _make_sanitizer()
        log = 'config: password = "SuperSecret123!"'
        result = sanitizer.sanitize(log)
        assert "SuperSecret123" not in result

    def test_preserves_normal_logs(self):
        sanitizer = _make_sanitizer()
        log = "2024-01-01 INFO Application started on port 8080"
        result = sanitizer.sanitize(log)
        assert result == log

    def test_disabled_sanitization(self):
        sanitizer = _make_sanitizer(sanitize_logs=False)
        log = "secret=mysecretvalue12345"
        result = sanitizer.sanitize(log)
        # When disabled, should return unchanged
        assert result == log

    def test_sanitize_dict(self):
        sanitizer = _make_sanitizer()
        logs = {
            "app": "token: Bearer abc123def456789xyz",
            "sidecar": "Normal log line without secrets",
        }
        result = sanitizer.sanitize_dict(logs)
        assert "[REDACTED]" in result["app"]
        assert result["sidecar"] == "Normal log line without secrets"

    def test_multiple_redactions(self):
        sanitizer = _make_sanitizer()
        log = (
            "api_key=key123456789abc\n"
            "password: hunter2isgreat\n"
            "token: Bearer mytoken12345678"
        )
        result = sanitizer.sanitize(log)
        assert result.count("[REDACTED]") >= 2
