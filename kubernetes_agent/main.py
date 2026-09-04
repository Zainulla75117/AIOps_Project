"""Application entrypoint and background task runner.

Initializes dependencies, starts the FastAPI server, and runs the
periodic scanning loop in the background.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running `python main.py` directly from the kubernetes_agent directory
_current_dir = Path(__file__).resolve().parent
_parent_dir = _current_dir.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

import asyncio
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from kubernetes_agent.analysis.correlator import MultiSignalCorrelator
from kubernetes_agent.analysis.gemini_provider import GeminiProvider
from kubernetes_agent.analysis.log_analyzer import LogAnalyzer
from kubernetes_agent.analysis.sanitizer import LogSanitizer
from kubernetes_agent.api import dependencies
from kubernetes_agent.api.namespace_manager import NamespaceManager
from kubernetes_agent.api.routes import router as core_router
from kubernetes_agent.api.settings_routes import router as settings_router
from kubernetes_agent.api.workloads_routes import router as workloads_router
from kubernetes_agent.api.history_routes import router as history_router
from kubernetes_agent.collectors.deployment_collector import DeploymentCollector
from kubernetes_agent.collectors.event_collector import EventCollector
from kubernetes_agent.collectors.log_collector import LogCollector
from kubernetes_agent.collectors.node_collector import NodeCollector
from kubernetes_agent.collectors.pod_collector import PodCollector
from kubernetes_agent.collectors.service_collector import ServiceCollector
from kubernetes_agent.config import get_config
from kubernetes_agent.db.mongo_client import MongoClient as AIOpsMongoClient
from kubernetes_agent.db.repositories import IncidentRepository, ScanRepository
from kubernetes_agent.detectors.registry import DetectorRegistry
from kubernetes_agent.engine.evidence_builder import EvidenceBuilder
from kubernetes_agent.engine.investigation import InvestigationEngine
from kubernetes_agent.engine.scanner import Scanner
from kubernetes_agent.utils.k8s_client import get_k8s_client
from kubernetes_agent.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


# Global reference to the background task so it's not garbage collected
_scan_task: asyncio.Task | None = None


async def periodic_scan_loop(scanner: Scanner, ns_manager: NamespaceManager) -> None:
    """Background task that runs the scanner periodically."""
    cfg = get_config()
    interval = cfg.scan_interval_seconds
    
    logger.info("periodic_scan_loop_started", interval_seconds=interval)
    
    while True:
        try:
            namespaces = ns_manager.get_monitored_namespaces()
            if namespaces:
                await scanner.scan(namespaces)
            else:
                logger.debug("periodic_scan_skipped", reason="no_namespaces_enabled")
        except asyncio.CancelledError:
            logger.info("periodic_scan_loop_stopped")
            break
        except Exception as exc:
            logger.error("periodic_scan_failed", error=str(exc))
            
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown events."""
    global _scan_task
    
    # 1. Setup Logging
    cfg = get_config()
    setup_logging(debug=True, json_output=False) # Use console logging for local dev
    logger.info("aiops_agent_starting", version="0.1.0")

    # 2. Connect to Kubernetes
    k8s = get_k8s_client()
    if not k8s.is_reachable():
        logger.error("kubernetes_unreachable_on_startup")

    # 3. Connect to MongoDB
    mongo = AIOpsMongoClient(cfg)
    await mongo.connect()
    dependencies.set_mongo(mongo)
    logger.info("mongodb_initialized", connected=mongo.is_connected)

    # 4. Initialize Namespace Manager
    ns_manager = NamespaceManager(cfg)
    dependencies.set_namespace_manager(ns_manager)

    # 5. Initialize Collectors
    pods = PodCollector(k8s)
    deps = DeploymentCollector(k8s)
    svcs = ServiceCollector(k8s)
    nodes = NodeCollector(k8s)
    events = EventCollector(k8s)
    logs = LogCollector(k8s, cfg)
    
    # Register collectors in DI
    dependencies.set_collectors(pods, deps, svcs, nodes, events)

    # 6. Initialize Detectors
    registry = DetectorRegistry()

    # 7. Initialize Analysis & Engine
    sanitizer = LogSanitizer(cfg)
    gemini = GeminiProvider(cfg)
    
    log_analyzer = LogAnalyzer(gemini, sanitizer, cfg)
    correlator = MultiSignalCorrelator(gemini)
    
    builder = EvidenceBuilder(events, logs)
    investigator = InvestigationEngine(builder, log_analyzer, correlator)
    
    # 8. Initialize Scanner (with MongoDB repositories)
    scan_repo = ScanRepository(mongo) if mongo.is_connected else None
    incident_repo = IncidentRepository(mongo) if mongo.is_connected else None
    
    scanner = Scanner(
        pod_collector=pods,
        deployment_collector=deps,
        service_collector=svcs,
        node_collector=nodes,
        registry=registry,
        investigator=investigator,
        cfg=cfg,
        scan_repo=scan_repo,
        incident_repo=incident_repo,
    )
    dependencies.set_scanner(scanner)
    
    # 9. Start background scan loop
    _scan_task = asyncio.create_task(periodic_scan_loop(scanner, ns_manager))
    
    yield # App is running
    
    # Shutdown
    logger.info("aiops_agent_shutting_down")
    if _scan_task:
        _scan_task.cancel()
        try:
            await _scan_task
        except asyncio.CancelledError:
            pass
    await mongo.close()
    k8s.close()


# ---- FastAPI App Creation ----

def create_app() -> FastAPI:
    """Factory to create the FastAPI application."""
    app = FastAPI(
        title="Kubernetes AIOps Agent",
        description="Intelligent cluster health monitoring and remediation.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS for development dashboard access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routes
    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(core_router)
    api_router.include_router(settings_router)
    api_router.include_router(workloads_router)
    api_router.include_router(history_router)
    app.include_router(api_router)
    
    # Mount the static dashboard build
    # Resolve the absolute path to the dashboard/dist directory robustly
    dashboard_dir = _parent_dir / "dashboard" / "dist"
    dashboard_dir.mkdir(parents=True, exist_ok=True) # Ensure it exists so StaticFiles doesn't crash
    app.mount("/", StaticFiles(directory=str(dashboard_dir), html=True), name="dashboard")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    cfg = get_config()
    uvicorn.run(
        "main:app",
        host=cfg.api_host,
        port=cfg.api_port,
        reload=False,
    )
