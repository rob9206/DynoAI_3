import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/sonner';
import { ThemeProvider } from 'next-themes';
import { lazy, Suspense, useState, type ReactNode } from 'react';
import Layout from './components/common/Layout';
import LoadingSpinner from './components/common/LoadingSpinner';

// Code-split routes for better initial load performance
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Results = lazy(() => import('./pages/Results'));
const History = lazy(() => import('./pages/History'));
const VEHeatmapDemo = lazy(() => import('./pages/VEHeatmapDemo'));
const JetstreamPage = lazy(() => import('./pages/JetstreamPage'));
const RunDetailPage = lazy(() => import('./pages/RunDetailPage'));
const TimeMachinePage = lazy(() => import('./pages/TimeMachinePage'));
const TuningWizardsPage = lazy(() => import('./pages/TuningWizardsPage'));
const JetDriveAutoTunePage = lazy(() => import('./pages/JetDriveAutoTunePage'));
const OperatorTrainingPage = lazy(() => import('./pages/OperatorTrainingPage'));
const AutoTuneDemo = lazy(() => import('./pages/AutoTuneDemo'));
const EngineAnalyzerPage = lazy(() => import('./pages/EngineAnalyzerPage'));
const TechViewPage = lazy(() => import('./pages/TechView'));
const AdminViewPage = lazy(() => import('./pages/AdminView'));

// ---------------------------------------------------------------------------
// Portal auth guard
// Reads token and user name from localStorage and injects them as props.
// Redirects to the main app if no token is found.
// ---------------------------------------------------------------------------

function PortalGuard({
  render,
}: {
  render: (token: string, user: { name: string }, onLogout: () => void) => ReactNode;
}) {
  // NOTE: Storing tokens in localStorage is susceptible to XSS. This is a
  // pragmatic choice until the backend supports httpOnly cookie auth.
  const [token, setToken] = useState(() => localStorage.getItem('portal_token') ?? '');
  const [userName] = useState(() => localStorage.getItem('portal_user_name') ?? '');

  const handleLogout = () => {
    localStorage.removeItem('portal_token');
    localStorage.removeItem('portal_user_name');
    setToken('');
  };

  if (!token) return <Navigate to="/jetdrive" replace />;

  return <>{render(token, { name: userName }, handleLogout)}</>;
}

// ---------------------------------------------------------------------------

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
                <Route path="/results/:runId" element={<Results />} />
                <Route path="/time-machine/:runId" element={<TimeMachinePage />} />
                <Route path="/history" element={<History />} />
                <Route path="/wizards" element={<TuningWizardsPage />} />
                <Route path="/training" element={<OperatorTrainingPage />} />
                <Route path="/engine-analyzer" element={<EngineAnalyzerPage />} />
                <Route path="/ve-heatmap-demo" element={<VEHeatmapDemo />} />
                <Route path="/autotune-demo" element={<AutoTuneDemo />} />
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
