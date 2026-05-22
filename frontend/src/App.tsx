import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/sonner';
import { ThemeProvider } from 'next-themes';
import { lazy, Suspense, useState, useEffect, type ReactNode } from 'react';
import Layout from './components/common/Layout';
import LoadingSpinner from './components/common/LoadingSpinner';

// Code-split routes for better initial load performance
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Results = lazy(() => import('./pages/Results'));
const History = lazy(() => import('./pages/History'));
const JetstreamPage = lazy(() => import('./pages/JetstreamPage'));
const RunDetailPage = lazy(() => import('./pages/RunDetailPage'));
const TimeMachinePage = lazy(() => import('./pages/TimeMachinePage'));
const JetDriveAutoTunePage = lazy(() => import('./pages/JetDriveAutoTunePage'));
const OperatorTrainingPage = lazy(() => import('./pages/OperatorTrainingPage'));
const EngineAnalyzerPage = lazy(() => import('./pages/EngineAnalyzerPage'));
const HardStartAnalyzerPage = lazy(() => import('./pages/HardStartAnalyzerPage'));
const TechViewPage = lazy(() => import('./pages/TechView'));
const AdminViewPage = lazy(() => import('./pages/AdminView'));
const WorkspacePage = lazy(() => import('./pages/WorkspacePage'));
const TuningSessionPage = lazy(() => import('./pages/TuningSessionPage'));

// ---------------------------------------------------------------------------
// Portal auth guard
// Reads token and user name from localStorage and injects them as props.
// Redirects to the main app if no token is found.
// ---------------------------------------------------------------------------

function PortalGuard({ render }: { render: (token: string, user: { name: string; role: string }, onLogout: () => void) => ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<{ name: string; role: string } | null>(null);

  useEffect(() => {
    const storedToken = localStorage.getItem('portal_token');
    const storedUser = localStorage.getItem('portal_user');
    
    if (storedToken && storedUser) {
      try {
        const userData = JSON.parse(storedUser);
        setToken(storedToken);
        setUser({ name: userData.name || 'User', role: userData.role || 'customer' });
      } catch {
        localStorage.removeItem('portal_token');
        localStorage.removeItem('portal_user');
      }
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('portal_token');
    localStorage.removeItem('portal_user');
    setToken(null);
    setUser(null);
    window.location.href = '/jetdrive';
  };

  if (!token || !user) {
    return <Navigate to="/jetdrive" replace />;
  }

  return <>{render(token, user, handleLogout)}</>;
}
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
        <Router>
          <Layout>
            <Suspense fallback={<LoadingSpinner />}>
              <Routes>
                <Route path="/" element={<Navigate to="/jetdrive" replace />} />
                <Route path="/jetdrive" element={<JetDriveAutoTunePage />} />
                <Route path="/jetstream" element={<JetstreamPage />} />
                <Route path="/runs/:runId" element={<RunDetailPage />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/workspace" element={<WorkspacePage />} />
                <Route
                  path="/workspace/:vehicleId/sessions/:sessionId"
                  element={<TuningSessionPage />}
                />
                <Route path="/results/:runId" element={<Results />} />
                <Route path="/time-machine/:runId" element={<TimeMachinePage />} />
                <Route path="/history" element={<History />} />
                <Route path="/training" element={<OperatorTrainingPage />} />
                <Route path="/hard-start-analyzer" element={<HardStartAnalyzerPage />} />
                <Route path="/engine-analyzer" element={<EngineAnalyzerPage />} />
                <Route path="/portal/tech" element={
                  <PortalGuard render={(token, user, onLogout) => <TechViewPage user={user} token={token} onLogout={onLogout} />} />
                } />
                <Route path="/portal/admin" element={
                  <PortalGuard render={(token, user, onLogout) => <AdminViewPage user={user} token={token} onLogout={onLogout} />} />
                } />
                <Route path="*" element={<Navigate to="/jetdrive" replace />} />
              </Routes>
            </Suspense>
          </Layout>
        </Router>
        <Toaster position="top-right" richColors duration={3000} visibleToasts={3} />
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
