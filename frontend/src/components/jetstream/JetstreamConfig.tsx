/**
 * Jetstream configuration panel
 */

import { useState, useEffect } from 'react';
import { Settings, Save, Loader2, Eye, EyeOff } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Switch } from '../ui/switch';
import { useJetstreamConfig, useUpdateJetstreamConfig } from '../../hooks/useJetstream';
import { toast } from '@/lib/toast';

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
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Jetstream Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="flex justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings className="h-5 w-5" />
          Jetstream Configuration
        </CardTitle>
        <CardDescription>
          Configure your connection to Dynojet Jetstream cloud service
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* API URL */}
        <div className="space-y-2">
          <Label htmlFor="api-url">API URL</Label>
          <Input
            id="api-url"
            type="url"
            placeholder="https://api.jetstream.dynojet.com"
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
          />
        </div>

        {/* API Key */}
        <div className="space-y-2">
          <Label htmlFor="api-key">API Key</Label>
          <div className="relative">
            <Input
              id="api-key"
              type={showApiKey ? 'text' : 'password'}
              placeholder="Enter your API key"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="pr-10"
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
          <p className="text-xs text-muted-foreground">
            Your API key will be masked when displayed
          </p>
        </div>

        {/* Poll Interval */}
        <div className="space-y-2">
          <Label htmlFor="poll-interval">Poll Interval (seconds)</Label>
          <Input
            id="poll-interval"
            type="number"
            min={10}
            max={300}
            value={pollInterval}
            onChange={(e) => setPollInterval(parseInt(e.target.value, 10))}
          />
          <p className="text-xs text-muted-foreground">
            How often to check for new runs (10-300 seconds)
          </p>
        </div>

        {/* Auto Process */}
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label htmlFor="auto-process">Auto Process</Label>
            <p className="text-xs text-muted-foreground">
              Automatically process new runs when discovered
            </p>
          </div>
          <Switch
            id="auto-process"
            checked={autoProcess}
            onCheckedChange={setAutoProcess}
          />
        </div>

        {/* Enabled */}
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label htmlFor="enabled">Enable Jetstream</Label>
            <p className="text-xs text-muted-foreground">
              Start polling for new runs automatically
            </p>
          </div>
          <Switch
            id="enabled"
            checked={enabled}
            onCheckedChange={setEnabled}
          />
        </div>

        {/* Save Button */}
        <Button
          onClick={handleSave}
          disabled={updateConfig.isPending}
          className="w-full"
        >
          {updateConfig.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <Save className="h-4 w-4 mr-2" />
          )}
          Save Configuration
        </Button>
      </CardContent>
    </Card>
  );
}
