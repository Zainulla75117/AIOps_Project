import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import type { AgentStatus } from '../api';
import { RefreshCw, Activity, Cpu, MessageSquare } from 'lucide-react';

const Overview: React.FC = () => {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);

  const fetchStatus = async () => {
    try {
      const data = await api.getStatus();
      setStatus(data);
    } catch (err) {
      console.error("Failed to fetch status", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleTriggerScan = async () => {
    setScanning(true);
    try {
      await api.triggerScan();
      setTimeout(fetchStatus, 3000);
    } catch (err) {
      console.error("Failed to trigger scan", err);
    } finally {
      setTimeout(() => setScanning(false), 1000);
    }
  };



  if (loading) return <div className="text-secondary p-6">Loading telemetry...</div>;
  if (!status) return <div className="text-critical p-6">AGENT DISCONNECTED</div>;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      
      {/* Header Strip */}
      <div style={{ 
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
        padding: 'var(--space-6)', borderBottom: '1px solid var(--border-subtle)' 
      }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', letterSpacing: '-0.03em' }}>Cluster Telemetry</h1>
          <p className="text-secondary font-mono mt-2" style={{ fontSize: '0.75rem', textTransform: 'uppercase' }}>
            {status.last_scan_at ? `T-MINUS 0s · LAST SYNC ${new Date(status.last_scan_at).toLocaleTimeString()}` : 'AWAITING FIRST SCAN'}
          </p>
        </div>
        <button className="btn btn-secondary" onClick={handleTriggerScan} disabled={scanning}>
          <RefreshCw size={14} className={scanning ? "spin" : ""} />
          {scanning ? "SCANNING..." : "FORCE SCAN"}
        </button>
      </div>

      {/* Asymmetric Split */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', flex: 1, minHeight: 0 }}>
        
        {/* Left: Massive Metrics + Chat */}
        <div style={{ padding: 'var(--space-8)', borderRight: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
          
          <div>
            <div className="text-muted font-mono mb-2" style={{ fontSize: '0.75rem', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <Activity size={14} /> ACTIVE INCIDENTS
            </div>
            <div className="font-mono" style={{ 
              fontSize: '8rem', 
              lineHeight: 0.9, 
              color: status.active_incidents > 0 ? 'var(--status-critical)' : 'var(--text-primary)',
              letterSpacing: '-0.05em'
            }}>
              {status.active_incidents.toString().padStart(2, '0')}
            </div>
          </div>

          {/* AI Chat CTA */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', background: 'rgba(17, 24, 39, 0.4)', borderRadius: '8px', border: '1px solid var(--border-subtle)', padding: 'var(--space-6)', textAlign: 'center' }}>
            <MessageSquare size={32} className="text-secondary mb-4" />
            <h3 style={{ fontSize: '1.1rem', marginBottom: 'var(--space-2)' }}>Ask the AI Agent</h3>
            <p className="text-muted" style={{ fontSize: '0.875rem', marginBottom: 'var(--space-6)', maxWidth: '300px' }}>
              Query live cluster data, troubleshoot incidents, and analyze logs using the context-aware assistant.
            </p>
            <Link to="/chat" className="btn btn-primary" style={{ padding: '12px 24px', fontSize: '0.875rem' }}>
              Open Agent Terminal
            </Link>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-6)', marginTop: 'auto' }}>
             <div>
                <div className="text-muted font-mono mb-2" style={{ fontSize: '0.75rem', textTransform: 'uppercase' }}>TOTAL SCANS EXECUTED</div>
                <div className="font-mono" style={{ fontSize: '2.5rem', letterSpacing: '-0.03em' }}>{status.total_scans}</div>
             </div>
             <div>
                <div className="text-muted font-mono mb-2" style={{ fontSize: '0.75rem', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                  <Cpu size={14} /> INFERENCE ENGINE
                </div>
                <div style={{ fontSize: '1.25rem', marginTop: 'var(--space-4)' }}>
                  {status.gemini_available ? (
                    <span style={{ color: 'var(--status-success)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      <span className="status-dot online"></span> ONLINE (GEMINI)
                    </span>
                  ) : (
                    <span style={{ color: 'var(--status-warning)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      <span className="status-dot" style={{ backgroundColor: 'var(--status-warning)' }}></span> DEGRADED (RULES ONLY)
                    </span>
                  )}
                </div>
             </div>
          </div>
        </div>

        {/* Right: Namespace Ticker */}
        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: 'var(--space-4) var(--space-6)', borderBottom: '1px solid var(--border-subtle)' }}>
            <span className="text-muted font-mono" style={{ fontSize: '0.75rem', textTransform: 'uppercase' }}>MONITORED SCOPE ({status.monitored_namespaces.length})</span>
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {status.monitored_namespaces.map(ns => (
              <div key={ns} style={{ 
                padding: 'var(--space-4) var(--space-6)', 
                borderBottom: '1px solid var(--border-subtle)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <span className="font-mono" style={{ fontSize: '0.875rem' }}>{ns}</span>
                <span className="status-dot" style={{ backgroundColor: 'var(--status-success)' }}></span>
              </div>
            ))}
            {status.monitored_namespaces.length === 0 && (
              <div className="text-muted" style={{ padding: 'var(--space-6)', fontSize: '0.875rem' }}>No namespaces configured.</div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};

export default Overview;
