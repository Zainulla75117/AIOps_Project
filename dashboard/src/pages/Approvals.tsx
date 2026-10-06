import React, { useState } from 'react';
import { Check, X, Terminal, Clock } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

// Mock data representing a plan from .brain/plans/
const MOCK_PLAN = `
# Remediation Plan: Fix CrashLoopBackOff in Nginx

**Issue ID:** crashloop-nginx-123
**Date:** 2026-10-06T15:30:00

## Reasoning
The \`nginx-deployment\` pod is failing due to an OOMKilled error followed by a CrashLoopBackOff. The current memory limit is set to \`128Mi\`, which is insufficient for the load it's receiving. We need to increase the memory limit to \`256Mi\` to stabilize the pod.

## Proposed Commands
\`\`\`bash
kubectl patch deployment nginx-deployment -p '{"spec":{"template":{"spec":{"containers":[{"name":"nginx","resources":{"limits":{"memory":"256Mi"}}}]}}}}'
\`\`\`

---
*Awaiting Human Approval*
`;

const Approvals: React.FC = () => {
  const [status, setStatus] = useState<'pending' | 'approved' | 'rejected'>('pending');

  const handleApprove = () => {
    setStatus('approved');
    // Here we would call the backend API to execute the plan
  };

  const handleReject = () => {
    setStatus('rejected');
    // Here we would call the backend API to discard the plan
  };

  return (
    <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto', fontFamily: 'var(--font-sans)' }}>
      <header style={{ marginBottom: '2rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Clock size={20} className="text-muted" />
          Pending Approvals
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
          Review and approve remediation plans drafted by the AIOps agent.
        </p>
      </header>

      {status === 'pending' ? (
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
              <span>ID: crashloop-nginx-123</span>
              <span>Source: .brain/plans/</span>
            </div>
          </div>
          
          <div style={{ padding: '1.5rem', fontSize: '0.9rem', lineHeight: 1.6 }} className="markdown-body">
            <ReactMarkdown>{MOCK_PLAN}</ReactMarkdown>
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
                backgroundColor: '#10b981', // emerald-500
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
              <p>The agent is now executing the commands. Check the History tab for results.</p>
            </div>
          ) : (
            <div>
              <X size={32} style={{ margin: '0 auto 1rem auto', color: '#ef4444' }} />
              <h3>Plan Rejected</h3>
              <p>The plan was discarded and moved to history.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Approvals;
