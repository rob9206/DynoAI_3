import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { ThemeProvider } from 'next-themes';
import Dashboard from './pages/Dashboard';
import Results from './pages/Results';
import History from './pages/History';
import VEHeatmapDemo from './pages/VEHeatmapDemo';
import JetstreamPage from './pages/JetstreamPage';
import RunDetailPage from './pages/RunDetailPage';
import Layout from './components/Layout';

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
            <Routes>
              <Route path="/" element={<Navigate to="/jetstream" replace />} />
              <Route path="/jetstream" element={<JetstreamPage />} />
              <Route path="/runs/:runId" element={<RunDetailPage />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/results/:runId" element={<Results />} />
              <Route path="/history" element={<History />} />
              <Route path="/ve-heatmap-demo" element={<VEHeatmapDemo />} />
              <Route path="*" element={<Navigate to="/jetstream" replace />} />
            </Routes>
          </Layout>
        </Router>
        <Toaster position="top-right" richColors />
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
