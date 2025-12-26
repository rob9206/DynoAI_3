import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/sonner';
import { ThemeProvider } from 'next-themes';
import { lazy, Suspense } from 'react';
import Layout from './components/Layout';
import LoadingSpinner from './components/LoadingSpinner';

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
      <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
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
                <Route path="/ve-heatmap-demo" element={<VEHeatmapDemo />} />
                <Route path="*" element={<Navigate to="/jetdrive" replace />} />
              </Routes>
            </Suspense>
          </Layout>
        </Router>
        <Toaster position="top-right" richColors />
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
