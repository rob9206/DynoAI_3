import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Download, ArrowLeft, FileText, Table, Box, Grid, Layers, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { getJobStatus, getVEData, getCoverageData, getDiagnostics, downloadFile, VEData, CoverageData, DiagnosticsData, AnalysisManifest } from '../lib/api';
import VEHeatmap from '../components/VEHeatmap';
import { VESurface } from '../components/VESurface';
import DiagnosticsPanel from '../components/DiagnosticsPanel';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Badge } from '../components/ui/badge';

export default function Results() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [manifest, setManifest] = useState<AnalysisManifest | null>(null);
  const [veData, setVeData] = useState<VEData | null>(null);
  const [coverageData, setCoverageData] = useState<CoverageData | null>(null);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'2d' | '3d'>('2d');
  const [veLoadError, setVeLoadError] = useState<string | null>(null);

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
          const veResult = await getVEData(runId!).catch(err => {
             console.error("VE Data Load Error:", err);
             setVeLoadError("Failed to load VE Data");
             return null;
          });
          const coverageResult = await getCoverageData(runId!).catch(() => null);
          const diagResult = await getDiagnostics(runId!).catch(() => null);

          setVeData(veResult);
          setCoverageData(coverageResult);
          setDiagnostics(diagResult);
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
        <div className="text-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="text-muted-foreground">Loading results...</p>
        </div>
      </div>
    );
  }

  if (!manifest) {
    return (
      <div className="text-center py-12 space-y-6">
        <p className="text-muted-foreground text-lg">No results found</p>
        <Button variant="link" onClick={() => navigate('/')}>
          Return to Dashboard
        </Button>
      </div>
    );
  }

  const hasVisualizations = !!veData || !!coverageData?.front || !!coverageData?.rear;

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Button
          variant="ghost"
          onClick={() => navigate('/')}
          className="flex items-center gap-2 pl-0 hover:pl-2 transition-all"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back to Dashboard</span>
        </Button>

        <Button
          onClick={downloadAll}
          className="flex items-center gap-2 shadow-sm"
        >
          <Download className="h-4 w-4" />
          <span>Download All</span>
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Rows Processed</CardDescription>
            <CardTitle className="text-3xl font-mono">
              {manifest.rowsProcessed.toLocaleString()}
            </CardTitle>
          </CardHeader>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Corrections Applied</CardDescription>
            <CardTitle className="text-3xl font-mono text-green-500">
              {manifest.correctionsApplied}
            </CardTitle>
          </CardHeader>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Avg Correction</CardDescription>
            <CardTitle className="text-3xl font-mono text-primary">
              {manifest.analysisMetrics.avgCorrection.toFixed(1)}%
            </CardTitle>
          </CardHeader>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Max Correction</CardDescription>
            <CardTitle className="text-3xl font-mono text-accent">
              {manifest.analysisMetrics.maxCorrection.toFixed(1)}%
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Analysis Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="h-5 w-5 text-primary" />
            Analysis Details
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
            <div className="space-y-1">
              <p className="text-muted-foreground">Input File</p>
              <p className="font-medium break-all">{manifest.inputFile}</p>
            </div>
            <div className="space-y-1">
              <p className="text-muted-foreground">Timestamp</p>
              <p className="font-medium font-mono">
                {new Date(manifest.timestamp).toLocaleString()}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-muted-foreground">Target AFR</p>
              <p className="font-medium font-mono">{manifest.analysisMetrics.targetAFR}</p>
            </div>
            <div className="space-y-1">
              <p className="text-muted-foreground">Smoothing Iterations</p>
              <p className="font-medium font-mono">{manifest.analysisMetrics.iterations}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-3 max-w-md mb-6">
          <TabsTrigger value="overview">Output Files</TabsTrigger>
          <TabsTrigger value="visualizations">Visualizations</TabsTrigger>
          <TabsTrigger value="diagnostics">Diagnostics</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {manifest.outputFiles.map((file, index) => {
              const fileIcon = file.name.endsWith('.csv') ? (
                <Table className="h-8 w-8 text-blue-500" />
              ) : file.name.endsWith('.json') ? (
                <FileText className="h-8 w-8 text-green-500" />
              ) : file.name.includes('Anomaly') ? (
                <AlertCircle className="h-8 w-8 text-yellow-500" />
              ) : (
                <FileText className="h-8 w-8 text-purple-500" />
              );

              const fileSize = typeof file === 'object' && 'size' in file ? 
                `${((file.size as number) / 1024).toFixed(1)} KB` : 
                '';

              return (
                <Card
                  key={index}
                  className="group hover:shadow-lg hover:scale-[1.02] transition-all duration-200 cursor-pointer overflow-hidden"
                  onClick={() => handleDownloadFile(file.name)}
                >
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between mb-4">
                      <div className="p-3 bg-primary/10 rounded-lg group-hover:bg-primary/20 transition-colors">
                        {fileIcon}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDownloadFile(file.name);
                        }}
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                    </div>
                    
                    <div className="space-y-2">
                      <h3 className="font-semibold text-sm text-foreground line-clamp-2 min-h-[2.5rem]">
                        {file.name}
                      </h3>
                      
                      <div className="flex items-center justify-between">
                        <Badge variant="secondary" className="text-xs font-normal">
                          {file.type}
                        </Badge>
                        {fileSize && (
                          <span className="text-xs text-muted-foreground font-mono">
                            {fileSize}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="mt-4 pt-4 border-t border-border">
                      <div className="flex items-center text-xs text-primary font-medium group-hover:translate-x-1 transition-transform">
                        <Download className="h-3 w-3 mr-1" />
                        Click to download
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </TabsContent>

        {/* Visualizations Tab */}
        <TabsContent value="visualizations" className="space-y-6 min-h-[200px]">
          {hasVisualizations ? (
            <div className="space-y-6">
              {veData && (
                <>
                  <div className="flex justify-between items-center">
                     <h3 className="text-lg font-medium">VE Corrections</h3>
                     <div className="bg-muted p-1 rounded-lg inline-flex">
                      <Button
                        variant={viewMode === '2d' ? 'default' : 'ghost'}
                        size="sm"
                        onClick={() => setViewMode('2d')}
                        className="h-8"
                      >
                        <Grid className="h-4 w-4 mr-2" />
                        2D View
                      </Button>
                      <Button
                        variant={viewMode === '3d' ? 'default' : 'ghost'}
                        size="sm"
                        onClick={() => setViewMode('3d')}
                        className="h-8"
                      >
                        <Box className="h-4 w-4 mr-2" />
                        3D View
                      </Button>
                    </div>
                  </div>

                  {viewMode === '2d' ? (
                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
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
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                      <Card>
                        <CardHeader>
                          <CardTitle>VE Table - Before Corrections</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="h-[500px] rounded-lg overflow-hidden border border-border bg-muted/10">
                            <VESurface data={veData} type="before" />
                          </div>
                          <p className="text-xs text-muted-foreground text-center mt-4">
                            Click and drag to rotate • Scroll to zoom
                          </p>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardHeader>
                          <CardTitle>VE Table - After Corrections</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="h-[500px] rounded-lg overflow-hidden border border-border bg-muted/10">
                            <VESurface data={veData} type="after" />
                          </div>
                          <p className="text-xs text-muted-foreground text-center mt-4">
                            Click and drag to rotate • Scroll to zoom
                          </p>
                        </CardContent>
                      </Card>
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
            </div>
          ) : (
            <Card className="py-12 text-center border-dashed">
              <CardContent className="space-y-4 pt-6">
                 <div className="p-4 bg-muted rounded-full w-fit mx-auto">
                   <AlertCircle className="h-8 w-8 text-muted-foreground" />
                 </div>
                <div className="space-y-2">
                   <p className="font-medium text-foreground">No visualization data available</p>
                   <p className="text-sm text-muted-foreground">
                     {veLoadError ? `Error: ${veLoadError}` : "The analysis did not produce compatible 3D/2D visualization data."}
                   </p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Diagnostics Tab */}
        <TabsContent value="diagnostics">
          {diagnostics?.anomalies ? (
            <DiagnosticsPanel
              anomalies={diagnostics.anomalies.anomalies || []}
              correctionDiagnostics={diagnostics.anomalies.correction_diagnostics}
            />
          ) : (
            <Card className="py-12 text-center">
              <CardContent>
                <p className="text-muted-foreground">No diagnostics data available</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
