/**
 * BikeConfigForm - Step 2 of the Setup Wizard
 * 
 * Comprehensive bike/vehicle configuration form:
 * - Make, model, year selection
 * - Displacement with unit toggle
 * - Engine type and cylinder count
 * - RPM and MAP range configuration
 * - Optional custom bin editor
 * - Quick preset buttons
 */

import { useState, useCallback, useMemo } from 'react';
import { Bike, Settings, ChevronDown, ChevronUp, Zap } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Slider } from '../ui/slider';
import {
  BikeConfig,
  EngineType,
  DisplacementUnit,
  BIKE_MAKES,
  ENGINE_TYPES,
  getDefaultRpmRange,
  getDefaultCylinders,
} from '../../types/bikeConfig';
import { listEnginePresets } from '../../utils/enginePresets';

interface BikeConfigFormProps {
  config: BikeConfig;
  onChange: (config: BikeConfig) => void;
  onPresetSelect?: (presetKey: string) => void;
}

export function BikeConfigForm({
  config,
  onChange,
  onPresetSelect,
}: BikeConfigFormProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [customBinsText, setCustomBinsText] = useState({
    rpm: config.customRpmBins?.join(', ') || '',
    map: config.customMapBins?.join(', ') || '',
  });

  const presets = useMemo(() => listEnginePresets(), []);

  const handleMakeChange = useCallback((value: string) => {
    onChange({ ...config, make: value });
  }, [config, onChange]);

  const handleModelChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...config, model: e.target.value });
  }, [config, onChange]);

  const handleYearChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const year = parseInt(e.target.value, 10);
    if (!isNaN(year) && year >= 1900 && year <= new Date().getFullYear() + 1) {
      onChange({ ...config, year });
    }
  }, [config, onChange]);

  const handleDisplacementChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const displacement = parseFloat(e.target.value);
    if (!isNaN(displacement) && displacement > 0) {
      onChange({ ...config, displacement });
    }
  }, [config, onChange]);

  const handleDisplacementUnitChange = useCallback((unit: DisplacementUnit) => {
    // Convert value when switching units
    let newDisplacement = config.displacement;
    if (unit === 'cc' && config.displacementUnit === 'ci') {
      newDisplacement = Math.round(config.displacement * 16.387);
    } else if (unit === 'ci' && config.displacementUnit === 'cc') {
      newDisplacement = Math.round(config.displacement / 16.387 * 10) / 10;
    }
    onChange({ ...config, displacement: newDisplacement, displacementUnit: unit });
  }, [config, onChange]);

  const handleEngineTypeChange = useCallback((value: EngineType) => {
    const defaults = getDefaultRpmRange(value);
    const cylinders = getDefaultCylinders(value);
    onChange({
      ...config,
      engineType: value,
      cylinders,
      rpmRange: defaults,
    });
  }, [config, onChange]);

  const handleCylindersChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const cylinders = parseInt(e.target.value, 10);
    if (!isNaN(cylinders) && cylinders >= 1 && cylinders <= 8) {
      onChange({ ...config, cylinders });
    }
  }, [config, onChange]);

  const handleRpmRangeChange = useCallback((values: number[]) => {
    onChange({
      ...config,
      rpmRange: { min: values[0], max: values[1] },
    });
  }, [config, onChange]);

  const handleMapRangeChange = useCallback((values: number[]) => {
    onChange({
      ...config,
      mapRange: { min: values[0], max: values[1] },
    });
  }, [config, onChange]);

  const handleCustomRpmBinsChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const text = e.target.value;
    setCustomBinsText(prev => ({ ...prev, rpm: text }));
    
    // Parse comma-separated values
    const bins = text.split(',')
      .map(s => parseInt(s.trim(), 10))
      .filter(n => !isNaN(n) && n > 0)
      .sort((a, b) => a - b);
    
    if (bins.length >= 2) {
      onChange({ ...config, customRpmBins: bins });
    } else if (text === '') {
      onChange({ ...config, customRpmBins: undefined });
    }
  }, [config, onChange]);

  const handleCustomMapBinsChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const text = e.target.value;
    setCustomBinsText(prev => ({ ...prev, map: text }));
    
    // Parse comma-separated values
    const bins = text.split(',')
      .map(s => parseInt(s.trim(), 10))
      .filter(n => !isNaN(n) && n > 0)
      .sort((a, b) => a - b);
    
    if (bins.length >= 2) {
      onChange({ ...config, customMapBins: bins });
    } else if (text === '') {
      onChange({ ...config, customMapBins: undefined });
    }
  }, [config, onChange]);

  // Generate year options (last 50 years)
  const yearOptions = useMemo(() => {
    const currentYear = new Date().getFullYear();
    return Array.from({ length: 50 }, (_, i) => currentYear - i);
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-br from-orange-500/20 to-amber-500/20 flex items-center justify-center">
          <Bike className="w-8 h-8 text-orange-400" />
        </div>
        <h2 className="text-2xl font-bold text-white mb-2">Configure Your Bike</h2>
        <p className="text-zinc-400 text-sm max-w-md mx-auto">
          Enter your motorcycle details for accurate VE table generation
        </p>
      </div>

      {/* Quick Presets */}
      {onPresetSelect && (
        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 mb-3">
              <Zap className="w-4 h-4 text-yellow-400" />
              <span className="text-sm font-medium text-zinc-300">Quick Start - Use a Preset</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {presets.map((preset) => (
                <Button
                  key={preset.key}
                  variant="outline"
                  size="sm"
                  onClick={() => onPresetSelect(preset.key)}
                  className="justify-start text-xs border-zinc-700 hover:border-orange-500/50 hover:text-orange-400"
                >
                  {preset.name}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Configuration Form */}
      <Card className="bg-zinc-900/80 border-zinc-800">
        <CardHeader className="pb-4">
          <CardTitle className="text-lg flex items-center gap-2">
            <Settings className="w-5 h-5 text-orange-400" />
            Vehicle Details
          </CardTitle>
          <CardDescription>
            Basic information about your motorcycle
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Make, Model, Year Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Make */}
            <div className="space-y-2">
              <Label>Make</Label>
              <Select value={config.make} onValueChange={handleMakeChange}>
                <SelectTrigger className="bg-zinc-800/50 border-zinc-700 w-full">
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
                placeholder="Street Glide"
                value={config.model}
                onChange={handleModelChange}
                className="bg-zinc-800/50 border-zinc-700"
              />
            </div>

            {/* Year */}
            <div className="space-y-2">
              <Label htmlFor="year">Year</Label>
              <Select value={config.year.toString()} onValueChange={(v) => onChange({ ...config, year: parseInt(v, 10) })}>
                <SelectTrigger className="bg-zinc-800/50 border-zinc-700 w-full">
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

          {/* Engine Configuration Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Displacement */}
            <div className="space-y-2">
              <Label htmlFor="displacement">Displacement</Label>
              <div className="flex gap-2">
                <Input
                  id="displacement"
                  type="number"
                  value={config.displacement}
                  onChange={handleDisplacementChange}
                  className="bg-zinc-800/50 border-zinc-700 flex-1"
                />
                <div className="flex rounded-md border border-zinc-700 overflow-hidden">
                  <button
                    type="button"
                    onClick={() => handleDisplacementUnitChange('cc')}
                    className={`px-3 py-2 text-xs font-medium transition-colors ${
                      config.displacementUnit === 'cc'
                        ? 'bg-orange-500/20 text-orange-400'
                        : 'bg-zinc-800/50 text-zinc-400 hover:text-white'
                    }`}
                  >
                    cc
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDisplacementUnitChange('ci')}
                    className={`px-3 py-2 text-xs font-medium transition-colors ${
                      config.displacementUnit === 'ci'
                        ? 'bg-orange-500/20 text-orange-400'
                        : 'bg-zinc-800/50 text-zinc-400 hover:text-white'
                    }`}
                  >
                    ci
                  </button>
                </div>
              </div>
            </div>

            {/* Engine Type */}
            <div className="space-y-2">
              <Label>Engine Type</Label>
              <Select value={config.engineType} onValueChange={handleEngineTypeChange}>
                <SelectTrigger className="bg-zinc-800/50 border-zinc-700 w-full">
                  <SelectValue placeholder="Select engine type" />
                </SelectTrigger>
                <SelectContent>
                  {ENGINE_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Cylinders */}
            <div className="space-y-2">
              <Label htmlFor="cylinders">Cylinders</Label>
              <Input
                id="cylinders"
                type="number"
                min={1}
                max={8}
                value={config.cylinders}
                onChange={handleCylindersChange}
                className="bg-zinc-800/50 border-zinc-700"
              />
            </div>
          </div>

          {/* RPM Range */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>RPM Range</Label>
              <span className="text-sm text-zinc-400">
                {config.rpmRange.min.toLocaleString()} - {config.rpmRange.max.toLocaleString()} RPM
              </span>
            </div>
            <Slider
              value={[config.rpmRange.min, config.rpmRange.max]}
              onValueChange={handleRpmRangeChange}
              min={500}
              max={18000}
              step={100}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-zinc-500">
              <span>500</span>
              <span>18,000</span>
            </div>
          </div>

          {/* MAP Range */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>MAP Range (kPa)</Label>
              <span className="text-sm text-zinc-400">
                {config.mapRange.min} - {config.mapRange.max} kPa
              </span>
            </div>
            <Slider
              value={[config.mapRange.min, config.mapRange.max]}
              onValueChange={handleMapRangeChange}
              min={10}
              max={250}
              step={5}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-zinc-500">
              <span>10 kPa</span>
              <span>250 kPa</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Advanced Options */}
      <Card className="bg-zinc-900/50 border-zinc-800">
        <CardContent className="pt-4">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="w-full flex items-center justify-between text-sm text-zinc-400 hover:text-white transition-colors"
          >
            <span className="flex items-center gap-2">
              <Settings className="w-4 h-4" />
              Advanced Options
            </span>
            {showAdvanced ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>

          {showAdvanced && (
            <div className="mt-4 pt-4 border-t border-zinc-800 space-y-4">
              <p className="text-xs text-zinc-500 mb-4">
                Define custom RPM and MAP bins for your VE table. Enter comma-separated values.
              </p>

              {/* Custom RPM Bins */}
              <div className="space-y-2">
                <Label htmlFor="custom-rpm-bins">Custom RPM Bins</Label>
                <Input
                  id="custom-rpm-bins"
                  type="text"
                  placeholder="1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000"
                  value={customBinsText.rpm}
                  onChange={handleCustomRpmBinsChange}
                  className="bg-zinc-800/50 border-zinc-700 font-mono text-xs"
                />
                {config.customRpmBins && (
                  <Badge variant="outline" className="text-green-400 border-green-500/30 text-xs">
                    {config.customRpmBins.length} bins defined
                  </Badge>
                )}
              </div>

              {/* Custom MAP Bins */}
              <div className="space-y-2">
                <Label htmlFor="custom-map-bins">Custom MAP Bins (kPa)</Label>
                <Input
                  id="custom-map-bins"
                  type="text"
                  placeholder="20, 30, 40, 50, 60, 70, 80, 90, 100, 110"
                  value={customBinsText.map}
                  onChange={handleCustomMapBinsChange}
                  className="bg-zinc-800/50 border-zinc-700 font-mono text-xs"
                />
                {config.customMapBins && (
                  <Badge variant="outline" className="text-green-400 border-green-500/30 text-xs">
                    {config.customMapBins.length} bins defined
                  </Badge>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Summary Badge */}
      <div className="flex justify-center">
        <Badge variant="outline" className="text-zinc-400 border-zinc-700 px-4 py-2">
          {config.year} {config.make} {config.model || '(Model)'} • {config.displacement} {config.displacementUnit} {ENGINE_TYPES.find(t => t.value === config.engineType)?.label}
        </Badge>
      </div>
    </div>
  );
}

export default BikeConfigForm;
