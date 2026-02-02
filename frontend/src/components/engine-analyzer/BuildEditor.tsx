/**
 * BuildEditor - Engine Build Configuration Editor
 *
 * Allows users to:
 * - Select components from the library to create a custom build
 * - View compatibility warnings
 * - Calculate derived values (displacement, compression)
 * - Save builds for use in tuning
 * - Get performance predictions
 */

import { useState, useCallback, useMemo } from 'react';
import {
  Wrench,
  AlertTriangle,
  CheckCircle,
  Calculator,
  Zap,
  Save,
  Trash2,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Alert, AlertDescription } from '../ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';

// Types matching backend schemas
interface HeadSpec {
  name: string;
  intake_valve_dia: number;
  exhaust_valve_dia: number;
  intake_port_cc?: number;
  chamber_cc?: number;
  peak_intake_cfm: number;
}

interface CamSpec {
  name: string;
  intake_duration_050: number;
  exhaust_duration_050: number;
  intake_lift: number;
  exhaust_lift: number;
  lobe_separation: number;
  overlap: number;
}

interface IntakeSpec {
  name: string;
  throttle_body_cfm?: number;
  runner_length_in?: number;
}

interface ShortBlockSpec {
  name: string;
  bore: number;
  stroke: number;
  rod_length: number;
  cylinders: number;
  compression_ratio?: number;
  displacement_ci: number;
}

interface EngineBuild {
  name: string;
  shortBlock?: ShortBlockSpec;
  heads?: HeadSpec;
  cam?: CamSpec;
  intake?: IntakeSpec;
}

interface PredictionResult {
  build_name: string;
  displacement_ci: number;
  peak_hp?: number;
  peak_hp_rpm?: number;
  peak_tq?: number;
  peak_tq_rpm?: number;
  prediction_notes: string[];
  confidence_level?: string;
}

interface BuildEditorProps {
  initialBuild?: EngineBuild;
  availableShortBlocks?: ShortBlockSpec[];
  availableHeads?: HeadSpec[];
  availableCams?: CamSpec[];
  availableIntakes?: IntakeSpec[];
  onSave?: (build: EngineBuild) => void;
  onPredict?: (build: EngineBuild) => void;
}

export function BuildEditor({
  initialBuild,
  availableShortBlocks = [],
  availableHeads = [],
  availableCams = [],
  availableIntakes = [],
  onSave,
  onPredict,
}: BuildEditorProps) {
  const [build, setBuild] = useState<EngineBuild>(
    initialBuild || { name: 'Custom Build' }
  );
  const [prediction, setPrediction] = useState<PredictionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Compatibility warnings
  const warnings = useMemo(() => {
    const w: string[] = [];

    if (build.shortBlock && build.heads) {
      // Check valve size vs bore
      const boreRatio = build.heads.intake_valve_dia / build.shortBlock.bore;
      if (boreRatio > 0.55) {
        w.push(`Large intake valve (${(boreRatio * 100).toFixed(0)}% of bore) - verify clearance`);
      }
    }

    if (build.cam && build.heads) {
      // Check lift vs valve size (rule of thumb: max lift ~0.25 × valve dia)
      const maxSafeLift = build.heads.intake_valve_dia * 0.28;
      if (build.cam.intake_lift > maxSafeLift) {
        w.push(`High lift cam (${build.cam.intake_lift}") may need spring upgrade`);
      }
    }

    if (build.cam) {
      // High overlap warning
      if (build.cam.overlap > 70) {
        w.push('High cam overlap - may need higher idle RPM and vacuum issues');
      }
    }

    return w;
  }, [build]);

  // Calculate displacement
  const displacement = useMemo(() => {
    if (!build.shortBlock) return null;
    const { bore, stroke, cylinders } = build.shortBlock;
    const ci = (Math.PI / 4) * (bore ** 2) * stroke * cylinders;
    return {
      ci: ci.toFixed(0),
      cc: (ci * 16.387).toFixed(0),
      liters: (ci * 16.387 / 1000).toFixed(1),
    };
  }, [build.shortBlock]);

  // Check if build is complete
  const isComplete = useMemo(() => {
    return !!(build.shortBlock && build.heads && build.cam);
  }, [build]);

  // Handle component selection
  const handleShortBlockChange = useCallback((name: string) => {
    const selected = availableShortBlocks.find((b) => b.name === name);
    setBuild((prev) => ({ ...prev, shortBlock: selected }));
    setPrediction(null);
  }, [availableShortBlocks]);

  const handleHeadsChange = useCallback((name: string) => {
    const selected = availableHeads.find((h) => h.name === name);
    setBuild((prev) => ({ ...prev, heads: selected }));
    setPrediction(null);
  }, [availableHeads]);

  const handleCamChange = useCallback((name: string) => {
    const selected = availableCams.find((c) => c.name === name);
    setBuild((prev) => ({ ...prev, cam: selected }));
    setPrediction(null);
  }, [availableCams]);

  const handleIntakeChange = useCallback((name: string) => {
    const selected = availableIntakes.find((i) => i.name === name);
    setBuild((prev) => ({ ...prev, intake: selected }));
    setPrediction(null);
  }, [availableIntakes]);

  // Get prediction from API
  const handleGetPrediction = useCallback(async () => {
    if (!isComplete) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/ea/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          build: {
            name: build.name,
            short_block: build.shortBlock,
            heads: build.heads,
            cam: build.cam,
            intake: build.intake,
          },
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get prediction');
      }

      const data = await response.json();
      setPrediction(data);

      if (onPredict) {
        onPredict(build);
      }
    } catch (err) {
      setError('Failed to generate prediction');
      console.error('Prediction error:', err);
    } finally {
      setLoading(false);
    }
  }, [build, isComplete, onPredict]);

  // Save build
  const handleSave = useCallback(() => {
    if (onSave) {
      onSave(build);
    }
  }, [build, onSave]);

  // Clear build
  const handleClear = useCallback(() => {
    setBuild({ name: 'Custom Build' });
    setPrediction(null);
  }, []);

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Wrench className="h-5 w-5" />
              Engine Build Editor
            </CardTitle>
            <CardDescription>
              Select components to create a custom engine build
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleClear}>
              <Trash2 className="h-4 w-4 mr-1" />
              Clear
            </Button>
            {onSave && (
              <Button variant="outline" size="sm" onClick={handleSave} disabled={!isComplete}>
                <Save className="h-4 w-4 mr-1" />
                Save
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Build Name */}
        <div className="space-y-2">
          <Label>Build Name</Label>
          <Input
            value={build.name}
            onChange={(e) => setBuild((prev) => ({ ...prev, name: e.target.value }))}
            placeholder="Enter build name..."
          />
        </div>

        {/* Component Selection */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Short Block */}
          <div className="space-y-2">
            <Label>Short Block</Label>
            <Select
              value={build.shortBlock?.name || ''}
              onValueChange={handleShortBlockChange}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select short block..." />
              </SelectTrigger>
              <SelectContent>
                {availableShortBlocks.map((block) => (
                  <SelectItem key={block.name} value={block.name}>
                    {block.name} ({block.displacement_ci.toFixed(0)}ci)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {build.shortBlock && (
              <div className="text-sm text-muted-foreground">
                {build.shortBlock.bore}" × {build.shortBlock.stroke}" • {build.shortBlock.cylinders} cyl
              </div>
            )}
          </div>

          {/* Heads */}
          <div className="space-y-2">
            <Label>Cylinder Heads</Label>
            <Select
              value={build.heads?.name || ''}
              onValueChange={handleHeadsChange}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select heads..." />
              </SelectTrigger>
              <SelectContent>
                {availableHeads.map((head) => (
                  <SelectItem key={head.name} value={head.name}>
                    {head.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {build.heads && (
              <div className="text-sm text-muted-foreground">
                {build.heads.intake_valve_dia}/{build.heads.exhaust_valve_dia}" valves
                {build.heads.peak_intake_cfm > 0 && ` • ${build.heads.peak_intake_cfm.toFixed(0)} CFM`}
              </div>
            )}
          </div>

          {/* Cam */}
          <div className="space-y-2">
            <Label>Camshaft</Label>
            <Select
              value={build.cam?.name || ''}
              onValueChange={handleCamChange}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select cam..." />
              </SelectTrigger>
              <SelectContent>
                {availableCams.map((cam) => (
                  <SelectItem key={cam.name} value={cam.name}>
                    {cam.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {build.cam && (
              <div className="text-sm text-muted-foreground">
                {build.cam.intake_duration_050}/{build.cam.exhaust_duration_050} @ {build.cam.lobe_separation} LSA
              </div>
            )}
          </div>

          {/* Intake */}
          <div className="space-y-2">
            <Label>Intake Manifold (Optional)</Label>
            <Select
              value={build.intake?.name || ''}
              onValueChange={handleIntakeChange}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select intake..." />
              </SelectTrigger>
              <SelectContent>
                {availableIntakes.map((intake) => (
                  <SelectItem key={intake.name} value={intake.name}>
                    {intake.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {build.intake && (
              <div className="text-sm text-muted-foreground">
                {build.intake.throttle_body_cfm && `${build.intake.throttle_body_cfm} CFM TB`}
              </div>
            )}
          </div>
        </div>

        {/* Calculated Values */}
        {displacement && (
          <div className="flex items-center gap-4 p-3 bg-muted rounded-lg">
            <Calculator className="h-5 w-5 text-muted-foreground" />
            <div className="flex-1">
              <div className="font-medium">Calculated Displacement</div>
              <div className="text-sm text-muted-foreground">
                {displacement.ci}ci / {displacement.cc}cc / {displacement.liters}L
              </div>
            </div>
          </div>
        )}

        {/* Warnings */}
        {warnings.length > 0 && (
          <div className="space-y-2">
            {warnings.map((warning, idx) => (
              <Alert key={idx} variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>{warning}</AlertDescription>
              </Alert>
            ))}
          </div>
        )}

        {/* Build Status */}
        <div className="flex items-center gap-2">
          {isComplete ? (
            <Badge variant="default" className="flex items-center gap-1">
              <CheckCircle className="h-3 w-3" />
              Build Complete
            </Badge>
          ) : (
            <Badge variant="secondary">
              Select short block, heads, and cam to complete build
            </Badge>
          )}
        </div>

        {/* Prediction Button */}
        <div className="flex justify-end">
          <Button
            onClick={handleGetPrediction}
            disabled={!isComplete || loading}
          >
            <Zap className="h-4 w-4 mr-2" />
            {loading ? 'Calculating...' : 'Get Prediction'}
          </Button>
        </div>

        {/* Error */}
        {error && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Prediction Results */}
        {prediction && (
          <div className="border rounded-lg p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">Performance Prediction</h3>
              {prediction.confidence_level && (
                <Badge variant={prediction.confidence_level === 'high' ? 'default' : 'secondary'}>
                  {prediction.confidence_level} confidence
                </Badge>
              )}
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {prediction.peak_hp && (
                <div className="text-center p-3 bg-muted rounded-lg">
                  <div className="text-2xl font-bold">{prediction.peak_hp.toFixed(0)}</div>
                  <div className="text-sm text-muted-foreground">
                    HP @ {prediction.peak_hp_rpm} RPM
                  </div>
                </div>
              )}
              {prediction.peak_tq && (
                <div className="text-center p-3 bg-muted rounded-lg">
                  <div className="text-2xl font-bold">{prediction.peak_tq.toFixed(0)}</div>
                  <div className="text-sm text-muted-foreground">
                    TQ @ {prediction.peak_tq_rpm} RPM
                  </div>
                </div>
              )}
            </div>

            {prediction.prediction_notes.length > 0 && (
              <div className="text-sm text-muted-foreground">
                <div className="font-medium mb-1">Notes:</div>
                <ul className="list-disc list-inside space-y-1">
                  {prediction.prediction_notes.map((note, idx) => (
                    <li key={idx}>{note}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default BuildEditor;
