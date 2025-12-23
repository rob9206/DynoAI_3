import { useMemo, useState, useEffect, useCallback } from 'react';
import { Zap, Activity, Radio, RefreshCw, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Switch } from '../ui/switch';
import { Alert, AlertDescription } from '../ui/alert';
import { useJetDriveLive } from '../../hooks/useJetDriveLive';

type QuickTunePanelProps = {
  apiUrl: string; // e.g. http://127.0.0.1:5001/api/jetdrive
};

interface AutoDetectConfig {
  enabled: boolean;
  rpmThreshold: number;
  minDuration: number; // seconds
  cooldownPeriod: number; // seconds between runs
}

export function QuickTunePanel({ apiUrl }: QuickTunePanelProps) {
  const defaultRunId = useMemo(() => `quick_${Date.now()}`, []);
  const [runId, setRunId] = useState(defaultRunId);
  const [busy, setBusy] = useState<null | 'simulate' | 'monitor' | 'live'>(null);
  
  // Auto-detection state
  const [autoDetectConfig, setAutoDetectConfig] = useState<AutoDetectConfig>({
    enabled: true,
    rpmThreshold: 2000,
    minDuration: 3,
    cooldownPeriod: 5
  });
  const [rpmHistory, setRpmHistory] = useState<number[]>([]);
  const [runDetected, setRunDetected] = useState(false);
  const [lastRunEndTime, setLastRunEndTime] = useState<number>(0);

  // Use JetDrive live hook for real-time RPM monitoring
  const {
    isCapturing,
    getChannelValue,
  } = useJetDriveLive({
    apiUrl,
    autoConnect: false,
    pollInterval: 50, // 50ms = 20 Hz for responsive detection
  });

  // Get RPM from multiple possible channels
  const getRPM = useCallback(() => {
    const rpmChannels = [
      'Digital RPM 1',
      'Digital RPM 2', 
      'RPM',
      'chan_42',
      'chan_43'
    ];
    
    for (const channel of rpmChannels) {
      const value = getChannelValue(channel);
      if (value !== null && value > 0) {
        return value;
      }
    }
    
    return 0;
  }, [getChannelValue]);

  // Monitor RPM continuously for auto-detection
  useEffect(() => {
    if (!isCapturing || !autoDetectConfig.enabled) return;
    
    const rpm = getRPM();
    
    // Update history (keep last 20 samples = 1 second at 50ms poll)
    setRpmHistory(prev => [...prev.slice(-19), rpm]);
    
  }, [isCapturing, autoDetectConfig.enabled, getRPM]);

  // Auto-detection logic
  useEffect(() => {
    if (!isCapturing || !autoDetectConfig.enabled || rpmHistory.length < 10) return;

    const avgRPM = rpmHistory.reduce((a, b) => a + b, 0) / rpmHistory.length;
    const threshold = autoDetectConfig.rpmThreshold;
    const now = Date.now() / 1000;

    // Check cooldown period
    const inCooldown = (now - lastRunEndTime) < autoDetectConfig.cooldownPeriod;
    
    // Detect run start: RPM crosses threshold going up (and not in cooldown)
    if (!runDetected && !inCooldown && avgRPM > threshold) {
      console.log('[QuickTune] Run detected! Avg RPM:', avgRPM);
      setRunDetected(true);
      toast.success('Dyno run detected!', {
        description: `RPM above ${threshold} - Auto-capture started`
      });
    }
    
    // Detect run end: RPM drops below threshold
    if (runDetected && avgRPM < threshold * 0.5) {
      console.log('[QuickTune] Run ended');
      setRunDetected(false);
      setLastRunEndTime(now);
      toast.info('Dyno run completed');
    }
    
  }, [isCapturing, autoDetectConfig, rpmHistory, runDetected, lastRunEndTime]);

  const postJson = async (url: string, body?: unknown) => {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(text || `Request failed (${res.status})`);
    }
    // Some endpoints return JSON, some may return empty
    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) return res.json();
    return null;
  };

  const runSimulate = async () => {
    setBusy('simulate');
    try {
      const data = await postJson(`${apiUrl}/analyze`, { run_id: runId, mode: 'simulate' });
      if (data?.success) {
        toast.success(`Quick simulation complete: ${data.run_id}`);
      } else {
        toast.error('Simulation failed', { description: data?.error ?? 'Unknown error' });
      }
    } catch (e) {
      toast.error('Simulation request failed', {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy(null);
    }
  };

  const startMonitor = async () => {
    setBusy('monitor');
    try {
      await postJson(`${apiUrl}/hardware/monitor/start`);
      toast.success('Hardware monitor started');
    } catch (e) {
      toast.error('Failed to start monitor', {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy(null);
    }
  };

  const startLive = async () => {
    setBusy('live');
    try {
      await postJson(`${apiUrl}/hardware/live/start`);
      toast.success('Live capture started');
    } catch (e) {
      toast.error('Failed to start live capture', {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card className="border-orange-500/30 bg-gradient-to-br from-orange-500/5 to-transparent">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2">
          <Zap className="h-5 w-5 text-orange-500" />
          Quick Tune
        </CardTitle>
        <CardDescription>
          One-click actions to get data flowing and generate a VE correction run.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Run Detection Alert */}
        {runDetected && (
          <Alert className="border-green-500 bg-green-500/10">
            <Zap className="h-4 w-4 text-green-500 animate-pulse" />
            <AlertDescription>
              Dyno run detected! Auto-capture in progress...
            </AlertDescription>
          </Alert>
        )}

        {/* Auto-detect settings */}
        <div className="space-y-3 p-3 rounded-lg bg-muted/30">
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium">Auto-Detect Settings</Label>
            <Switch
              checked={autoDetectConfig.enabled}
              onCheckedChange={(enabled) => 
                setAutoDetectConfig(prev => ({ ...prev, enabled }))
              }
            />
          </div>
          
          {autoDetectConfig.enabled && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs text-muted-foreground">RPM Threshold</Label>
                  <Input
                    type="number"
                    value={autoDetectConfig.rpmThreshold}
                    onChange={(e) => 
                      setAutoDetectConfig(prev => ({ 
                        ...prev, 
                        rpmThreshold: parseInt(e.target.value, 10) || 2000
                      }))
                    }
                    className="h-8 text-sm"
                  />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Cooldown (sec)</Label>
                  <Input
                    type="number"
                    value={autoDetectConfig.cooldownPeriod}
                    onChange={(e) => 
                      setAutoDetectConfig(prev => ({ 
                        ...prev, 
                        cooldownPeriod: parseInt(e.target.value, 10) || 5
                      }))
                    }
                    className="h-8 text-sm"
                  />
                </div>
              </div>

              {/* Debug display */}
              {process.env.NODE_ENV === 'development' && isCapturing && (
                <div className="text-xs text-muted-foreground p-2 bg-background/50 rounded">
                  RPM: {getRPM().toFixed(0)} | Avg: {rpmHistory.length > 0 ? (rpmHistory.reduce((a,b) => a+b, 0) / rpmHistory.length).toFixed(0) : '0'}
                  {' '}| Detected: {runDetected ? 'YES' : 'NO'}
                </div>
              )}
            </>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
          <div className="md:col-span-1">
            <Label htmlFor="quick-run-id">Run ID</Label>
            <Input
              id="quick-run-id"
              value={runId}
              onChange={(e) => setRunId(e.target.value)}
              placeholder="quick_run_..."
            />
          </div>

          <Button
            onClick={() => void startMonitor()}
            variant="outline"
            disabled={busy !== null}
            className="justify-start"
          >
            <Activity className={`h-4 w-4 mr-2 ${busy === 'monitor' ? 'animate-pulse' : ''}`} />
            Start Monitor
          </Button>

          <Button
            onClick={() => void startLive()}
            variant="outline"
            disabled={busy !== null}
            className="justify-start"
          >
            <Radio className={`h-4 w-4 mr-2 ${busy === 'live' ? 'animate-pulse' : ''}`} />
            Start Live Capture
          </Button>
        </div>

        <div className="flex flex-col md:flex-row gap-3">
          <Button
            onClick={() => void runSimulate()}
            disabled={!runId || busy !== null}
            className="bg-orange-600 hover:bg-orange-700"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${busy === 'simulate' ? 'animate-spin' : ''}`} />
            Run Simulation
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

