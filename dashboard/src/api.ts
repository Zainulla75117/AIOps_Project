import axios from 'axios';

// We assume the frontend is served by the backend or proxied via Vite config
const API_BASE = '/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface AgentStatus {
  agent_version: string;
  uptime_seconds: number;
  last_scan_at: string | null;
  last_scan_duration_ms: number | null;
  total_scans: number;
  active_incidents: number;
  monitored_namespaces: string[];
  gemini_available: boolean;
}

export interface NamespacePermission {
  name: string;
  enabled: boolean;
  is_system: boolean;
  discovered_at: string;
}

export interface NamespaceSettings {
  namespaces: Record<string, NamespacePermission>;
  last_updated: string;
}

export interface IncidentReport {
  id: string;
  timestamp: string;
  status: 'open' | 'acknowledged' | 'resolved';
  severity: 'critical' | 'warning' | 'info';
  what_went_wrong: string;
  observations: string[];
  inferences: string[];
  root_cause?: {
    category: string;
    description: string;
    confidence: number;
    reasoning: string;
  };
  affected_resources: Array<{
    kind: string;
    name: string;
    namespace: string;
  }>;
  recommendation?: {
    action: string;
    rationale: string;
    commands: string[];
    risk_level: 'low' | 'medium' | 'high';
    requires_restart: boolean;
    additional_investigation: string[];
  };
  evidence_summary: Record<string, any>;
  log_snippets: string[];
  llm_analysis_available: boolean;
  analysis_duration_ms: number;
}

// ---- Workloads Types ----

export interface WorkloadsSummary {
  namespaces_monitored: string[];
  pods: { total: number; running: number; pending: number; failed: number; succeeded: number };
  nodes: { total: number; ready: number; not_ready: number };
  deployments: { total: number; healthy: number; unhealthy: number };
  services: { total: number };
  events: { total: number; warning: number; normal: number };
}

export interface NodeInfo {
  name: string;
  labels: Record<string, string>;
  conditions: Array<{ type: string; status: string; reason?: string; message?: string; last_transition_time?: string }>;
  capacity_cpu: string | null;
  capacity_memory: string | null;
  capacity_pods: string | null;
  allocatable_cpu: string | null;
  allocatable_memory: string | null;
  allocatable_pods: string | null;
  kubelet_version: string | null;
  os_image: string | null;
  container_runtime: string | null;
  unschedulable: boolean;
  taints: Array<{ key: string; value?: string; effect: string }>;
  creation_timestamp: string;
}

export interface PodInfo {
  name: string;
  namespace: string;
  phase: string;
  node_name: string | null;
  qos_class: string | null;
  creation_timestamp: string;
  owner_kind: string | null;
  owner_name: string | null;
  labels: Record<string, string>;
  container_statuses: Array<{
    name: string;
    image: string;
    ready: boolean;
    restart_count: number;
    state: { state: string; reason?: string; message?: string };
  }>;
  conditions: Array<{ type: string; status: string; reason?: string; message?: string }>;
}

export interface DeploymentInfo {
  name: string;
  namespace: string;
  replicas: number;
  ready_replicas: number;
  available_replicas: number;
  unavailable_replicas: number;
  updated_replicas: number;
  strategy: string | null;
  creation_timestamp: string;
  labels: Record<string, string>;
  conditions: Array<{ type: string; status: string; reason?: string; message?: string }>;
}

export interface ServiceInfo {
  name: string;
  namespace: string;
  type: string;
  cluster_ip: string | null;
  ports: Array<{ name?: string; port: number; target_port?: string; protocol: string; node_port?: number }>;
  selector: Record<string, string>;
  creation_timestamp: string;
}

export interface EventInfo {
  name: string;
  namespace: string;
  type: string;
  reason: string;
  message: string;
  count: number;
  involved_kind: string;
  involved_name: string;
  involved_namespace: string;
  source_component: string | null;
  first_timestamp: string | null;
  last_timestamp: string | null;
}

// ---- History Types ----

export interface ChatMessage {
  message_id: string;
  session_id: string;
  query: string;
  reply: string;
  context_summary: Record<string, any>;
  response_time_ms: number;
  timestamp: string;
}

export interface ChatSession {
  session_id: string;
  message_count: number;
  first_message: string;
  last_message: string;
  first_query: string;
}

export interface IncidentHistoryItem {
  incident_id: string;
  status: string;
  severity: string;
  what_went_wrong: string;
  observations: string[];
  affected_resources: Array<{ kind: string; name: string; namespace: string }>;
  created_at: string;
  resolved_at: string | null;
  duration_seconds?: number;
}

export interface ScanHistoryItem {
  scan_id: number;
  timestamp: string;
  duration_ms: number;
  namespaces_scanned: string[];
  counts: {
    pods: number;
    pods_running: number;
    pods_pending: number;
    pods_failed: number;
    nodes: number;
    nodes_ready: number;
    deployments: number;
    deployments_healthy: number;
    services: number;
  };
  anomalies_detected: number;
  incidents_created: number;
  active_incidents: number;
}

// ---- API Functions ----

export const api = {
  // Core
  getStatus: async (): Promise<AgentStatus> => {
    const res = await apiClient.get<AgentStatus>('/status');
    return res.data;
  },
  
  getIncidents: async (): Promise<IncidentReport[]> => {
    const res = await apiClient.get<IncidentReport[]>('/incidents');
    return res.data;
  },
  
  triggerScan: async (): Promise<{scan_id: string, message: string}> => {
    const res = await apiClient.post('/scan');
    return res.data;
  },
  
  getNamespaceSettings: async (): Promise<NamespaceSettings> => {
    const res = await apiClient.get<NamespaceSettings>('/settings/namespaces');
    return res.data;
  },
  
  toggleNamespace: async (namespace: string, enabled: boolean): Promise<NamespacePermission> => {
    const res = await apiClient.put<NamespacePermission>(`/settings/namespaces/${namespace}`, { enabled });
    return res.data;
  },

  askQuery: async (query: string, sessionId?: string): Promise<{ reply: string }> => {
    const res = await apiClient.post<{ reply: string }>('/chat', { query, session_id: sessionId });
    return res.data;
  },

  // Workloads
  getWorkloadsSummary: async (): Promise<WorkloadsSummary> => {
    const res = await apiClient.get<WorkloadsSummary>('/workloads/summary');
    return res.data;
  },

  getNodes: async (): Promise<NodeInfo[]> => {
    const res = await apiClient.get<NodeInfo[]>('/workloads/nodes');
    return res.data;
  },

  getPods: async (): Promise<PodInfo[]> => {
    const res = await apiClient.get<PodInfo[]>('/workloads/pods');
    return res.data;
  },

  getDeployments: async (): Promise<DeploymentInfo[]> => {
    const res = await apiClient.get<DeploymentInfo[]>('/workloads/deployments');
    return res.data;
  },

  getServices: async (): Promise<ServiceInfo[]> => {
    const res = await apiClient.get<ServiceInfo[]>('/workloads/services');
    return res.data;
  },

  getEvents: async (limit: number = 100): Promise<EventInfo[]> => {
    const res = await apiClient.get<EventInfo[]>(`/workloads/events?limit=${limit}`);
    return res.data;
  },

  // History
  getChatHistory: async (sessionId?: string, limit: number = 50): Promise<ChatMessage[]> => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (sessionId) params.set('session_id', sessionId);
    const res = await apiClient.get<ChatMessage[]>(`/history/chat?${params}`);
    return res.data;
  },

  getChatSessions: async (limit: number = 20): Promise<ChatSession[]> => {
    const res = await apiClient.get<ChatSession[]>(`/history/chat/sessions?limit=${limit}`);
    return res.data;
  },

  getIncidentHistory: async (limit: number = 50, status: string = 'all', severity: string = 'all'): Promise<IncidentHistoryItem[]> => {
    const res = await apiClient.get<IncidentHistoryItem[]>(`/history/incidents?limit=${limit}&status=${status}&severity=${severity}`);
    return res.data;
  },

  getScanHistory: async (limit: number = 100): Promise<ScanHistoryItem[]> => {
    const res = await apiClient.get<ScanHistoryItem[]>(`/history/scans?limit=${limit}`);
    return res.data;
  },

  getScanMetrics: async (hours: number = 24): Promise<ScanHistoryItem[]> => {
    const res = await apiClient.get<ScanHistoryItem[]>(`/history/scans/metrics?hours=${hours}`);
    return res.data;
  },
};
