import { useState } from 'react';
import { VEHeatmap } from '@/components/results/VEHeatmap';
import { VEHeatmapLegend } from '@/components/results/VEHeatmapLegend';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';

// Sample VE delta data with a mix of positive, negative, clamped and near-zero values
const sampleData: number[][] = [
  [-2.5, -1.8, -0.3, 0.5, 1.2, 2.8, 4.5, 6.2, 8.1, 10.5],
  [-3.2, -2.1, -0.8, 0.2, 0.8, 2.1, 3.8, 5.5, 7.8, 9.2],
  [-4.1, -2.8, -1.5, -0.3, 0.5, 1.5, 3.0, 4.8, 6.5, 8.0],
  [-5.2, -3.5, -2.0, -0.8, 0.1, 1.0, 2.5, 4.0, 5.5, 7.0],
  [-6.5, -4.2, -2.5, -1.2, -0.2, 0.8, 2.0, 3.5, 5.0, 6.5],
  [-8.0, -5.5, -3.2, -1.8, -0.5, 0.5, 1.5, 3.0, 4.5, 6.0],
  [-10.2, -7.0, -4.5, -2.5, -1.0, 0.2, 1.2, 2.5, 4.0, 5.5],
  [-12.5, -8.5, -5.5, -3.2, -1.5, -0.2, 0.8, 2.0, 3.5, 5.0],
  [-14.0, -10.0, -6.5, -4.0, -2.0, -0.5, 0.5, 1.5, 3.0, 4.5],
  [-15.0, -11.5, -8.0, -5.0, -2.8, -1.0, 0.2, 1.0, 2.5, 4.0],
];

const rpmLabels = ['1000', '1500', '2000', '2500', '3000', '3500', '4000', '4500', '5000', '5500'];
const tpsLabels = ['0', '10', '20', '30', '40', '50', '60', '70', '80', '100'];

export default function VEHeatmapDemo() {
  const [showValues, setShowValues] = useState(true);
  const [showClampIndicators, setShowClampIndicators] = useState(true);
  const [clampLimit, setClampLimit] = useState(7);
  const [selectedCell, setSelectedCell] = useState<{ row: number; col: number } | null>(null);

  const handleCellClick = (row: number, col: number, value: number) => {
    setSelectedCell({ row, col });
    console.log(`Clicked: RPM=${rpmLabels[row]}, Load=${tpsLabels[col]}, Value=${value}`);
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8 p-8">
      <div>
        <h1 className="text-3xl font-bold mb-2">VE Heatmap Component Demo</h1>
        <p className="text-muted-foreground">
          Visualization of VE (Volumetric Efficiency) delta corrections with color-coded cells.
        </p>
      </div>

      {/* Controls */}
      <Card>
        <CardHeader>
          <CardTitle>Controls</CardTitle>
          <CardDescription>Adjust the heatmap display options</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-6">
            <div className="flex items-center space-x-2">
              <Switch 
                id="show-values" 
                checked={showValues} 
                onCheckedChange={setShowValues}
              />
              <Label htmlFor="show-values">Show Values</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Switch 
                id="show-clamp" 
                checked={showClampIndicators} 
                onCheckedChange={setShowClampIndicators}
              />
              <Label htmlFor="show-clamp">Show Clamp Indicators</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Label htmlFor="clamp-limit">Clamp Limit: ±{clampLimit}%</Label>
              <input
                type="range"
                id="clamp-limit"
                min="3"
                max="15"
                value={clampLimit}
                onChange={(e) => setClampLimit(parseInt(e.target.value, 10))}
                className="w-24"
              />
            </div>
          </div>
          {selectedCell && (
            <div className="text-sm p-3 bg-muted rounded-md">
              <strong>Selected Cell:</strong> RPM {rpmLabels[selectedCell.row]}, 
              Load {tpsLabels[selectedCell.col]}, 
              Value: {sampleData[selectedCell.row][selectedCell.col].toFixed(2)}%
            </div>
          )}
        </CardContent>
      </Card>

      {/* Legend */}
      <Card>
        <CardHeader>
          <CardTitle>Legend</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center">
          <VEHeatmapLegend 
            clampLimit={clampLimit} 
            showClampIndicator={showClampIndicators} 
            orientation="horizontal" 
          />
        </CardContent>
      </Card>

      {/* Main Heatmap */}
      <VEHeatmap
        data={sampleData}
        rowLabels={rpmLabels}
        colLabels={tpsLabels}
        clampLimit={clampLimit}
        showClampIndicators={showClampIndicators}
        showValues={showValues}
        onCellClick={handleCellClick}
        highlightCell={selectedCell ?? undefined}
        title="VE Delta Corrections"
      />

      {/* Vertical Legend Example */}
      <Card>
        <CardHeader>
          <CardTitle>Vertical Legend</CardTitle>
        </CardHeader>
        <CardContent>
          <VEHeatmapLegend 
            clampLimit={clampLimit} 
            showClampIndicator={showClampIndicators} 
            orientation="vertical" 
          />
        </CardContent>
      </Card>

      {/* Example Usage */}
      <Card>
        <CardHeader>
          <CardTitle>Example Usage</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="bg-muted p-4 rounded-md overflow-x-auto text-sm">
{`import { VEHeatmap } from '@/components/results/VEHeatmap';
import { VEHeatmapLegend } from '@/components/results/VEHeatmapLegend';

function ResultsView({ veData }) {
  return (
    <div className="space-y-4">
      <VEHeatmapLegend clampLimit={7} />
      <VEHeatmap
        data={veData.delta}
        rowLabels={veData.rpmLabels}
        colLabels={veData.tpsLabels}
        clampLimit={7}
        showClampIndicators={true}
        title="VE Delta Corrections"
      />
    </div>
  );
}`}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}
