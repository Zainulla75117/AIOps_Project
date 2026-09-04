"""Core API routes for the AIOps Agent."""

import asyncio
import time
import uuid

from fastapi import APIRouter, Depends, BackgroundTasks

from kubernetes_agent.api.dependencies import (
    get_agent_config,
    get_chat_repo,
    get_deployment_collector,
    get_event_collector,
    get_namespaces,
    get_node_collector,
    get_pod_collector,
    get_scanner,
    get_service_collector,
)
from kubernetes_agent.api.namespace_manager import NamespaceManager
from kubernetes_agent.collectors.deployment_collector import DeploymentCollector
from kubernetes_agent.collectors.event_collector import EventCollector
from kubernetes_agent.collectors.node_collector import NodeCollector
from kubernetes_agent.collectors.pod_collector import PodCollector
from kubernetes_agent.collectors.service_collector import ServiceCollector
from kubernetes_agent.config import AgentConfig
from kubernetes_agent.db.repositories import ChatRepository
from kubernetes_agent.engine.scanner import Scanner
from kubernetes_agent.analysis.gemini_provider import GeminiProvider
from kubernetes_agent.models.api import AgentStatusResponse, ScanTriggerResponse, ChatRequest, ChatResponse
from kubernetes_agent.models.incident import IncidentReport
from kubernetes_agent.utils.security import mask_sensitive_data
import re

router = APIRouter(tags=["Core"])


@router.get("/status", response_model=AgentStatusResponse)
async def get_status(
    cfg: AgentConfig = Depends(get_agent_config),
    scanner: Scanner = Depends(get_scanner),
    ns_manager: NamespaceManager = Depends(get_namespaces),
):
    """Get the current health and status of the agent."""
    from kubernetes_agent import __version__
    
    # Check Gemini config
    gemini_ready = bool(
        cfg.gemini_api_key and cfg.gemini_api_key != "test-key-not-real"
    )
    
    return AgentStatusResponse(
        agent_version=__version__,
        uptime_seconds=0.0,  # TODO: Track uptime in main.py if needed
        last_scan_at=scanner.last_scan_at,
        last_scan_duration_ms=scanner.last_scan_duration_ms,
        total_scans=scanner.total_scans,
        active_incidents=len(scanner.active_incidents),
        monitored_namespaces=ns_manager.get_monitored_namespaces(),
        gemini_available=gemini_ready,
    )


@router.get("/incidents", response_model=list[IncidentReport])
async def list_incidents(scanner: Scanner = Depends(get_scanner)):
    """List all currently active incidents detected by the agent."""
    # Sort by severity (critical -> warning -> info) then by timestamp
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    incidents = scanner.active_incidents
    incidents.sort(
        key=lambda i: (severity_order.get(i.severity.value, 9), i.timestamp),
        reverse=True
    )
    return incidents


@router.post("/scan", response_model=ScanTriggerResponse)
async def trigger_scan(
    background_tasks: BackgroundTasks,
    scanner: Scanner = Depends(get_scanner),
    ns_manager: NamespaceManager = Depends(get_namespaces),
):
    """Manually trigger a background scan cycle."""
    namespaces = ns_manager.get_monitored_namespaces()
    
    if not namespaces:
        return ScanTriggerResponse(
            scan_id="none",
            status="skipped",
            message="No namespaces enabled for monitoring."
        )
        
    # Queue the scan as a background task so we return 202 immediately
    scan_id = f"manual-{scanner.total_scans + 1}"
    background_tasks.add_task(scanner.scan, namespaces)
    
    return ScanTriggerResponse(
        scan_id=scan_id,
        status="started",
        message=f"Scan triggered for {len(namespaces)} namespaces."
    )


def _build_cluster_context(
    pods: list,
    nodes: list,
    deployments: list,
    services: list,
    events: list,
    incidents: list[IncidentReport],
) -> str:
    """Build a compact cluster context string for the LLM prompt."""
    # Pod summary
    pods_running = sum(1 for p in pods if p.phase == "Running")
    pods_pending = sum(1 for p in pods if p.phase == "Pending")
    pods_failed = sum(1 for p in pods if p.phase == "Failed")
    pods_crashloop = []
    pods_high_restarts = []
    for p in pods:
        for cs in p.container_statuses:
            if cs.state.reason == "CrashLoopBackOff":
                pods_crashloop.append(f"{p.namespace}/{p.name}")
            if cs.restart_count >= 5:
                pods_high_restarts.append(
                    f"{p.namespace}/{p.name} ({cs.restart_count} restarts)"
                )

    # Node summary
    nodes_ready = sum(1 for n in nodes if n.is_ready)
    node_issues = []
    for n in nodes:
        issues = []
        if n.has_memory_pressure:
            issues.append("MemoryPressure")
        if n.has_disk_pressure:
            issues.append("DiskPressure")
        if n.has_pid_pressure:
            issues.append("PIDPressure")
        if not n.is_ready:
            issues.append("NotReady")
        if issues:
            node_issues.append(f"{n.name}: {', '.join(issues)}")

    # Deployment summary
    deps_healthy = sum(1 for d in deployments if d.is_available)
    unhealthy_deps = []
    for d in deployments:
        if not d.is_available or d.unavailable_replicas > 0:
            unhealthy_deps.append(
                f"{d.namespace}/{d.name} "
                f"(desired={d.replicas}, ready={d.ready_replicas}, "
                f"available={d.available_replicas})"
            )

    # Events summary (warnings only)
    warning_events = [e for e in events if e.type == "Warning"]
    recent_warnings = warning_events[:20]  # Cap to keep context manageable

    # Active incidents summary
    incident_summaries = []
    for inc in incidents:
        incident_summaries.append(
            f"[{inc.severity.value.upper()}] {inc.what_went_wrong} "
            f"(status: {inc.status.value})"
        )

    # Build context string
    lines = [
        "=== LIVE CLUSTER STATE ===",
        "",
        f"PODS: {len(pods)} total | {pods_running} Running | {pods_pending} Pending | {pods_failed} Failed",
    ]
    if pods_crashloop:
        lines.append(f"  CrashLoopBackOff: {', '.join(pods_crashloop[:10])}")
    if pods_high_restarts:
        lines.append(f"  High restarts: {', '.join(pods_high_restarts[:10])}")

    # Individual pod details (limited)
    lines.append("")
    lines.append("POD DETAILS:")
    for p in pods[:30]:  # Limit to 30 pods
        status = p.phase
        restarts = p.total_restarts
        node = p.node_name or "unassigned"
        lines.append(f"  {p.namespace}/{p.name} | {status} | restarts={restarts} | node={node}")

    lines.append("")
    lines.append(f"NODES: {len(nodes)} total | {nodes_ready} Ready | {len(nodes) - nodes_ready} NotReady")
    if node_issues:
        for issue in node_issues:
            lines.append(f"  ⚠ {issue}")
    for n in nodes:
        lines.append(
            f"  {n.name} | {'Ready' if n.is_ready else 'NOT READY'} | "
            f"kubelet={n.kubelet_version} | cpu={n.capacity_cpu} | mem={n.capacity_memory}"
        )

    lines.append("")
    lines.append(f"DEPLOYMENTS: {len(deployments)} total | {deps_healthy} Healthy | {len(deployments) - deps_healthy} Unhealthy")
    if unhealthy_deps:
        for dep in unhealthy_deps:
            lines.append(f"  ⚠ {dep}")
    for d in deployments:
        lines.append(
            f"  {d.namespace}/{d.name} | replicas={d.replicas} | "
            f"ready={d.ready_replicas} | available={d.available_replicas}"
        )

    lines.append("")
    lines.append(f"SERVICES: {len(services)} total")
    for s in services[:20]:
        ports_str = ", ".join(
            f"{p.get('port', '?')}/{p.get('protocol', 'TCP')}" for p in s.ports
        )
        lines.append(f"  {s.namespace}/{s.name} | {s.type} | {ports_str}")

    if recent_warnings:
        lines.append("")
        lines.append(f"WARNING EVENTS ({len(warning_events)} total, showing {len(recent_warnings)}):")
        for e in recent_warnings:
            lines.append(f"  [{e.reason}] {e.involved_kind}/{e.involved_name}: {e.message[:120]}")

    if incident_summaries:
        lines.append("")
        lines.append(f"ACTIVE INCIDENTS ({len(incident_summaries)}):")
        for s in incident_summaries:
            lines.append(f"  {s}")

    return "\n".join(lines)


@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(
    request: ChatRequest,
    cfg: AgentConfig = Depends(get_agent_config),
    scanner: Scanner = Depends(get_scanner),
    ns_manager: NamespaceManager = Depends(get_namespaces),
    pods_coll: PodCollector = Depends(get_pod_collector),
    nodes_coll: NodeCollector = Depends(get_node_collector),
    deps_coll: DeploymentCollector = Depends(get_deployment_collector),
    svcs_coll: ServiceCollector = Depends(get_service_collector),
    events_coll: EventCollector = Depends(get_event_collector),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Chat with the agent using live cluster context."""
    gemini = GeminiProvider(cfg)
    
    if not gemini.is_available():
        return ChatResponse(reply="Error: Gemini API is not configured or unavailable.")

    start_time = time.monotonic()

    # 1. Collect live cluster data
    namespaces = ns_manager.get_monitored_namespaces()
    try:
        pods, nodes, deployments, services, events = await asyncio.gather(
            asyncio.to_thread(pods_coll.collect, namespaces),
            asyncio.to_thread(nodes_coll.collect_all),
            asyncio.to_thread(deps_coll.collect, namespaces),
            asyncio.to_thread(svcs_coll.collect, namespaces),
            asyncio.to_thread(events_coll.collect, namespaces),
        )
    except Exception:
        pods, nodes, deployments, services, events = [], [], [], [], []

    # 2. Build context
    cluster_context = _build_cluster_context(
        pods, nodes, deployments, services, events, scanner.active_incidents
    )

    # 2.5 Inject app logs if relevant
    logs_context = ""
    # Did the user explicitly ask for logs for a specific pod?
    pod_match = re.search(r"logs?(?:\s+for)?\s+([a-zA-Z0-9-]+)", request.query.lower())
    target_pod = pod_match.group(1) if pod_match else None
    
    # Or, if there's a crashing pod, auto-fetch logs for the first one to help the LLM
    if not target_pod:
        for p in pods:
            for cs in p.container_statuses:
                if cs.state.reason == "CrashLoopBackOff" or cs.state.state == "terminated":
                    target_pod = p.name
                    break
            if target_pod:
                break
    
    if target_pod:
        # Find the namespace for this pod
        target_ns = next((p.namespace for p in pods if p.name == target_pod), None)
        if target_ns:
            try:
                raw_logs = await asyncio.to_thread(pods_coll.get_pod_logs, target_ns, target_pod, 50)
                masked_logs = mask_sensitive_data(raw_logs)
                logs_context = f"\n\n=== RECENT LOGS FOR POD {target_ns}/{target_pod} ===\n{masked_logs}\n"
            except Exception as e:
                logs_context = f"\n\n[Could not fetch logs for {target_ns}/{target_pod}: {e}]\n"

    # 3. Build prompt with context
    system_instruction = (
        "You are an expert Kubernetes AIOps assistant embedded in a cluster monitoring dashboard. "
        "You have access to LIVE cluster data provided below. "
        "Answer the user's question using ONLY the provided cluster data. "
        "Be specific — reference actual pod names, node names, deployment names, and exact counts. "
        "If you see problems, explain what they are and suggest fixes. "
        "If the data shows everything is healthy, say so confidently. "
        "Format your response clearly with sections if needed. Keep it concise but thorough. "
        "Do NOT make up data that is not in the provided context.\n\n"
        "IMPORTANT: Always provide exactly 3 suggested follow-up questions the user could ask next to continue "
        "troubleshooting or exploring. Wrap these questions inside a <follow_ups> XML tag at the very end of your response, "
        "with each question on a new line starting with a dash. "
        "Example:\n"
        "<follow_ups>\n- What are the logs for pod XYZ?\n- Why did node ABC restart?\n- Show me unhealthy deployments.\n</follow_ups>"
    )

    prompt = f"{cluster_context}{logs_context}\n\n=== USER QUESTION ===\n{request.query}"

    # 4. Call Gemini
    try:
        response = await gemini.analyze(
            system_instruction=system_instruction,
            prompt=prompt,
            schema=ChatResponse,
        )
        reply = response.reply if isinstance(response, ChatResponse) else str(response)
    except Exception as exc:
        reply = f"An error occurred: {exc}"

    elapsed_ms = (time.monotonic() - start_time) * 1000

    # 5. Save to MongoDB
    session_id = request.session_id if hasattr(request, "session_id") and request.session_id else str(uuid.uuid4())
    context_summary = {
        "pods": len(pods),
        "nodes": len(nodes),
        "deployments": len(deployments),
        "services": len(services),
        "incidents": len(scanner.active_incidents),
        "namespaces": namespaces,
    }
    await chat_repo.save_message(
        session_id=session_id,
        query=request.query,
        reply=reply,
        context_summary=context_summary,
        response_time_ms=elapsed_ms,
    )

    return ChatResponse(reply=reply)
