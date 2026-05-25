/**
 * Operator Training Page - Virtual dyno operator training simulator
 * 
 * Features:
 * - Configurable dyno types (Inertia, Inertia+Load, Load Holding)
 * - Real-time throttle and load control
 * - RPM hold mode with PID control
 * - Safety scenario training
 * - Live gauges and alerts
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Gauge, Play, Square, RotateCcw, AlertTriangle, Flame,
  Thermometer, Activity, Target, Zap, Shield, Award,
  ChevronRight, Settings2, Info, Volume2, VolumeX
} from 'lucide-react';
import { toast } from '@/lib/toast';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5001';
const TRAINING_API = `${API_BASE}/api/training`;

// =============================================================================
// Types
// =============================================================================

interface TrainingState {
  rpm: number;
  throttle: number;
  load_target: number;
  current_load: number;
  brake_torque: number;
  engine_torque: number;
  horsepower: number;
  afr: number;
  afr_front: number;
  afr_rear: number;
  egt_front: number;
  egt_rear: number;
  oil_temp: number;
  coolant_temp: number;
  knock_level: number;
  map_kpa: number;
  rpm_hold_active: boolean;
  rpm_hold_target: number;
  dyno_type: string;
  alerts: Alert[];
  safety_score: number;
  active_scenario: string;
}

interface Alert {
  type: string;
  severity: 'warning' | 'critical';
  message: string;
  value: number;
}

interface Scenario {
  id: string;
  name: string;
  description: string;
  training_goal: string;
}

type DynoType = 'inertia' | 'inertia_load' | 'load_holding';

// =============================================================================
// Gauge Components
// =============================================================================

function SweepGauge({
  value,
  min = 0,
  max = 100,
  label,
  unit,
  size = 160,
  warningThreshold,
  criticalThreshold,
  decimals = 0
}: {
  value: number;
  min?: number;
  max?: number;
  label: string;
  unit: string;
  size?: number;
  warningThreshold?: number;
  criticalThreshold?: number;
  decimals?: number;
}) {
  const startAngle = -225;
  const endAngle = 45;
  const range = endAngle - startAngle;
  const percentage = Math.max(0, Math.min(1, (value - min) / (max - min)));
  const angle = startAngle + (percentage * range);

  const getColor = () => {
    if (criticalThreshold && value >= criticalThreshold) return '#ef4444';
    if (warningThreshold && value >= warningThreshold) return '#f59e0b';
    return '#22c55e';
  };

  const radius = size / 2 - 15;
  const centerX = size / 2;
  const centerY = size / 2;

  const createArc = (startDeg: number, endDeg: number, r: number) => {
    const start = (startDeg * Math.PI) / 180;
    const end = (endDeg * Math.PI) / 180;
    const x1 = centerX + r * Math.cos(start);
    const y1 = centerY + r * Math.sin(start);
    const x2 = centerX + r * Math.cos(end);
    const y2 = centerY + r * Math.sin(end);
    const largeArc = endDeg - startDeg > 180 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`;
  };

  const needleAngle = angle;
  const needleLength = radius - 20;
  const needleX = centerX + needleLength * Math.cos((needleAngle * Math.PI) / 180);
  const needleY = centerY + needleLength * Math.sin((needleAngle * Math.PI) / 180);

  const color = getColor();

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size * 0.7} viewBox={`0 0 ${size} ${size * 0.7}`}>
        {/* Background arc */}
        <path
          d={createArc(startAngle, endAngle, radius)}
          fill="none"
          stroke="#374151"
          strokeWidth="8"
          strokeLinecap="round"
        />

        {/* Warning zone */}
        {warningThreshold && (
          <path
            d={createArc(
              startAngle + ((warningThreshold - min) / (max - min)) * range,
              criticalThreshold
                ? startAngle + ((criticalThreshold - min) / (max - min)) * range
                : endAngle,
              radius
            )}
            fill="none"
            stroke="#f59e0b"
            strokeWidth="8"
            strokeLinecap="round"
            opacity="0.4"
          />
        )}

        {/* Critical zone */}
        {criticalThreshold && (
          <path
            d={createArc(
              startAngle + ((criticalThreshold - min) / (max - min)) * range,
              endAngle,
              radius
            )}
            fill="none"
            stroke="#ef4444"
            strokeWidth="8"
            strokeLinecap="round"
            opacity="0.4"
          />
        )}

        {/* Value arc */}
        <path
          d={createArc(startAngle, angle, radius - 1)}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
        />

        {/* Needle */}
        <line
          x1={centerX}
          y1={centerY}
          x2={needleX}
          y2={needleY}
          stroke={color}
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle cx={centerX} cy={centerY} r="8" fill={color} />
        <circle cx={centerX} cy={centerY} r="4" fill="#1f2937" />
      </svg>

      <div className="text-center -mt-2">
        <div className="text-2xl font-mono font-bold" style={{ color }}>
          {value.toFixed(decimals)}
        </div>
        <div className="text-xs text-zinc-400 uppercase tracking-wider">{label}</div>
        <div className="text-xs text-zinc-500">{unit}</div>
      </div>
    </div>
  );
}

function VerticalBar({
  value,
  min = 0,
  max = 100,
  label,
  unit,
  height = 120,
  warningThreshold,
  criticalThreshold,
  decimals = 0
}: {
  value: number;
  min?: number;
  max?: number;
  label: string;
  unit: string;
  height?: number;
  warningThreshold?: number;
  criticalThreshold?: number;
  decimals?: number;
}) {
  const percentage = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));

  const getColor = () => {
    if (criticalThreshold && value >= criticalThreshold) return '#ef4444';
    if (warningThreshold && value >= warningThreshold) return '#f59e0b';
    return '#22c55e';
  };

  const color = getColor();

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="text-xs text-zinc-400 uppercase tracking-wider">{label}</div>
      <div
        className="relative bg-zinc-800 rounded-full overflow-hidden"
        style={{ width: 24, height }}
      >
        <motion.div
          className="absolute bottom-0 left-0 right-0 rounded-full"
          initial={{ height: 0 }}
          animate={{ height: `${percentage}%` }}
          transition={{ duration: 0.15 }}
          style={{
            backgroundColor: color,
            boxShadow: `0 0 10px ${color}40`
          }}
        />
        {warningThreshold && (
          <div
            className="absolute left-0 right-0 h-0.5 bg-amber-500"
            style={{ bottom: `${((warningThreshold - min) / (max - min)) * 100}%` }}
          />
        )}
        {criticalThreshold && (
          <div
            className="absolute left-0 right-0 h-0.5 bg-red-500"
            style={{ bottom: `${((criticalThreshold - min) / (max - min)) * 100}%` }}
          />
        )}
      </div>
      <div className="text-center">
        <div className="text-sm font-mono font-bold" style={{ color }}>
          {value.toFixed(decimals)}
        </div>
        <div className="text-xs text-zinc-500">{unit}</div>
      </div>
    </div>
  );
}

function ControlSlider({
  value,
  onChange,
  label,
  disabled = false,
  color = '#22c55e'
}: {
  value: number;
  onChange: (value: number) => void;
  label: string;
  disabled?: boolean;
  color?: string;
}) {
  return (
    <div className={`w-full ${disabled ? 'opacity-50' : ''}`}>
      <div className="flex justify-between mb-2">
        <span className="text-sm text-zinc-400">{label}</span>
        <span className="text-sm font-mono text-white">{Math.round(value)}%</span>
      </div>
      <Slider
        value={[value]}
        onValueChange={([v]) => onChange(v)}
        min={0}
        max={100}
        step={1}
        disabled={disabled}
        className="w-full"
      />
    </div>
  );
}

// =============================================================================
// Main Page Component
// =============================================================================

export default function OperatorTrainingPage() {
  // State
  const [running, setRunning] = useState(false);
  const [state, setState] = useState<TrainingState | null>(null);
  const [dynoType, setDynoType] = useState<DynoType>('inertia');
  const [throttle, setThrottle] = useState(0);
  const [loadTarget, setLoadTarget] = useState(0);
  const [rpmHoldActive, setRpmHoldActive] = useState(false);
  const [rpmHoldTarget, setRpmHoldTarget] = useState(3500);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [audioEnabled, setAudioEnabled] = useState(false);

  const pollRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch scenarios on mount
  useEffect(() => {
    fetch(`${TRAINING_API}/scenarios`)
      .then(res => res.json())
      .then(data => {
        if (data.success) setScenarios(data.scenarios);
      })
      .catch(console.error);
  }, []);

  // Poll for state when running
  useEffect(() => {
    if (running) {
      const poll = async () => {
        try {
          const res = await fetch(`${TRAINING_API}/status`);
          const data = await res.json();
          if (data.success) {
            setState(data.state);
          }
        } catch (e) {
          console.error('Poll error:', e);
        }
      };

      poll();
      pollRef.current = setInterval(poll, 100); // 10Hz polling

      return () => {
        if (pollRef.current) clearInterval(pollRef.current);
      };
    }
  }, [running]);

  // API calls
  const startSimulator = async () => {
    try {
      // Start the dedicated training simulation service.
      const res = await fetch(`${TRAINING_API}/start`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setRunning(true);
        toast.success('Training simulator started');
      }
    } catch (e) {
      toast.error('Failed to start simulator');
    }
  };

  const stopSimulator = async () => {
    try {
      await fetch(`${TRAINING_API}/stop`, { method: 'POST' });
      setRunning(false);
      setThrottle(0);
      setLoadTarget(0);
      toast.info('Simulator stopped');
    } catch (e) {
      toast.error('Failed to stop simulator');
    }
  };

  const resetSimulator = async () => {
    try {
      await fetch(`${TRAINING_API}/reset`, { method: 'POST' });
      setThrottle(0);
      setLoadTarget(0);
      setRpmHoldActive(false);
      toast.info('Training reset');
    } catch (e) {
      toast.error('Failed to reset');
    }
  };

  const handleThrottleChange = async (value: number) => {
    setThrottle(value);
    try {
      await fetch(`${TRAINING_API}/throttle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tps: value })
      });
    } catch (e) {
      console.error('Throttle error:', e);
    }
  };

  const handleLoadChange = async (value: number) => {
    setLoadTarget(value);
    try {
      await fetch(`${TRAINING_API}/load`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ load: value })
      });
    } catch (e) {
      console.error('Load error:', e);
    }
  };

  const handleDynoTypeChange = async (type: DynoType) => {
    setDynoType(type);
    try {
      await fetch(`${TRAINING_API}/dyno-config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dyno_type: type })
      });
      if (type === 'inertia') {
        setLoadTarget(0);
        setRpmHoldActive(false);
      }
    } catch (e) {
      toast.error('Failed to change dyno type');
    }
  };

  const handleRpmHoldToggle = async (active: boolean) => {
    setRpmHoldActive(active);
    try {
      await fetch(`${TRAINING_API}/rpm-hold`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active, target_rpm: rpmHoldTarget })
      });
    } catch (e) {
      console.error('RPM hold error:', e);
    }
  };

  const triggerScenario = async (scenarioId: string) => {
    try {
      const res = await fetch(`${TRAINING_API}/scenario`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: scenarioId, duration: 10 })
      });
      const data = await res.json();
      if (data.success) {
        toast.warning(`Scenario triggered: ${scenarioId}`);
      }
    } catch (e) {
      toast.error('Failed to trigger scenario');
    }
  };

  const acknowledgeAlert = async (alertType: string) => {
    try {
      await fetch(`${TRAINING_API}/acknowledge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alert_type: alertType })
      });
    } catch (e) {
      console.error('Acknowledge error:', e);
    }
  };

  const emergencyStop = () => {
    handleThrottleChange(0);
    handleLoadChange(0);
    stopSimulator();
  };

  // Derived state
  const hasLoadControl = dynoType !== 'inertia';
  const hasRpmHold = dynoType === 'load_holding';
  const hasCriticalAlert = state?.alerts?.some(a => a.severity === 'critical') ?? false;

  const dynoTypeLabels: Record<DynoType, string> = {
    inertia: 'Inertia Only',
    inertia_load: 'Inertia + Load (DJ 424x)',
    load_holding: 'Load Holding (Mustang/SF)'
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950">
      {/* Header */}
      <div className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-sm sticky top-0 z-40">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-2 rounded-lg bg-gradient-to-br from-amber-500 to-orange-600 shadow-lg shadow-orange-500/20">
                <Shield className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white flex items-center gap-2">
                  Operator Training Simulator
                  <Badge variant="outline" className="text-xs border-amber-500/50 text-amber-400">
                    TRAINING MODE
                  </Badge>
                </h1>
                <p className="text-xs text-zinc-500">Virtual dyno operation practice • No risk to equipment</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {/* Safety Score */}
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-800/50 border border-zinc-700">
                <Award className="h-4 w-4 text-amber-400" />
                <span className="text-sm text-zinc-400">Safety Score:</span>
                <span className="text-sm font-mono font-bold text-white">
                  {state?.safety_score?.toFixed(0) ?? 100}
                </span>
              </div>

              {/* Status */}
              <div className="flex items-center gap-2">
                <div className={`w-2.5 h-2.5 rounded-full ${running ? 'bg-green-500 animate-pulse' : 'bg-zinc-600'}`} />
                <span className="text-sm text-zinc-400">{running ? 'RUNNING' : 'STOPPED'}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-6">
        {/* Dyno Type Selector */}
        <Card className="mb-6 bg-zinc-900/50 border-zinc-800">
          <CardContent className="py-4">
            <div className="flex items-center gap-4">
              <span className="text-sm text-zinc-400 uppercase tracking-wider">Dyno Configuration</span>
              <div className="flex gap-2">
                {(Object.keys(dynoTypeLabels) as DynoType[]).map((type) => (
                  <Button
                    key={type}
                    variant={dynoType === type ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => handleDynoTypeChange(type)}
                    className={dynoType === type
                      ? 'bg-orange-500 hover:bg-orange-600 text-white'
                      : 'border-zinc-700 text-zinc-400 hover:text-white'
                    }
                  >
                    {dynoTypeLabels[type]}
                  </Button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Main Grid */}
        <div className="grid grid-cols-12 gap-6">
          {/* Left Panel - Controls */}
          <div className="col-span-3 space-y-4">
            {/* Throttle & Load Controls */}
            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider flex items-center gap-2">
                  <Gauge className="h-4 w-4" />
                  Controls
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <ControlSlider
                  value={throttle}
                  onChange={handleThrottleChange}
                  label="Throttle"
                  color="#22c55e"
                />

                <ControlSlider
                  value={loadTarget}
                  onChange={handleLoadChange}
                  label="Load Target"
                  disabled={!hasLoadControl}
                  color="#3b82f6"
                />

                {hasRpmHold && (
                  <div className="border-t border-zinc-800 pt-4">
                    <div className="flex items-center justify-between mb-3">
                      <Label className="text-sm text-zinc-400">RPM Hold Mode</Label>
                      <Switch
                        checked={rpmHoldActive}
                        onCheckedChange={handleRpmHoldToggle}
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-zinc-500">Target:</span>
                      <Input
                        type="number"
                        value={rpmHoldTarget}
                        onChange={(e) => setRpmHoldTarget(parseInt(e.target.value) || 3500)}
                        className="w-20 h-8 text-sm bg-zinc-800 border-zinc-700"
                        min={1500}
                        max={6500}
                        step={100}
                      />
                      <span className="text-xs text-zinc-500">RPM</span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Action Buttons */}
            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardContent className="py-4 space-y-2">
                {!running ? (
                  <Button
                    onClick={startSimulator}
                    className="w-full bg-green-600 hover:bg-green-500"
                  >
                    <Play className="h-4 w-4 mr-2" />
                    Start Simulator
                  </Button>
                ) : (
                  <Button
                    onClick={() => { handleThrottleChange(0); handleLoadChange(0); }}
                    variant="secondary"
                    className="w-full"
                  >
                    <Square className="h-4 w-4 mr-2" />
                    Idle Down
                  </Button>
                )}

                <Button
                  onClick={emergencyStop}
                  variant="destructive"
                  className="w-full font-bold"
                >
                  <AlertTriangle className="h-4 w-4 mr-2" />
                  EMERGENCY STOP
                </Button>

                <Button
                  onClick={resetSimulator}
                  variant="outline"
                  size="sm"
                  className="w-full border-zinc-700"
                >
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Reset Training
                </Button>
              </CardContent>
            </Card>

            {/* Training Scenarios */}
            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider flex items-center gap-2">
                  <Zap className="h-4 w-4" />
                  Training Scenarios
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-2">
                  {scenarios.map((scenario) => (
                    <TooltipProvider key={scenario.id}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            onClick={() => triggerScenario(scenario.id)}
                            disabled={!running}
                            variant="outline"
                            size="sm"
                            className="border-amber-700/50 bg-amber-900/20 hover:bg-amber-800/30 text-amber-300 text-xs"
                          >
                            {scenario.name.split(' ')[0]}
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent side="right" className="max-w-xs">
                          <p className="font-medium">{scenario.name}</p>
                          <p className="text-xs text-zinc-400">{scenario.description}</p>
                          <p className="text-xs text-green-400 mt-1">Goal: {scenario.training_goal}</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Center Panel - Main Gauges */}
          <div className="col-span-6">
            <Card className={`bg-zinc-900/50 border transition-colors ${
              hasCriticalAlert ? 'border-red-500 shadow-lg shadow-red-500/20' : 'border-zinc-800'
            }`}>
              <CardContent className="py-6">
                {/* Primary Gauges */}
                <div className="flex justify-around items-center mb-6">
                  <SweepGauge
                    value={state?.rpm ?? 900}
                    min={0}
                    max={8000}
                    label="RPM"
                    unit="rev/min"
                    size={180}
                    warningThreshold={6200}
                    criticalThreshold={6800}
                  />
                  <SweepGauge
                    value={state?.horsepower ?? 0}
                    min={0}
                    max={200}
                    label="Power"
                    unit="HP"
                    size={180}
                  />
                  <SweepGauge
                    value={state?.engine_torque ?? 0}
                    min={0}
                    max={150}
                    label="Torque"
                    unit="ft-lb"
                    size={180}
                  />
                </div>

                {/* Secondary Values */}
                <div className="grid grid-cols-4 gap-4 border-t border-zinc-800 pt-4">
                  <div className="text-center p-3 bg-zinc-800/50 rounded-lg">
                    <div className={`text-2xl font-mono font-bold ${
                      (state?.afr ?? 14) >= 14.5 ? 'text-red-500' :
                      (state?.afr ?? 14) >= 13.5 ? 'text-amber-500' : 'text-green-500'
                    }`}>
                      {(state?.afr ?? 14.0).toFixed(1)}
                    </div>
                    <div className="text-xs text-zinc-400 mt-1">AFR</div>
                  </div>
                  <div className="text-center p-3 bg-zinc-800/50 rounded-lg">
                    <div className="text-2xl font-mono font-bold text-blue-400">
                      {(state?.current_load ?? 0).toFixed(0)}%
                    </div>
                    <div className="text-xs text-zinc-400 mt-1">Load</div>
                  </div>
                  <div className="text-center p-3 bg-zinc-800/50 rounded-lg">
                    <div className="text-2xl font-mono font-bold text-zinc-300">
                      {(state?.brake_torque ?? 0).toFixed(0)}
                    </div>
                    <div className="text-xs text-zinc-400 mt-1">Brake ft-lb</div>
                  </div>
                  <div className="text-center p-3 bg-zinc-800/50 rounded-lg">
                    <div className={`text-2xl font-mono font-bold ${
                      (state?.knock_level ?? 0) >= 3 ? 'text-red-500' : 'text-green-500'
                    }`}>
                      {(state?.knock_level ?? 0).toFixed(1)}
                    </div>
                    <div className="text-xs text-zinc-400 mt-1">Knock</div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Alerts Panel */}
            <Card className={`mt-4 bg-zinc-900/50 border transition-colors ${
              hasCriticalAlert ? 'border-red-500' : 'border-zinc-800'
            }`}>
              <CardHeader className="py-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4" />
                    Safety Alerts
                  </CardTitle>
                  <Badge variant="outline" className="border-zinc-700">
                    Score: {state?.safety_score?.toFixed(0) ?? 100}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 min-h-[60px]">
                  {(!state?.alerts || state.alerts.length === 0) ? (
                    <div className="text-sm text-green-500/70 flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-green-500" />
                      All parameters nominal
                    </div>
                  ) : (
                    <AnimatePresence>
                      {state.alerts.map((alert, idx) => (
                        <motion.div
                          key={`${alert.type}-${idx}`}
                          initial={{ opacity: 0, x: -20 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: 20 }}
                          className={`flex items-center justify-between gap-3 p-2 rounded-lg cursor-pointer ${
                            alert.severity === 'critical'
                              ? 'bg-red-500/20 border border-red-500/50'
                              : 'bg-amber-500/20 border border-amber-500/50'
                          }`}
                          onClick={() => acknowledgeAlert(alert.type)}
                        >
                          <div className="flex items-center gap-2">
                            <span className={`text-lg ${
                              alert.severity === 'critical' ? 'text-red-500' : 'text-amber-500'
                            }`}>
                              {alert.severity === 'critical' ? '⚠' : '⚡'}
                            </span>
                            <span className={`text-sm font-medium ${
                              alert.severity === 'critical' ? 'text-red-400' : 'text-amber-400'
                            }`}>
                              {alert.message}
                            </span>
                          </div>
                          <span className="text-xs text-zinc-500">Click to acknowledge</span>
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right Panel - Thermal */}
          <div className="col-span-3">
            <Card className="bg-zinc-900/50 border-zinc-800 h-full">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider flex items-center gap-2">
                  <Thermometer className="h-4 w-4" />
                  Thermal Monitoring
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex justify-around mb-6">
                  <VerticalBar
                    value={state?.egt_front ?? 650}
                    min={400}
                    max={1600}
                    label="EGT Front"
                    unit="°F"
                    height={140}
                    warningThreshold={1350}
                    criticalThreshold={1450}
                  />
                  <VerticalBar
                    value={state?.egt_rear ?? 680}
                    min={400}
                    max={1600}
                    label="EGT Rear"
                    unit="°F"
                    height={140}
                    warningThreshold={1400}
                    criticalThreshold={1500}
                  />
                </div>

                <div className="space-y-3 border-t border-zinc-800 pt-4">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-zinc-400">Oil Temp</span>
                    <span className="text-sm font-mono text-white">
                      {(state?.oil_temp ?? 180).toFixed(0)}°F
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-zinc-400">Coolant</span>
                    <span className="text-sm font-mono text-white">
                      {(state?.coolant_temp ?? 185).toFixed(0)}°F
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-zinc-400">MAP</span>
                    <span className="text-sm font-mono text-white">
                      {(state?.map_kpa ?? 30).toFixed(0)} kPa
                    </span>
                  </div>
                </div>

                {/* Operator Tips */}
                <div className="mt-6 pt-4 border-t border-zinc-800">
                  <div className="text-xs text-zinc-500 mb-2 flex items-center gap-1">
                    <Info className="h-3 w-3" />
                    OPERATOR TIPS
                  </div>
                  <ul className="text-xs text-zinc-400 space-y-1">
                    <li>• Watch EGT during extended WOT</li>
                    <li>• Target AFR: 12.8-13.2 at WOT</li>
                    <li>• Cool down between pulls</li>
                    <li>• React quickly to knock alerts</li>
                  </ul>
                </div>

                {/* Active Scenario Indicator */}
                {state?.active_scenario && state.active_scenario !== 'none' && (
                  <div className="mt-4 p-3 bg-amber-500/20 border border-amber-500/50 rounded-lg">
                    <div className="flex items-center gap-2">
                      <Zap className="h-4 w-4 text-amber-400 animate-pulse" />
                      <span className="text-sm font-medium text-amber-400">
                        Scenario Active: {state.active_scenario}
                      </span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 text-center text-xs text-zinc-600">
          DynoAI Operator Training Simulator • Physics-Informed Calibration • Virtual V-Twin Engine
        </div>
      </div>
    </div>
  );
}
