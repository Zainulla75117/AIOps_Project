import React, { useEffect, useState, useRef } from 'react';
import { api } from '../api';
import ReactMarkdown from 'react-markdown';
import { MessageSquare, Send, Link2, Sparkles } from 'lucide-react';

const SUGGESTED_PROMPTS = [
  "How are pods doing?",
  "Any problems in the cluster?",
  "Show unhealthy deployments",
  "Node status & capacity",
  "Which pods have high restarts?",
  "What warning events are happening?",
];

const Chat: React.FC = () => {
  const [chatQuery, setChatQuery] = useState("");
  const [chatMessages, setChatMessages] = useState<Array<{type: 'user' | 'agent'; text: string; followUps?: string[]}>>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load recent chat history from MongoDB
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const history = await api.getChatHistory(undefined, 10);
        if (history.length > 0) {
          const msgs: Array<{type: 'user' | 'agent'; text: string; followUps?: string[]}> = [];
          // History comes newest-first, reverse for display
          const reversed = [...history].reverse();
          for (const msg of reversed.slice(-6)) {  // Show last 6 messages
            msgs.push({ type: 'user', text: msg.query });
            
            let replyText = msg.reply;
            let followUps: string[] = [];
            const followUpsMatch = replyText.match(/<follow_ups>([\s\S]*?)<\/follow_ups>/);
            if (followUpsMatch) {
              replyText = replyText.replace(followUpsMatch[0], '').trim();
              followUps = followUpsMatch[1]
                .split('\n')
                .map(l => l.replace(/^- /, '').trim())
                .filter(Boolean);
            }
            
            msgs.push({ type: 'agent', text: replyText, followUps });
          }
          setChatMessages(msgs);
        }
      } catch {
        // Silently ignore history load failures
      }
    };
    loadHistory();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const handleChatSubmit = async (query: string) => {
    const trimmedQuery = query.trim();
    if (!trimmedQuery) return;

    setChatLoading(true);
    setChatMessages(prev => [...prev, { type: 'user', text: trimmedQuery }]);
    setChatQuery("");

    try {
      const response = await api.askQuery(trimmedQuery, sessionId);
      
      let replyText = response.reply;
      let followUps: string[] = [];
      const followUpsMatch = replyText.match(/<follow_ups>([\s\S]*?)<\/follow_ups>/);
      if (followUpsMatch) {
        replyText = replyText.replace(followUpsMatch[0], '').trim();
        followUps = followUpsMatch[1]
          .split('\n')
          .map(l => l.replace(/^- /, '').trim())
          .filter(Boolean);
      }
      
      setChatMessages(prev => [...prev, { type: 'agent', text: replyText, followUps }]);
    } catch (err) {
      console.error("Chat error", err);
      setChatMessages(prev => [...prev, { type: 'agent', text: "Error communicating with the agent." }]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleChatSubmit(chatQuery);
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: 'var(--space-6)', maxWidth: '1000px', margin: '0 auto', width: '100%' }}>
      {/* AI Chat Interface */}
      <div className={`chat-terminal-container ${chatLoading ? 'chat-thinking' : ''}`} style={{ flex: 1 }}>
        <div className="chat-header">
          <MessageSquare size={14} className="text-muted" />
          <span className="text-muted font-mono" style={{ fontSize: '0.75rem', textTransform: 'uppercase' }}>AGENT TERMINAL</span>
          <span className="chat-context-badge">
            <Link2 size={10} />
            LIVE CLUSTER DATA
          </span>
        </div>
        
        <div className="chat-messages" style={{ flexDirection: 'column' }}>
          {chatMessages.length === 0 && !chatLoading && (
            <div className="text-muted font-mono" style={{ fontSize: '0.8rem', padding: 'var(--space-3) 0' }}>
              <Sparkles size={14} style={{ marginRight: '6px', verticalAlign: 'middle' }} />
              Ask about your cluster — answers use live K8s data.
            </div>
          )}
          {chatMessages.map((msg, idx) => (
            <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
              <div className={msg.type === 'user' ? 'chat-user-query' : 'chat-agent-reply'}>
                {msg.type === 'agent' ? (
                  <ReactMarkdown>{msg.text}</ReactMarkdown>
                ) : (
                  msg.text
                )}
              </div>
              
              {/* Render follow-ups if this is the last agent message, or if it has them */}
              {msg.type === 'agent' && msg.followUps && msg.followUps.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', marginTop: 'var(--space-2)', marginLeft: '12px' }}>
                  {msg.followUps.map(fup => (
                    <button
                      key={fup}
                      className="chat-suggestion-chip"
                      onClick={() => handleChatSubmit(fup)}
                      disabled={chatLoading}
                      style={{ fontSize: '0.65rem' }}
                    >
                      {fup}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
          {chatLoading && (
            <div className="chat-agent-reply typing-cursor">
              Analyzing cluster state
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Suggested Prompts */}
        {chatMessages.length === 0 && (
          <div className="chat-suggestions">
            {SUGGESTED_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                className="chat-suggestion-chip"
                onClick={() => handleChatSubmit(prompt)}
                disabled={chatLoading}
              >
                {prompt}
              </button>
            ))}
          </div>
        )}

        <form onSubmit={handleFormSubmit} className="chat-input-area">
          <div className="chat-input-prefix">_&gt;</div>
          <input 
            type="text" 
            value={chatQuery}
            onChange={(e) => setChatQuery(e.target.value)}
            placeholder="Query the agent..."
            disabled={chatLoading}
            className="chat-input"
          />
          <button 
            type="submit" 
            disabled={chatLoading || !chatQuery.trim()}
            className="chat-submit-btn"
          >
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
};

export default Chat;
