import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import type { IngestionJob } from '../api';
import {
  Upload, FileText, Trash2, Eye, LogOut, Cpu,
  FileType, Database, File as FileIcon, X, ChevronLeft,
  CheckCircle, AlertCircle, Loader, Clock, Layers, Table2
} from 'lucide-react';

interface DocumentInfo {
  source: string;
  chunk_count: number;
}

interface ChunkPreview {
  index: number;
  content: string;
  metadata: Record<string, any>;
  length: number;
}

const EXTENSION_ICONS: Record<string, React.ReactNode> = {
  '.pdf': <FileType size={14} />,
  '.txt': <FileText size={14} />,
  '.md': <FileText size={14} />,
  '.csv': <FileIcon size={14} />,
  '.db': <Database size={14} />,
};

function getExtBadge(filename: string) {
  const ext = '.' + filename.split('.').pop()?.toLowerCase();
  const icon = EXTENSION_ICONS[ext] || <FileIcon size={14} />;
  return (
    <span className="admin-ext-badge">
      {icon}
      <span>{ext.toUpperCase()}</span>
    </span>
  );
}

function formatElapsed(createdAt: string): string {
  const start = new Date(createdAt).getTime();
  const now = Date.now();
  const seconds = Math.floor((now - start) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (minutes < 60) return `${minutes}m ${secs}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return n.toString();
}

const Admin: React.FC = () => {
  const navigate = useNavigate();
  const token = localStorage.getItem('admin_token') || '';
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  // Ingestion progress
  const [ingestionJobs, setIngestionJobs] = useState<IngestionJob[]>([]);
  const progressPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Track which completed jobs have been "seen" so they linger briefly
  const [dismissedJobs, setDismissedJobs] = useState<Set<string>>(new Set());

  // Chunk preview modal
  const [previewSource, setPreviewSource] = useState<string | null>(null);
  const [previewChunks, setPreviewChunks] = useState<ChunkPreview[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);

  const loadDocuments = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.getDocuments(token);
      setDocuments(Array.isArray(res.documents) ? res.documents : []);
    } catch (err: any) {
      if (err?.response?.status === 401) {
        localStorage.removeItem('admin_token');
        navigate('/admin/login');
      }
    } finally {
      setLoading(false);
    }
  }, [token, navigate]);

  const fetchProgress = useCallback(async () => {
    try {
      const res = await api.getIngestionProgress(token);
      const jobs = Array.isArray(res.jobs) ? res.jobs : [];
      setIngestionJobs(jobs);

      // If any job just completed, refresh the documents list
      const hasNewlyCompleted = jobs.some(
        (j) => j.status === 'completed' && !dismissedJobs.has(j.job_id)
      );
      if (hasNewlyCompleted) {
        loadDocuments();
      }

      // Auto-dismiss completed/failed jobs after 8 seconds
      jobs.forEach((j) => {
        if ((j.status === 'completed' || j.status === 'failed') && !dismissedJobs.has(j.job_id)) {
          setTimeout(() => {
            setDismissedJobs((prev) => new Set(prev).add(j.job_id));
          }, 8000);
        }
      });
    } catch {
      // Silently ignore — progress polling is best-effort
    }
  }, [token, dismissedJobs, loadDocuments]);

  // Start/stop polling based on active jobs
  useEffect(() => {
    // Always fetch once on mount
    fetchProgress();

    // Poll every 3 seconds
    progressPollRef.current = setInterval(fetchProgress, 3000);

    return () => {
      if (progressPollRef.current) clearInterval(progressPollRef.current);
    };
  }, [fetchProgress]);

  // Stop polling when no active jobs remain
  useEffect(() => {
    const hasActive = ingestionJobs.some(
      (j) => j.status === 'processing' || !dismissedJobs.has(j.job_id)
    );
    if (!hasActive && progressPollRef.current && ingestionJobs.length > 0) {
      // Keep polling — a new upload could start anytime
    }
  }, [ingestionJobs, dismissedJobs]);

  useEffect(() => {
    if (!token) {
      navigate('/admin/login');
      return;
    }
    loadDocuments();
  }, [token, navigate, loadDocuments]);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    setUploading(true);
    setUploadResult(null);

    let successCount = 0;
    let failCount = 0;

    for (const file of Array.from(files)) {
      try {
        await api.uploadDocument(file, token);
        successCount++;
      } catch (err: any) {
        failCount++;
        const detail = err?.response?.data?.detail || err.message;
        console.error(`Failed to upload ${file.name}:`, detail);
      }
    }

    if (successCount > 0 && failCount === 0) {
      setUploadResult({ type: 'success', message: `${successCount} file(s) accepted for processing` });
    } else if (failCount > 0 && successCount > 0) {
      setUploadResult({ type: 'error', message: `${successCount} accepted, ${failCount} failed` });
    } else {
      setUploadResult({ type: 'error', message: `Upload failed` });
    }

    setUploading(false);

    // Immediately fetch progress to show the new job
    fetchProgress();

    // Clear result after 4 seconds
    setTimeout(() => setUploadResult(null), 4000);
  };

  const handleDelete = async (source: string) => {
    if (!confirm(`Delete "${source}" and all its chunks?`)) return;
    setDeleting(source);
    try {
      await api.deleteDocument(source, token);
      loadDocuments();
    } catch (err: any) {
      console.error('Delete failed:', err);
    } finally {
      setDeleting(null);
    }
  };

  const handlePreview = async (source: string) => {
    setPreviewSource(source);
    setPreviewLoading(true);
    try {
      const res = await api.getDocumentChunks(source, token);
      setPreviewChunks(Array.isArray(res.chunks) ? res.chunks : []);
    } catch {
      setPreviewChunks([]);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('admin_token');
    navigate('/admin/login');
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleUpload(e.dataTransfer.files);
  };

  // Filter out dismissed jobs
  const visibleJobs = ingestionJobs.filter((j) => !dismissedJobs.has(j.job_id));

  return (
    <div className="admin-page">
      {/* Header */}
      <header className="admin-header">
        <div className="admin-header-left">
          <a href="/" className="admin-back-link">
            <ChevronLeft size={16} />
          </a>
          <Cpu size={16} className="text-muted" />
          <span className="font-mono" style={{ fontSize: '12px' }}>ADMIN PANEL</span>
          <span className="badge badge-info" style={{ marginLeft: '8px' }}>RAG DOCUMENTS</span>
        </div>
        <button className="btn btn-secondary" onClick={handleLogout} style={{ fontSize: '12px', gap: '6px' }}>
          <LogOut size={13} />
          Logout
        </button>
      </header>

      <div className="admin-content">
        {/* Upload Area */}
        <div
          className={`admin-upload-zone ${dragOver ? 'admin-upload-zone-active' : ''} ${uploading ? 'admin-upload-zone-uploading' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.txt,.md,.csv,.db"
            onChange={(e) => handleUpload(e.target.files)}
            style={{ display: 'none' }}
          />

          {uploading ? (
            <div className="admin-upload-content">
              <Loader size={24} className="spin text-info" />
              <span className="font-mono text-muted" style={{ fontSize: '13px' }}>Uploading files…</span>
            </div>
          ) : (
            <div className="admin-upload-content">
              <Upload size={24} className="text-muted" />
              <span className="text-secondary" style={{ fontSize: '14px' }}>
                Drop files here or <span style={{ color: 'var(--accent)', cursor: 'pointer' }}>browse</span>
              </span>
              <div className="admin-upload-formats">
                <span className="admin-format-tag">PDF</span>
                <span className="admin-format-tag">TXT</span>
                <span className="admin-format-tag">MD</span>
                <span className="admin-format-tag">CSV</span>
                <span className="admin-format-tag">DB</span>
              </div>
            </div>
          )}
        </div>

        {/* Upload Result Toast */}
        {uploadResult && (
          <div className={`admin-toast admin-toast-${uploadResult.type}`}>
            {uploadResult.type === 'success' ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
            <span>{uploadResult.message}</span>
          </div>
        )}

        {/* Active Ingestion Progress */}
        {visibleJobs.length > 0 && (
          <div className="admin-section">
            <div className="admin-section-header">
              <h2 className="font-mono" style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Active Ingestions ({visibleJobs.filter(j => j.status === 'processing').length} running)
              </h2>
            </div>

            <div className="admin-ingestion-list">
              {visibleJobs.map((job) => (
                <IngestionProgressCard key={job.job_id} job={job} />
              ))}
            </div>
          </div>
        )}

        {/* Documents Table */}
        <div className="admin-section">
          <div className="admin-section-header">
            <h2 className="font-mono" style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Uploaded Documents ({documents.length})
            </h2>
          </div>

          {loading ? (
            <div className="admin-empty">
              <Loader size={18} className="spin text-muted" />
              <span className="text-muted" style={{ fontSize: '13px' }}>Loading documents…</span>
            </div>
          ) : documents.length === 0 ? (
            <div className="admin-empty">
              <FileText size={24} className="text-muted" style={{ opacity: 0.4 }} />
              <span className="text-muted" style={{ fontSize: '13px' }}>No documents uploaded yet</span>
              <span className="text-muted" style={{ fontSize: '11px' }}>Upload documents to enable RAG-powered chat</span>
            </div>
          ) : (
            <div className="workloads-table-wrap">
              <table className="workloads-table">
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Chunks</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr key={doc.source}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          {getExtBadge(doc.source)}
                          <span className="font-mono" style={{ fontSize: '13px' }}>{doc.source}</span>
                        </div>
                      </td>
                      <td>
                        <span className="badge badge-neutral">{doc.chunk_count} chunks</span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: '4px', justifyContent: 'flex-end' }}>
                          <button
                            className="btn btn-secondary"
                            style={{ padding: '4px 8px', fontSize: '11px' }}
                            onClick={() => handlePreview(doc.source)}
                            title="Preview chunks"
                          >
                            <Eye size={12} />
                          </button>
                          <button
                            className="btn btn-secondary"
                            style={{ padding: '4px 8px', fontSize: '11px', color: 'var(--status-critical)' }}
                            onClick={() => handleDelete(doc.source)}
                            disabled={deleting === doc.source}
                            title="Delete document"
                          >
                            {deleting === doc.source ? <Loader size={12} className="spin" /> : <Trash2 size={12} />}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Chunk Preview Modal */}
      {previewSource && (
        <div className="admin-modal-overlay" onClick={() => setPreviewSource(null)}>
          <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Eye size={14} className="text-muted" />
                <span className="font-mono" style={{ fontSize: '12px', textTransform: 'uppercase' }}>
                  Chunk Preview
                </span>
                <span className="badge badge-info">{previewSource}</span>
              </div>
              <button className="btn btn-secondary" style={{ padding: '4px 6px' }} onClick={() => setPreviewSource(null)}>
                <X size={14} />
              </button>
            </div>
            <div className="admin-modal-body">
              {previewLoading ? (
                <div className="admin-empty">
                  <Loader size={18} className="spin text-muted" />
                </div>
              ) : previewChunks.length === 0 ? (
                <div className="admin-empty">
                  <span className="text-muted">No chunks found</span>
                </div>
              ) : (
                <div className="admin-chunks-list">
                  {previewChunks.map((chunk) => (
                    <div key={chunk.index} className="admin-chunk-item">
                      <div className="admin-chunk-meta">
                        <span className="badge badge-neutral">#{chunk.index}</span>
                        <span className="text-muted font-mono" style={{ fontSize: '10px' }}>
                          {chunk.length} chars
                        </span>
                        {chunk.metadata.table && (
                          <span className="badge badge-info">table: {chunk.metadata.table}</span>
                        )}
                      </div>
                      <pre className="admin-chunk-content">{chunk.content}</pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};


// ---- Ingestion Progress Card Component ----

const IngestionProgressCard: React.FC<{ job: IngestionJob }> = ({ job }) => {
  const percentage = job.total_rows > 0
    ? Math.min(Math.round((job.processed_rows / job.total_rows) * 100), 100)
    : 0;

  const isProcessing = job.status === 'processing';
  const isCompleted = job.status === 'completed';
  const isFailed = job.status === 'failed';
  const isIndeterminate = isProcessing && job.total_rows === 0;

  const statusClass = isCompleted
    ? 'admin-ingestion-card-completed'
    : isFailed
      ? 'admin-ingestion-card-failed'
      : '';

  return (
    <div className={`admin-ingestion-card ${statusClass}`}>
      {/* Top row: filename + status */}
      <div className="admin-ingestion-header">
        <div className="admin-ingestion-file">
          {getExtBadge(job.filename)}
          <span className="font-mono" style={{ fontSize: '13px' }}>{job.filename}</span>
        </div>
        <div className="admin-ingestion-status">
          {isProcessing && (
            <span className="admin-ingestion-badge admin-ingestion-badge-processing">
              <Loader size={10} className="spin" />
              Processing
            </span>
          )}
          {isCompleted && (
            <span className="admin-ingestion-badge admin-ingestion-badge-completed">
              <CheckCircle size={10} />
              Completed
            </span>
          )}
          {isFailed && (
            <span className="admin-ingestion-badge admin-ingestion-badge-failed">
              <AlertCircle size={10} />
              Failed
            </span>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="admin-progress-bar">
        <div
          className={`admin-progress-fill ${isIndeterminate ? 'admin-progress-fill-indeterminate' : ''} ${isCompleted ? 'admin-progress-fill-completed' : ''} ${isFailed ? 'admin-progress-fill-failed' : ''}`}
          style={{
            width: isIndeterminate ? '100%' : `${percentage}%`,
          }}
        />
      </div>

      {/* Stats row */}
      <div className="admin-ingestion-meta">
        {isProcessing && job.total_rows > 0 && (
          <span className="admin-ingestion-stat">
            <span className="admin-ingestion-stat-value">{percentage}%</span>
          </span>
        )}
        {job.total_rows > 0 && (
          <span className="admin-ingestion-stat">
            <Layers size={10} />
            <span>{formatNumber(job.processed_rows)} / {formatNumber(job.total_rows)} rows</span>
          </span>
        )}
        {job.chunks_created > 0 && (
          <span className="admin-ingestion-stat">
            <FileText size={10} />
            <span>{formatNumber(job.chunks_created)} chunks</span>
          </span>
        )}
        {job.current_table && isProcessing && (
          <span className="admin-ingestion-stat">
            <Table2 size={10} />
            <span>{job.current_table}</span>
          </span>
        )}
        <span className="admin-ingestion-stat admin-ingestion-stat-time">
          <Clock size={10} />
          <span>{formatElapsed(job.created_at)}</span>
        </span>
        {isFailed && job.error && (
          <span className="admin-ingestion-stat admin-ingestion-stat-error">
            {job.error}
          </span>
        )}
      </div>
    </div>
  );
};


export default Admin;
