/**
 * Jetstream configuration panel
 */

import { useState, useEffect } from 'react';
import { Settings, Save, Loader2, Eye, EyeOff, Radio, Shield, Clock } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Switch } from '../ui/switch';
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

  // Populate form when config loads
  useEffect(() => {
    if (config) {
      setApiUrl(config.api_url);
      setApiKey(config.api_key);
      setPollInterval(config.poll_interval_seconds);
      setAutoProcess(config.auto_process);
      setEnabled(config.enabled);
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
        </CardTitle>
        <CardDescription className="font-mono text-xs uppercase tracking-wider text-muted-foreground/70">
          Establish Uplink to Jetstream Cloud Service
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6 pt-6">
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
