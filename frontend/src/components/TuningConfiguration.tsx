import { Settings } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Label } from './ui/label';
import { Input } from './ui/input';
import { AnalysisParams } from '../lib/api';
import { Separator } from './ui/separator';
import { Slider } from './ui/slider';

interface TuningConfigurationProps {
  params: AnalysisParams;
  setParams: (params: AnalysisParams) => void;
  disabled?: boolean;
}

export function TuningConfiguration({ params, setParams, disabled }: TuningConfigurationProps) {
  return (
    <Card className="h-full border-border/50 shadow-sm">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Settings className="h-5 w-5 text-primary" />
          Tuning Configuration
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-4">
          <div className="grid gap-4">
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <Label htmlFor="smoothPasses" className="text-base font-medium">Smoothing Intensity</Label>
                <span className="text-sm text-muted-foreground bg-muted px-2 py-0.5 rounded font-mono">
                  {params.smoothPasses} passes
                </span>
              </div>
              <Slider
                id="smoothPasses"
                min={0}
                max={5}
                step={1}
                value={[params.smoothPasses]}
                onValueChange={(vals) => setParams({ ...params, smoothPasses: vals[0] })}
                disabled={disabled}
                className="py-2"
              />
              <p className="text-xs text-muted-foreground">
                Higher values blend adjacent cells more aggressively.
              </p>
            </div>

            <Separator />

            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <Label htmlFor="clamp" className="text-base font-medium">Correction Limit (Clamp)</Label>
                <span className="text-sm text-muted-foreground bg-muted px-2 py-0.5 rounded font-mono">
                  ±{params.clamp}%
                </span>
              </div>
              <Slider
                id="clamp"
                min={5}
                max={20}
                step={0.5}
                value={[params.clamp]}
                onValueChange={(vals) => setParams({ ...params, clamp: vals[0] })}
                disabled={disabled}
                className="py-2"
              />
              <p className="text-xs text-muted-foreground">
                Maximum allowed VE change per cell.
              </p>
            </div>
          </div>
          
          <Separator />

          <div className="space-y-3 pt-2">
             <Label className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
               Rear Cylinder Bias
             </Label>
             
             <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="rearBias" className="text-sm">Fuel Bias (%)</Label>
                  <Input
                    id="rearBias"
                    type="number"
                    value={params.rearBias}
                    onChange={(e) => setParams({ ...params, rearBias: parseFloat(e.target.value) })}
                    disabled={disabled}
                    className="font-mono"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="rearRuleDeg" className="text-sm">Spark Retard (deg)</Label>
                  <Input
                    id="rearRuleDeg"
                    type="number"
                    value={params.rearRuleDeg}
                    onChange={(e) => setParams({ ...params, rearRuleDeg: parseFloat(e.target.value) })}
                    disabled={disabled}
                    className="font-mono"
                  />
                </div>
             </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

