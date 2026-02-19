import { useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { FileArrowUp, Play, CheckCircle, DownloadSimple, ChartLine } from '@phosphor-icons/react';
import { parseCSV, simulateAnalysis, downloadFile } from '@/lib/analysis';
import { runRealAnalysis, downloadOutputFile } from '@/lib/analysis-api';
import type { ManifestData, AnalysisStatus } from '@/lib/types';
import { toast } from '@/lib/toast';

interface AnalyzeRunProps {
  onAnalysisComplete: (manifest: ManifestData) => void;
}

export function AnalyzeRun({ onAnalysisComplete }: AnalyzeRunProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [status, setStatus] = useState<AnalysisStatus>({
    stage: 'idle',
    progress: 0,
    message: 'Ready to analyze'
  });
  const [manifest, setManifest] = useState<ManifestData | null>(null);
  const [useRealAPI, setUseRealAPI] = useState(true);  // Toggle for real vs simulated
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.endsWith('.csv')) {
        toast.error('Please select a CSV file');
        return;
      }
      setSelectedFile(file);
      setManifest(null);
      setStatus({ stage: 'idle', progress: 0, message: 'Ready to analyze' });
    }
  };

  const handleAnalyze = async (): Promise<void> => {
    if (!selectedFile) return;

    try {
      setStatus({ stage: 'parsing', progress: 10, message: 'Reading CSV file...' });

      if (useRealAPI) {
        // Use real Python backend
        const result = await runRealAnalysis(selectedFile, (progress, message) => {
          setStatus({ stage: 'analyzing', progress, message });
        });

        setStatus({ stage: 'complete', progress: 100, message: 'Analysis complete!' });
        setManifest(result);
        onAnalysisComplete(result);
        toast.success('Analysis completed successfully');
      } else {
        // Use simulated analysis (for testing without backend)
        const text = await selectedFile.text();
        const csvData = parseCSV(text);

        if (csvData.length === 0) {
          throw new Error('No valid data found in CSV file');
        }

        setStatus({ stage: 'analyzing', progress: 25, message: 'Starting analysis...' });

        const result = await simulateAnalysis(csvData, (progress, message) => {
          setStatus({ stage: 'analyzing', progress, message });
        });

        setStatus({ stage: 'complete', progress: 100, message: 'Analysis complete!' });
        setManifest(result);
        onAnalysisComplete(result);
        toast.success('Analysis completed successfully (simulated)');
      }
    } catch (error) {
      setStatus({
        stage: 'error',
        progress: 0,
        message: error instanceof Error ? error.message : 'Analysis failed'
      });
      toast.error('Analysis failed');
    }
  };

  const handleAnalyzeClick = (): void => {
    void handleAnalyze();
  };

  const handleModeToggle = (): void => {
    setUseRealAPI((prev) => !prev);
  };

  const handleDownload = (fileName: string) => {
    if (useRealAPI && manifest?.runId) {
      // Use real API download
      downloadOutputFile(manifest.runId, fileName);
      toast.success(`Downloaded ${fileName}`);
    } else {
      // Fallback to simulated download
      const content = `Sample output file: ${fileName}\nGenerated: ${new Date().toISOString()}`;
      downloadFile(content, fileName);
      toast.success(`Downloaded ${fileName}`);
    }
  };

  const handleDownloadManifest = () => {
    if (!manifest) return;
    const content = JSON.stringify(manifest, null, 2);
    downloadFile(content, 'manifest.json', 'application/json');
    toast.success('Downloaded manifest.json');
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground mb-2">Analyze Run</h1>
        <p className="text-muted-foreground">
          Upload dyno CSV data to analyze AFR corrections and generate tuning tables
        </p>
      </div>

      <Card className="p-6">
        <div className="flex flex-col gap-4">
          <div>
            <h3 className="text-sm font-medium uppercase tracking-wide text-muted-foreground mb-3">
              CSV File Input
            </h3>
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-border rounded-lg p-8 text-center cursor-pointer hover:border-primary hover:bg-muted/50 transition-colors"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileSelect}
                className="hidden"
                id="csv-upload"
              />
              <FileArrowUp size={48} className="mx-auto mb-3 text-muted-foreground" />
              {selectedFile ? (
                <div>
                  <p className="font-medium text-foreground mb-1">{selectedFile.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {(selectedFile.size / 1024).toFixed(1)} KB
                  </p>
                </div>
              ) : (
                <div>
                  <p className="font-medium text-foreground mb-1">Click to select CSV file</p>
                  <p className="text-sm text-muted-foreground">or drag and drop</p>
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center justify-between rounded-lg border px-4 py-3">
            <div>
              <p className="text-sm font-medium text-foreground">Processing Mode</p>
              <p className="text-xs text-muted-foreground">
                {useRealAPI ? 'Send file to the Python backend' : 'Run fully in the browser'}
              </p>
            </div>
            <Button variant="secondary" size="sm" type="button" onClick={handleModeToggle}>
              {useRealAPI ? 'Real API' : 'Simulated'}
            </Button>
          </div>

          <Button
            onClick={handleAnalyzeClick}
            disabled={!selectedFile || status.stage === 'analyzing'}
            size="lg"
            className="w-full"
          >
            <Play size={20} className="mr-2" />
            {status.stage === 'analyzing' ? 'Analyzing...' : 'Run Analysis'}
          </Button>
        </div>
      </Card>

      {(status.stage === 'analyzing' || status.stage === 'complete') && (
        <Card className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <ChartLine size={24} className="text-primary" />
            <div className="flex-1">
              <h3 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
                Analysis Status
              </h3>
              <p className="text-sm text-foreground">{status.message}</p>
            </div>
            {status.stage === 'complete' && (
              <CheckCircle size={24} className="text-accent" weight="fill" />
            )}
          </div>
          <Progress value={status.progress} className="h-2" />
        </Card>
      )}

      {status.stage === 'error' && (
        <Alert variant="destructive">
          <AlertDescription>{status.message}</AlertDescription>
        </Alert>
      )}

      {manifest && (
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
              Manifest Statistics
            </h3>
            <Button variant="outline" size="sm" onClick={handleDownloadManifest}>
              <DownloadSimple size={16} className="mr-2" />
              Download JSON
            </Button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                Rows Processed
              </p>
              <p className="text-2xl font-mono font-medium text-foreground">
                {manifest.rowsProcessed}
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                Corrections Applied
              </p>
              <p className="text-2xl font-mono font-medium text-accent">
                {manifest.correctionsApplied}
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                Avg Correction
              </p>
              <p className="text-2xl font-mono font-medium text-foreground">
                {manifest.analysisMetrics.avgCorrection}%
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                Iterations
              </p>
              <p className="text-2xl font-mono font-medium text-foreground">
                {manifest.analysisMetrics.iterations}
              </p>
            </div>
          </div>

          <Separator className="mb-4" />

          <div>
            <h4 className="text-sm font-medium text-foreground mb-3">Output Files</h4>
            <div className="flex flex-col gap-2">
              {manifest.outputFiles.map((file, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-3 rounded-md bg-muted/50 hover:bg-muted transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <Badge variant="secondary">{file.type}</Badge>
                    <span className="text-sm font-medium text-foreground">{file.name}</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDownload(file.name)}
                  >
                    <DownloadSimple size={18} />
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
