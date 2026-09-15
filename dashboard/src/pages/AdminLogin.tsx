import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { Lock, AlertCircle, Cpu } from 'lucide-react';

const AdminLogin: React.FC = () => {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await api.adminLogin(password);
      localStorage.setItem('admin_token', res.token);
      navigate('/admin');
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Authentication failed';
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="admin-login-page">
      <div className="admin-login-card">
        <div className="admin-login-header">
          <div className="admin-login-logo">
            <Cpu size={18} />
            <span className="font-mono">K8S AGENT</span>
          </div>
          <h1 className="admin-login-title">Admin Access</h1>
          <p className="admin-login-subtitle text-muted">
            Enter your password to manage RAG documents
          </p>
        </div>

        <form onSubmit={handleSubmit} className="admin-login-form">
          {error && (
            <div className="admin-login-error">
              <AlertCircle size={14} />
              <span>{error}</span>
            </div>
          )}

          <div className="admin-login-field">
            <label className="admin-login-label font-mono" htmlFor="admin-password">
              PASSWORD
            </label>
            <div className="admin-login-input-wrap">
              <Lock size={14} className="admin-login-input-icon" />
              <input
                id="admin-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter admin password"
                className="admin-login-input"
                autoFocus
                disabled={loading}
              />
            </div>
          </div>

          <button
            type="submit"
            className="admin-login-btn"
            disabled={loading || !password.trim()}
          >
            {loading ? (
              <span className="admin-login-btn-loading">Authenticating…</span>
            ) : (
              <>
                <Lock size={14} />
                Sign In
              </>
            )}
          </button>
        </form>

        <div className="admin-login-footer">
          <a href="/" className="admin-login-back text-muted">
            ← Back to Dashboard
          </a>
        </div>
      </div>
    </div>
  );
};

export default AdminLogin;
