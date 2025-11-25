import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Loader2, AlertTriangle, CheckCircle, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { useGenerateBaseline } from '@/hooks/useBaseline';
import { ConfidenceHeatmap } from '@/components/baseline/ConfidenceHeatmap';
import { BaselineResult } from '@/api/baseline';

export function BaselinePage() {
  const { runId } = useParams<{ runId: string }>();
  const [showConfidence, setShowConfidence] = useState(false);
  const [result, setResult] = useState<BaselineResult | null>(null);

  const generateMutation = useGenerateBaseline();

  const handleGenerate = async () => {
    if (!runId) return;
    const data = await generateMutation.mutateAsync(runId);
    if (data.status === 'ok') {
      setResult(data);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">One-Pull Baseline™</h1>
          <p className="text-muted-foreground">
            Generate a complete VE starting map from a single partial-throttle pull
          </p>
        </div>
        {runId && (
          <Badge variant="outline" className="font-mono">
            Run: {runId.slice(-8)}
          </Badge>
        )}
      </div>

      {/* Generation Card */}
      {!result && (
        <Card>
          <CardHeader>
            <CardTitle>Generate Baseline</CardTitle>
            <CardDescription>
              Upload or select a partial-throttle (50-70%) pull to generate your baseline VE table
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert>
              <Info className="h-4 w-4" />
              <AlertTitle>Requirements</AlertTitle>
              <AlertDescription>
                <ul className="list-disc list-inside mt-2 space-y-1 text-sm">
                  <li>Single pull at ~60% throttle</li>
                  <li>RPM sweep from idle to near redline</li>
                  <li>Working wideband AFR sensor</li>
                  <li>At least 50 data points (100+ recommended)</li>
                </ul>
              </AlertDescription>
            </Alert>

            <Button
              onClick={handleGenerate}
              disabled={!runId || generateMutation.isPending}
              className="w-full"
            >
              {generateMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generating Baseline...
                </>
              ) : (
                'Generate Baseline'
              )}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {result && result.status === 'ok' && (
        <>
          {/* Summary Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-green-500" />
                Baseline Generated
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-sm text-muted-foreground">Measured Cells</div>
                  <div className="text-2xl font-bold font-mono">{result.summary.measured_cells}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Interpolated</div>
                  <div className="text-2xl font-bold font-mono">{result.summary.interpolated_cells}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Extrapolated</div>
                  <div className="text-2xl font-bold font-mono">{result.summary.extrapolated_cells}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Avg Confidence</div>
                  <div className="text-2xl font-bold font-mono">{result.summary.avg_confidence}%</div>
                </div>
              </div>

              <div className="mt-4">
                <div className="flex justify-between text-sm mb-1">
                  <span>Overall Confidence</span>
                  <span>{result.summary.avg_confidence}%</span>
                </div>
                <Progress value={result.summary.avg_confidence} />
              </div>

              {/* FDC Status */}
              <div className="mt-4 flex items-center gap-2">
                <span className="text-sm text-muted-foreground">FDC Stability:</span>
                {result.fdc_analysis.is_stable ? (
                  <Badge variant="default">Stable</Badge>
                ) : (
                  <Badge variant="destructive">Unstable</Badge>
                )}
                <span className="text-xs text-muted-foreground">
                  (score: {(result.fdc_analysis.stability_score * 100).toFixed(0)}%)
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Warnings */}
          {result.warnings.length > 0 && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Warnings</AlertTitle>
              <AlertDescription>
                <ul className="list-disc list-inside mt-2">
                  {result.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          {/* Recommendations */}
          {result.recommendations.length > 0 && (
            <Alert>
              <Info className="h-4 w-4" />
              <AlertTitle>Recommendations</AlertTitle>
              <AlertDescription>
                <ul className="list-disc list-inside mt-2">
                  {result.recommendations.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          {/* Heatmap */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>VE Corrections</CardTitle>
                <div className="flex items-center space-x-2">
                  <Switch
                    id="confidence-mode"
                    checked={showConfidence}
                    onCheckedChange={setShowConfidence}
                  />
                  <Label htmlFor="confidence-mode">Show Confidence</Label>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <ConfidenceHeatmap
                veCorrections={result.preview.ve_corrections}
                confidenceMap={result.preview.confidence_map}
                cellTypes={result.preview.cell_types}
                rpmAxis={result.preview.rpm_axis}
                mapAxis={result.preview.map_axis}
                showConfidence={showConfidence}
              />
            </CardContent>
          </Card>

          {/* Actions */}
          <div className="flex gap-4">
            <Button variant="outline" className="flex-1">
              Download CSV
            </Button>
            <Button className="flex-1">
              Apply Baseline
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
