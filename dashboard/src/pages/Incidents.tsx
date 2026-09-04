import React, { useEffect, useState } from 'react';
import { api } from '../api';
import type { IncidentReport } from '../api';
import { formatDistanceToNow } from 'date-fns';
import { Cpu, CheckCircle2, FileText, ChevronRight, X } from 'lucide-react';

const SeverityBadge: React.FC<{ severity: string }> = ({ severity }) => {
  if (severity === 'critical') return <span className="badge badge-critical">CRITICAL</span>;
  if (severity === 'warning') return <span className="badge badge-warning">WARNING</span>;
  return <span className="badge badge-info">INFO</span>;
};

const Incidents: React.FC = () => {
  const [incidents, setIncidents] = useState<IncidentReport[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<IncidentReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchIncidents = async () => {
      try {
        const data = await api.getIncidents();
        setIncidents(data);
      } catch (err) {
        console.error("Failed to fetch incidents", err);
      } finally {
        setLoading(false);
      }
    };
    fetchIncidents();
    const interval = setInterval(fetchIncidents, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="text-secondary p-6 font-mono text-sm">INITIALIZING INCIDENT STREAM...</div>;

  // Detail View
  if (selectedIncident) {
    const inc = selectedIncident;
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        
        {/* Detail Header */}
        <div style={{ 
          display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
          padding: 'var(--space-6)', borderBottom: '1px solid var(--border-subtle)' 
        }}>
          <div>
             <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
               <SeverityBadge severity={inc.severity} />
               <span className="text-muted font-mono" style={{ fontSize: '0.75rem' }}>{inc.id}</span>
             </div>
             <h1 style={{ fontSize: '1.25rem', letterSpacing: '-0.02em', margin: 0 }}>{inc.what_went_wrong}</h1>
          </div>
          <button className="btn btn-secondary" onClick={() => setSelectedIncident(null)}>
            <X size={16} /> CLOSE
          </button>
        </div>

        {/* Vertical Split Pane */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', flex: 1, minHeight: 0 }}>
          
          {/* Left Pane: Analysis & Recommendation */}
          <div style={{ borderRight: '1px solid var(--border-subtle)', overflowY: 'auto' }}>
             
             {/* Affected Resources Strip */}
             <div style={{ padding: 'var(--space-4) var(--space-6)', borderBottom: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-surface)' }}>
                <span className="text-muted font-mono" style={{ fontSize: '0.75rem', textTransform: 'uppercase', marginRight: 'var(--space-4)' }}>SCOPE</span>
                <span className="font-mono text-sm">
                  {inc.affected_resources.map(r => `${r.namespace}/${r.name}`).join(', ')}
                </span>
             </div>

             <div style={{ padding: 'var(--space-6)' }}>
                <div className="mb-8">
                  <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', textTransform: 'uppercase', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                    <Cpu size={14} className="text-info" /> ROOT CAUSE ANALYSIS
                  </h3>
                  {inc.root_cause ? (
                    <>
                      <p style={{ marginBottom: '16px', fontSize: '1rem', color: 'var(--text-primary)' }}>{inc.root_cause.description}</p>
                      <div className="font-mono text-secondary" style={{ fontSize: '0.8125rem', paddingLeft: 'var(--space-4)', borderLeft: '1px solid var(--border-subtle)' }}>
                        {inc.root_cause.reasoning}
                      </div>
                    </>
                  ) : (
                    <p className="font-mono text-secondary text-sm">ERR_NO_LLM_INFERENCE</p>
                  )}
                </div>

                <div>
                  <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', textTransform: 'uppercase', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                    <CheckCircle2 size={14} className="text-success" /> RECOMMENDED ACTION
                  </h3>
                  {inc.recommendation ? (
                    <>
                      <p style={{ fontWeight: 500, marginBottom: '8px', color: 'var(--status-success)', fontSize: '1rem' }}>
                        {inc.recommendation.action}
                      </p>
                      <p className="text-secondary mb-4 text-sm">{inc.recommendation.rationale}</p>
                      
                      {inc.recommendation.commands.length > 0 && (
                        <div className="mt-6">
                          {inc.recommendation.commands.map((cmd, i) => (
                            <pre key={i} className="mb-2" style={{ border: '1px solid var(--border-strong)' }}><code>{cmd}</code></pre>
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="font-mono text-secondary text-sm">ERR_NO_REMEDIATION</p>
                  )}
                </div>
             </div>
          </div>

          {/* Right Pane: Raw Evidence */}
          <div style={{ overflowY: 'auto', backgroundColor: 'var(--bg-app)', display: 'flex', flexDirection: 'column' }}>
             <div style={{ padding: 'var(--space-4) var(--space-6)', borderBottom: '1px solid var(--border-subtle)', position: 'sticky', top: 0, backgroundColor: 'var(--bg-app)' }}>
                <span className="text-muted font-mono" style={{ fontSize: '0.75rem', textTransform: 'uppercase' }}>RAW EVIDENCE & OBSERVATIONS</span>
             </div>
             
             <div style={{ padding: 'var(--space-6)', flex: 1 }}>
                <ul style={{ paddingLeft: 0, listStyle: 'none', marginBottom: 'var(--space-8)' }}>
                  {inc.observations.map((obs, i) => (
                    <li key={i} className="font-mono text-secondary" style={{ fontSize: '0.8125rem', marginBottom: 'var(--space-3)', paddingLeft: 'var(--space-3)', borderLeft: '1px solid var(--border-strong)' }}>
                      {obs}
                    </li>
                  ))}
                </ul>

                {inc.log_snippets.length > 0 && (
                  <div>
                    <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', textTransform: 'uppercase', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                      <FileText size={14} /> SANITIZED LOG STREAM
                    </h3>
                    <pre style={{ border: 'none', padding: 0 }}>
                      <code style={{ background: 'transparent', padding: 0 }}>{inc.log_snippets.join('\n')}</code>
                    </pre>
                  </div>
                )}
             </div>
          </div>

        </div>
      </div>
    );
  }

  // List View
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: 'var(--space-6)', borderBottom: '1px solid var(--border-subtle)' }}>
        <h1 style={{ fontSize: '1.25rem', letterSpacing: '-0.03em', margin: 0 }}>Active Incidents</h1>
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {incidents.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
            <CheckCircle2 size={32} style={{ color: 'var(--status-success)', marginBottom: 'var(--space-4)' }} />
            <span className="font-mono text-sm uppercase">SYSTEM NOMINAL // NO ANOMALIES DETECTED</span>
          </div>
        ) : (
          <div>
            {incidents.map((inc) => (
              <div 
                key={inc.id} 
                className="data-grid-row"
                onClick={() => setSelectedIncident(inc)} 
                style={{ cursor: 'pointer', display: 'grid', gridTemplateColumns: '80px 1fr 200px 150px 40px', gap: 'var(--space-4)' }}
              >
                <div><SeverityBadge severity={inc.severity} /></div>
                <div style={{ fontWeight: 500, display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                  {inc.what_went_wrong}
                  {!inc.llm_analysis_available && <span className="badge badge-neutral">RULES</span>}
                </div>
                <div className="font-mono text-secondary" style={{ fontSize: '0.8125rem' }}>
                  {inc.affected_resources[0]?.namespace}/{inc.affected_resources[0]?.name}
                </div>
                <div className="font-mono text-muted" style={{ fontSize: '0.75rem', textTransform: 'uppercase' }}>
                  {formatDistanceToNow(new Date(inc.timestamp), { addSuffix: true })}
                </div>
                <div style={{ textAlign: 'right' }}><ChevronRight size={16} className="text-muted" /></div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Incidents;
