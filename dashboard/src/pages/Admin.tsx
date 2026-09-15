import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import {
  Upload, FileText, Trash2, Eye, LogOut, Cpu,
  FileType, Database, File as FileIcon, X, ChevronLeft,
  CheckCircle, AlertCircle, Loader
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

  // Chunk preview modal
  const [previewSource, setPreviewSource] = useState<string | null>(null);
  const [previewChunks, setPreviewChunks] = useState<ChunkPreview[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);

  const loadDocuments = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.getDocuments(token);
      setDocuments(res.documents);
    } catch (err: any) {
      if (err?.response?.status === 401) {
        localStorage.removeItem('admin_token');
        navigate('/admin/login');
      }
    } finally {
      setLoading(false);
    }
  }, [token, navigate]);

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
      setUploadResult({ type: 'success', message: `${successCount} file(s) uploaded successfully` });
    } else if (failCount > 0 && successCount > 0) {
      setUploadResult({ type: 'error', message: `${successCount} uploaded, ${failCount} failed` });
    } else {
      setUploadResult({ type: 'error', message: `Upload failed` });
    }

    setUploading(false);
    loadDocuments();

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
      setPreviewChunks(res.chunks);
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
              <span className="font-mono text-muted" style={{ fontSize: '13px' }}>Processing documents…</span>
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

export default Admin;
