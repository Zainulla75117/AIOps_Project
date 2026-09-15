import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import AdminGuard from './components/AdminGuard';

import Overview from './pages/Overview';
import Chat from './pages/Chat';
import Workloads from './pages/Workloads';
import Incidents from './pages/Incidents';
import History from './pages/History';
import Namespaces from './pages/Namespaces';
import Settings from './pages/Settings';
import AdminLogin from './pages/AdminLogin';
import Admin from './pages/Admin';
import { ThemeProvider } from './components/ThemeProvider';

function App() {
  return (
    <ThemeProvider defaultTheme="system">
      <BrowserRouter>
        <Routes>
          {/* Main dashboard layout */}
          <Route path="/" element={<Layout />}>
            <Route index element={<Overview />} />
            <Route path="chat" element={<Chat />} />
            <Route path="workloads" element={<Workloads />} />
            <Route path="incidents" element={<Incidents />} />
            <Route path="history" element={<History />} />
            <Route path="settings/namespaces" element={<Namespaces />} />
            <Route path="settings" element={<Settings />} />
          </Route>

          {/* Admin routes (outside main layout) */}
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route path="/admin" element={<AdminGuard><Admin /></AdminGuard>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
