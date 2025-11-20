import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Download, ArrowLeft, FileText, Table, Box, Grid } from 'lucide-react';
import { toast } from 'sonner';
import { getJobStatus, getVEData, getCoverageData, getDiagnostics, downloadFile, VEData, CoverageData, DiagnosticsData, AnalysisManifest } from '../lib/api';
import VEHeatmap from '../components/VEHeatmap';
import { VESurface } from '../components/VESurface';
import DiagnosticsPanel from '../components/DiagnosticsPanel';

export default function Results() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [manifest, setManifest] = useState<AnalysisManifest | null>(null);
  const [veData, setVeData] = useState<VEData | null>(null);
  const [coverageData, setCoverageData] = useState<CoverageData | null>(null);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'visualizations' | 'diagnostics'>('overview');
  const [viewMode, setViewMode] = useState<'2d' | '3d'>('2d');

  useEffect(() => {
    if (!runId) {
      navigate('/');
      return;
    }

    loadResults();
  }, [runId]);

  const loadResults = async () => {
    try {
      const status = await getJobStatus(runId!);

      if (status.status === 'completed' && status.manifest) {
        setManifest(status.manifest);

        // Load additional data
        try {
          const [ve, coverage, diag] = await Promise.all([
            getVEData(runId!).catch(() => null),
            getCoverageData(runId!).catch(() => null),
            getDiagnostics(runId!).catch(() => null),
          ]);

          setVeData(ve);
          setCoverageData(coverage);
          setDiagnostics(diag);
        } catch (err) {
          console.warn('Some visualization data could not be loaded:', err);
        }
      } else if (status.status === 'error') {
        toast.error(status.error || 'Analysis failed');
        navigate('/');
      } else {
        // Still processing
        setTimeout(loadResults, 2000);
        return;
      }
    } catch (error: any) {
      console.error('Error loading results:', error);
      toast.error('Failed to load results');
      navigate('/');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadFile = async (filename: string) => {
    try {
      const blob = await downloadFile(runId!, filename);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success(`Downloaded ${filename}`);
    } catch (error) {
      toast.error(`Failed to download ${filename}`);
    }
  };

  const downloadAll = () => {
    if (!manifest) return;

    manifest.outputFiles.forEach((file, index) => {
      setTimeout(() => {
        handleDownloadFile(file.name);
      }, index * 200);
    });

    toast.success('Downloading all files');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-400">Loading results...</p>
        </div>
      </div>
    );
  }

  if (!manifest) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400">No results found</p>
        <button
          onClick={() => navigate('/')}
          className="mt-4 text-blue-500 hover:text-blue-400"
        >
          Return to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <button
          onClick={() => navigate('/')}
          className="flex items-center space-x-2 text-gray-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
          <span>Back to Dashboard</span>
        </button>

        <button
          onClick={downloadAll}
          className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
        >
          <Download className="h-4 w-4" />
          <span>Download All</span>
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-gray-800/50 backdrop-blur-sm rounded-lg p-6 border border-gray-700">
          <p className="text-sm text-gray-400 mb-1">Rows Processed</p>
          <p className="text-3xl font-bold text-white">
            {manifest.rowsProcessed.toLocaleString()}
          </p>
        </div>

        <div className="bg-gray-800/50 backdrop-blur-sm rounded-lg p-6 border border-gray-700">
          <p className="text-sm text-gray-400 mb-1">Corrections Applied</p>
          <p className="text-3xl font-bold text-green-500">
            {manifest.correctionsApplied}
          </p>
        </div>

        <div className="bg-gray-800/50 backdrop-blur-sm rounded-lg p-6 border border-gray-700">
          <p className="text-sm text-gray-400 mb-1">Avg Correction</p>
          <p className="text-3xl font-bold text-blue-500">
            {manifest.analysisMetrics.avgCorrection.toFixed(1)}%
          </p>
        </div>

        <div className="bg-gray-800/50 backdrop-blur-sm rounded-lg p-6 border border-gray-700">
          <p className="text-sm text-gray-400 mb-1">Max Correction</p>
          <p className="text-3xl font-bold text-orange-500">
            {manifest.analysisMetrics.maxCorrection.toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Analysis Info */}
      <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl p-6 border border-gray-700 mb-8">
        <h2 className="text-xl font-semibold text-white mb-4">Analysis Details</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-400">Input File:</span>
            <span className="ml-2 text-white">{manifest.inputFile}</span>
          </div>
          <div>
            <span className="text-gray-400">Timestamp:</span>
            <span className="ml-2 text-white">
              {new Date(manifest.timestamp).toLocaleString()}
            </span>
          </div>
          <div>
            <span className="text-gray-400">Target AFR:</span>
            <span className="ml-2 text-white">{manifest.analysisMetrics.targetAFR}</span>
          </div>
          <div>
            <span className="text-gray-400">Smoothing Iterations:</span>
            <span className="ml-2 text-white">{manifest.analysisMetrics.iterations}</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl border border-gray-700 overflow-hidden">
        <div className="flex border-b border-gray-700">
          <button
            onClick={() => setActiveTab('overview')}
            className={`px-6 py-3 font-medium transition-colors ${activeTab === 'overview'
                ? 'bg-gray-700 text-white border-b-2 border-blue-500'
                : 'text-gray-400 hover:text-white'
              }`}
          >
            Output Files
          </button>
          <button
            onClick={() => setActiveTab('visualizations')}
            className={`px-6 py-3 font-medium transition-colors ${activeTab === 'visualizations'
                ? 'bg-gray-700 text-white border-b-2 border-blue-500'
                : 'text-gray-400 hover:text-white'
              }`}
          >
            Visualizations
          </button>
          <button
            onClick={() => setActiveTab('diagnostics')}
            className={`px-6 py-3 font-medium transition-colors ${activeTab === 'diagnostics'
                ? 'bg-gray-700 text-white border-b-2 border-blue-500'
                : 'text-gray-400 hover:text-white'
              }`}
          >
            Diagnostics
          </button>
        </div>

        <div className="p-6">
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="space-y-3">
              {manifest.outputFiles.map((file, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-4 bg-gray-900/50 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors"
                >
                  <div className="flex items-center space-x-3">
                    {file.name.endsWith('.csv') ? (
                      <Table className="h-5 w-5 text-blue-500" />
                    ) : (
                      <FileText className="h-5 w-5 text-green-500" />
                    )}
                    <div>
                      <p className="text-sm font-medium text-white">{file.name}</p>
                      <p className="text-xs text-gray-500">{file.type}</p>
                    </div>
                  </div>

                  <button
                    onClick={() => handleDownloadFile(file.name)}
                    className="flex items-center space-x-2 text-blue-500 hover:text-blue-400 transition-colors"
                  >
                    <Download className="h-4 w-4" />
                    <span className="text-sm">Download</span>
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Visualizations Tab */}
          {activeTab === 'visualizations' && (
            <div className="space-y-6">
              {veData && (
                <>
                  <div className="flex justify-end mb-4">
                    <div className="bg-gray-800 p-1 rounded-lg inline-flex border border-gray-700">
                      <button
                        onClick={() => setViewMode('2d')}
                        className={`p-2 rounded flex items-center space-x-2 ${viewMode === '2d'
                            ? 'bg-gray-700 text-white shadow-sm'
                            : 'text-gray-400 hover:text-white hover:bg-gray-700/50'
                          }`}
                        title="2D Heatmap"
                      >
                        <Grid className="h-4 w-4" />
                        <span className="text-sm font-medium">2D View</span>
                      </button>
                      <button
                        onClick={() => setViewMode('3d')}
                        className={`p-2 rounded flex items-center space-x-2 ${viewMode === '3d'
                            ? 'bg-gray-700 text-white shadow-sm'
                            : 'text-gray-400 hover:text-white hover:bg-gray-700/50'
                          }`}
                        title="3D Surface"
                      >
                        <Box className="h-4 w-4" />
                        <span className="text-sm font-medium">3D View</span>
                      </button>
                    </div>
                  </div>

                  {viewMode === '2d' ? (
                    <>
                      <VEHeatmap
                        data={veData.before}
                        rpm={veData.rpm}
                        load={veData.load}
                        title="VE Table - Before Corrections"
                      />
                      <VEHeatmap
                        data={veData.after}
                        rpm={veData.rpm}
                        load={veData.load}
                        title="VE Table - After Corrections"
                      />
                    </>
                  ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      <div className="space-y-4">
                        <h3 className="text-lg font-semibold text-white">VE Table - Before Corrections</h3>
                        <div className="h-[500px] border border-gray-700 rounded-lg overflow-hidden">
                          <VESurface data={veData} type="before" />
                        </div>
                        <p className="text-sm text-gray-400 text-center">
                          Click and drag to rotate • Scroll to zoom
                        </p>
                      </div>
                      <div className="space-y-4">
                        <h3 className="text-lg font-semibold text-white">VE Table - After Corrections</h3>
                        <div className="h-[500px] border border-gray-700 rounded-lg overflow-hidden">
                          <VESurface data={veData} type="after" />
                        </div>
                        <p className="text-sm text-gray-400 text-center">
                          Click and drag to rotate • Scroll to zoom
                        </p>
                      </div>
                    </div>
                  )}
                </>
              )}

              {coverageData?.front && (
                <VEHeatmap
                  data={coverageData.front.data}
                  rpm={coverageData.front.rpm}
                  load={coverageData.front.load}
                  title="Data Coverage - Front Cylinder"
                />
              )}

              {coverageData?.rear && (
                <VEHeatmap
                  data={coverageData.rear.data}
                  rpm={coverageData.rear.rpm}
                  load={coverageData.rear.load}
                  title="Data Coverage - Rear Cylinder"
                />
              )}

              {!veData && !coverageData && (
                <p className="text-center text-gray-400 py-8">
                  No visualization data available
                </p>
              )}
            </div>
          )}

          {/* Diagnostics Tab */}
          {activeTab === 'diagnostics' && (
            <>
              {diagnostics?.anomalies ? (
                <DiagnosticsPanel
                  anomalies={diagnostics.anomalies.anomalies || []}
                  correctionDiagnostics={diagnostics.anomalies.correction_diagnostics}
                />
              ) : (
                <p className="text-center text-gray-400 py-8">
                  No diagnostics data available
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
