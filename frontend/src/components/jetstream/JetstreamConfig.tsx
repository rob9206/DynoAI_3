/**
 * Jetstream configuration panel
 */

import { useState, useEffect } from 'react';
import { Settings, Save, Loader2, Eye, EyeOff, Radio, Shield, Clock } from 'lucide-react';
import { Settings, Save, Loader2, Eye, EyeOff, Flame } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Switch } from '../ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Separator } from '../ui/separator';
import { useJetstreamConfig, useUpdateJetstreamConfig } from '../../hooks/useJetstream';
import { toast } from 'sonner';

export function JetstreamConfig() {
  const { data: config, isLoading } = useJetstreamConfig();
  const updateConfig = useUpdateJetstreamConfig();

  const [apiUrl, setApiUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [pollInterval, setPollInterval] = useState(30);
  const [autoProcess, setAutoProcess] = useState(true);
  const [enabled, setEnabled] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);

  // Tuning options state
  const [decelManagement, setDecelManagement] = useState(false);
  const [decelSeverity, setDecelSeverity] = useState<'low' | 'medium' | 'high'>('medium');
  const [decelRpmMin, setDecelRpmMin] = useState(1500);
  const [decelRpmMax, setDecelRpmMax] = useState(5500);
  const [balanceCylinders, setBalanceCylinders] = useState(false);
  const [balanceMode, setBalanceMode] = useState<'equalize' | 'match_front' | 'match_rear'>('equalize');
  const [balanceMaxCorrection, setBalanceMaxCorrection] = useState(3.0);

  // Populate form when config loads
  useEffect(() => {
    if (config) {
      setApiUrl(config.api_url);
      setApiKey(config.api_key);
      setPollInterval(config.poll_interval_seconds);
      setAutoProcess(config.auto_process);
      setEnabled(config.enabled);

      // Load tuning options
      if (config.tuning_options) {
        setDecelManagement(config.tuning_options.decel_management);
        setDecelSeverity(config.tuning_options.decel_severity);
        setDecelRpmMin(config.tuning_options.decel_rpm_min);
        setDecelRpmMax(config.tuning_options.decel_rpm_max);
        setBalanceCylinders(config.tuning_options.balance_cylinders);
        setBalanceMode(config.tuning_options.balance_mode);
        setBalanceMaxCorrection(config.tuning_options.balance_max_correction);
      }
    }
  }, [config]);

  const handleSave = () => {
    updateConfig.mutate(
      {
        api_url: apiUrl,
        api_key: apiKey,
        poll_interval_seconds: pollInterval,
        auto_process: autoProcess,
        enabled,
        tuning_options: {
          decel_management: decelManagement,
          decel_severity: decelSeverity,
          decel_rpm_min: decelRpmMin,
          decel_rpm_max: decelRpmMax,
          balance_cylinders: balanceCylinders,
          balance_mode: balanceMode,
          balance_max_correction: balanceMaxCorrection,
        },
      },
      {
        onSuccess: () => {
          toast.success('Configuration saved');
        },
        onError: (error) => {
          toast.error(`Failed to save: ${error instanceof Error ? error.message : 'Unknown error'}`);
        },
      }
    );
  };

  if (isLoading) {
    return (
      <Card className="border-border/50 bg-card/30 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-mono uppercase tracking-tight">
            <Settings className="h-5 w-5 text-primary" />
            Link Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="flex justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/50 bg-card/30 backdrop-blur-sm h-full">
      <CardHeader className="border-b border-border/40 pb-4">
        <CardTitle className="flex items-center gap-2 font-mono uppercase tracking-tight">
          <Settings className="h-5 w-5 text-primary" />
          Link Configuration
    <Card className="flex flex-col max-h-[calc(100vh-6rem)]">
      <CardHeader className="flex-shrink-0">
        <CardTitle className="flex items-center gap-2">
          <Settings className="h-5 w-5" />
          Jetstream Configuration
        </CardTitle>
        <CardDescription className="font-mono text-xs uppercase tracking-wider text-muted-foreground/70">
          Establish Uplink to Jetstream Cloud Service
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6 pt-6">
      <CardContent className="space-y-6 overflow-y-auto flex-1">
        {/* API URL */}
        <div className="space-y-2">
          <Label htmlFor="api-url" className="font-mono uppercase text-xs tracking-wide text-muted-foreground">Endpoint URL</Label>
          <div className="relative">
            <Radio className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              id="api-url"
              type="url"
              placeholder="https://api.jetstream.dynojet.com"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              className="pl-9 font-mono text-sm"
            />
          </div>
        </div>

        {/* API Key */}
        <div className="space-y-2">
          <Label htmlFor="api-key" className="font-mono uppercase text-xs tracking-wide text-muted-foreground">Access Key</Label>
          <div className="relative">
            <Shield className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              id="api-key"
              type={showApiKey ? 'text' : 'password'}
              placeholder="Enter your API key"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="pl-9 pr-10 font-mono text-sm"
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="absolute right-0 top-0 h-full px-3"
              onClick={() => setShowApiKey(!showApiKey)}
            >
              {showApiKey ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
            </Button>
          </div>
          <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider">
            Credentials Masked for Security
          </p>
        </div>

        {/* Poll Interval */}
        <div className="space-y-2">
          <Label htmlFor="poll-interval" className="font-mono uppercase text-xs tracking-wide text-muted-foreground">Polling Cycle</Label>
          <div className="relative">
            <Clock className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              id="poll-interval"
              type="number"
              min={10}
              max={300}
              value={pollInterval}
              onChange={(e) => setPollInterval(parseInt(e.target.value, 10))}
              className="pl-9 font-mono text-sm"
            />
          </div>
          <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider">
            Sync Frequency (Seconds)
          </p>
        </div>

        <div className="bg-muted/20 p-4 rounded-lg border border-border/50 space-y-4">
            {/* Auto Process */}
            <div className="flex items-center justify-between">
            <div className="space-y-0.5">
                <Label htmlFor="auto-process" className="font-mono uppercase text-xs tracking-wide font-bold">Auto-Processing</Label>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
                Analyze incoming telemetry immediately
                </p>
            </div>
            <Switch
                id="auto-process"
                checked={autoProcess}
                onCheckedChange={setAutoProcess}
            />
            </div>

            {/* Enabled */}
            <div className="flex items-center justify-between border-t border-border/30 pt-4">
            <div className="space-y-0.5">
                <Label htmlFor="enabled" className="font-mono uppercase text-xs tracking-wide font-bold text-primary">Link Active</Label>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
                Enable background polling service
                </p>
            </div>
            <Switch
                id="enabled"
                checked={enabled}
                onCheckedChange={setEnabled}
            />
            </div>
        </div>

        <Separator className="my-4" />

        {/* Tuning Options Section */}
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Flame className="h-5 w-5 text-orange-500" />
            <h3 className="text-lg font-semibold">Tuning Options</h3>
          </div>
          <p className="text-sm text-muted-foreground">
            Configure automated tuning features applied during run processing
          </p>

          {/* Decel Fuel Management Toggle */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="decel-management">Decel Fuel Management</Label>
              <p className="text-xs text-muted-foreground">
                Automatically generate VE corrections to eliminate exhaust popping
              </p>
            </div>
            <Switch
              id="decel-management"
              checked={decelManagement}
              onCheckedChange={setDecelManagement}
            />
          </div>

          {/* Decel Severity */}
          {decelManagement && (
            <div className="space-y-4 pl-4 border-l-2 border-orange-500/30">
              <div className="space-y-2">
                <Label htmlFor="decel-severity">Enrichment Severity</Label>
                <Select
                  value={decelSeverity}
                  onValueChange={(value: 'low' | 'medium' | 'high') => setDecelSeverity(value)}
                >
                  <SelectTrigger id="decel-severity">
                    <SelectValue placeholder="Select severity" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low - Minimal enrichment, may have some popping</SelectItem>
                    <SelectItem value="medium">Medium - Balanced (recommended)</SelectItem>
                    <SelectItem value="high">High - Aggressive, eliminates all popping</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Higher severity = more fuel added during deceleration
                </p>
              </div>

              {/* RPM Range */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="decel-rpm-min">Min RPM</Label>
                  <Input
                    id="decel-rpm-min"
                    type="number"
                    min={1000}
                    max={decelRpmMax - 500}
                    step={100}
                    value={decelRpmMin}
                    onChange={(e) => setDecelRpmMin(parseInt(e.target.value, 10))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="decel-rpm-max">Max RPM</Label>
                  <Input
                    id="decel-rpm-max"
                    type="number"
                    min={decelRpmMin + 500}
                    max={7000}
                    step={100}
                    value={decelRpmMax}
                    onChange={(e) => setDecelRpmMax(parseInt(e.target.value, 10))}
                  />
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                RPM range where decel corrections are applied (default: 1500-5500)
              </p>
            </div>
          )}
        </div>

        {/* Per-Cylinder Auto-Balancing */}
        <div className="space-y-3 pt-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="balance-cylinders" className="text-base flex items-center gap-2">
                <Activity className="h-4 w-4 text-blue-500" />
                Per-Cylinder Auto-Balancing
              </Label>
              <p className="text-xs text-muted-foreground">
                Automatically equalize AFR between front and rear cylinders.
              </p>
            </div>
            <Switch
              id="balance-cylinders"
              checked={balanceCylinders}
              onCheckedChange={setBalanceCylinders}
            />
          </div>

          {balanceCylinders && (
            <div className="space-y-4 pl-6 pt-2">
              <div className="space-y-2">
                <Label htmlFor="balance-mode">Balance Mode</Label>
                <Select
                  value={balanceMode}
                  onValueChange={(value: 'equalize' | 'match_front' | 'match_rear') => setBalanceMode(value)}
                >
                  <SelectTrigger id="balance-mode">
                    <SelectValue placeholder="Select mode" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="equalize">Equalize (Both toward average)</SelectItem>
                    <SelectItem value="match_front">Match Front (Rear to front)</SelectItem>
                    <SelectItem value="match_rear">Match Rear (Front to rear)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Strategy for balancing cylinder AFR.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="balance-max-correction">Max Correction (%)</Label>
                <Input
                  id="balance-max-correction"
                  type="number"
                  min={1.0}
                  max={5.0}
                  step={0.5}
                  value={balanceMaxCorrection}
                  onChange={(e) => setBalanceMaxCorrection(parseFloat(e.target.value))}
                />
                <p className="text-xs text-muted-foreground">
                  Maximum VE adjustment per iteration (default: 3.0%).
                </p>
              </div>
            </div>
          )}
        </div>

        <Separator className="my-4" />

        {/* Save Button */}
        <Button
          onClick={handleSave}
          disabled={updateConfig.isPending}
          className="w-full font-mono uppercase tracking-wider h-12"
        >
          {updateConfig.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <Save className="h-4 w-4 mr-2" />
          )}
          Commit Configuration
        </Button>
      </CardContent>
    </Card>
  );
}
