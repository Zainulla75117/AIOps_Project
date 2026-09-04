"""Namespace settings API routes."""

from fastapi import APIRouter, Depends, HTTPException

from kubernetes_agent.api.dependencies import get_namespaces
from kubernetes_agent.api.namespace_manager import NamespaceManager
from kubernetes_agent.models.api import (
    NamespacePermission,
    NamespaceSettings,
    NamespaceToggleRequest,
)

router = APIRouter(prefix="/settings/namespaces", tags=["Settings"])


@router.get("", response_model=NamespaceSettings)
async def get_namespace_settings(
    manager: NamespaceManager = Depends(get_namespaces),
):
    """Get all namespace monitoring permissions."""
    return manager.get_all()


@router.put("/{namespace}", response_model=NamespacePermission)
async def toggle_namespace(
    namespace: str,
    request: NamespaceToggleRequest,
    manager: NamespaceManager = Depends(get_namespaces),
):
    """Enable or disable monitoring for a specific namespace."""
    if not namespace:
        raise HTTPException(status_code=400, detail="Namespace cannot be empty")
        
    return manager.set_namespace_enabled(namespace, request.enabled)
