import React, { useEffect, useState } from 'react';
import { api } from '../api';
import type { NamespacePermission, NamespaceSettings } from '../api';
import { Search } from 'lucide-react';

const Namespaces: React.FC = () => {
  const [settings, setSettings] = useState<NamespaceSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const fetchSettings = async () => {
    try {
      const data = await api.getNamespaceSettings();
      setSettings(data);
    } catch (err) {
      console.error("Failed to fetch namespace settings", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleToggle = async (namespace: string, currentlyEnabled: boolean) => {
    try {
      if (settings) {
        const newSettings = { ...settings };
        newSettings.namespaces[namespace].enabled = !currentlyEnabled;
        setSettings(newSettings);
      }
      await api.toggleNamespace(namespace, !currentlyEnabled);
    } catch (err) {
      console.error("Failed to toggle namespace", err);
      fetchSettings();
    }
  };

  if (loading) return <div className="text-secondary p-6 font-mono text-sm">LOADING SCOPE...</div>;
  if (!settings) return <div className="text-critical p-6 font-mono text-sm">ERR_LOAD_SETTINGS</div>;

  const nsList = Object.values(settings.namespaces)
    .filter(ns => ns.name.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (a.is_system && !b.is_system) return 1;
      if (!a.is_system && b.is_system) return -1;
      return a.name.localeCompare(b.name);
    });

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      
      {/* Header */}
      <div style={{ padding: 'var(--space-6)', borderBottom: '1px solid var(--border-subtle)', display: 'flex', gap: 'var(--space-6)', alignItems: 'center' }}>
        <h1 style={{ fontSize: '1.25rem', letterSpacing: '-0.03em', margin: 0, whiteSpace: 'nowrap' }}>Namespace Scope</h1>
        
        {/* Search Bar - Integrated in Header */}
        <div style={{ display: 'flex', alignItems: 'center', backgroundColor: 'var(--bg-surface)', padding: '6px 12px', flex: 1, maxWidth: '400px' }}>
          <Search size={14} className="text-muted mr-2" />
          <input 
            type="text" 
            placeholder="FILTER NAMESPACES..." 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="font-mono text-sm"
            style={{ 
              background: 'transparent', 
              border: 'none', 
              color: 'var(--text-primary)', 
              width: '100%',
              outline: 'none',
              textTransform: 'uppercase'
            }}
          />
        </div>
      </div>

      {/* List Content */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {nsList.map((ns: NamespacePermission) => (
          <div key={ns.name} className="data-grid-row" style={{ gridTemplateColumns: '1fr 100px 100px', gap: 'var(--space-4)' }}>
            
            {/* Name & Type */}
            <div>
              <div style={{ fontWeight: 500, fontSize: '0.9375rem', marginBottom: '2px', color: ns.enabled ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                {ns.name}
              </div>
              <div className="font-mono text-muted" style={{ fontSize: '0.6875rem', textTransform: 'uppercase' }}>
                {ns.is_system ? 'SYSTEM_NAMESPACE' : 'APP_NAMESPACE'}
              </div>
            </div>

            {/* Status */}
            <div className="font-mono" style={{ fontSize: '0.75rem', color: ns.enabled ? 'var(--status-success)' : 'var(--text-muted)' }}>
              {ns.enabled ? '[ ACTIVE ]' : '[ IGNORED ]'}
            </div>

            {/* Action Toggle */}
            <div style={{ textAlign: 'right' }}>
              <button 
                onClick={() => handleToggle(ns.name, ns.enabled)}
                className="font-mono"
                style={{
                  fontSize: '0.75rem',
                  textTransform: 'uppercase',
                  color: ns.enabled ? 'var(--text-primary)' : 'var(--text-secondary)',
                  borderBottom: `1px solid ${ns.enabled ? 'var(--text-primary)' : 'transparent'}`,
                  transition: 'all 0.15s ease'
                }}
              >
                {ns.enabled ? 'DISABLE' : 'ENABLE'}
              </button>
            </div>
            
          </div>
        ))}
        {nsList.length === 0 && (
          <div className="text-secondary font-mono p-6 text-sm">NO RESULTS</div>
        )}
      </div>

    </div>
  );
};

export default Namespaces;
