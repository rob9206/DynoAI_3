/**
 * Virtual ECU Panel - Configure and control Virtual ECU simulation
 * 
 * Allows users to:
 * - Enable/disable Virtual ECU mode
 * - Configure VE table scenarios (perfect, wrong, custom)
 * - Set VE error parameters
 * - View ECU diagnostics
 * - Compare with/without ECU simulation
 */

import { useState } from 'react';
import { Cpu, AlertTriangle, CheckCircle2, Info, Zap, Settings2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { Slider } from '../ui/slider';
import { Switch } from '../ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { Badge } from '../ui/badge';
import { Alert, AlertDescription } from '../ui/alert';

export type VEScenario = 'perfect' | 'lean' | 'rich' | 'custom';

interface VirtualECUPanelProps {
  enabled: boolean;
  onEnabledChange: (enabled: boolean) => void;
  scenario: VEScenario;
  onScenarioChange: (scenario: VEScenario) => void;
  veErrorPct: number;
  onVeErrorChange: (error: number) => void;
  veErrorStd: number;
  onVeErrorStdChange: (std: number) => void;
}

export function VirtualECUPanel({
  enabled,
  onEnabledChange,
  scenario,
  onScenarioChange,
  veErrorPct,
  onVeErrorChange,
  veErrorStd,
  onVeErrorStdChange,
}: VirtualECUPanelProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const scenarioDescriptions: Record<VEScenario, { desc: string; icon: JSX.Element; color: string }> = {
    perfect: {
      desc: 'VE table matches engine perfectly. AFR will be on target (±0.05 sensor noise).',
      icon: <CheckCircle2 className="h-4 w-4" />,
      color: 'text-green-500',
    },
    lean: {
      desc: 'VE table is 10% too low (typical untuned engine). AFR will be LEAN.',
      icon: <AlertTriangle className="h-4 w-4" />,
      color: 'text-orange-500',
    },
    rich: {
      desc: 'VE table is 10% too high. AFR will be RICH.',
      icon: <AlertTriangle className="h-4 w-4" />,
      color: 'text-blue-500',
    },
    custom: {
      desc: 'Custom VE error. Adjust parameters below.',
      icon: <Settings2 className="h-4 w-4" />,
      color: 'text-purple-500',
    },
  };

  const currentScenario = scenarioDescriptions[scenario];

  return (
    <Card className="border-purple-500/30 bg-gradient-to-br from-purple-500/5 to-transparent">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Cpu className="h-5 w-5 text-purple-500" />
            <CardTitle>Virtual ECU</CardTitle>
            {enabled && (
              <Badge variant="outline" className="bg-purple-500/10 text-purple-500 border-purple-500/30">
                Active
              </Badge>
            )}
          </div>
          <Switch checked={enabled} onCheckedChange={onEnabledChange} />
        </div>
        <CardDescription>
          Simulate ECU fuel delivery based on VE tables. Creates realistic AFR errors when VE is wrong.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {!enabled && (
          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription>
              Enable Virtual ECU to simulate realistic tuning scenarios. AFR errors will be based on VE
              table mismatches instead of random patterns.
            </AlertDescription>
          </Alert>
        )}

        {enabled && (
          <>
            {/* Scenario Selection */}
            <div className="space-y-2">
              <Label>VE Table Scenario</Label>
              <Select value={scenario} onValueChange={(v) => onScenarioChange(v as VEScenario)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="perfect">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                      <span>Perfect VE (On Target)</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="lean">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-orange-500" />
                      <span>Lean (VE -10%)</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="rich">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-blue-500" />
                      <span>Rich (VE +10%)</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="custom">
                    <div className="flex items-center gap-2">
                      <Settings2 className="h-4 w-4 text-purple-500" />
                      <span>Custom</span>
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>

              {/* Scenario Description */}
              <div className={`flex items-start gap-2 p-3 rounded-lg bg-muted/50 ${currentScenario.color}`}>
                {currentScenario.icon}
                <p className="text-sm text-muted-foreground">{currentScenario.desc}</p>
              </div>
            </div>

            {/* Custom Parameters */}
            {scenario === 'custom' && (
              <div className="space-y-4 p-4 border rounded-lg bg-muted/20">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>VE Error (%)</Label>
                    <span className="text-sm font-mono text-muted-foreground">
                      {veErrorPct > 0 ? '+' : ''}
                      {veErrorPct.toFixed(1)}%
                    </span>
                  </div>
                  <Slider
                    value={[veErrorPct]}
                    onValueChange={(v) => onVeErrorChange(v[0])}
                    min={-20}
                    max={20}
                    step={0.5}
                    className="w-full"
                  />
                  <p className="text-xs text-muted-foreground">
                    Negative = Lean (ECU delivers less fuel), Positive = Rich (ECU delivers more fuel)
                  </p>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>VE Error Variation (±%)</Label>
                    <span className="text-sm font-mono text-muted-foreground">±{veErrorStd.toFixed(1)}%</span>
                  </div>
                  <Slider
                    value={[veErrorStd]}
                    onValueChange={(v) => onVeErrorStdChange(v[0])}
                    min={0}
                    max={10}
                    step={0.5}
                    className="w-full"
                  />
                  <p className="text-xs text-muted-foreground">
                    Variation across cells (0 = uniform error, 10 = high variation)
                  </p>
                </div>
              </div>
            )}

            {/* Expected Results */}
            <div className="space-y-2">
              <Label className="text-sm font-semibold">Expected Results</Label>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="p-2 rounded bg-muted/30">
                  <div className="text-muted-foreground">AFR Error</div>
                  <div className="font-mono font-semibold">
                    {scenario === 'perfect' && '±0.05 (sensor noise)'}
                    {scenario === 'lean' && '+1.0 to +1.5 AFR'}
                    {scenario === 'rich' && '-1.0 to -1.5 AFR'}
                    {scenario === 'custom' &&
                      `${veErrorPct > 0 ? '-' : '+'}${Math.abs(veErrorPct * 0.12).toFixed(1)} AFR`}
                  </div>
                </div>
                <div className="p-2 rounded bg-muted/30">
                  <div className="text-muted-foreground">Correction Needed</div>
                  <div className="font-mono font-semibold">
                    {scenario === 'perfect' && 'None'}
                    {scenario === 'lean' && '+10% VE'}
                    {scenario === 'rich' && '-10% VE'}
                    {scenario === 'custom' && `${veErrorPct > 0 ? '-' : '+'}${Math.abs(veErrorPct).toFixed(0)}% VE`}
                  </div>
                </div>
              </div>
            </div>

            {/* Advanced Settings Toggle */}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full"
            >
              <Settings2 className="h-4 w-4 mr-2" />
              {showAdvanced ? 'Hide' : 'Show'} Advanced Settings
            </Button>

            {showAdvanced && (
              <div className="space-y-3 p-4 border rounded-lg bg-muted/20">
                <div className="text-sm font-semibold">Advanced ECU Settings</div>

                <div className="space-y-2">
                  <Label className="text-xs">Cylinder Balance</Label>
                  <Select defaultValue="same">
                    <SelectTrigger className="h-8 text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="same">Same VE (Front/Rear)</SelectItem>
                      <SelectItem value="front_rich">Front 5% Richer</SelectItem>
                      <SelectItem value="rear_rich">Rear 5% Richer</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label className="text-xs">Environmental</Label>
                  <Select defaultValue="sealevel">
                    <SelectTrigger className="h-8 text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="sealevel">Sea Level (29.92 inHg)</SelectItem>
                      <SelectItem value="altitude">5000 ft (24.9 inHg)</SelectItem>
                      <SelectItem value="hot">Hot Day (95°F)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}

            {/* Info Box */}
            <Alert className="bg-purple-500/5 border-purple-500/30">
              <Zap className="h-4 w-4 text-purple-500" />
              <AlertDescription className="text-sm">
                <strong>How it works:</strong> The Virtual ECU calculates fuel delivery based on its VE
                table. When the table is wrong, the resulting AFR will have errors that need tuning
                corrections. This is exactly what happens in real engines!
              </AlertDescription>
            </Alert>
          </>
        )}
      </CardContent>
    </Card>
  );
}

