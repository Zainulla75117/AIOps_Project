"""Namespace settings manager.

Handles loading, saving, and querying namespace monitoring settings.
Persists settings to a local JSON file.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.models.api import NamespacePermission, NamespaceSettings
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)


class NamespaceManager:
    """Manages which namespaces the agent is allowed to monitor."""

    def __init__(self, cfg: AgentConfig | None = None) -> None:
        self._cfg = cfg or get_config()
        self._file_path = Path(self._cfg.namespace_settings_path)
        self._settings = NamespaceSettings()
        
        # Ensure data directory exists
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self.load()

    def load(self) -> None:
        """Load settings from disk, or initialize with defaults if none exist."""
        if self._file_path.exists():
            try:
                with open(self._file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._settings = NamespaceSettings.model_validate(data)
                logger.info("namespace_settings_loaded", path=str(self._file_path))
            except Exception as exc:
                logger.error("namespace_settings_load_failed", error=str(exc))
                self._init_defaults()
        else:
            self._init_defaults()

    def _init_defaults(self) -> None:
        """Initialize settings from configuration defaults."""
        self._settings = NamespaceSettings()
        
        for ns_name in self._cfg.namespaces_default_enabled:
            self._settings.namespaces[ns_name] = NamespacePermission(
                name=ns_name,
                enabled=True,
                is_system=False,
                enabled_at=datetime.utcnow(),
            )
            
        for ns_name in self._cfg.namespaces_system:
            self._settings.namespaces[ns_name] = NamespacePermission(
                name=ns_name,
                enabled=False,
                is_system=True,
            )
            
        self.save()
        logger.info("namespace_settings_initialized_from_defaults")

    def save(self) -> None:
        """Persist settings to disk."""
        self._settings.last_updated = datetime.utcnow()
        try:
            temp_path = self._file_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(self._settings.model_dump_json(indent=2))
            os.replace(temp_path, self._file_path)
            logger.debug("namespace_settings_saved")
        except Exception as exc:
            logger.error("namespace_settings_save_failed", error=str(exc))

    def get_all(self) -> NamespaceSettings:
        """Get all namespace settings."""
        return self._settings

    def get_monitored_namespaces(self) -> list[str]:
        """Get a list of all currently enabled namespaces."""
        return [
            ns.name for ns in self._settings.namespaces.values() if ns.enabled
        ]

    def set_namespace_enabled(self, namespace: str, enabled: bool) -> NamespacePermission:
        """Enable or disable a specific namespace."""
        if namespace not in self._settings.namespaces:
            # We discover it on the fly
            self._settings.namespaces[namespace] = NamespacePermission(
                name=namespace,
                is_system=namespace in self._cfg.namespaces_system,
            )
            
        ns_perm = self._settings.namespaces[namespace]
        
        if ns_perm.enabled != enabled:
            ns_perm.enabled = enabled
            if enabled:
                ns_perm.enabled_at = datetime.utcnow()
                ns_perm.disabled_at = None
            else:
                ns_perm.disabled_at = datetime.utcnow()
            
            self.save()
            logger.info("namespace_permission_changed", namespace=namespace, enabled=enabled)
            
        return ns_perm
