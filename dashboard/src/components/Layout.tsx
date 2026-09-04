import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Cpu } from 'lucide-react';
import './Layout.css';

const Layout: React.FC = () => {
  return (
    <div className="app-layout">
      {/* Minimal Top Navigation */}
      <header className="top-nav">
        <div className="nav-left">
          <div className="logo-container">
            <Cpu size={16} className="logo-icon text-muted" />
            <span className="logo-text font-mono" style={{ fontSize: '12px' }}>K8S AGENT</span>
          </div>
          
          <nav className="nav-links">
            <NavLink to="/" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'} end>
              Overview
            </NavLink>
            <NavLink to="/chat" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Chat
            </NavLink>
            <NavLink to="/workloads" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Workloads
            </NavLink>
            <NavLink to="/incidents" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Incidents
            </NavLink>
            <NavLink to="/history" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              History
            </NavLink>
            <NavLink to="/settings/namespaces" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Namespaces
            </NavLink>
            <NavLink to="/settings" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'} end>
              Settings
            </NavLink>
          </nav>
        </div>

        <div className="nav-right">
           <div className="status-indicator">
             <span className="status-dot online"></span>
             <span className="font-mono text-muted" style={{ fontSize: '11px', textTransform: 'uppercase' }}>Active</span>
           </div>
        </div>
      </header>

      {/* Edge-to-Edge Content Area */}
      <main className="main-content">
        <div className="content-scroll">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default Layout;
