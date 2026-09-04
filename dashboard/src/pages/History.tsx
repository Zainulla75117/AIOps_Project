import React, { useEffect, useState } from 'react';
import { api } from '../api';
import type { ChatMessage, IncidentHistoryItem, ScanHistoryItem } from '../api';
import ReactMarkdown from 'react-markdown';
import { MessageSquare, AlertTriangle, BarChart3, RefreshCw, Clock, Zap } from 'lucide-react';

type TabKey = 'chat' | 'incidents' | 'scans';

const History: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabKey>('chat');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [incidents, setIncidents] = useState<IncidentHistoryItem[]>([]);
  const [scans, setScans] = useState<ScanHistoryItem[]>([]);
  const [incidentFilter, setIncidentFilter] = useState<string>('all');

  const fetchData = async (tab?: TabKey) => {
    const t = tab || activeTab;
    try {
      if (t === 'chat') {
        const data = await api.getChatHistory(undefined, 100);
        setChatMessages(data);
      } else if (t === 'incidents') {
        const data = await api.getIncidentHistory(100, incidentFilter);
        setIncidents(data);
      } else if (t === 'scans') {
        const data = await api.getScanHistory(100);
        setScans(data);
      }
    } catch (err) {
      console.error(`Failed to fetch ${t} history`, err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchData();
  }, [activeTab, incidentFilter]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  const tabs: { key: TabKey; label: string; icon: React.ReactNode }[] = [
    { key: 'chat', label: 'Chat History', icon: <MessageSquare size={14} /> },
    { key: 'incidents', label: 'Incident Timeline', icon: <AlertTriangle size={14} /> },
    { key: 'scans', label: 'Scan Metrics', icon: <BarChart3 size={14} /> },
  ];

  const formatTime = (ts: string) => {
    const d = new Date(ts);
    return d.toLocaleString();
  };

  const formatDuration = (seconds: number | undefined) => {
    if (!seconds) return '—';
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  };

  const severityClass = (severity: string) => {
    switch (severity) {
      case 'critical': return 'badge-critical';
      case 'warning': return 'badge-warning';
      case 'info': return 'badge-info';
      default: return 'badge-neutral';
    }
  };

  const statusClass = (status: string) => {
    switch (status) {
      case 'open': return 'badge-critical';
      case 'resolved': return 'badge-success';
      case 'acknowledged': return 'badge-warning';
      default: return 'badge-neutral';
    }
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: 'var(--space-4) var(--space-6)', borderBottom: '1px solid var(--border-subtle)'
      }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', letterSpacing: '-0.03em' }}>History</h1>
          <p className="text-muted font-mono mt-2" style={{ fontSize: '0.7rem', textTransform: 'uppercase' }}>
            PERSISTED DATA · MONGODB
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
            onClick={() => setActiveTab(tab.key)}
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
            {/* ---- Chat History ---- */}
            {activeTab === 'chat' && (
              <div className="history-chat-list">
                {chatMessages.length === 0 && (
                  <div className="text-muted" style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
                    No chat history yet. Start a conversation from the Overview page.
                  </div>
                )}
                {chatMessages.map((msg) => (
                  <div key={msg.message_id} className="history-chat-item">
                    <div className="history-chat-meta">
                      <span className="text-muted font-mono" style={{ fontSize: '0.7rem' }}>
                        <Clock size={10} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
                        {formatTime(msg.timestamp)}
                      </span>
                      <span className="text-muted font-mono" style={{ fontSize: '0.7rem' }}>
                        <Zap size={10} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
                        {Math.round(msg.response_time_ms)}ms
                      </span>
                      {msg.context_summary?.pods !== undefined && (
                        <span className="text-muted font-mono" style={{ fontSize: '0.65rem' }}>
                          Context: {msg.context_summary.pods} pods · {msg.context_summary.nodes} nodes · {msg.context_summary.deployments} deps
                        </span>
                      )}
                    </div>
                    <div className="history-chat-query">
                      <span className="text-muted font-mono" style={{ marginRight: '6px' }}>&gt;</span>
                      {msg.query}
                    </div>
                    <div className="history-chat-reply">
                      <ReactMarkdown>{msg.reply}</ReactMarkdown>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* ---- Incident Timeline ---- */}
            {activeTab === 'incidents' && (
              <div>
                <div style={{ marginBottom: 'var(--space-4)', display: 'flex', gap: 'var(--space-3)' }}>
                  {['all', 'open', 'resolved'].map(f => (
                    <button
                      key={f}
                      className={`btn ${incidentFilter === f ? 'btn-primary' : 'btn-secondary'}`}
                      onClick={() => setIncidentFilter(f)}
                      style={{ fontSize: '0.75rem', textTransform: 'uppercase' }}
                    >
                      {f}
                    </button>
                  ))}
                </div>

                {incidents.length === 0 && (
                  <div className="text-muted" style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
                    No incidents recorded yet.
                  </div>
                )}

                <div className="history-incident-list">
                  {incidents.map((inc) => (
                    <div key={inc.incident_id} className="history-incident-item">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
                        <span className={`badge ${severityClass(inc.severity)}`}>{inc.severity}</span>
                        <span className={`badge ${statusClass(inc.status)}`}>{inc.status}</span>
                        <span className="text-muted font-mono" style={{ fontSize: '0.7rem', marginLeft: 'auto' }}>
                          {formatTime(inc.created_at)}
                        </span>
                      </div>
                      <div style={{ fontWeight: 500, marginBottom: 'var(--space-2)' }}>{inc.what_went_wrong}</div>
                      {inc.affected_resources.length > 0 && (
                        <div className="text-secondary" style={{ fontSize: '0.8rem' }}>
                          Affected: {inc.affected_resources.map(r => `${r.kind}/${r.name}`).join(', ')}
                        </div>
                      )}
                      {inc.resolved_at && (
                        <div className="text-muted" style={{ fontSize: '0.75rem', marginTop: 'var(--space-2)' }}>
                          Resolved: {formatTime(inc.resolved_at)}
                          {inc.duration_seconds ? ` (${formatDuration(inc.duration_seconds)})` : ''}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ---- Scan Metrics ---- */}
            {activeTab === 'scans' && (
              <div>
                {scans.length === 0 && (
                  <div className="text-muted" style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
                    No scan history yet. Scans are recorded every {60}s.
                  </div>
                )}

                {/* Summary cards from latest scan */}
                {scans.length > 0 && (
                  <div className="workloads-summary-grid mb-6">
                    <div className="summary-card">
                      <div className="summary-card-header"><BarChart3 size={14} className="text-muted" /><span>Total Scans</span></div>
                      <div className="summary-card-value">{scans.length}</div>
                    </div>
                    <div className="summary-card">
                      <div className="summary-card-header"><Zap size={14} className="text-muted" /><span>Avg Duration</span></div>
                      <div className="summary-card-value">{Math.round(scans.reduce((s, sc) => s + sc.duration_ms, 0) / scans.length)}ms</div>
                    </div>
                    <div className="summary-card">
                      <div className="summary-card-header"><AlertTriangle size={14} className="text-muted" /><span>Total Anomalies</span></div>
                      <div className="summary-card-value">{scans.reduce((s, sc) => s + sc.anomalies_detected, 0)}</div>
                    </div>
                  </div>
                )}

                <div className="workloads-table-wrap">
                  <table className="workloads-table">
                    <thead>
                      <tr>
                        <th>Scan #</th>
                        <th>Time</th>
                        <th>Duration</th>
                        <th>Pods</th>
                        <th>Nodes</th>
                        <th>Deployments</th>
                        <th>Anomalies</th>
                        <th>Incidents</th>
                      </tr>
                    </thead>
                    <tbody>
                      {scans.map((scan) => (
                        <tr key={scan.scan_id}>
                          <td className="font-mono">#{scan.scan_id}</td>
                          <td className="text-muted font-mono" style={{ fontSize: '0.75rem' }}>
                            {new Date(scan.timestamp).toLocaleTimeString()}
                          </td>
                          <td className="font-mono">{Math.round(scan.duration_ms)}ms</td>
                          <td className="font-mono">
                            <span className="text-success">{scan.counts.pods_running}</span>
                            <span className="text-muted">/{scan.counts.pods}</span>
                          </td>
                          <td className="font-mono">
                            <span className="text-success">{scan.counts.nodes_ready}</span>
                            <span className="text-muted">/{scan.counts.nodes}</span>
                          </td>
                          <td className="font-mono">
                            <span className="text-success">{scan.counts.deployments_healthy}</span>
                            <span className="text-muted">/{scan.counts.deployments}</span>
                          </td>
                          <td className={`font-mono ${scan.anomalies_detected > 0 ? 'text-warning' : 'text-muted'}`}>
                            {scan.anomalies_detected}
                          </td>
                          <td className={`font-mono ${scan.incidents_created > 0 ? 'text-critical' : 'text-muted'}`}>
                            {scan.incidents_created}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default History;
