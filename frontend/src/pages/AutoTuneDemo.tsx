import { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import { VE3DSurface } from '@/components/autotune/VE3DSurface';
import {
  Play,
  Pause,
  RotateCcw,
  ChevronRight,
  ChevronLeft,
  Zap,
  Target,
  Waves,
  Shield,
  Layers,
  Gauge,
  Flame,
  BarChart3,
  Settings2,
  Sparkles,
  Info,
  Eye,
  Box,
  Grid3X3,
  ArrowRight,
  CheckCircle2,
  CircleDot,
} from 'lucide-react';

// =============================================================================
// Types
// =============================================================================

interface CellData {
  value: number;
  gradient?: number;
  adaptivePasses?: number;
  blendFactor?: number;
}

type Grid = CellData[][];

// =============================================================================
// Demo Data Generator
// =============================================================================

const generateDemoGrid = (): Grid => {
  // Create a realistic VE table shape like HP Tuners/EFI Live shows:
  // - Smooth "bowl" rising from idle to WOT
  // - Values represent VE% (scaled for visualization)
  // - Low at idle (low RPM, low MAP), high at WOT (high RPM, high MAP)
  // - Then add subtle measurement artifacts that smoothing will clean up
  
  const rows = 12; // RPM axis (800 to 6500 RPM)
  const cols = 11; // MAP axis (20 to 100 kPa)
  
  const baseGrid: number[][] = [];
  
  for (let r = 0; r < rows; r++) {
    const row: number[] = [];
    for (let c = 0; c < cols; c++) {
      // Normalized position 0-1
      const rpmNorm = r / (rows - 1);  // 0 = idle, 1 = redline
      const mapNorm = c / (cols - 1);  // 0 = vacuum, 1 = WOT
      
      // Base VE shape - classic "bowl" that rises with RPM and load
      // Idle: ~50%, WOT at redline: ~95%
      const baseVE = 48 + 
        (mapNorm * 35) +           // Load contribution (vacuum to WOT)
        (rpmNorm * 12) +           // RPM contribution
        (rpmNorm * mapNorm * 8) -  // Synergy at high RPM/high load
        (Math.pow(rpmNorm - 0.7, 2) * 8); // Slight dip past peak torque
      
      row.push(baseVE);
    }
    baseGrid.push(row);
  }
  
  // Add realistic imperfections that AFR analysis would reveal:
  // - Lean spots (positive corrections needed)
  // - Rich spots (negative corrections needed)
  // - Some measurement noise
  const noisyGrid = baseGrid.map((row, r) =>
    row.map((value, c) => {
      let veValue = value;
      
      // Common lean spot at mid-RPM, mid-to-high load (cruise to part throttle)
      if (r >= 4 && r <= 7 && c >= 5 && c <= 8) {
        veValue -= 4 + Math.sin(r * 0.8) * 2; // Needs more fuel here
      }
      
      // Slight rich spot at idle/low load (cold start enrichment remnant)
      if (r <= 2 && c <= 3) {
        veValue += 3 + Math.cos(c * 0.5);
      }
      
      // High RPM lean spot (common at WOT near redline)
      if (r >= 9 && c >= 7) {
        veValue -= 2.5;
      }
      
      // Add subtle cell-to-cell noise (sensor/measurement variation)
      const noise = Math.sin(r * 2.3 + c * 1.7) * 1.2 + 
                   Math.cos(r * 1.1 - c * 2.1) * 0.8;
      veValue += noise;
      
      // Add a few random "bad cells" that look like sensor glitches
      if ((r === 3 && c === 6) || (r === 8 && c === 4)) {
        veValue -= 5; // Sharp lean spike (needs significant correction)
      }
      if ((r === 5 && c === 2) || (r === 10 && c === 7)) {
        veValue += 4; // Sharp rich spike
      }
      
      return {
        value: veValue,
        gradient: 0,
        adaptivePasses: 2,
        blendFactor: 0,
      };
    })
  );

  return noisyGrid;
};

// =============================================================================
// Kernel Smoothing Implementation
// =============================================================================

const calculateGradients = (grid: Grid): Grid => {
  const rows = grid.length;
  const cols = grid[0].length;
  const result: Grid = grid.map(row => row.map(cell => ({ ...cell })));

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const centerVal = grid[r][c].value;
      let maxDiff = 0;
      const neighbors: number[] = [];

      if (r > 0) neighbors.push(grid[r - 1][c].value);
      if (r < rows - 1) neighbors.push(grid[r + 1][c].value);
      if (c > 0) neighbors.push(grid[r][c - 1].value);
      if (c < cols - 1) neighbors.push(grid[r][c + 1].value);

      for (const n of neighbors) {
        maxDiff = Math.max(maxDiff, Math.abs(centerVal - n));
      }

      result[r][c].gradient = maxDiff;
    }
  }

  return result;
};

const applyAdaptiveSmoothing = (grid: Grid, passes: number = 2): Grid => {
  const rows = grid.length;
  const cols = grid[0].length;
  let result: Grid = grid.map(row => row.map(cell => ({ ...cell })));

  // Calculate local variance to identify noise vs real features
  const getLocalVariance = (g: Grid, r: number, c: number): number => {
    const neighbors: number[] = [g[r][c].value];
    if (r > 0) neighbors.push(g[r - 1][c].value);
    if (r < rows - 1) neighbors.push(g[r + 1][c].value);
    if (c > 0) neighbors.push(g[r][c - 1].value);
    if (c < cols - 1) neighbors.push(g[r][c + 1].value);
    
    const mean = neighbors.reduce((a, b) => a + b, 0) / neighbors.length;
    const variance = neighbors.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / neighbors.length;
    return Math.sqrt(variance);
  };

  // Run smoothing passes
  for (let pass = 0; pass < passes; pass++) {
    const passResult: Grid = result.map(row => row.map(cell => ({ ...cell })));
    
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const centerVal = result[r][c].value;
        const localVar = getLocalVariance(result, r, c);
        
        // High local variance = noise spike, needs more smoothing
        // Low local variance = smooth region, preserve
        let smoothingWeight: number;
        if (localVar > 3.0) {
          smoothingWeight = 0.65; // High variance: aggressive smoothing
        } else if (localVar < 1.0) {
          smoothingWeight = 0.15; // Low variance: minimal smoothing
        } else {
          smoothingWeight = 0.15 + (localVar - 1.0) / 2.0 * 0.5;
        }

        passResult[r][c].adaptivePasses = Math.round(smoothingWeight * 10);

        // Gather weighted neighbors
        const neighbors: { value: number; weight: number }[] = [{ value: centerVal, weight: 1.2 }];

        // Cardinal neighbors
        if (r > 0) neighbors.push({ value: result[r - 1][c].value, weight: 1.0 });
        if (r < rows - 1) neighbors.push({ value: result[r + 1][c].value, weight: 1.0 });
        if (c > 0) neighbors.push({ value: result[r][c - 1].value, weight: 1.0 });
        if (c < cols - 1) neighbors.push({ value: result[r][c + 1].value, weight: 1.0 });

        // Diagonal neighbors
        if (r > 0 && c > 0) neighbors.push({ value: result[r - 1][c - 1].value, weight: 0.6 });
        if (r > 0 && c < cols - 1) neighbors.push({ value: result[r - 1][c + 1].value, weight: 0.6 });
        if (r < rows - 1 && c > 0) neighbors.push({ value: result[r + 1][c - 1].value, weight: 0.6 });
        if (r < rows - 1 && c < cols - 1) neighbors.push({ value: result[r + 1][c + 1].value, weight: 0.6 });

        const weightedSum = neighbors.reduce((sum, n) => sum + n.value * n.weight, 0);
        const totalWeight = neighbors.reduce((sum, n) => sum + n.weight, 0);
        const smoothedVal = weightedSum / totalWeight;

        passResult[r][c].value = centerVal * (1 - smoothingWeight) + smoothedVal * smoothingWeight;
      }
    }
    result = passResult;
  }

  return result;
};

const applyGradientBlending = (
  originalGrid: Grid,
  smoothedGrid: Grid,
  gradientThreshold: number = 2.5
): Grid => {
  const rows = smoothedGrid.length;
  const cols = smoothedGrid[0].length;
  const result: Grid = smoothedGrid.map(row => row.map(cell => ({ ...cell })));

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const originalVal = originalGrid[r][c].value;
      const smoothedVal = smoothedGrid[r][c].value;
      const gradientMagnitude = originalGrid[r][c].gradient || 0;

      // Restore sharp edges where gradients are high (preserves important transitions)
      if (gradientMagnitude > gradientThreshold) {
        // Higher threshold means only the sharpest edges get protected
        const blendFactor = Math.min(0.85, (gradientMagnitude - gradientThreshold) / (gradientThreshold * 1.5));
        result[r][c].value = (1 - blendFactor) * smoothedVal + blendFactor * originalVal;
        result[r][c].blendFactor = blendFactor;
      } else {
        result[r][c].blendFactor = 0;
      }
    }
  }

  return result;
};

const applyCoverageWeightedSmoothing = (grid: Grid): Grid => {
  const rows = grid.length;
  const cols = grid[0].length;
  let result: Grid = grid.map(row => row.map(cell => ({ ...cell })));

  // Two passes of gentle refinement for a polished final surface
  for (let pass = 0; pass < 2; pass++) {
    const passResult: Grid = result.map(row => row.map(cell => ({ ...cell })));
    const alpha = pass === 0 ? 0.35 : 0.25; // First pass stronger, second gentler
    const centerBias = 1.4;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const centerVal = result[r][c].value;
        const neighborValues: number[] = [centerVal];
        const neighborWeights: number[] = [centerBias];

        // Cardinal neighbors
        const cardinalNeighbors = [
          { row: r - 1, col: c },
          { row: r + 1, col: c },
          { row: r, col: c - 1 },
          { row: r, col: c + 1 },
        ];

        for (const { row: nr, col: nc } of cardinalNeighbors) {
          if (nr >= 0 && nr < rows && nc >= 0 && nc < cols) {
            neighborValues.push(result[nr][nc].value);
            neighborWeights.push(1.0);
          }
        }

        // Diagonal neighbors (lower weight for subtle refinement)
        const diagonalNeighbors = [
          { row: r - 1, col: c - 1 },
          { row: r - 1, col: c + 1 },
          { row: r + 1, col: c - 1 },
          { row: r + 1, col: c + 1 },
        ];

        for (const { row: nr, col: nc } of diagonalNeighbors) {
          if (nr >= 0 && nr < rows && nc >= 0 && nc < cols) {
            neighborValues.push(result[nr][nc].value);
            neighborWeights.push(0.4);
          }
        }

        const weightedSum = neighborValues.reduce(
          (sum, v, i) => sum + v * neighborWeights[i],
          0
        );
        const totalWeight = neighborWeights.reduce((sum, w) => sum + w, 0);
        const smoothedVal = weightedSum / totalWeight;

        passResult[r][c].value = alpha * smoothedVal + (1 - alpha) * centerVal;
      }
    }
    result = passResult;
  }

  return result;
};

// Helper to extract just values from grid
const extractValues = (grid: Grid): number[][] => {
  return grid.map(row => row.map(cell => cell.value));
};

// =============================================================================
// Stage Info
// =============================================================================

const STAGES = [
  {
    id: 0,
    title: 'Raw VE Table',
    subtitle: 'Initial table with measurement artifacts',
    description: 'VE table after AFR-based corrections. Notice the overall "bowl" shape rising from idle (~50%) to WOT (~90%). Several cells have noise from sensor variation and a few outlier readings that need cleaning up.',
    icon: Layers,
    color: 'zinc',
    tip: 'Look for the bumps and dips - those are measurement noise that will be smoothed.',
  },
  {
    id: 1,
    title: 'Gradient Detection',
    subtitle: 'Finding transition zones',
    description: 'Calculate cell-to-cell differences across the table. High gradients identify important boundaries like the transition from idle to cruise, or part-throttle to WOT.',
    icon: Target,
    color: 'amber',
    tip: 'The steep slopes of the VE curve are detected and will be protected.',
  },
  {
    id: 2,
    title: 'Adaptive Smoothing',
    subtitle: 'Variance-based filtering',
    description: 'Areas with high local variance (noise spikes) get aggressive smoothing. Smooth regions are preserved. Watch the random bumps flatten out while the overall shape stays intact.',
    icon: Waves,
    color: 'emerald',
    tip: 'The noisy cells smooth out - the surface becomes cleaner like a professionally tuned table.',
  },
  {
    id: 3,
    title: 'Gradient Blending',
    subtitle: 'Restoring transitions',
    description: 'In high-gradient zones, blend back toward original values. This prevents the smoothing from softening important VE transitions that the ECU needs for proper fueling.',
    icon: Shield,
    color: 'purple',
    tip: 'Transition zones between idle/cruise/WOT are sharpened back up.',
  },
  {
    id: 4,
    title: 'Final Refinement',
    subtitle: 'Table polish',
    description: 'Final weighted averaging pass to ensure smooth interpolation across the entire table. The result is a clean, professional VE table ready for the ECU with no noise artifacts.',
    icon: Sparkles,
    color: 'cyan',
    tip: 'Compare before/after - same overall shape, but much smoother cell-to-cell transitions!',
  },
];

// =============================================================================
// Components
// =============================================================================

const StageCard = ({
  stage,
  isActive,
  isComplete,
  onClick,
}: {
  stage: typeof STAGES[0];
  isActive: boolean;
  isComplete: boolean;
  onClick: () => void;
}) => {
  const Icon = stage.icon;
  const colorMap: Record<string, string> = {
    zinc: 'border-zinc-600 bg-zinc-800/50',
    amber: 'border-amber-500/50 bg-amber-500/10',
    emerald: 'border-emerald-500/50 bg-emerald-500/10',
    purple: 'border-purple-500/50 bg-purple-500/10',
    cyan: 'border-cyan-500/50 bg-cyan-500/10',
  };

  const activeColorMap: Record<string, string> = {
    zinc: 'border-zinc-400 bg-zinc-700/50 shadow-zinc-500/20',
    amber: 'border-amber-400 bg-amber-500/20 shadow-amber-500/30',
    emerald: 'border-emerald-400 bg-emerald-500/20 shadow-emerald-500/30',
    purple: 'border-purple-400 bg-purple-500/20 shadow-purple-500/30',
    cyan: 'border-cyan-400 bg-cyan-500/20 shadow-cyan-500/30',
  };

  const iconColorMap: Record<string, string> = {
    zinc: 'text-zinc-400',
    amber: 'text-amber-400',
    emerald: 'text-emerald-400',
    purple: 'text-purple-400',
    cyan: 'text-cyan-400',
  };

  return (
    <motion.button
      onClick={onClick}
      className={`relative p-4 rounded-xl border-2 transition-all duration-300 text-left w-full ${
        isActive
          ? `${activeColorMap[stage.color]} shadow-lg`
          : isComplete
          ? colorMap[stage.color]
          : 'border-zinc-800 bg-zinc-900/30'
      }`}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
    >
      <div className="flex items-start gap-3">
        <div
          className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
            isActive
              ? `bg-${stage.color}-500 text-black`
              : isComplete
              ? `bg-${stage.color}-500/30 ${iconColorMap[stage.color]}`
              : 'bg-zinc-800 text-zinc-500'
          }`}
          style={{
            backgroundColor: isActive
              ? stage.color === 'zinc' ? '#71717a' :
                stage.color === 'amber' ? '#f59e0b' :
                stage.color === 'emerald' ? '#10b981' :
                stage.color === 'purple' ? '#a855f7' :
                '#06b6d4'
              : undefined
          }}
        >
          <Icon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-zinc-500">
              {stage.id === 0 ? 'INPUT' : `STAGE ${stage.id}`}
            </span>
            {isComplete && !isActive && (
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            )}
            {isActive && (
              <CircleDot className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
            )}
          </div>
          <h4 className={`font-semibold truncate ${isActive ? 'text-white' : 'text-zinc-300'}`}>
            {stage.title}
          </h4>
          <p className="text-xs text-zinc-500 truncate">{stage.subtitle}</p>
        </div>
      </div>
    </motion.button>
  );
};

const ProcessFlow = ({ currentStage }: { currentStage: number }) => {
  return (
    <div className="flex items-center justify-center gap-1 py-4 overflow-x-auto">
      {STAGES.map((stage, i) => {
        const Icon = stage.icon;
        const isActive = currentStage === stage.id;
        const isComplete = currentStage > stage.id;

        return (
          <div key={stage.id} className="flex items-center">
            <motion.div
              className={`flex flex-col items-center gap-1 px-2 ${
                isActive ? 'scale-110' : ''
              }`}
              animate={{ scale: isActive ? 1.1 : 1 }}
            >
              <div
                className={`w-10 h-10 rounded-lg flex items-center justify-center transition-all ${
                  isActive
                    ? 'bg-amber-500 text-black shadow-lg shadow-amber-500/30'
                    : isComplete
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : 'bg-zinc-800 text-zinc-500'
                }`}
              >
                <Icon className="w-5 h-5" />
              </div>
              <span className={`text-[10px] font-medium ${
                isActive ? 'text-amber-400' : isComplete ? 'text-emerald-400' : 'text-zinc-600'
              }`}>
                {stage.id === 0 ? 'Input' : `S${stage.id}`}
              </span>
            </motion.div>
            {i < STAGES.length - 1 && (
              <ArrowRight className={`w-4 h-4 mx-1 ${
                currentStage > i ? 'text-emerald-500' : 'text-zinc-700'
              }`} />
            )}
          </div>
        );
      })}
    </div>
  );
};

const Legend3D = () => (
  <div className="flex flex-wrap items-center justify-center gap-6 text-xs">
    <div className="flex items-center gap-2">
      <div className="w-16 h-4 rounded bg-gradient-to-r from-green-600 via-yellow-500 via-orange-500 to-red-600 shadow-sm" />
      <span className="text-zinc-400">Low VE → High VE</span>
    </div>
  </div>
);

const AxisLabels = () => (
  <div className="flex items-center justify-center gap-6 text-xs mt-2">
    <div className="flex items-center gap-1.5">
      <div className="w-2 h-2 rounded-full bg-red-500" />
      <span className="text-zinc-400">X = MAP (kPa)</span>
    </div>
    <div className="flex items-center gap-1.5">
      <div className="w-2 h-2 rounded-full bg-green-500" />
      <span className="text-zinc-400">Y = VE %</span>
    </div>
    <div className="flex items-center gap-1.5">
      <div className="w-2 h-2 rounded-full bg-blue-500" />
      <span className="text-zinc-400">Z = Engine Speed (RPM)</span>
    </div>
  </div>
);

// =============================================================================
// Main Component
// =============================================================================

export default function AutoTuneDemo() {
  const [currentStage, setCurrentStage] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(2500);
  const [view3D, setView3D] = useState(true);
  const [showComparison, setShowComparison] = useState(true);

  const originalGrid = useMemo(() => generateDemoGrid(), []);

  // Calculate all stage grids
  const grids = useMemo(() => {
    const stage0 = originalGrid;
    const stage1 = calculateGradients(stage0);
    const stage2 = applyAdaptiveSmoothing(stage1, 2);
    const stage3 = applyGradientBlending(stage1, stage2, 1.0);
    const stage4 = applyCoverageWeightedSmoothing(stage3);
    return [stage0, stage1, stage2, stage3, stage4];
  }, [originalGrid]);

  const currentGrid = grids[currentStage];
  const currentStageInfo = STAGES[currentStage];

  // Auto-play
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      setCurrentStage(prev => {
        if (prev >= 4) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, speed);

    return () => clearInterval(interval);
  }, [isPlaying, speed]);

  const handlePlayPause = useCallback(() => {
    if (currentStage === 4) {
      setCurrentStage(0);
    }
    setIsPlaying(prev => !prev);
  }, [currentStage]);

  const handleReset = useCallback(() => {
    setCurrentStage(0);
    setIsPlaying(false);
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950 p-4 md:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <motion.div
          className="text-center space-y-3"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Badge className="bg-gradient-to-r from-amber-500 to-orange-500 text-black font-bold px-4 py-1">
            Interactive VE Table Demo
          </Badge>
          <h1 className="text-4xl md:text-5xl font-black bg-gradient-to-r from-amber-400 via-orange-400 to-rose-400 bg-clip-text text-transparent">
            VE Table Smoothing
          </h1>
          <p className="text-lg text-zinc-400 max-w-2xl mx-auto">
            Watch DynoAI clean up a noisy VE table - removing sensor artifacts 
            while preserving the essential fueling shape
          </p>
        </motion.div>

        {/* Process Flow */}
        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardContent className="pt-4">
            <ProcessFlow currentStage={currentStage} />
          </CardContent>
        </Card>

        {/* Main Content */}
        <div className="grid lg:grid-cols-4 gap-6">
          {/* Left Sidebar - Stage Selection */}
          <div className="lg:col-span-1 space-y-3">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-zinc-400">Processing Stages</h3>
              <Badge variant="outline" className="text-xs">
                {currentStage === 0 ? 'Input' : `${currentStage}/4`}
              </Badge>
            </div>
            {STAGES.map(stage => (
              <StageCard
                key={stage.id}
                stage={stage}
                isActive={currentStage === stage.id}
                isComplete={currentStage > stage.id}
                onClick={() => {
                  setCurrentStage(stage.id);
                  setIsPlaying(false);
                }}
              />
            ))}
          </div>

          {/* Main Visualization Area */}
          <div className="lg:col-span-3 space-y-4">
            {/* Controls */}
            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardContent className="p-4">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentStage(Math.max(0, currentStage - 1))}
                      disabled={currentStage === 0}
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </Button>
                    <Button
                      variant={isPlaying ? 'destructive' : 'default'}
                      size="sm"
                      onClick={handlePlayPause}
                      className="w-24"
                    >
                      {isPlaying ? (
                        <>
                          <Pause className="w-4 h-4 mr-1" />
                          Pause
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4 mr-1" />
                          Play
                        </>
                      )}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentStage(Math.min(4, currentStage + 1))}
                      disabled={currentStage === 4}
                    >
                      <ChevronRight className="w-4 h-4" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={handleReset}>
                      <RotateCcw className="w-4 h-4" />
                    </Button>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-zinc-500">Speed:</span>
                      <Slider
                        value={[speed]}
                        onValueChange={([v]) => setSpeed(v)}
                        min={1000}
                        max={5000}
                        step={500}
                        className="w-24"
                      />
                      <span className="text-xs text-zinc-400 w-10">{(speed / 1000).toFixed(1)}s</span>
                    </div>

                    <div className="flex items-center gap-2 border-l border-zinc-700 pl-4">
                      <Grid3X3 className={`w-4 h-4 ${!view3D ? 'text-amber-400' : 'text-zinc-500'}`} />
                      <Switch
                        checked={view3D}
                        onCheckedChange={setView3D}
                      />
                      <Box className={`w-4 h-4 ${view3D ? 'text-amber-400' : 'text-zinc-500'}`} />
                    </div>

                    <div className="flex items-center gap-2">
                      <Eye className="w-4 h-4 text-zinc-500" />
                      <Switch
                        checked={showComparison}
                        onCheckedChange={setShowComparison}
                      />
                      <span className="text-xs text-zinc-400">Compare</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* 3D Visualization */}
            <AnimatePresence mode="wait">
              <motion.div
                key={`${currentStage}-${view3D}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                {view3D ? (
                  <div className={`grid ${showComparison && currentStage > 0 ? 'md:grid-cols-2' : 'grid-cols-1'} gap-4`}>
                    {showComparison && currentStage > 0 && (
                      <Card className="bg-zinc-900/50 border-zinc-800">
                        <CardHeader className="pb-2">
                          <CardTitle className="text-sm flex items-center gap-2">
                            <Layers className="w-4 h-4 text-zinc-400" />
                            Original Input
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="p-2">
                          <div className="aspect-[4/3]">
                            <VE3DSurface
                              grid={extractValues(originalGrid)}
                              stage={0}
                              autoRotate={false}
                            />
                          </div>
                        </CardContent>
                      </Card>
                    )}
                    <Card className="bg-zinc-900/50 border-zinc-800">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm flex items-center gap-2">
                          {(() => {
                            const Icon = currentStageInfo.icon;
                            return <Icon className="w-4 h-4 text-amber-400" />;
                          })()}
                          {currentStage === 0 ? 'Raw VE Corrections' : `After Stage ${currentStage}: ${currentStageInfo.title}`}
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="p-2">
                        <div className="aspect-[4/3]">
                          <VE3DSurface
                            grid={extractValues(currentGrid)}
                            stage={currentStage}
                            highlightChanges={currentStage > 0}
                            originalGrid={extractValues(originalGrid)}
                            autoRotate={true}
                          />
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                ) : (
                  /* 2D Heatmap View */
                  <Card className="bg-zinc-900/50 border-zinc-800">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">
                        {currentStage === 0 ? 'Raw VE Corrections' : `After Stage ${currentStage}`}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="flex gap-4 justify-center">
                        {showComparison && currentStage > 0 && (
                          <div>
                            <p className="text-xs text-zinc-500 text-center mb-2">Original</p>
                            <HeatmapGrid grid={extractValues(originalGrid)} />
                          </div>
                        )}
                        <div>
                          <p className="text-xs text-zinc-500 text-center mb-2">
                            {currentStage === 0 ? 'Input' : 'Current'}
                          </p>
                          <HeatmapGrid grid={extractValues(currentGrid)} />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </motion.div>
            </AnimatePresence>

            {/* Legend */}
            <div className="space-y-2">
              <Legend3D />
              {view3D && <AxisLabels />}
              <p className="text-xs text-zinc-500 text-center">
                Drag to rotate • Scroll to zoom • Click stage cards to jump
              </p>
            </div>

            {/* Stage Details */}
            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  {(() => {
                    const Icon = currentStageInfo.icon;
                    return <Icon className="w-5 h-5 text-amber-400" />;
                  })()}
                  {currentStageInfo.title}
                </CardTitle>
                <CardDescription>{currentStageInfo.subtitle}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-zinc-300">{currentStageInfo.description}</p>
                <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
                  <Info className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-amber-200">{currentStageInfo.tip}</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center text-sm text-zinc-500 pt-4 border-t border-zinc-800">
          <p>DynoAI 4-Stage Kernel Smoothing • Deterministic • Reproducible</p>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// 2D Heatmap Component
// =============================================================================

const HeatmapGrid = ({ grid }: { grid: number[][] }) => {
  // Find min/max for normalization
  let min = Infinity, max = -Infinity;
  grid.forEach(row => row.forEach(v => { min = Math.min(min, v); max = Math.max(max, v); }));
  const range = max - min || 1;
  
  const getColor = (value: number) => {
    // HP Tuners style: green -> yellow -> orange -> red
    const t = (value - min) / range;
    
    if (t < 0.25) {
      const s = t / 0.25;
      return `hsl(${120 - s * 30}, 70%, ${35 + s * 10}%)`;
    } else if (t < 0.5) {
      const s = (t - 0.25) / 0.25;
      return `hsl(${90 - s * 40}, 80%, ${45 + s * 5}%)`;
    } else if (t < 0.75) {
      const s = (t - 0.5) / 0.25;
      return `hsl(${50 - s * 25}, 85%, ${50 - s * 5}%)`;
    } else {
      const s = (t - 0.75) / 0.25;
      return `hsl(${25 - s * 20}, 90%, ${45 + s * 5}%)`;
    }
  };

  return (
    <div className="inline-block">
      <div className="grid gap-0.5" style={{ gridTemplateColumns: `repeat(${grid[0].length}, 1fr)` }}>
        {grid.map((row, r) =>
          row.map((value, c) => (
            <div
              key={`${r}-${c}`}
              className="w-6 h-5 rounded-sm flex items-center justify-center text-[8px] font-mono text-white/95 shadow-sm"
              style={{ backgroundColor: getColor(value) }}
              title={`RPM row ${r + 1}, MAP col ${c + 1}: ${value.toFixed(1)}%`}
            >
              {value.toFixed(0)}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
