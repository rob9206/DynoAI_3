/**
 * DynoConnectionSetup - Step 1 of the Setup Wizard
 * 
 * Allows users to configure and test their dyno connection:
 * - IP address input
 * - Network interface selection
 * - Connection test with status feedback
 * - Display of dyno info on successful connection
 */

import { useState, useCallback, useEffect } from 'react';
import { Wifi, WifiOff, RefreshCw, CheckCircle2, AlertCircle, Server, Disc } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import type { DynoConnectionConfig } from '../../types/bikeConfig';

interface DynoInfo {
  model: string;
  serial_number: string;
  location: string;
  firmware_version: string;
  drum1?: {
    mass_slugs: number;
    circumference_ft: number;
    configured: boolean;
  };
}

interface DynoConnectionSetupProps {
  config: DynoConnectionConfig;
  onChange: (config: DynoConnectionConfig) => void;
  onConnectionSuccess: (info: DynoInfo) => void;
  apiUrl?: string;
}

export function DynoConnectionSetup({
  config,
  onChange,
  onConnectionSuccess,
  apiUrl = 'http://127.0.0.1:5001/api/jetdrive',
}: DynoConnectionSetupProps) {
  const [testing, setTesting] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dynoInfo, setDynoInfo] = useState<DynoInfo | null>(null);
  const [networkInterfaces, setNetworkInterfaces] = useState<string[]>([]);

  // Fetch available network interfaces on mount
  useEffect(() => {
    const fetchInterfaces = async () => {
      try {
        const res = await fetch(`${apiUrl}/hardware/interfaces`);
        if (res.ok) {
          const data = await res.json();
          if (data.interfaces) {
            setNetworkInterfaces(data.interfaces);
          }
        }
      } catch {
        // Silently fail - user can enter manually
      }
    };
    fetchInterfaces();
  }, [apiUrl]);

  const handleIpChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...config, ipAddress: e.target.value });
    setConnectionStatus('idle');
    setErrorMessage(null);
  }, [config, onChange]);

  const handleInterfaceChange = useCallback((value: string) => {
    onChange({ ...config, networkInterface: value });
    setConnectionStatus('idle');
    setErrorMessage(null);
  }, [config, onChange]);

  const handlePortChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const port = parseInt(e.target.value, 10);
    if (!isNaN(port) && port > 0 && port <= 65535) {
      onChange({ ...config, port });
    }
  }, [config, onChange]);

  const testConnection = useCallback(async () => {
    setTesting(true);
    setErrorMessage(null);
    setConnectionStatus('idle');

    try {
      // First, try to connect/discover
      const connectRes = await fetch(`${apiUrl}/hardware/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ip_address: config.ipAddress,
          interface: config.networkInterface,
          port: config.port,
        }),
      });

      if (!connectRes.ok) {
        const errorData = await connectRes.json().catch(() => ({}));
        throw new Error(errorData.error || `Connection failed (${connectRes.status})`);
      }

      // Fetch dyno config to get info
      const configRes = await fetch(`${apiUrl}/dyno/config`);
      if (!configRes.ok) {
        throw new Error('Failed to fetch dyno configuration');
      }

      const configData = await configRes.json();
      if (configData.success && configData.config) {
        const info: DynoInfo = {
          model: configData.config.model,
          serial_number: configData.config.serial_number,
          location: configData.config.location,
          firmware_version: configData.config.firmware_version,
          drum1: configData.config.drum1,
        };
        setDynoInfo(info);
        setConnectionStatus('success');
        onConnectionSuccess(info);
      } else {
        throw new Error('Invalid configuration response');
      }
    } catch (err) {
      setConnectionStatus('error');
      setErrorMessage(err instanceof Error ? err.message : 'Connection failed');
    } finally {
      setTesting(false);
    }
  }, [apiUrl, config, onConnectionSuccess]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center">
          <Wifi className="w-8 h-8 text-cyan-400" />
        </div>
        <h2 className="text-2xl font-bold text-white mb-2">Connect Your Dyno</h2>
        <p className="text-zinc-400 text-sm max-w-md mx-auto">
          Enter your dyno's network settings to establish a JetDrive connection
        </p>
      </div>

      {/* Connection Form */}
      <Card className="bg-zinc-900/80 border-zinc-800">
        <CardHeader className="pb-4">
          <CardTitle className="text-lg flex items-center gap-2">
            <Server className="w-5 h-5 text-blue-400" />
            Network Settings
          </CardTitle>
          <CardDescription>
            Configure the connection to your Dynojet dynamometer
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* IP Address */}
          <div className="space-y-2">
            <Label htmlFor="ip-address">Dyno IP Address</Label>
            <Input
              id="ip-address"
              type="text"
              placeholder="192.168.1.100"
              value={config.ipAddress}
              onChange={handleIpChange}
              className="bg-zinc-800/50 border-zinc-700"
            />
            <p className="text-xs text-zinc-500">
              The IP address of your Dynojet dynamometer
            </p>
          </div>

          {/* Network Interface */}
          <div className="space-y-2">
            <Label htmlFor="network-interface">Network Interface</Label>
            {networkInterfaces.length > 0 ? (
              <Select value={config.networkInterface} onValueChange={handleInterfaceChange}>
                <SelectTrigger className="bg-zinc-800/50 border-zinc-700 w-full">
                  <SelectValue placeholder="Select network interface" />
                </SelectTrigger>
                <SelectContent>
                  {networkInterfaces.map((iface) => (
                    <SelectItem key={iface} value={iface}>
                      {iface}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <Input
                id="network-interface"
                type="text"
                placeholder="192.168.1.50"
                value={config.networkInterface}
                onChange={(e) => handleInterfaceChange(e.target.value)}
                className="bg-zinc-800/50 border-zinc-700"
              />
            )}
            <p className="text-xs text-zinc-500">
              Your computer's IP on the same network as the dyno
            </p>
          </div>

          {/* Port */}
          <div className="space-y-2">
            <Label htmlFor="port">JetDrive Port</Label>
            <Input
              id="port"
              type="number"
              value={config.port}
              onChange={handlePortChange}
              className="bg-zinc-800/50 border-zinc-700 w-32"
            />
            <p className="text-xs text-zinc-500">
              Default: 22344 (usually doesn't need to change)
            </p>
          </div>

          {/* Test Connection Button */}
          <div className="pt-4">
            <Button
              onClick={testConnection}
              disabled={testing || !config.ipAddress}
              className="w-full h-12 text-lg font-semibold bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500"
            >
              {testing ? (
                <>
                  <RefreshCw className="w-5 h-5 mr-2 animate-spin" />
                  Testing Connection...
                </>
              ) : (
                <>
                  <Wifi className="w-5 h-5 mr-2" />
                  Test Connection
                </>
              )}
            </Button>
          </div>

          {/* Error Message */}
          {connectionStatus === 'error' && errorMessage && (
            <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/30">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-red-400">Connection Failed</p>
                  <p className="text-xs text-red-300/70 mt-1">{errorMessage}</p>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Success - Dyno Info */}
      {connectionStatus === 'success' && dynoInfo && (
        <Card className="bg-gradient-to-br from-green-500/10 to-emerald-500/10 border-green-500/30">
          <CardContent className="pt-6">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                <CheckCircle2 className="w-6 h-6 text-green-400" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-green-400 mb-3">
                  Connected Successfully
                </h3>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Model</p>
                    <p className="text-white font-medium">{dynoInfo.model}</p>
                  </div>
                  <div>
                    <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Serial</p>
                    <p className="text-white font-mono text-sm">{dynoInfo.serial_number}</p>
                  </div>
                  <div>
                    <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Location</p>
                    <p className="text-white">{dynoInfo.location}</p>
                  </div>
                  <div>
                    <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Firmware</p>
                    <p className="text-white font-mono text-sm">{dynoInfo.firmware_version}</p>
                  </div>
                </div>

                {dynoInfo.drum1 && (
                  <div className="mt-4 pt-4 border-t border-zinc-700/50">
                    <div className="flex items-center gap-2 mb-3">
                      <Disc className="w-4 h-4 text-amber-400" />
                      <span className="text-sm text-zinc-400">Drum Specifications</span>
                      {dynoInfo.drum1.configured ? (
                        <Badge variant="outline" className="text-green-400 border-green-500/30 text-xs">
                          Configured
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-amber-400 border-amber-500/30 text-xs">
                          Not Configured
                        </Badge>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-zinc-500">Mass:</span>
                        <span className="text-white ml-2">{dynoInfo.drum1.mass_slugs?.toFixed(3)} slugs</span>
                      </div>
                      <div>
                        <span className="text-zinc-500">Circumference:</span>
                        <span className="text-white ml-2">{dynoInfo.drum1.circumference_ft?.toFixed(3)} ft</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default DynoConnectionSetup;
