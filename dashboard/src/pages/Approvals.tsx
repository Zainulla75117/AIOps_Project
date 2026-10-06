import React, { useState, useEffect } from 'react';
import { Check, X, Terminal, Clock, RefreshCw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { api, type PlanSummary, type PlanContent } from '../api';

const Approvals: React.FC = () => {
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [currentPlanContent, setCurrentPlanContent] = useState<PlanContent | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [status, setStatus] = useState<'pending' | 'approved' | 'rejected'>('pending');

  const fetchPlans = async () => {
    setLoading(true);
    try {
      const pendingPlans = await api.getPlans();
      setPlans(pendingPlans);
      
      if (pendingPlans.length > 0) {
        const content = await api.getPlan(pendingPlans[0].id);
        setCurrentPlanContent(content);
        setStatus('pending');
      } else {
        setCurrentPlanContent(null);
      }
    } catch (error) {
      console.error("Failed to fetch plans:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlans();
  }, []);

  const handleApprove = () => {
    setStatus('approved');
    // TODO: Call API to execute plan. For now we just mock the status change.
    setTimeout(() => {
      fetchPlans(); // Refresh the list after execution
    }, 2000);
  };

  const handleReject = () => {
    setStatus('rejected');
    // TODO: Call API to discard plan.
    setTimeout(() => {
      fetchPlans();
    }, 2000);
  };

  return (
    <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto', fontFamily: 'var(--font-sans)' }}>
      <header style={{ marginBottom: '2rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Clock size={20} className="text-muted" />
            Pending Approvals {plans.length > 0 && `(${plans.length})`}
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
            Review and approve remediation plans drafted by the AIOps agent.
          </p>
        </div>
        <button 
          onClick={fetchPlans}
          style={{ padding: '0.5rem', border: '1px solid var(--border-color)', borderRadius: '4px', backgroundColor: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
        >
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </header>

      {loading ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Loading plans...</div>
      ) : plans.length === 0 ? (
        <div style={{ padding: '3rem', textAlign: 'center', border: '1px dashed var(--border-color)', borderRadius: '8px', color: 'var(--text-muted)' }}>
          <Check size={48} style={{ margin: '0 auto 1rem auto', color: '#10b981', opacity: 0.5 }} />
          <h3>All Caught Up</h3>
          <p>There are no pending remediation plans requiring your approval.</p>
        </div>
      ) : status === 'pending' && currentPlanContent ? (
        <div style={{ 
          border: '1px solid var(--border-color)', 
          borderRadius: '8px', 
          overflow: 'hidden',
          backgroundColor: 'var(--surface-color)',
          boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
        }}>
          <div style={{ padding: '1.5rem', backgroundColor: '#fafafa', borderBottom: '1px solid var(--border-color)' }}>
            <h2 style={{ fontSize: '1.125rem', fontWeight: 500, marginBottom: '0.5rem' }}>
              Action Required: Review Plan
            </h2>
            <div style={{ display: 'flex', gap: '1rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
              <span>ID: {currentPlanContent.id}</span>
              <span>Source: .brain/plans/{currentPlanContent.id}.md</span>
            </div>
          </div>
          
          <div style={{ padding: '1.5rem', fontSize: '0.9rem', lineHeight: 1.6 }} className="markdown-body">
            <ReactMarkdown>{currentPlanContent.content}</ReactMarkdown>
          </div>

          <div style={{ 
            padding: '1rem 1.5rem', 
            backgroundColor: '#fafafa', 
            borderTop: '1px solid var(--border-color)',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '1rem'
          }}>
            <button 
              onClick={handleReject}
              style={{ 
                padding: '0.5rem 1rem', 
                borderRadius: '4px', 
                border: '1px solid var(--border-color)',
                backgroundColor: 'white',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}
            >
              <X size={16} /> Reject
            </button>
            <button 
              onClick={handleApprove}
              style={{ 
                padding: '0.5rem 1rem', 
                borderRadius: '4px', 
                border: 'none',
                backgroundColor: '#10b981',
                color: 'white',
                fontWeight: 500,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}
            >
              <Check size={16} /> Approve & Run
            </button>
          </div>
        </div>
      ) : (
        <div style={{ 
          padding: '2rem', 
          textAlign: 'center', 
          border: '1px dashed var(--border-color)', 
          borderRadius: '8px',
          color: 'var(--text-muted)'
        }}>
          {status === 'approved' ? (
            <div>
              <Terminal size={32} style={{ margin: '0 auto 1rem auto', color: '#10b981' }} />
              <h3>Plan Approved</h3>
              <p>The agent is now executing the commands. Checking for remaining plans...</p>
            </div>
          ) : (
            <div>
              <X size={32} style={{ margin: '0 auto 1rem auto', color: '#ef4444' }} />
              <h3>Plan Rejected</h3>
              <p>The plan was discarded. Checking for remaining plans...</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Approvals;
