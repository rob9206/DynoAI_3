/**
 * DynoConfigPanel - Display connected Dynoware RT configuration
 * 
 * Shows drum specifications from the backend configuration:
 * - Model & serial number
 * - Drum 1 specs (mass, circumference, inertia)
 * - Network connection info
 * - Power calculation preview
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
    Disc, Info, Server, Wifi, Calculator, RefreshCw, 
    CheckCircle2, AlertCircle, Settings2 
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';

interface DrumSpec {
    serial_number: string;
    mass_slugs: number;
    retarder_mass_slugs: number;
    circumference_ft: number;
    num_tabs: number;
    radius_ft: number;
    inertia_lbft2: number;
    configured: boolean;
}

interface DynoConfigData {
    model: string;
    serial_number: string;
    location: string;
    ip_address: string;
    jetdrive_port: number;
    firmware_version: string;
    atmo_version: string;
    num_modules: number;
    drum1: DrumSpec;
    drum2: DrumSpec;
}

interface DynoConfigPanelProps {
    apiUrl?: string;
    /** Show compact version */
    compact?: boolean;
}

export function DynoConfigPanel({ 
    apiUrl = 'http://127.0.0.1:5001/api/jetdrive',
    compact = false 
}: DynoConfigPanelProps) {
    const [config, setConfig] = useState<DynoConfigData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [connecting, setConnecting] = useState(false);
    const [connected, setConnected] = useState<boolean | null>(null);
    const [capturing, setCapturing] = useState(false);
    const [liveError, setLiveError] = useState<string | null>(null);
    const [channels, setChannels] = useState<Record<string, any>>({});
    const [lastUpdate, setLastUpdate] = useState<string | null>(null);

    const fetchConfig = async () => {
        setLoading(true);
        setError(null);
        
        try {
            const res = await fetch(`${apiUrl}/dyno/config`);
            if (!res.ok) throw new Error('Failed to fetch dyno config');
            
            const data = await res.json();
            if (data.success) {
                setConfig(data.config);
            } else {
                throw new Error(data.error || 'Unknown error');
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load config');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchConfig();
    }, [apiUrl]);

    // Connection helpers
    const handleConnect = async () => {
        setConnecting(true);
        setLiveError(null);
        try {
            const res = await fetch(`${apiUrl}/hardware/connect`, { method: 'POST' });
            const data = await res.json();
            setConnected(Boolean(data.connected));
        } catch (e) {
            setConnected(false);
            setLiveError(e instanceof Error ? e.message : 'Connect failed');
        } finally {
            setConnecting(false);
        }
    };

    const handleStart = async () => {
        setLiveError(null);
        try {
            const res = await fetch(`${apiUrl}/hardware/start`, { method: 'POST' });
            if (!res.ok) throw new Error('Failed to start live capture');
            setCapturing(true);
        } catch (e) {
            setLiveError(e instanceof Error ? e.message : 'Start failed');
        }
    };

    const handleStop = async () => {
        setLiveError(null);
        try {
            const res = await fetch(`${apiUrl}/hardware/stop`, { method: 'POST' });
            if (!res.ok) throw new Error('Failed to stop live capture');
            setCapturing(false);
        } catch (e) {
            setLiveError(e instanceof Error ? e.message : 'Stop failed');
        }
    };

    // Poll live channels when capturing
    useEffect(() => {
        if (!capturing) return;
        let cancelled = false;
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`${apiUrl}/hardware/live/data`);
                if (!res.ok) return;
                const data = await res.json();
                if (cancelled) return;
                setChannels(data.channels || {});
                setLastUpdate(data.last_update || null);
            } catch {
                // ignore transient poll errors
            }
        }, 2000);  // Poll every 2 seconds to avoid rate limits
        return () => {
            cancelled = true;
            clearInterval(interval);
        };
    }, [apiUrl, capturing]);

    if (loading) {
        return (
            <Card className="bg-zinc-900/80 border-zinc-800">
                <CardContent className="py-8 text-center">
                    <RefreshCw className="w-6 h-6 mx-auto mb-2 animate-spin text-zinc-500" />
                    <p className="text-sm text-zinc-500">Loading dyno configuration...</p>
                </CardContent>
            </Card>
        );
    }

    if (error || !config) {
        return (
            <Card className="bg-zinc-900/80 border-zinc-800">
                <CardContent className="py-8 text-center">
                    <AlertCircle className="w-6 h-6 mx-auto mb-2 text-red-500" />
                    <p className="text-sm text-red-400">{error || 'No configuration loaded'}</p>
                    <Button 
                        variant="outline" 
                        size="sm" 
                        className="mt-4"
                        onClick={fetchConfig}
                    >
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Retry
                    </Button>
                </CardContent>
            </Card>
        );
    }

    if (compact) {
        return (
            <Card className="bg-zinc-900/80 border-zinc-800">
                <CardContent className="py-3 px-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <Disc className="w-5 h-5 text-amber-500" />
                            <div>
                                <p className="text-sm font-medium text-zinc-200">{config.model}</p>
                                <p className="text-xs text-zinc-500">{config.location}</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-zinc-400">
                            <span>⌀ {config.drum1?.circumference_ft?.toFixed(3) ?? 'N/A'} ft</span>
                            <span>{config.drum1?.mass_slugs?.toFixed(3) ?? 'N/A'} slugs</span>
                            {config.drum1?.configured ? (
                                <Badge variant="outline" className="text-emerald-400 border-emerald-600">
                                    <CheckCircle2 className="w-3 h-3 mr-1" />
                                    Configured
                                </Badge>
                            ) : (
                                <Badge variant="outline" className="text-amber-400 border-amber-600">
                                    <AlertCircle className="w-3 h-3 mr-1" />
                                    Not Configured
                                </Badge>
                            )}
                        </div>
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="bg-zinc-900/80 border-zinc-800">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Settings2 className="w-5 h-5 text-amber-500" />
                        <CardTitle className="text-lg">Dyno Configuration</CardTitle>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={fetchConfig}
                        >
                            <RefreshCw className="w-4 h-4" />
                        </Button>
                        <Button 
                            variant={connected ? 'outline' : 'default'} 
                            size="sm"
                            onClick={handleConnect}
                            disabled={connecting}
                        >
                            <Wifi className="w-4 h-4 mr-2" />
                            {connecting ? 'Connecting…' : connected ? 'Reconnect' : 'Connect'}
                        </Button>
                        <Button 
                            variant={capturing ? 'outline' : 'default'} 
                            size="sm"
                            onClick={capturing ? handleStop : handleStart}
                        >
                            {capturing ? 'Stop' : 'Start'}
                        </Button>
                    </div>
                </div>
                <CardDescription>
                    Connected dynamometer specifications for power calculations
                </CardDescription>
            </CardHeader>
            
            <CardContent className="space-y-6">
                {/* Device Info */}
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="grid grid-cols-2 gap-4"
                >
                    <div className="space-y-3">
                        <div className="flex items-center gap-2 text-zinc-400">
                            <Server className="w-4 h-4" />
                            <span className="text-xs uppercase tracking-wider">Device</span>
                        </div>
                        <div className="space-y-2 pl-6">
                            <div>
                                <p className="text-lg font-semibold text-amber-400">{config.model}</p>
                                <p className="text-sm text-zinc-500">{config.location}</p>
                            </div>
                            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                                <span className="text-zinc-500">Serial:</span>
                                <span className="text-zinc-300 font-mono">{config.serial_number}</span>
                                <span className="text-zinc-500">DWRT:</span>
                                <span className="text-zinc-300 font-mono text-xs">{config.firmware_version}</span>
                                <span className="text-zinc-500">ATMO:</span>
                                <span className="text-zinc-300 font-mono">{config.atmo_version}</span>
                                <span className="text-zinc-500">Modules:</span>
                                <span className="text-zinc-300">{config.num_modules}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div className="space-y-3">
                        <div className="flex items-center gap-2 text-zinc-400">
                            <Wifi className="w-4 h-4" />
                            <span className="text-xs uppercase tracking-wider">Network</span>
                        </div>
                        <div className="space-y-2 pl-6">
                            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                                <span className="text-zinc-500">IP:</span>
                                <span className="text-zinc-300 font-mono">{config.ip_address}</span>
                                <span className="text-zinc-500">JetDrive:</span>
                                <span className="text-zinc-300 font-mono">UDP {config.jetdrive_port}</span>
                            </div>
                        </div>
                    </div>
                </motion.div>

                {/* Drum 1 Specs */}
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="space-y-3"
                >
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-zinc-400">
                            <Disc className="w-4 h-4" />
                            <span className="text-xs uppercase tracking-wider">Drum 1</span>
                        </div>
                        {config.drum1?.configured ? (
                            <Badge variant="outline" className="text-emerald-400 border-emerald-600">
                                <CheckCircle2 className="w-3 h-3 mr-1" />
                                Configured
                            </Badge>
                        ) : (
                            <Badge variant="outline" className="text-amber-400 border-amber-600">
                                <AlertCircle className="w-3 h-3 mr-1" />
                                Not Configured
                            </Badge>
                        )}
                    </div>
                    
                    <div className="grid grid-cols-3 gap-4 pl-6">
                        <div className="bg-zinc-800/50 rounded-lg p-3 text-center">
                            <p className="text-2xl font-bold text-emerald-400">
                                {config.drum1?.mass_slugs?.toFixed(3) ?? 'N/A'}
                            </p>
                            <p className="text-xs text-zinc-500 mt-1">Mass (slugs)</p>
                        </div>
                        <div className="bg-zinc-800/50 rounded-lg p-3 text-center">
                            <p className="text-2xl font-bold text-cyan-400">
                                {config.drum1?.circumference_ft?.toFixed(3) ?? 'N/A'}
                            </p>
                            <p className="text-xs text-zinc-500 mt-1">Circumference (ft)</p>
                        </div>
                        <div className="bg-zinc-800/50 rounded-lg p-3 text-center">
                            <p className="text-2xl font-bold text-violet-400">
                                {config.drum1?.radius_ft?.toFixed(4) ?? 'N/A'}
                            </p>
                            <p className="text-xs text-zinc-500 mt-1">Radius (ft)</p>
                        </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4 pl-6 text-sm">
                        <div className="flex justify-between">
                            <span className="text-zinc-500">Serial Number:</span>
                            <span className="text-zinc-300 font-mono">{config.drum1?.serial_number ?? 'N/A'}</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-zinc-500">Pickup Tabs:</span>
                            <span className="text-zinc-300">{config.drum1?.num_tabs ?? 'N/A'}</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-zinc-500">Retarder Mass:</span>
                            <span className="text-zinc-300">{config.drum1?.retarder_mass_slugs ?? 0} slugs</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-zinc-500">Inertia:</span>
                            <span className="text-zinc-300">{config.drum1?.inertia_lbft2?.toFixed(4) ?? 'N/A'} lb·ft²</span>
                        </div>
                    </div>
                </motion.div>

                {/* Drum 2 (if configured) */}
                {config.drum2?.configured && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="space-y-3"
                    >
                        <div className="flex items-center gap-2 text-zinc-400">
                            <Disc className="w-4 h-4" />
                            <span className="text-xs uppercase tracking-wider">Drum 2</span>
                        </div>
                        <div className="grid grid-cols-3 gap-4 pl-6">
                            <div className="bg-zinc-800/50 rounded-lg p-3 text-center">
                                <p className="text-xl font-bold text-emerald-400">
                                    {config.drum2?.mass_slugs?.toFixed(3) ?? 'N/A'}
                                </p>
                                <p className="text-xs text-zinc-500 mt-1">Mass (slugs)</p>
                            </div>
                            <div className="bg-zinc-800/50 rounded-lg p-3 text-center">
                                <p className="text-xl font-bold text-cyan-400">
                                    {config.drum2?.circumference_ft?.toFixed(3) ?? 'N/A'}
                                </p>
                                <p className="text-xs text-zinc-500 mt-1">Circumference (ft)</p>
                            </div>
                        </div>
                    </motion.div>
                )}

                {/* Power Calculation Info */}
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    className="bg-zinc-800/30 rounded-lg p-4"
                >
                    <div className="flex items-center gap-2 text-zinc-400 mb-3">
                        <Calculator className="w-4 h-4" />
                        <span className="text-xs uppercase tracking-wider">Power Calculation</span>
                    </div>
                    <div className="space-y-2 text-sm font-mono text-zinc-400">
                        <p>HP = (Force × Velocity) / 550</p>
                        <p className="text-xs text-zinc-500 pl-4">
                            where Velocity = Circumference × RPM / 60
                        </p>
                        <p>Torque = Force × Radius</p>
                        <p className="text-xs text-zinc-500 pl-4">
                            = Force × {config.drum1?.radius_ft?.toFixed(4) ?? 'N/A'} ft
                        </p>
                    </div>
                </motion.div>

                {/* Live Telemetry */}
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.35 }}
                    className="bg-zinc-800/30 rounded-lg p-4"
                >
                    <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2 text-zinc-400">
                            <Info className="w-4 h-4" />
                            <span className="text-xs uppercase tracking-wider">Live Telemetry</span>
                        </div>
                        {lastUpdate && (
                            <span className="text-[10px] text-zinc-500">Last: {lastUpdate}</span>
                        )}
                    </div>
                    {liveError && (
                        <div className="text-xs text-red-400 mb-2">{liveError}</div>
                    )}
                    <div className="grid grid-cols-4 gap-3 text-center">
                        <div className="bg-zinc-900/40 rounded-lg p-3">
                            <p className="text-xs text-zinc-500">RPM</p>
                            <p className="text-lg font-semibold text-emerald-400">
                                {Number(channels?.['Digital RPM 1']?.value ?? channels?.['RPM']?.value ?? 0).toFixed(0)}
                            </p>
                        </div>
                        <div className="bg-zinc-900/40 rounded-lg p-3">
                            <p className="text-xs text-zinc-500">HP</p>
                            <p className="text-lg font-semibold text-cyan-400">
                                {Number(channels?.['Horsepower']?.value ?? 0).toFixed(1)}
                            </p>
                        </div>
                        <div className="bg-zinc-900/40 rounded-lg p-3">
                            <p className="text-xs text-zinc-500">Torque</p>
                            <p className="text-lg font-semibold text-violet-400">
                                {Number(channels?.['Torque']?.value ?? 0).toFixed(1)}
                            </p>
                        </div>
                        <div className="bg-zinc-900/40 rounded-lg p-3">
                            <p className="text-xs text-zinc-500">AFR</p>
                            <p className="text-lg font-semibold text-pink-400">
                                {Number(channels?.['Air/Fuel Ratio 1']?.value ?? channels?.['AFR']?.value ?? 0).toFixed(2)}
                            </p>
                        </div>
                    </div>
                </motion.div>
            </CardContent>
        </Card>
    );
}

export default DynoConfigPanel;

