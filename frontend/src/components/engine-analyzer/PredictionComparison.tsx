/**
 * PredictionComparison - EA Prediction vs Actual Dyno Results
 *
 * Side-by-side comparison view:
 * - VE table comparison (predicted vs measured)
 * - Power/torque curve overlay
 * - Deviation highlighting for tuning focus areas
 */

import { useMemo } from 'react';
import {
  GitCompare,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Badge } from '../ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';

interface PowerCurvePoint {
  rpm: number;
  hp?: number;
  tq?: number;
}

interface PredictionResult {
  build_name: string;
  displacement_ci: number;
  compression_ratio?: number;
  rpm_bins: number[];
  map_bins: number[];
  ve_table_front: number[][];
  ve_table_rear?: number[][];
  power_curve: PowerCurvePoint[];
  torque_curve: PowerCurvePoint[];
  peak_hp?: number;
  peak_hp_rpm?: number;
  peak_tq?: number;
  peak_tq_rpm?: number;
  prediction_notes: string[];
  confidence_level?: string;
}

interface ActualResults {
  rpm_bins: number[];
  map_bins: number[];
  ve_table_front: number[][];
  ve_table_rear?: number[][];
  power_curve?: PowerCurvePoint[];
  torque_curve?: PowerCurvePoint[];
  peak_hp?: number;
  peak_hp_rpm?: number;
  peak_tq?: number;
  peak_tq_rpm?: number;
}

interface PredictionComparisonProps {
  prediction: PredictionResult;
  actual?: ActualResults;
}

export function PredictionComparison({
  prediction,
  actual,
}: PredictionComparisonProps) {
  // Calculate VE deviations
  const veDeviations = useMemo(() => {
    if (!actual?.ve_table_front) return null;

    const deviations: number[][] = [];
    const maxDeviation = { value: 0, rpm: 0, map: 0 };

    for (let i = 0; i < prediction.ve_table_front.length; i++) {
      const row: number[] = [];
      for (let j = 0; j < prediction.ve_table_front[i].length; j++) {
        const pred = prediction.ve_table_front[i]?.[j] || 0;
        const act = actual.ve_table_front[i]?.[j] || 0;
        const dev = act - pred;
        row.push(dev);

        if (Math.abs(dev) > Math.abs(maxDeviation.value)) {
          maxDeviation.value = dev;
          maxDeviation.rpm = prediction.rpm_bins[i];
          maxDeviation.map = prediction.map_bins[j];
        }
      }
      deviations.push(row);
    }

    return { deviations, maxDeviation };
  }, [prediction, actual]);

  // Calculate power comparison
  const powerComparison = useMemo(() => {
    if (!actual?.peak_hp || !prediction.peak_hp) return null;

    const hpDiff = actual.peak_hp - prediction.peak_hp;
    const hpPct = (hpDiff / prediction.peak_hp) * 100;

    const tqDiff = (actual.peak_tq || 0) - (prediction.peak_tq || 0);
    const tqPct = prediction.peak_tq ? (tqDiff / prediction.peak_tq) * 100 : 0;

    return {
      hpDiff,
      hpPct,
      tqDiff,
      tqPct,
      hpRpmDiff: (actual.peak_hp_rpm || 0) - (prediction.peak_hp_rpm || 0),
      tqRpmDiff: (actual.peak_tq_rpm || 0) - (prediction.peak_tq_rpm || 0),
    };
  }, [prediction, actual]);

  // Get cell color based on deviation
  const getCellColor = (deviation: number) => {
    const absD = Math.abs(deviation);
    if (absD < 2) return 'bg-green-500/20';
    if (absD < 5) return 'bg-yellow-500/20';
    if (absD < 10) return 'bg-orange-500/30';
    return 'bg-red-500/40';
  };

  // Get deviation icon
  const getDeviationIcon = (deviation: number) => {
    if (Math.abs(deviation) < 2) return <Minus className="h-3 w-3 text-muted-foreground" />;
    if (deviation > 0) return <TrendingUp className="h-3 w-3 text-green-500" />;
    return <TrendingDown className="h-3 w-3 text-red-500" />;
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <GitCompare className="h-5 w-5" />
              Prediction vs Actual
            </CardTitle>
            <CardDescription>
              Compare Engine Analyzer prediction with dyno results
            </CardDescription>
          </div>
          {prediction.confidence_level && (
            <Badge variant={prediction.confidence_level === 'high' ? 'default' : 'secondary'}>
              {prediction.confidence_level} confidence prediction
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent>
        <Tabs defaultValue="summary">
          <TabsList className="grid grid-cols-3 w-full">
            <TabsTrigger value="summary">Summary</TabsTrigger>
            <TabsTrigger value="ve">VE Table</TabsTrigger>
            <TabsTrigger value="power">Power Curves</TabsTrigger>
          </TabsList>

          {/* Summary Tab */}
          <TabsContent value="summary" className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Prediction Summary */}
              <div className="border rounded-lg p-4">
                <h3 className="font-medium mb-3 flex items-center gap-2">
                  <Badge variant="outline">Predicted</Badge>
                  {prediction.build_name}
                </h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Displacement:</span>
                    <span>{prediction.displacement_ci.toFixed(0)}ci</span>
                  </div>
                  {prediction.peak_hp && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Peak HP:</span>
                      <span>{prediction.peak_hp.toFixed(0)} @ {prediction.peak_hp_rpm} RPM</span>
                    </div>
                  )}
                  {prediction.peak_tq && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Peak TQ:</span>
                      <span>{prediction.peak_tq.toFixed(0)} @ {prediction.peak_tq_rpm} RPM</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Actual Summary */}
              <div className="border rounded-lg p-4">
                <h3 className="font-medium mb-3 flex items-center gap-2">
                  <Badge variant="default">Actual</Badge>
                  Dyno Results
                </h3>
                {actual ? (
                  <div className="space-y-2 text-sm">
                    {actual.peak_hp && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Peak HP:</span>
                        <span>{actual.peak_hp.toFixed(0)} @ {actual.peak_hp_rpm} RPM</span>
                      </div>
                    )}
                    {actual.peak_tq && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Peak TQ:</span>
                        <span>{actual.peak_tq.toFixed(0)} @ {actual.peak_tq_rpm} RPM</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-sm text-muted-foreground">
                    No dyno results available yet
                  </div>
                )}
              </div>
            </div>

            {/* Comparison Stats */}
            {powerComparison && (
              <div className="border rounded-lg p-4">
                <h3 className="font-medium mb-3">Comparison</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center p-3 bg-muted rounded-lg">
                    <div className="flex items-center justify-center gap-1">
                      {getDeviationIcon(powerComparison.hpDiff)}
                      <span className="text-xl font-bold">
                        {powerComparison.hpDiff > 0 ? '+' : ''}{powerComparison.hpDiff.toFixed(0)}
                      </span>
                    </div>
                    <div className="text-sm text-muted-foreground">HP Difference</div>
                    <div className="text-xs text-muted-foreground">
                      ({powerComparison.hpPct > 0 ? '+' : ''}{powerComparison.hpPct.toFixed(1)}%)
                    </div>
                  </div>
                  <div className="text-center p-3 bg-muted rounded-lg">
                    <div className="flex items-center justify-center gap-1">
                      {getDeviationIcon(powerComparison.tqDiff)}
                      <span className="text-xl font-bold">
                        {powerComparison.tqDiff > 0 ? '+' : ''}{powerComparison.tqDiff.toFixed(0)}
                      </span>
                    </div>
                    <div className="text-sm text-muted-foreground">TQ Difference</div>
                    <div className="text-xs text-muted-foreground">
                      ({powerComparison.tqPct > 0 ? '+' : ''}{powerComparison.tqPct.toFixed(1)}%)
                    </div>
                  </div>
                  <div className="text-center p-3 bg-muted rounded-lg">
                    <div className="text-xl font-bold">
                      {powerComparison.hpRpmDiff > 0 ? '+' : ''}{powerComparison.hpRpmDiff}
                    </div>
                    <div className="text-sm text-muted-foreground">HP Peak RPM Δ</div>
                  </div>
                  <div className="text-center p-3 bg-muted rounded-lg">
                    <div className="text-xl font-bold">
                      {powerComparison.tqRpmDiff > 0 ? '+' : ''}{powerComparison.tqRpmDiff}
                    </div>
                    <div className="text-sm text-muted-foreground">TQ Peak RPM Δ</div>
                  </div>
                </div>

                {/* Accuracy Assessment */}
                <div className="mt-4 flex items-center gap-2">
                  {Math.abs(powerComparison.hpPct) < 5 ? (
                    <>
                      <CheckCircle className="h-4 w-4 text-green-500" />
                      <span className="text-sm text-green-600">
                        Prediction within 5% - good accuracy
                      </span>
                    </>
                  ) : Math.abs(powerComparison.hpPct) < 10 ? (
                    <>
                      <AlertTriangle className="h-4 w-4 text-yellow-500" />
                      <span className="text-sm text-yellow-600">
                        Prediction within 10% - acceptable accuracy
                      </span>
                    </>
                  ) : (
                    <>
                      <AlertTriangle className="h-4 w-4 text-red-500" />
                      <span className="text-sm text-red-600">
                        Significant deviation - review component specs
                      </span>
                    </>
                  )}
                </div>
              </div>
            )}

            {/* Prediction Notes */}
            {prediction.prediction_notes.length > 0 && (
              <div className="border rounded-lg p-4">
                <h3 className="font-medium mb-2">Prediction Notes</h3>
                <ul className="text-sm text-muted-foreground space-y-1">
                  {prediction.prediction_notes.map((note, idx) => (
                    <li key={idx}>• {note}</li>
                  ))}
                </ul>
              </div>
            )}
          </TabsContent>

          {/* VE Table Tab */}
          <TabsContent value="ve" className="space-y-4">
            {veDeviations ? (
              <>
                <div className="flex items-center justify-between">
                  <h3 className="font-medium">VE Deviation Map (Actual - Predicted)</h3>
                  <div className="flex items-center gap-2 text-sm">
                    <span className="px-2 py-1 bg-green-500/20 rounded">±2%</span>
                    <span className="px-2 py-1 bg-yellow-500/20 rounded">±5%</span>
                    <span className="px-2 py-1 bg-orange-500/30 rounded">±10%</span>
                    <span className="px-2 py-1 bg-red-500/40 rounded">&gt;10%</span>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr>
                        <th className="p-2 text-left">RPM \ MAP</th>
                        {prediction.map_bins.map((map) => (
                          <th key={map} className="p-2 text-center">{map}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {veDeviations.deviations.map((row, i) => (
                        <tr key={i}>
                          <td className="p-2 font-medium">{prediction.rpm_bins[i]}</td>
                          {row.map((dev, j) => (
                            <td
                              key={j}
                              className={`p-2 text-center ${getCellColor(dev)}`}
                            >
                              {dev > 0 ? '+' : ''}{dev.toFixed(1)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Max Deviation Highlight */}
                <div className="flex items-center gap-2 p-3 bg-muted rounded-lg">
                  <AlertTriangle className="h-4 w-4 text-yellow-500" />
                  <span className="text-sm">
                    Maximum deviation: <strong>{veDeviations.maxDeviation.value.toFixed(1)}%</strong> at{' '}
                    {veDeviations.maxDeviation.rpm} RPM / {veDeviations.maxDeviation.map} kPa
                  </span>
                </div>
              </>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <p>No actual VE data available for comparison</p>
                <p className="text-sm mt-2">Run a dyno session to compare with prediction</p>
              </div>
            )}
          </TabsContent>

          {/* Power Curves Tab */}
          <TabsContent value="power" className="space-y-4">
            <div className="border rounded-lg p-4">
              <h3 className="font-medium mb-4">Power Curve Comparison</h3>

              {/* Simple bar chart representation */}
              <div className="space-y-4">
                <div>
                  <div className="text-sm text-muted-foreground mb-2">Horsepower</div>
                  <div className="h-32 flex items-end gap-1">
                    {prediction.power_curve.map((point, idx) => {
                      const actualPoint = actual?.power_curve?.find((p) => p.rpm === point.rpm);
                      const predHp = point.hp || 0;
                      const actHp = actualPoint?.hp || 0;
                      const maxHp = Math.max(prediction.peak_hp || 100, actual?.peak_hp || 100);

                      return (
                        <div key={idx} className="flex-1 flex flex-col items-center gap-1">
                          <div className="w-full flex gap-0.5 h-full items-end">
                            <div
                              className="flex-1 bg-primary/50 rounded-t"
                              style={{ height: `${(predHp / maxHp) * 100}%` }}
                              title={`Predicted: ${predHp.toFixed(0)} HP`}
                            />
                            {actualPoint && (
                              <div
                                className="flex-1 bg-green-500/70 rounded-t"
                                style={{ height: `${(actHp / maxHp) * 100}%` }}
                                title={`Actual: ${actHp.toFixed(0)} HP`}
                              />
                            )}
                          </div>
                          {idx % 4 === 0 && (
                            <span className="text-xs text-muted-foreground">
                              {(point.rpm / 1000).toFixed(1)}k
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="flex items-center justify-center gap-4 text-sm">
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-primary/50 rounded" />
                    <span>Predicted</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-green-500/70 rounded" />
                    <span>Actual</span>
                  </div>
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

export default PredictionComparison;
