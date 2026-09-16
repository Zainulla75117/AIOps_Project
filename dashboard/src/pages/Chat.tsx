import React, { useEffect, useState, useRef, useCallback } from 'react';
import { api } from '../api';
import type { ChatSession } from '../api';
import ReactMarkdown from 'react-markdown';
import {
  MessageSquare, Send, Link2, FileText, ChevronDown,
  Plus, Trash2, Pencil, PanelLeftClose, PanelLeft,
  Cpu, Bot, User, Copy, CheckCircle, MoreHorizontal,
  Search, AlertTriangle, AlertCircle, BarChart3, RefreshCcw, ClipboardList
} from 'lucide-react';

const SUGGESTED_PROMPTS = [
  { text: "How are pods doing?", icon: <Search size={14} /> },
  { text: "Any problems in the cluster?", icon: <AlertTriangle size={14} /> },
  { text: "Show unhealthy deployments", icon: <AlertCircle size={14} /> },
  { text: "Node status & capacity", icon: <BarChart3 size={14} /> },
  { text: "Which pods have high restarts?", icon: <RefreshCcw size={14} /> },
  { text: "What warning events are happening?", icon: <ClipboardList size={14} /> },
];

type LLMModel = 'bedrock' | 'gemini';

const MODEL_LABELS: Record<LLMModel, string> = {
  bedrock: 'Claude Haiku',
  gemini: 'Gemini',
};

const ClaudeLogo = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect width="24" height="24" rx="6" fill="#D97757" />
    <path d="M8 17L12 9L16 17H13.5L12 14L10.5 17H8Z" fill="#FFF" />
  </svg>
);

const GeminiLogo = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="gemini-grad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#4A90E2" />
        <stop offset="50%" stopColor="#9013FE" />
        <stop offset="100%" stopColor="#F5A623" />
      </linearGradient>
    </defs>
    <path d="M12 0C12 6.627 17.373 12 24 12C17.373 12 12 17.373 12 24C12 17.373 6.627 12 0 12C6.627 12 12 6.627 12 0Z" fill="url(#gemini-grad)" />
  </svg>
);

interface ChatMsg {
  type: 'user' | 'agent';
  text: string;
  followUps?: string[];
  sources?: string[];
  modelUsed?: string;
  timestamp?: string;
}

// ---- Helpers ----

function groupSessionsByDate(sessions: ChatSession[]) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const week = new Date(today.getTime() - 7 * 86400000);

  const groups: { label: string; sessions: ChatSession[] }[] = [
    { label: 'Today', sessions: [] },
    { label: 'Yesterday', sessions: [] },
    { label: 'Previous 7 Days', sessions: [] },
    { label: 'Older', sessions: [] },
  ];

  for (const s of sessions) {
    const d = new Date(s.last_message);
    if (d >= today) groups[0].sessions.push(s);
    else if (d >= yesterday) groups[1].sessions.push(s);
    else if (d >= week) groups[2].sessions.push(s);
    else groups[3].sessions.push(s);
  }

  return groups.filter(g => g.sessions.length > 0);
}

function getSessionTitle(s: ChatSession): string {
  if (s.session_title) return s.session_title;
  const q = s.first_query || 'New conversation';
  return q.length > 40 ? q.slice(0, 40) + '…' : q;
}

function parseFollowUps(text: string): { cleaned: string; followUps: string[] } {
  let cleaned = text;
  let followUps: string[] = [];
  const match = text.match(/<follow_ups>([\s\S]*?)<\/follow_ups>/);
  if (match) {
    cleaned = text.replace(match[0], '').trim();
    followUps = match[1].split('\n').map(l => l.replace(/^- /, '').trim()).filter(Boolean);
  }
  return { cleaned, followUps };
}



// ---- Code Block with Copy ----
function CodeBlock({ children, className }: { children: React.ReactNode; className?: string }) {
  const [copied, setCopied] = useState(false);
  const code = String(children).replace(/\n$/, '');

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="chat-code-block-wrap">
      <div className="chat-code-header">
        <span className="font-mono text-muted" style={{ fontSize: '10px' }}>
          {className?.replace('language-', '') || 'code'}
        </span>
        <button className="chat-code-copy-btn" onClick={handleCopy} title="Copy code">
          {copied ? <CheckCircle size={11} /> : <Copy size={11} />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre className={className}><code>{code}</code></pre>
    </div>
  );
}

// ---- Main Component ----
const Chat: React.FC = () => {
  // Session state
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const generateSessionId = () => {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return 'session-' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
  };

  const [activeSessionId, setActiveSessionId] = useState<string>(() => generateSessionId());
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sessionsLoading, setSessionsLoading] = useState(true);

  // Rename state
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  // Context menu
  const [contextMenu, setContextMenu] = useState<{ sessionId: string; x: number; y: number } | null>(null);

  // Chat state
  const [chatQuery, setChatQuery] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState<LLMModel>('bedrock');
  const [showModelDropdown, setShowModelDropdown] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ---- Load sessions ----
  const loadSessions = useCallback(async () => {
    try {
      setSessionsLoading(true);
      const data = await api.getChatSessions(50);
      setSessions(Array.isArray(data) ? data : []);
    } catch { /* ignore */ }
    finally { setSessionsLoading(false); }
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  // ---- Load messages for active session ----
  const loadSessionMessages = useCallback(async (sessionId: string) => {
    try {
      const history = await api.getChatHistory(sessionId, 100);
      if (history.length > 0) {
        const msgs: ChatMsg[] = [];
        const reversed = [...history].reverse();
        for (const msg of reversed) {
          const { cleaned, followUps } = parseFollowUps(msg.reply);
          msgs.push({ type: 'user', text: msg.query, timestamp: msg.timestamp });
          msgs.push({
            type: 'agent',
            text: cleaned,
            followUps,
            sources: msg.context_summary?.rag_sources || [],
            modelUsed: msg.context_summary?.model_used,
            timestamp: msg.timestamp,
          });
        }
        setChatMessages(msgs);
      } else {
        setChatMessages([]);
      }
    } catch {
      setChatMessages([]);
    }
  }, []);

  // When active session changes, load its messages
  useEffect(() => {
    // Check if this is an existing session
    const existing = (Array.isArray(sessions) ? sessions : []).find(s => s.session_id === activeSessionId);
    if (existing) {
      loadSessionMessages(activeSessionId);
    } else {
      setChatMessages([]);
    }
  }, [activeSessionId, sessions, loadSessionMessages]);

  // ---- Close dropdowns on outside click ----
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowModelDropdown(false);
      }
      setContextMenu(null);
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // ---- Auto-scroll ----
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // ---- Focus rename input ----
  useEffect(() => {
    if (renamingId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingId]);

  // ---- Chat submit ----
  const handleChatSubmit = async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed) return;

    setChatLoading(true);
    setChatMessages(prev => [...prev, { type: 'user', text: trimmed }]);
    setChatQuery('');

    try {
      const response = await api.askQuery(trimmed, activeSessionId, selectedModel);
      const { cleaned, followUps } = parseFollowUps(response.reply);

      setChatMessages(prev => [...prev, {
        type: 'agent',
        text: cleaned,
        followUps,
        sources: response.sources || [],
        modelUsed: response.model_used,
      }]);

      // Refresh session list (new session may have been created)
      loadSessions();
    } catch (err) {
      console.error('Chat error', err);
      setChatMessages(prev => [...prev, { type: 'agent', text: 'Error communicating with the agent.' }]);
    } finally {
      setChatLoading(false);
      inputRef.current?.focus();
    }
  };

  // ---- Session actions ----
  const handleNewChat = () => {
    setActiveSessionId(generateSessionId());
    setChatMessages([]);
    setChatQuery('');
    inputRef.current?.focus();
  };

  const handleSelectSession = (sessionId: string) => {
    if (sessionId !== activeSessionId) {
      setActiveSessionId(sessionId);
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await api.deleteSession(sessionId);
      if (sessionId === activeSessionId) handleNewChat();
      loadSessions();
    } catch { /* ignore */ }
    setContextMenu(null);
  };

  const handleStartRename = (session: ChatSession) => {
    setRenamingId(session.session_id);
    setRenameValue(getSessionTitle(session));
    setContextMenu(null);
  };

  const handleFinishRename = async () => {
    if (!renamingId || !renameValue.trim()) {
      setRenamingId(null);
      return;
    }
    try {
      await api.renameSession(renamingId, renameValue.trim());
      loadSessions();
    } catch { /* ignore */ }
    setRenamingId(null);
  };

  const handleContextMenu = (e: React.MouseEvent, sessionId: string) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({ sessionId, x: e.clientX, y: e.clientY });
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleChatSubmit(chatQuery);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleChatSubmit(chatQuery);
    }
  };

  const grouped = groupSessionsByDate(sessions);

  return (
    <div className="chat-layout">
      {/* ===== Sidebar ===== */}
      <aside className={`chat-sidebar ${sidebarOpen ? '' : 'chat-sidebar-collapsed'}`}>
        <div className="chat-sidebar-header">
          <button className="chat-new-btn" onClick={handleNewChat}>
            <Plus size={14} />
            <span>New Chat</span>
          </button>
          <button className="chat-sidebar-toggle" onClick={() => setSidebarOpen(false)} title="Close sidebar">
            <PanelLeftClose size={15} />
          </button>
        </div>

        <div className="chat-sidebar-sessions">
          {sessionsLoading ? (
            <div className="chat-sidebar-empty">
              <span className="text-muted" style={{ fontSize: '12px' }}>Loading…</span>
            </div>
          ) : sessions.length === 0 ? (
            <div className="chat-sidebar-empty">
              <MessageSquare size={16} className="text-muted" style={{ opacity: 0.4 }} />
              <span className="text-muted" style={{ fontSize: '11px' }}>No conversations yet</span>
            </div>
          ) : (
            grouped.map(group => (
              <div key={group.label} className="chat-sidebar-group">
                <div className="chat-sidebar-group-label">{group.label}</div>
                {group.sessions.map(session => (
                  <div
                    key={session.session_id}
                    className={`chat-sidebar-item ${session.session_id === activeSessionId ? 'active' : ''}`}
                    onClick={() => handleSelectSession(session.session_id)}
                    onContextMenu={(e) => handleContextMenu(e, session.session_id)}
                  >
                    {renamingId === session.session_id ? (
                      <div className="chat-rename-wrap">
                        <input
                          ref={renameInputRef}
                          value={renameValue}
                          onChange={e => setRenameValue(e.target.value)}
                          onKeyDown={e => { if (e.key === 'Enter') handleFinishRename(); if (e.key === 'Escape') setRenamingId(null); }}
                          onBlur={handleFinishRename}
                          className="chat-rename-input"
                        />
                      </div>
                    ) : (
                      <>
                        <MessageSquare size={12} className="chat-sidebar-item-icon" />
                        <span className="chat-sidebar-item-title">{getSessionTitle(session)}</span>
                        <button
                          className="chat-sidebar-item-menu"
                          onClick={(e) => handleContextMenu(e, session.session_id)}
                        >
                          <MoreHorizontal size={12} />
                        </button>
                      </>
                    )}
                  </div>
                ))}
              </div>
            ))
          )}
        </div>
      </aside>

      {/* Sidebar toggle (when collapsed) */}
      {!sidebarOpen && (
        <button className="chat-sidebar-open-btn" onClick={() => setSidebarOpen(true)} title="Open sidebar">
          <PanelLeft size={16} />
        </button>
      )}

      {/* ===== Main Chat Area ===== */}
      <div className="chat-main">
        {/* Header */}
        <div className="chat-header">
          {!sidebarOpen && (
            <button className="chat-sidebar-toggle-inline" onClick={() => setSidebarOpen(true)}>
              <PanelLeft size={14} />
            </button>
          )}
          <Cpu size={13} className="text-muted" />
          <span className="text-muted font-mono" style={{ fontSize: '11px', textTransform: 'uppercase' }}>K8s Agent</span>

          {/* Model Selector */}
          <div className="chat-model-selector" ref={dropdownRef}>
            <button className="chat-model-btn" onClick={() => setShowModelDropdown(!showModelDropdown)} type="button">
              {selectedModel === 'gemini' ? <GeminiLogo /> : <ClaudeLogo />}
              <span>{MODEL_LABELS[selectedModel]}</span>
              <ChevronDown size={10} />
            </button>
            {showModelDropdown && (
              <div className="chat-model-dropdown">
                {(Object.keys(MODEL_LABELS) as LLMModel[]).map(model => (
                  <button
                    key={model}
                    className={`chat-model-option ${model === selectedModel ? 'active' : ''}`}
                    onClick={() => { setSelectedModel(model); setShowModelDropdown(false); }}
                  >
                    {model === 'gemini' ? <GeminiLogo /> : <ClaudeLogo />}
                    <span>{MODEL_LABELS[model]}</span>
                    {model === 'bedrock' && <span className="chat-model-default">DEFAULT</span>}
                  </button>
                ))}
              </div>
            )}
          </div>

          <span className="chat-context-badge">
            <Link2 size={10} />
            LIVE CLUSTER + DOCS
          </span>
        </div>

        {/* Messages Area */}
        <div className="chat-messages-area">
          {chatMessages.length === 0 && !chatLoading ? (
            /* ---- Empty State Hero ---- */
            <div className="chat-empty-hero">
              <div className="chat-empty-icon">
                <Bot size={32} />
              </div>
              <h2 className="chat-empty-title">K8s Agent</h2>
              <p className="chat-empty-subtitle text-muted">
                Ask about your cluster — powered by live K8s data and project docs
              </p>
              <div className="chat-empty-prompts">
                {SUGGESTED_PROMPTS.map(p => (
                  <button key={p.text} className="chat-empty-prompt-card" onClick={() => handleChatSubmit(p.text)} disabled={chatLoading}>
                    <span className="chat-empty-prompt-icon">{p.icon}</span>
                    <span className="chat-empty-prompt-text">{p.text}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* ---- Message Bubbles ---- */
            <div className="chat-messages-list">
              {chatMessages.map((msg, idx) => (
                <div key={idx} className={`chat-msg ${msg.type === 'user' ? 'chat-msg-user' : 'chat-msg-agent'}`}>
                  {/* Avatar */}
                  <div className={`chat-msg-avatar ${msg.type === 'user' ? 'chat-msg-avatar-user' : 'chat-msg-avatar-agent'}`}>
                    {msg.type === 'user' ? <User size={14} /> : <Bot size={14} />}
                  </div>

                  {/* Content */}
                  <div className="chat-msg-content">
                    <div className="chat-msg-bubble">
                      {msg.type === 'agent' ? (
                        <ReactMarkdown
                          components={{
                            code({ children, className, ...rest }: any) {
                              const isBlock = className?.startsWith('language-');
                              if (isBlock) {
                                return <CodeBlock className={className}>{children}</CodeBlock>;
                              }
                              return <code className="chat-inline-code" {...rest}>{children}</code>;
                            },
                          }}
                        >
                          {msg.text}
                        </ReactMarkdown>
                      ) : (
                        <p>{msg.text}</p>
                      )}
                    </div>

                    {/* Meta row: sources + model badge */}
                    {msg.type === 'agent' && (msg.sources?.length || msg.modelUsed) && (
                      <div className="chat-msg-meta">
                        {msg.sources && msg.sources.length > 0 && (
                          <div className="chat-sources">
                            <FileText size={10} />
                            {msg.sources.map(src => (
                              <span key={src} className="chat-source-badge">{src}</span>
                            ))}
                          </div>
                        )}
                        {msg.modelUsed && (
                          <span className="chat-model-used-badge" data-model={msg.modelUsed}>
                            {msg.modelUsed === 'bedrock' ? 'Claude Haiku' : 'Gemini'}
                          </span>
                        )}
                      </div>
                    )}

                    {/* Follow-ups */}
                    {msg.type === 'agent' && msg.followUps && msg.followUps.length > 0 && (
                      <div className="chat-followups">
                        {msg.followUps.map(fup => (
                          <button key={fup} className="chat-followup-chip" onClick={() => handleChatSubmit(fup)} disabled={chatLoading}>
                            {fup}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {/* Thinking indicator */}
              {chatLoading && (
                <div className="chat-msg chat-msg-agent">
                  <div className="chat-msg-avatar chat-msg-avatar-agent">
                    <Bot size={14} />
                  </div>
                  <div className="chat-msg-content">
                    <div className="chat-msg-bubble chat-thinking-bubble">
                      <div className="chat-thinking-dots">
                        <span /><span /><span />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="chat-input-container">
          <form onSubmit={handleFormSubmit} className="chat-input-form">
            <textarea
              ref={inputRef}
              value={chatQuery}
              onChange={e => setChatQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your cluster..."
              disabled={chatLoading}
              className="chat-input-textarea"
              rows={1}
            />
            <button type="submit" disabled={chatLoading || !chatQuery.trim()} className="chat-send-btn">
              <Send size={16} />
            </button>
          </form>
          <div className="chat-input-footer">
            <span className="text-muted font-mono" style={{ fontSize: '9px' }}>
              Shift+Enter for new line
            </span>
          </div>
        </div>
      </div>

      {/* ===== Context Menu ===== */}
      {contextMenu && (
        <div
          className="chat-context-menu"
          style={{ top: contextMenu.y, left: contextMenu.x }}
        >
          <button onClick={() => {
            const s = (Array.isArray(sessions) ? sessions : []).find(s => s.session_id === contextMenu.sessionId);
            if (s) handleStartRename(s);
          }}>
            <Pencil size={12} />
            <span>Rename</span>
          </button>
          <button className="chat-context-danger" onClick={() => handleDeleteSession(contextMenu.sessionId)}>
            <Trash2 size={12} />
            <span>Delete</span>
          </button>
        </div>
      )}
    </div>
  );
};

export default Chat;
