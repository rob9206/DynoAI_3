import { useState, type ChangeEvent } from 'react';
import { AlertCircle, FileUp, Play, Zap } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  getMockHardStartResult,
  type HardStartAnalysisResponse,
  type RecommendedAction,
} from '@/api/hardStart';
import { HardStartCharts } from '@/components/hard-start/HardStartCharts';
import { HardStartHypotheses } from '@/components/hard-start/HardStartHypotheses';
import { HardStartSegmentList } from '@/components/hard-start/HardStartSegmentList';
import { HardStartSummaryCards } from '@/components/hard-start/HardStartSummaryCards';

function priorityBadgeVariant(priority: RecommendedAction['priority']): 'default' | 'secondary' | 'destructive' {
  if (priority === 'immediate') {
    return 'destructive';
  }
  if (priority === 'soon') {
    return 'secondary';
  }
  return 'default';
}

export default function HardStartAnalyzerPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<HardStartAnalysisResponse | null>(null);

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0] ?? null;
    setSelectedFile(nextFile);
    setError(null);
  };

  const handleAnalyze = () => {
    if (!selectedFile) {
      setError('Select a DynoWare crank log file before running analysis.');
      return;
    }

    setIsAnalyzing(true);
    setError(null);

    try {
      // TODO: replace with analyzeHardStart(selectedFile) when POST /api/hard_start/analyze is available.
      const response = getMockHardStartResult(selectedFile.name);
      setAnalysis(response);
    } catch (analyzeError) {
      console.error('Hard start analysis failed:', analyzeError);
      setError('Failed to analyze log. Please try again.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="mx-auto grid w-full max-w-7xl gap-6">
      <section className="rounded-2xl border bg-card p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="grid gap-1">
            <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
              <Zap className="h-6 w-6 text-amber-500" />
              Hard Start Analyzer
            </h1>
            <p className="text-sm text-muted-foreground">
              Upload a DynoWare crank log and review backend-provided hard-start analysis output.
            </p>
          </div>
          {analysis && (
            <Badge variant="outline" className="text-xs">
              Run: {analysis.run_id}
            </Badge>
          )}
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Upload DynoWare Crank Log</CardTitle>
          <CardDescription>
            Select a log export file and run Hard Start analysis.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="hard-start-file">Crank Log File</Label>
            <Input
              id="hard-start-file"
              type="file"
              accept=".txt,.csv"
              onChange={handleFileChange}
            />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" onClick={handleAnalyze} disabled={!selectedFile || isAnalyzing}>
              <Play data-icon="inline-start" />
              {isAnalyzing ? 'Analyzing...' : 'Analyze'}
            </Button>
            {selectedFile && (
              <div className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                <FileUp className="h-4 w-4" />
                <span>{selectedFile.name}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Analysis Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {analysis && (
        <>
          <HardStartSummaryCards summary={analysis.summary} />

          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertTitle className="flex items-center gap-2">
              <span>{analysis.recommended_action.title}</span>
              <Badge variant={priorityBadgeVariant(analysis.recommended_action.priority)}>
                {analysis.recommended_action.priority}
              </Badge>
            </AlertTitle>
            <AlertDescription>{analysis.recommended_action.description}</AlertDescription>
          </Alert>

          <Tabs defaultValue="charts" className="grid gap-4">
            <TabsList className="w-fit">
              <TabsTrigger value="charts">Charts</TabsTrigger>
              <TabsTrigger value="segments">Segments</TabsTrigger>
              <TabsTrigger value="hypotheses">Hypotheses</TabsTrigger>
            </TabsList>
            <TabsContent value="charts">
              <HardStartCharts timeSeries={analysis.time_series} segments={analysis.segments} />
            </TabsContent>
            <TabsContent value="segments">
              <HardStartSegmentList segments={analysis.segments} />
            </TabsContent>
            <TabsContent value="hypotheses">
              <HardStartHypotheses hypotheses={analysis.hypotheses} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}

