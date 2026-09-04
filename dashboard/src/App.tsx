import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';

import Overview from './pages/Overview';
import Chat from './pages/Chat';
import Workloads from './pages/Workloads';
import Incidents from './pages/Incidents';
import History from './pages/History';
import Namespaces from './pages/Namespaces';
import Settings from './pages/Settings';
import { ThemeProvider } from './components/ThemeProvider';

function App() {
  return (
    <ThemeProvider defaultTheme="system">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Overview />} />
            <Route path="chat" element={<Chat />} />
            <Route path="workloads" element={<Workloads />} />
            <Route path="incidents" element={<Incidents />} />
            <Route path="history" element={<History />} />
            <Route path="settings/namespaces" element={<Namespaces />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
