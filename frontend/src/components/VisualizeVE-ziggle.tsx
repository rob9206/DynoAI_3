import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Cube, CheckCircle } from '@phosphor-icons/react';
import { VESurface } from '@/components/VESurface';
import { generateVEData } from '@/lib/analysis';
import { fetchVEData } from '@/lib/analysis-api';
import type { VEData, ManifestData } from '@/lib/types';
import { toast } from 'sonner';

interface VisualizeVEProps {
  manifest: ManifestData | null;
}

export function VisualizeVE({ manifest }: VisualizeVEProps) {
  const [veData, setVeData] = useState<VEData | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerate = useCallback(async (): Promise<void> => {
    setIsGenerating(true);
    toast.info('Generating 3D surfaces...');

    try {
      // Try to fetch real VE data if runId is available
      if (manifest?.runId) {
        const data = await fetchVEData(manifest.runId);
        setVeData(data);
        toast.success('3D visualization ready (from analysis)');
      } else {
        // Fallback to generated data
        await new Promise(resolve => setTimeout(resolve, 1000));
        const data = generateVEData();
        setVeData(data);
        toast.success('3D visualization ready (simulated)');
      }
    } catch (error) {
      console.error('Failed to fetch VE data:', error);
      // Fallback to generated data
      const data = generateVEData();
      setVeData(data);
      toast.warning('Using simulated VE data');
    } finally {
      setIsGenerating(false);
    }
  }, [manifest]);

  useEffect(() => {
    if (!manifest || veData) return;
    void handleGenerate();
  }, [manifest, veData, handleGenerate]);

  if (!manifest) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2">Visualize VE</h1>
          <p className="text-muted-foreground">
            Interactive 3D visualization of volumetric efficiency before and after tuning
          </p>
        </div>

        <Alert>
          <AlertDescription>
            Please run an analysis first to generate VE visualization data.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground mb-2">Visualize VE</h1>
        <p className="text-muted-foreground">
          Interactive 3D visualization of volumetric efficiency before and after tuning
        </p>
      </div>

      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Cube size={24} className="text-primary" />
            <div>
              <h3 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
                3D Surface Generation
              </h3>
              <p className="text-sm text-foreground">
                {veData ? 'Surfaces ready' : 'Generate visualization'}
              </p>
            </div>
          </div>
          {veData && <CheckCircle size={24} className="text-accent" weight="fill" />}
        </div>

        {!veData && (
          <Button onClick={() => { void handleGenerate(); }} disabled={isGenerating} className="w-full">
            <Cube size={20} className="mr-2" />
            {isGenerating ? 'Generating...' : 'Generate 3D Surfaces'}
          </Button>
        )}
      </Card>

      {veData && (
        <>
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <Badge variant="secondary" className="mb-2">Before Tuning</Badge>
                <h3 className="text-lg font-semibold text-foreground">Original VE Surface</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Baseline volumetric efficiency across RPM and load ranges
                </p>
              </div>
            </div>
            <div className="bg-gradient-to-br from-slate-950 to-slate-900 rounded-lg p-2">
              <VESurface data={veData} type="before" />
            </div>
            <p className="text-xs text-muted-foreground mt-3 text-center">
              Click and drag to rotate • RPM × Load × VE%
            </p>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <Badge className="mb-2 bg-accent text-accent-foreground">After Tuning</Badge>
                <h3 className="text-lg font-semibold text-foreground">Optimized VE Surface</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Improved volumetric efficiency with AFR corrections applied
                </p>
              </div>
            </div>
            <div className="bg-gradient-to-br from-slate-950 to-slate-900 rounded-lg p-2">
              <VESurface data={veData} type="after" />
            </div>
            <p className="text-xs text-muted-foreground mt-3 text-center">
              Click and drag to rotate • RPM × Load × VE%
            </p>
          </Card>

          <Card className="p-6">
            <h3 className="text-sm font-medium uppercase tracking-wide text-muted-foreground mb-4">
              Improvement Summary
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-lg bg-muted/50">
                <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                  Avg Improvement
                </p>
                <p className="text-2xl font-mono font-medium text-accent">+3.2%</p>
              </div>
              <div className="p-4 rounded-lg bg-muted/50">
                <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                  Peak VE
                </p>
                <p className="text-2xl font-mono font-medium text-foreground">94.7%</p>
              </div>
              <div className="p-4 rounded-lg bg-muted/50">
                <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                  Target AFR
                </p>
                <p className="text-2xl font-mono font-medium text-foreground">
                  {manifest.analysisMetrics.targetAFR}
                </p>
              </div>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
