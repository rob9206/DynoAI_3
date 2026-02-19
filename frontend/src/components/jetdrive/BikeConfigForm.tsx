/**
 * BikeConfigForm - Step 2 of the Setup Wizard
 * 
 * Captures detailed bike/vehicle configuration:
 * - Make, Model, Year
 * - Displacement and units
 * - Engine type and cylinder count
 * - RPM and MAP ranges
 * - Optional custom bin editor (advanced)
 * - Quick-start presets
 */

import { useState, useCallback, useMemo } from 'react';
import { Bike, Settings2, ChevronDown, ChevronUp, Sparkles, Info } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Slider } from '../ui/slider';
import { Badge } from '../ui/badge';
import { cn } from '../../lib/utils';
import {
  BikeConfig,
  EngineType,
  DisplacementUnit,
  BIKE_MAKES,
  ENGINE_TYPES,
  DEFAULT_BIKE_CONFIG,
  getDefaultRpmRange,
  getDefaultCylinders,
} from '../../types/bikeConfig';
import { listEnginePresets, bikeConfigFromPreset } from '../../utils/enginePresets';

interface BikeConfigFormProps {
  config: BikeConfig;
  onChange: (config: BikeConfig) => void;
  onPresetSelect?: (presetKey: string) => void;
}

export function BikeConfigForm({ config, onChange, onPresetSelect }: BikeConfigFormProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [customBinsMode, setCustomBinsMode] = useState(false);

  const presets = useMemo(() => listEnginePresets(), []);

  // Update a single field
  const updateField = useCallback(<K extends keyof BikeConfig>(field: K, value: BikeConfig[K]) => {
    onChange({ ...config, [field]: value });
  }, [config, onChange]);

  // Handle engine type change - auto-update related fields
  const handleEngineTypeChange = useCallback((engineType: EngineType) => {
    const defaultRpm = getDefaultRpmRange(engineType);
    const defaultCylinders = getDefaultCylinders(engineType);
    
    onChange({
      ...config,
      engineType,
      cylinders: defaultCylinders,
      rpmRange: defaultRpm,
    });
  }, [config, onChange]);

  // Handle preset selection
  const handlePresetClick = useCallback((presetKey: string) => {
    const presetConfig = bikeConfigFromPreset(presetKey);
    if (presetConfig) {
      onChange(presetConfig);
      onPresetSelect?.(presetKey);
    }
  }, [onChange, onPresetSelect]);

  // Generate year options (last 30 years)
  const yearOptions = useMemo(() => {
    const currentYear = new Date().getFullYear();
    return Array.from({ length: 30 }, (_, i) => currentYear - i);
  }, []);

  // Custom RPM bins editor
  const handleRpmBinsChange = useCallback((value: string) => {
    const bins = value.split(',').map(s => parseInt(s.trim(), 10)).filter(n => !isNaN(n));
    if (bins.length > 0) {
      updateField('customRpmBins', bins);
    }
  }, [updateField]);

  // Custom MAP bins editor
  const handleMapBinsChange = useCallback((value: string) => {
    const bins = value.split(',').map(s => parseInt(s.trim(), 10)).filter(n => !isNaN(n));
    if (bins.length > 0) {
      updateField('customMapBins', bins);
    }
  }, [updateField]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-br from-orange-500/20 to-amber-500/20 flex items-center justify-center">
          <Bike className="w-8 h-8 text-orange-400" />
        </div>
        <h2 className="text-2xl font-bold text-white mb-2">Configure Your Bike</h2>
        <p className="text-zinc-400 text-sm max-w-md mx-auto">
          Enter your vehicle details for accurate VE table generation
        </p>
      </div>

      {/* Quick Presets */}
      <Card className="bg-zinc-900/60 border-zinc-800">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-amber-400" />
            Quick Start Presets
          </CardTitle>
          <CardDescription className="text-xs">
            Select a preset to auto-fill common configurations
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-2">
            {presets.map((preset) => (
              <Button
                key={preset.key}
                variant="outline"
                size="sm"
                onClick={() => handlePresetClick(preset.key)}
                className={cn(
                  'justify-start text-xs h-auto py-2 px-3',
                  'border-zinc-700 hover:border-amber-500/50 hover:bg-amber-500/5',
                  'transition-all duration-200'
                )}
              >
                <div className="text-left">
                  <div className="font-medium text-zinc-200">{preset.name}</div>
                  <div className="text-[10px] text-zinc-500">{preset.description}</div>
                </div>
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Main Configuration Form */}
      <Card className="bg-zinc-900/80 border-zinc-800">
        <CardHeader className="pb-4">
          <CardTitle className="text-lg flex items-center gap-2">
            <Settings2 className="w-5 h-5 text-blue-400" />
            Vehicle Details
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Row 1: Make, Model, Year */}
          <div className="grid grid-cols-3 gap-4">
            {/* Make */}
            <div className="space-y-2">
              <Label htmlFor="make">Make</Label>
              <Select value={config.make} onValueChange={(v) => updateField('make', v)}>
                <SelectTrigger className="bg-zinc-800/50 border-zinc-700">
                  <SelectValue placeholder="Select make" />
                </SelectTrigger>
                <SelectContent>
                  {BIKE_MAKES.map((make) => (
                    <SelectItem key={make} value={make}>
                      {make}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Model */}
            <div className="space-y-2">
              <Label htmlFor="model">Model</Label>
              <Input
                id="model"
                type="text"
                placeholder="e.g., Street Glide"
                value={config.model}
                onChange={(e) => updateField('model', e.target.value)}
                className="bg-zinc-800/50 border-zinc-700"
              />
            </div>

            {/* Year */}
            <div className="space-y-2">
              <Label htmlFor="year">Year</Label>
              <Select 
                value={config.year.toString()} 
                onValueChange={(v) => updateField('year', parseInt(v, 10))}
              >
                <SelectTrigger className="bg-zinc-800/50 border-zinc-700">
                  <SelectValue placeholder="Select year" />
                </SelectTrigger>
                <SelectContent>
                  {yearOptions.map((year) => (
                    <SelectItem key={year} value={year.toString()}>
                      {year}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Row 2: Displacement */}
          <div className="grid grid-cols-2 gap-4">
            {/* Displacement */}
            <div className="space-y-2">
              <Label htmlFor="displacement">Displacement</Label>
              <div className="flex gap-2">
                <Input
                  id="displacement"
                  type="number"
                  value={config.displacement}
                  onChange={(e) => updateField('displacement', parseFloat(e.target.value) || 0)}
                  className="bg-zinc-800/50 border-zinc-700 flex-1"
                />
                <Select 
                  value={config.displacementUnit} 
                  onValueChange={(v) => updateField('displacementUnit', v as DisplacementUnit)}
                >
                  <SelectTrigger className="bg-zinc-800/50 border-zinc-700 w-24">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cc">cc</SelectItem>
                    <SelectItem value="ci">ci</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Cylinders */}
            <div className="space-y-2">
              <Label htmlFor="cylinders">Cylinders</Label>
              <Select 
                value={config.cylinders.toString()} 
                onValueChange={(v) => updateField('cylinders', parseInt(v, 10))}
              >
                <SelectTrigger className="bg-zinc-800/50 border-zinc-700">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[1, 2, 3, 4, 6, 8].map((n) => (
                    <SelectItem key={n} value={n.toString()}>
                      {n} cylinder{n > 1 ? 's' : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Row 3: Engine Type */}
          <div className="space-y-2">
            <Label>Engine Type</Label>
            <div className="grid grid-cols-3 gap-2">
              {ENGINE_TYPES.map((type) => (
                <Button
                  key={type.value}
                  variant="outline"
                  size="sm"
                  onClick={() => handleEngineTypeChange(type.value)}
                  className={cn(
                    'border-zinc-700 transition-all',
                    config.engineType === type.value
                      ? 'border-cyan-500 bg-cyan-500/10 text-cyan-400'
                      : 'hover:border-zinc-600'
                  )}
                >
                  {type.label}
                </Button>
              ))}
            </div>
          </div>

          {/* Row 4: RPM Range */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>RPM Range</Label>
              <Badge variant="outline" className="text-xs font-mono">
                {config.rpmRange.min.toLocaleString()} - {config.rpmRange.max.toLocaleString()} RPM
              </Badge>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-xs text-zinc-500">Minimum RPM</Label>
                <Input
                  type="number"
                  value={config.rpmRange.min}
                  onChange={(e) => updateField('rpmRange', { 
                    ...config.rpmRange, 
                    min: parseInt(e.target.value, 10) || 0 
                  })}
                  className="bg-zinc-800/50 border-zinc-700"
                  step={500}
                />
              </div>
              <div className="space-y-2">
                <Label className="text-xs text-zinc-500">Maximum RPM</Label>
                <Input
                  type="number"
                  value={config.rpmRange.max}
                  onChange={(e) => updateField('rpmRange', { 
                    ...config.rpmRange, 
                    max: parseInt(e.target.value, 10) || 0 
                  })}
                  className="bg-zinc-800/50 border-zinc-700"
                  step={500}
                />
              </div>
            </div>
          </div>

          {/* Row 5: MAP Range */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>MAP Range (kPa)</Label>
              <Badge variant="outline" className="text-xs font-mono">
                {config.mapRange.min} - {config.mapRange.max} kPa
              </Badge>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-xs text-zinc-500">Minimum MAP</Label>
                <Input
                  type="number"
                  value={config.mapRange.min}
                  onChange={(e) => updateField('mapRange', { 
                    ...config.mapRange, 
                    min: parseInt(e.target.value, 10) || 0 
                  })}
                  className="bg-zinc-800/50 border-zinc-700"
                  step={10}
                />
              </div>
              <div className="space-y-2">
                <Label className="text-xs text-zinc-500">Maximum MAP</Label>
                <Input
                  type="number"
                  value={config.mapRange.max}
                  onChange={(e) => updateField('mapRange', { 
                    ...config.mapRange, 
                    max: parseInt(e.target.value, 10) || 0 
                  })}
                  className="bg-zinc-800/50 border-zinc-700"
                  step={10}
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Advanced Options Toggle */}
      <button
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="w-full flex items-center justify-center gap-2 py-2 text-sm text-zinc-400 hover:text-zinc-300 transition-colors"
      >
        {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        {showAdvanced ? 'Hide' : 'Show'} Advanced Options
      </button>

      {/* Advanced Options */}
      {showAdvanced && (
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Info className="w-4 h-4 text-purple-400" />
              Custom VE Table Bins
            </CardTitle>
            <CardDescription className="text-xs">
              Define custom RPM and MAP bins for your VE table (comma-separated values)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Toggle for custom bins */}
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCustomBinsMode(!customBinsMode)}
                className={cn(
                  'border-zinc-700',
                  customBinsMode && 'border-purple-500 bg-purple-500/10 text-purple-400'
                )}
              >
                {customBinsMode ? 'Using Custom Bins' : 'Use Custom Bins'}
              </Button>
              <span className="text-xs text-zinc-500">
                {customBinsMode 
                  ? 'Enter your own bin values below' 
                  : 'Using default bins based on engine type'}
              </span>
            </div>

            {customBinsMode && (
              <>
                {/* Custom RPM Bins */}
                <div className="space-y-2">
                  <Label className="text-xs">Custom RPM Bins</Label>
                  <Input
                    type="text"
                    placeholder="1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500"
                    value={config.customRpmBins?.join(', ') || ''}
                    onChange={(e) => handleRpmBinsChange(e.target.value)}
                    className="bg-zinc-800/50 border-zinc-700 font-mono text-xs"
                  />
                  <p className="text-[10px] text-zinc-500">
                    Enter RPM values separated by commas
                  </p>
                </div>

                {/* Custom MAP Bins */}
                <div className="space-y-2">
                  <Label className="text-xs">Custom MAP Bins (kPa)</Label>
                  <Input
                    type="text"
                    placeholder="20, 30, 40, 50, 60, 70, 80, 90, 100, 110"
                    value={config.customMapBins?.join(', ') || ''}
                    onChange={(e) => handleMapBinsChange(e.target.value)}
                    className="bg-zinc-800/50 border-zinc-700 font-mono text-xs"
                  />
                  <p className="text-[10px] text-zinc-500">
                    Enter MAP values in kPa separated by commas
                  </p>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* Configuration Summary */}
      <Card className="bg-gradient-to-br from-zinc-900/80 to-zinc-800/40 border-zinc-700/50">
        <CardContent className="pt-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500/20 to-blue-500/20 flex items-center justify-center">
              <Bike className="w-5 h-5 text-cyan-400" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-white">
                {config.year} {config.make} {config.model || '(No model)'}
              </p>
              <p className="text-xs text-zinc-400">
                {config.displacement} {config.displacementUnit} {ENGINE_TYPES.find(t => t.value === config.engineType)?.label}
              </p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4 text-xs">
            <div>
              <span className="text-zinc-500">Cylinders:</span>
              <span className="text-white ml-1">{config.cylinders}</span>
            </div>
            <div>
              <span className="text-zinc-500">RPM:</span>
              <span className="text-white ml-1">{config.rpmRange.min.toLocaleString()}-{config.rpmRange.max.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-zinc-500">MAP:</span>
              <span className="text-white ml-1">{config.mapRange.min}-{config.mapRange.max} kPa</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default BikeConfigForm;
