"""Agent configuration via Pydantic Settings.

Configuration is loaded from environment variables prefixed with ``AIOPS_``.
A ``.env`` file is also supported for local development.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


from pathlib import Path

_current_dir = Path(__file__).resolve().parent
_parent_dir = _current_dir.parent

class AgentConfig(BaseSettings):
    """Central configuration for the AIOps Agent."""

    model_config = SettingsConfigDict(
        env_prefix="AIOPS_",
        env_file=(".env", str(_parent_dir / ".env")),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ---- Kubernetes ----
    k8s_in_cluster: bool = True
    k8s_kubeconfig: str | None = None

    # ---- Namespace permissions (defaults — overridden by dashboard) ----
    namespaces_default_enabled: list[str] = Field(default=["default"])
    namespaces_system: list[str] = Field(
        default=["kube-system", "kube-public", "kube-node-lease", "aiops-system"]
    )
    namespace_settings_path: str = "data/namespace_settings.json"

    # ---- Scanning ----
    scan_interval_seconds: int = 60
    restart_threshold: int = 5
    restart_window_seconds: int = 1800  # 30 minutes
    pending_threshold_seconds: int = 300  # 5 minutes

    # ---- Log collection ----
    log_tail_lines: int = 500
    log_since_seconds: int = 3600  # 1 hour
    log_max_bytes: int = 51200  # 50 KB per container

    # ---- Gemini LLM ----
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.7-flash"
    gemini_temperature: float = 0.2
    gemini_max_tokens: int = 4096
    gemini_timeout_seconds: int = 30

    # ---- Security ----
    sanitize_logs: bool = True
    redact_patterns: list[str] = Field(
        default=[
            r"(?i)(api[_-]?key|apikey|secret|token|password|passwd|pwd|auth)"
            r"\s*[:=]\s*['\"]?[\w\-\.\/\+]{8,}['\"]?",
            r"Bearer\s+[\w\-\.]+",
            r"eyJ[\w\-]+\.eyJ[\w\-]+\.[\w\-]+",  # JWT tokens
            r"(?i)(mongodb|postgres|mysql|redis|amqp)://[^\s]+",  # Connection strings
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Emails
        ]
    )

    # ---- MongoDB ----
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "aiops_agent"

    # ---- API ----
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str | None = None


# Module-level singleton (created on first import)
_config: AgentConfig | None = None


def get_config() -> AgentConfig:
    """Return the global config singleton, creating it on first call."""
    global _config
    if _config is None:
        _config = AgentConfig()
    return _config


def reset_config() -> None:
    """Reset the global config singleton (useful in tests)."""
    global _config
    _config = None
