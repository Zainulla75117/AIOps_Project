import React, { useEffect, useState } from 'react';
import { api } from '../api';
import type { WorkloadsSummary, NodeInfo, PodInfo, DeploymentInfo, ServiceInfo, EventInfo } from '../api';
import { RefreshCw, Server, Box, Layers, Globe, AlertTriangle, Activity } from 'lucide-react';

type TabKey = 'overview' | 'nodes' | 'pods' | 'deployments' | 'services' | 'events';

const Workloads: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [summary, setSummary] = useState<WorkloadsSummary | null>(null);
  const [nodes, setNodes] = useState<NodeInfo[]>([]);
  const [pods, setPods] = useState<PodInfo[]>([]);
  const [deployments, setDeployments] = useState<DeploymentInfo[]>([]);
  const [services, setServices] = useState<ServiceInfo[]>([]);
  const [events, setEvents] = useState<EventInfo[]>([]);

  const fetchData = async (tab?: TabKey) => {
    const t = tab || activeTab;
    try {
      if (t === 'overview') {
        const data = await api.getWorkloadsSummary();
        setSummary(data);
      } else if (t === 'nodes') {
        const data = await api.getNodes();
        setNodes(data);
      } else if (t === 'pods') {
        const data = await api.getPods();
        setPods(data);
      } else if (t === 'deployments') {
        const data = await api.getDeployments();
        setDeployments(data);
      } else if (t === 'services') {
        const data = await api.getServices();
        setServices(data);
      } else if (t === 'events') {
        const data = await api.getEvents();
        setEvents(data);
      }
    } catch (err) {
      console.error(`Failed to fetch ${t}`, err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchData();
    const interval = setInterval(() => fetchData(), 30000);
    return () => clearInterval(interval);
  }, [activeTab]);

  const handleTabChange = (tab: TabKey) => {
    setActiveTab(tab);
  };

  const handleRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  const tabs: { key: TabKey; label: string; icon: React.ReactNode }[] = [
    { key: 'overview', label: 'Overview', icon: <Activity size={14} /> },
    { key: 'nodes', label: 'Nodes', icon: <Server size={14} /> },
    { key: 'pods', label: 'Pods', icon: <Box size={14} /> },
    { key: 'deployments', label: 'Deployments', icon: <Layers size={14} /> },
    { key: 'services', label: 'Services', icon: <Globe size={14} /> },
    { key: 'events', label: 'Events', icon: <AlertTriangle size={14} /> },
  ];

  const getAge = (ts: string | null) => {
    if (!ts) return '—';
    const diff = Date.now() - new Date(ts).getTime();
    const days = Math.floor(diff / 86400000);
    const hours = Math.floor((diff % 86400000) / 3600000);
    const mins = Math.floor((diff % 3600000) / 60000);
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${mins}m`;
    return `${mins}m`;
  };

  const phaseColor = (phase: string) => {
    switch (phase) {
      case 'Running': return 'var(--status-success)';
      case 'Pending': return 'var(--status-warning)';
      case 'Failed': return 'var(--status-critical)';
      case 'Succeeded': return 'var(--status-info)';
      default: return 'var(--text-muted)';
    }
  };

  const getNodeStatus = (node: NodeInfo) => {
    const ready = node.conditions.find(c => c.type === 'Ready');
    return ready?.status === 'True' ? 'Ready' : 'NotReady';
  };

  const getNodeIssues = (node: NodeInfo) => {
    const issues: string[] = [];
    node.conditions.forEach(c => {
      if (c.type !== 'Ready' && c.status === 'True') issues.push(c.type);
      if (c.type === 'Ready' && c.status !== 'True') issues.push('NotReady');
    });
    if (node.unschedulable) issues.push('Unschedulable');
    return issues;
  };

  const getTotalRestarts = (pod: PodInfo) => {
    return pod.container_statuses.reduce((sum, cs) => sum + cs.restart_count, 0);
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: 'var(--space-4) var(--space-6)', borderBottom: '1px solid var(--border-subtle)'
      }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', letterSpacing: '-0.03em' }}>Workloads</h1>
          <p className="text-muted font-mono mt-2" style={{ fontSize: '0.7rem', textTransform: 'uppercase' }}>
            LIVE CLUSTER RESOURCES · ENABLED NAMESPACES
          </p>
        </div>
        <button className="btn btn-secondary" onClick={handleRefresh} disabled={refreshing}>
          <RefreshCw size={14} className={refreshing ? 'spin' : ''} />
          {refreshing ? 'REFRESHING...' : 'REFRESH'}
        </button>
      </div>

      {/* Tabs */}
      <div className="workloads-tabs">
        {tabs.map(tab => (
          <button
            key={tab.key}
            className={`workloads-tab ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => handleTabChange(tab.key)}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: 'var(--space-6)' }}>
        {loading ? (
          <div className="text-secondary" style={{ padding: 'var(--space-8)' }}>Loading...</div>
        ) : (
          <>
            {/* ---- Overview ---- */}
            {activeTab === 'overview' && summary && (
              <div className="workloads-summary-grid">
                <div className="summary-card">
                  <div className="summary-card-header">
                    <Box size={16} className="text-muted" />
                    <span>Pods</span>
                  </div>
                  <div className="summary-card-value">{summary.pods.total}</div>
                  <div className="summary-card-breakdown">
                    <span className="text-success">{summary.pods.running} Running</span>
                    {summary.pods.pending > 0 && <span className="text-warning">{summary.pods.pending} Pending</span>}
                    {summary.pods.failed > 0 && <span className="text-critical">{summary.pods.failed} Failed</span>}
                    {summary.pods.succeeded > 0 && <span className="text-info">{summary.pods.succeeded} Completed</span>}
                  </div>
                </div>

                <div className="summary-card">
                  <div className="summary-card-header">
                    <Server size={16} className="text-muted" />
                    <span>Nodes</span>
                  </div>
                  <div className="summary-card-value">{summary.nodes.total}</div>
                  <div className="summary-card-breakdown">
                    <span className="text-success">{summary.nodes.ready} Ready</span>
                    {summary.nodes.not_ready > 0 && <span className="text-critical">{summary.nodes.not_ready} NotReady</span>}
                  </div>
                </div>

                <div className="summary-card">
                  <div className="summary-card-header">
                    <Layers size={16} className="text-muted" />
                    <span>Deployments</span>
                  </div>
                  <div className="summary-card-value">{summary.deployments.total}</div>
                  <div className="summary-card-breakdown">
                    <span className="text-success">{summary.deployments.healthy} Healthy</span>
                    {summary.deployments.unhealthy > 0 && <span className="text-critical">{summary.deployments.unhealthy} Unhealthy</span>}
                  </div>
                </div>

                <div className="summary-card">
                  <div className="summary-card-header">
                    <Globe size={16} className="text-muted" />
                    <span>Services</span>
                  </div>
                  <div className="summary-card-value">{summary.services.total}</div>
                </div>

                <div className="summary-card">
                  <div className="summary-card-header">
                    <AlertTriangle size={16} className="text-muted" />
                    <span>Events</span>
                  </div>
                  <div className="summary-card-value">{summary.events.total}</div>
                  <div className="summary-card-breakdown">
                    {summary.events.warning > 0 && <span className="text-warning">{summary.events.warning} Warnings</span>}
                    <span className="text-muted">{summary.events.normal} Normal</span>
                  </div>
                </div>

                <div className="summary-card">
                  <div className="summary-card-header">
                    <Activity size={16} className="text-muted" />
                    <span>Namespaces</span>
                  </div>
                  <div className="summary-card-value">{summary.namespaces_monitored.length}</div>
                  <div className="summary-card-breakdown">
                    {summary.namespaces_monitored.map(ns => (
                      <span key={ns} className="text-secondary">{ns}</span>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* ---- Nodes ---- */}
            {activeTab === 'nodes' && (
              <div className="workloads-table-wrap">
                <table className="workloads-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Status</th>
                      <th>Kubelet</th>
                      <th>CPU</th>
                      <th>Memory</th>
                      <th>Pods</th>
                      <th>Runtime</th>
                      <th>Issues</th>
                      <th>Age</th>
                    </tr>
                  </thead>
                  <tbody>
                    {nodes.map(node => {
                      const status = getNodeStatus(node);
                      const issues = getNodeIssues(node);
                      return (
                        <tr key={node.name}>
                          <td className="font-mono">{node.name}</td>
                          <td>
                            <span className={`badge ${status === 'Ready' ? 'badge-success' : 'badge-critical'}`}>
                              {status}
                            </span>
                          </td>
                          <td className="text-secondary font-mono">{node.kubelet_version || '—'}</td>
                          <td className="text-secondary font-mono">{node.capacity_cpu || '—'}</td>
                          <td className="text-secondary font-mono">{node.capacity_memory || '—'}</td>
                          <td className="text-secondary font-mono">{node.capacity_pods || '—'}</td>
                          <td className="text-secondary font-mono" style={{ fontSize: '0.75rem' }}>{node.container_runtime || '—'}</td>
                          <td>
                            {issues.length > 0 ? issues.map(i => (
                              <span key={i} className="badge badge-warning mr-3" style={{ marginRight: '4px' }}>{i}</span>
                            )) : <span className="text-muted">—</span>}
                          </td>
                          <td className="text-muted font-mono">{getAge(node.creation_timestamp)}</td>
                        </tr>
                      );
                    })}
                    {nodes.length === 0 && (
                      <tr><td colSpan={9} className="text-muted" style={{ textAlign: 'center', padding: 'var(--space-8)' }}>No nodes found</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* ---- Pods ---- */}
            {activeTab === 'pods' && (
              <div className="workloads-table-wrap">
                <table className="workloads-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Namespace</th>
                      <th>Phase</th>
                      <th>Restarts</th>
                      <th>Containers</th>
                      <th>Node</th>
                      <th>Owner</th>
                      <th>Age</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pods.map(pod => {
                      const restarts = getTotalRestarts(pod);
                      const readyContainers = pod.container_statuses.filter(c => c.ready).length;
                      const totalContainers = pod.container_statuses.length;
                      return (
                        <tr key={`${pod.namespace}/${pod.name}`}>
                          <td className="font-mono">{pod.name}</td>
                          <td className="text-secondary">{pod.namespace}</td>
                          <td>
                            <span style={{ color: phaseColor(pod.phase), fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                              ● {pod.phase}
                            </span>
                          </td>
                          <td className={`font-mono ${restarts >= 5 ? 'text-critical' : restarts > 0 ? 'text-warning' : 'text-muted'}`}>
                            {restarts}
                          </td>
                          <td className="font-mono text-secondary">{readyContainers}/{totalContainers}</td>
                          <td className="text-muted font-mono" style={{ fontSize: '0.75rem' }}>{pod.node_name || '—'}</td>
                          <td className="text-muted" style={{ fontSize: '0.75rem' }}>
                            {pod.owner_kind ? `${pod.owner_kind}/${pod.owner_name}` : '—'}
                          </td>
                          <td className="text-muted font-mono">{getAge(pod.creation_timestamp)}</td>
                        </tr>
                      );
                    })}
                    {pods.length === 0 && (
                      <tr><td colSpan={8} className="text-muted" style={{ textAlign: 'center', padding: 'var(--space-8)' }}>No pods found</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* ---- Deployments ---- */}
            {activeTab === 'deployments' && (
              <div className="workloads-table-wrap">
                <table className="workloads-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Namespace</th>
                      <th>Desired</th>
                      <th>Ready</th>
                      <th>Available</th>
                      <th>Unavailable</th>
                      <th>Strategy</th>
                      <th>Status</th>
                      <th>Age</th>
                    </tr>
                  </thead>
                  <tbody>
                    {deployments.map(dep => {
                      const healthy = dep.available_replicas >= dep.replicas && dep.unavailable_replicas === 0;
                      return (
                        <tr key={`${dep.namespace}/${dep.name}`}>
                          <td className="font-mono">{dep.name}</td>
                          <td className="text-secondary">{dep.namespace}</td>
                          <td className="font-mono">{dep.replicas}</td>
                          <td className={`font-mono ${dep.ready_replicas < dep.replicas ? 'text-warning' : ''}`}>
                            {dep.ready_replicas}
                          </td>
                          <td className={`font-mono ${dep.available_replicas < dep.replicas ? 'text-warning' : ''}`}>
                            {dep.available_replicas}
                          </td>
                          <td className={`font-mono ${dep.unavailable_replicas > 0 ? 'text-critical' : 'text-muted'}`}>
                            {dep.unavailable_replicas}
                          </td>
                          <td className="text-muted font-mono" style={{ fontSize: '0.75rem' }}>{dep.strategy || '—'}</td>
                          <td>
                            <span className={`badge ${healthy ? 'badge-success' : 'badge-critical'}`}>
                              {healthy ? 'Healthy' : 'Degraded'}
                            </span>
                          </td>
                          <td className="text-muted font-mono">{getAge(dep.creation_timestamp)}</td>
                        </tr>
                      );
                    })}
                    {deployments.length === 0 && (
                      <tr><td colSpan={9} className="text-muted" style={{ textAlign: 'center', padding: 'var(--space-8)' }}>No deployments found</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* ---- Services ---- */}
            {activeTab === 'services' && (
              <div className="workloads-table-wrap">
                <table className="workloads-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Namespace</th>
                      <th>Type</th>
                      <th>Cluster IP</th>
                      <th>Ports</th>
                      <th>Age</th>
                    </tr>
                  </thead>
                  <tbody>
                    {services.map(svc => (
                      <tr key={`${svc.namespace}/${svc.name}`}>
                        <td className="font-mono">{svc.name}</td>
                        <td className="text-secondary">{svc.namespace}</td>
                        <td>
                          <span className="badge badge-neutral">{svc.type}</span>
                        </td>
                        <td className="text-secondary font-mono">{svc.cluster_ip || '—'}</td>
                        <td className="font-mono text-secondary" style={{ fontSize: '0.75rem' }}>
                          {svc.ports.map(p => `${p.port}/${p.protocol}${p.node_port ? `:${p.node_port}` : ''}`).join(', ') || '—'}
                        </td>
                        <td className="text-muted font-mono">{getAge(svc.creation_timestamp)}</td>
                      </tr>
                    ))}
                    {services.length === 0 && (
                      <tr><td colSpan={6} className="text-muted" style={{ textAlign: 'center', padding: 'var(--space-8)' }}>No services found</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* ---- Events ---- */}
            {activeTab === 'events' && (
              <div className="workloads-table-wrap">
                <table className="workloads-table">
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>Reason</th>
                      <th>Resource</th>
                      <th>Message</th>
                      <th>Count</th>
                      <th>Last Seen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((evt, idx) => (
                      <tr key={`${evt.namespace}/${evt.name}-${idx}`} className={evt.type === 'Warning' ? 'event-warning-row' : ''}>
                        <td>
                          <span className={`badge ${evt.type === 'Warning' ? 'badge-warning' : 'badge-neutral'}`}>
                            {evt.type}
                          </span>
                        </td>
                        <td className="font-mono">{evt.reason}</td>
                        <td className="text-secondary font-mono" style={{ fontSize: '0.75rem' }}>
                          {evt.involved_kind}/{evt.involved_name}
                        </td>
                        <td className="text-secondary" style={{ fontSize: '0.8rem', maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {evt.message}
                        </td>
                        <td className={`font-mono ${evt.count > 5 ? 'text-warning' : 'text-muted'}`}>{evt.count}</td>
                        <td className="text-muted font-mono" style={{ fontSize: '0.75rem' }}>
                          {evt.last_timestamp ? new Date(evt.last_timestamp).toLocaleTimeString() : '—'}
                        </td>
                      </tr>
                    ))}
                    {events.length === 0 && (
                      <tr><td colSpan={6} className="text-muted" style={{ textAlign: 'center', padding: 'var(--space-8)' }}>No events found</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default Workloads;
