import React from 'react';
import { useTheme } from '../components/ThemeProvider';
import { Monitor, Moon, Sun } from 'lucide-react';

const Settings: React.FC = () => {
  const { theme, setTheme } = useTheme();

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      
      {/* Header */}
      <div style={{ padding: 'var(--space-6)', borderBottom: '1px solid var(--border-subtle)', display: 'flex', gap: 'var(--space-6)', alignItems: 'center' }}>
        <h1 style={{ fontSize: '1.25rem', letterSpacing: '-0.03em', margin: 0, whiteSpace: 'nowrap' }}>System Settings</h1>
      </div>

      {/* Settings Content */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        <div className="data-grid-row" style={{ gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
          
          <div>
            <div style={{ fontWeight: 500, fontSize: '0.9375rem', marginBottom: '2px', color: 'var(--text-primary)' }}>
              Appearance
            </div>
            <div className="font-mono text-muted" style={{ fontSize: '0.6875rem', textTransform: 'uppercase' }}>
              INTERFACE THEME PREFERENCE
            </div>
          </div>

          <div style={{ display: 'flex', gap: 'var(--space-2)', justifyContent: 'flex-end' }}>
            <button 
              onClick={() => setTheme('light')}
              style={{
                display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
                padding: 'var(--space-2) var(--space-4)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: theme === 'light' ? 'var(--text-primary)' : 'transparent',
                color: theme === 'light' ? 'var(--bg-app)' : 'var(--text-secondary)',
                fontSize: '0.75rem', textTransform: 'uppercase', fontFamily: 'var(--font-mono)'
              }}
            >
              <Sun size={14} /> LIGHT
            </button>
            <button 
              onClick={() => setTheme('dark')}
              style={{
                display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
                padding: 'var(--space-2) var(--space-4)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: theme === 'dark' ? 'var(--text-primary)' : 'transparent',
                color: theme === 'dark' ? 'var(--bg-app)' : 'var(--text-secondary)',
                fontSize: '0.75rem', textTransform: 'uppercase', fontFamily: 'var(--font-mono)'
              }}
            >
              <Moon size={14} /> DARK
            </button>
            <button 
              onClick={() => setTheme('system')}
              style={{
                display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
                padding: 'var(--space-2) var(--space-4)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: theme === 'system' ? 'var(--text-primary)' : 'transparent',
                color: theme === 'system' ? 'var(--bg-app)' : 'var(--text-secondary)',
                fontSize: '0.75rem', textTransform: 'uppercase', fontFamily: 'var(--font-mono)'
              }}
            >
              <Monitor size={14} /> SYSTEM
            </button>
          </div>
          
        </div>
      </div>

    </div>
  );
};

export default Settings;
