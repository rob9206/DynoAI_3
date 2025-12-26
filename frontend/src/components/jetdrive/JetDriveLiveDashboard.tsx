/**
 * JetDriveLiveDashboard - Real-time dashboard for JetDrive dyno data
 * 
 * Reuses LiveLink gauge and chart components with JetDrive data source.
 * Shows atmospheric data (humidity, temp, pressure) alongside dyno channels.
 * Includes integrated audio capture for knock detection.
 */

import { useState, useMemo, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
    Activity, Gauge, Flame, Thermometer, Zap, Wind, Battery,
    Droplets, Radio, Play, Square, RefreshCw, Settings2, Mic, Search
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Badge } from '../ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { LiveLinkGauge } from '../livelink/LiveLinkGauge';
import { LiveLinkChart } from '../livelink/LiveLinkChart';
import { useJetDriveLive, JETDRIVE_CHANNEL_CONFIG, getChannelConfig, type JetDriveChannel } from '../../hooks/useJetDriveLive';
import { AudioCapturePanel } from './AudioCapturePanel';
import { InnovateAFRPanel } from './InnovateAFRPanel';
import type { RecordedAudio } from '../../hooks/useAudioCapture';
import { toast } from '@/lib/toast';
import { useQuery } from '@tanstack/react-query';
import { cn } from '../../lib/utils';

function quantizeToDecimals(value: number, decimals: number): number {
    if (!Number.isFinite(value)) return value;
    const safeDecimals = Math.max(0, decimals);
    const factor = Math.pow(10, safeDecimals);
    return Math.round(value * factor) / factor;
}

// Infer units from channel name or value
function inferUnits(name: string, value: number): string {
    const nameLower = name.toLowerCase();

    // Temperature-like values (15-50 range typically)
    if (nameLower.includes('temp') || (value > 10 && value < 60 && !nameLower.includes('afr'))) {
        return '°C';
    }
    // Pressure-like values (90-110 kPa range)
    if (nameLower.includes('press') || (value > 85 && value < 115)) {
        return 'kPa';
    }
    // Humidity-like values (0-100%)
    if (nameLower.includes('humid')) {
        return '%';
    }
    // AFR-like values (10-18 range)
    if (nameLower.includes('afr') || nameLower.includes('fuel') || (value > 9 && value < 20)) {
        return ':1';
    }
    // Lambda-like values (0.7-1.5 range)
    if (nameLower.includes('lambda') || (value > 0.5 && value < 2.0 && value !== Math.floor(value))) {
        return 'λ';
    }
    // RPM-like values (>100)
    if (nameLower.includes('rpm') || value > 500) {
        return 'rpm';
    }
    // Voltage-like values (0-5V or 10-15V)
    if (nameLower.includes('volt') || nameLower.includes('vbat')) {
        return 'V';
    }

    return '';
}

// Channel icons
const CHANNEL_ICONS: Record<string, typeof Activity> = {
    'Humidity': Droplets,
    'Pressure': Wind,
    'Temperature 1': Thermometer,
    'Temperature 2': Thermometer,
    'Force Drum 1': Zap,
    'Acceleration': Activity,
    'Digital RPM 1': Gauge,
    'Digital RPM 2': Gauge,
    'Air/Fuel Ratio 1': Flame,
    'Air/Fuel Ratio 2': Flame,
    'Lambda 1': Flame,
    'Lambda 2': Flame,
    'AFR 1': Flame,
    'AFR': Flame,
};

// Preset channel groups
const CHANNEL_PRESETS = {
    atmospheric: ['Humidity', 'Pressure', 'Temperature 1', 'Temperature 2'],
    dyno: ['Digital RPM 1', 'Digital RPM 2', 'Force Drum 1', 'Acceleration', 'Horsepower', 'Torque'],
    performance: ['Horsepower', 'Torque', 'MAP kPa', 'TPS', 'IAT', 'VBatt'],
    afr: ['Air/Fuel Ratio 1', 'Air/Fuel Ratio 2', 'Lambda 1', 'Lambda 2'],
    all: Object.keys(JETDRIVE_CHANNEL_CONFIG),
};

interface JetDriveLiveDashboardProps {
    apiUrl?: string;
    autoStart?: boolean;
    /** Callback when audio recording completes */
    onAudioRecorded?: (recording: RecordedAudio) => void;
}

export function JetDriveLiveDashboard({
    apiUrl = 'http://127.0.0.1:5001/api/jetdrive',
    autoStart = false,
    onAudioRecorded,
}: JetDriveLiveDashboardProps) {
    const [selectedPreset, setSelectedPreset] = useState<keyof typeof CHANNEL_PRESETS>('all');
    const [chartChannel, setChartChannel] = useState<string>('');
    const [audioEnabled, setAudioEnabled] = useState(true);

    // Health monitoring
    const { data: health } = useQuery({
        queryKey: ['jetdrive-health', apiUrl],
        queryFn: async () => {
            const res = await fetch(`${apiUrl}/hardware/health`);
            if (!res.ok) throw new Error('Health check failed');
            return res.json();
        },
        refetchInterval: 5000, // Check every 5 seconds
        retry: false,
    });

    const {
        isConnected,
        isCapturing,
        connectionError,
        providerName,
        channelCount,
        channels,
        history,
        startCapture,
        stopCapture,
        clearHistory,
    } = useJetDriveLive({
        apiUrl,
        autoConnect: autoStart,
        pollInterval: 800,
    });

    // Get channels to display based on preset and available data
    const displayedChannels = useMemo(() => {
        const presetChannels = CHANNEL_PRESETS[selectedPreset];
        return Object.entries(channels)
            .filter(([name]) => selectedPreset === 'all' || presetChannels.includes(name))
            .map(([name, data]) => ({
                name,
                data,
                config: getChannelConfig(name),
            }));
    }, [channels, selectedPreset]);

    // Chart data
    const chartData = useMemo(() => {
        if (!chartChannel || !history[chartChannel]) return [];
        return history[chartChannel].map(h => ({
            time: h.time,
            value: h.value,
        }));
    }, [history, chartChannel]);

    // Set default chart channel
    useMemo(() => {
        if (!chartChannel && Object.keys(channels).length > 0) {
            setChartChannel(Object.keys(channels)[0]);
        }
    }, [channels, chartChannel]);

    const handleToggleCapture = async () => {
        try {
            if (isCapturing) {
                await stopCapture();
            } else {
                await startCapture();
            }
        } catch (err) {
            console.error('Toggle capture error:', err);
        }
    };

    // Handle audio recording completion
    const handleAudioRecorded = useCallback((recording: RecordedAudio | null) => {
        if (recording && onAudioRecorded) {
            onAudioRecorded(recording);
        }
    }, [onAudioRecorded]);

    // Handle channel discovery
    const handleDiscoverChannels = async () => {
        try {
            const res = await fetch(`${apiUrl}/hardware/channels/discover`);
            if (!res.ok) throw new Error('Failed to discover channels');
            
            const data = await res.json();
            
            if (data.success) {
                console.log('=== JetDrive Channel Discovery ===');
                console.table(data.channels);
                toast.success(`Found ${data.channel_count} channels`, {
                    description: 'Check browser console for detailed channel information'
                });
            } else {
                toast.error('Channel discovery failed', {
                    description: data.error || 'Unknown error'
                });
            }
        } catch (err) {
            console.error('Channel discovery error:', err);
            toast.error('Failed to discover channels', {
                description: err instanceof Error ? err.message : 'Unknown error'
            });
        }
    };

    return (
        <div className="space-y-6">
            {/* Header with status */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <div className={cn(
                            "w-3 h-3 rounded-full",
                            isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
                        )} />
                        <span className="font-medium">
                            {isConnected ? providerName || 'Connected' : 'Disconnected'}
                        </span>
                        {health && health.healthy && (
                            <span className="text-xs text-muted-foreground">
                                ({health.latency_ms?.toFixed(0)}ms)
                            </span>
                        )}
                    </div>
                    {isConnected && (
                        <Badge variant="secondary">
                            {channelCount} channels
                        </Badge>
                    )}
                    {isCapturing && (
                        <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                            <Radio className="w-3 h-3 mr-1 animate-pulse" />
                            LIVE
                        </Badge>
                    )}
                    {health?.simulated && (
                        <Badge variant="outline" className="text-yellow-500 border-yellow-500/30">
                            SIMULATED
                        </Badge>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    <Select value={selectedPreset} onValueChange={(v) => setSelectedPreset(v as keyof typeof CHANNEL_PRESETS)}>
                        <SelectTrigger className="w-[140px]">
                            <SelectValue placeholder="Channels" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Channels</SelectItem>
                            <SelectItem value="atmospheric">Atmospheric</SelectItem>
                            <SelectItem value="dyno">Dyno</SelectItem>
                            <SelectItem value="afr">AFR / Lambda</SelectItem>
                        </SelectContent>
                    </Select>

                    <Button
                        variant="outline"
                        size="icon"
                        onClick={handleDiscoverChannels}
                        title="Discover available channels"
                    >
                        <Search className="h-4 w-4" />
                    </Button>

                    <Button
                        variant="outline"
                        size="icon"
                        onClick={clearHistory}
                        title="Clear history"
                    >
                        <RefreshCw className="h-4 w-4" />
                    </Button>

                    <Button
                        variant={isCapturing ? "destructive" : "default"}
                        onClick={handleToggleCapture}
                        disabled={!isConnected}
                    >
                        {isCapturing ? (
                            <>
                                <Square className="h-4 w-4 mr-2" />
                                Stop
                            </>
                        ) : (
                            <>
                                <Play className="h-4 w-4 mr-2" />
                                Start Capture
                            </>
                        )}
                    </Button>
                </div>
            </div>

            {/* Error display */}
            {connectionError && (
                <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400">
                    {connectionError}
                </div>
            )}

            {/* Main content */}
            {!isConnected ? (
                <Card>
                    <CardContent className="py-12 text-center">
                        <Activity className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                        <h3 className="text-lg font-medium mb-2">Not Connected</h3>
                        <p className="text-muted-foreground">
                            Start the hardware monitor in the JetDrive Hardware tab to connect.
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <Tabs defaultValue="gauges" className="space-y-4">
                    <TabsList>
                        <TabsTrigger value="gauges">Gauges</TabsTrigger>
                        <TabsTrigger value="wideband" className="flex items-center gap-1.5">
                            <Flame className="h-3.5 w-3.5 text-orange-500" />
                            Wideband
                        </TabsTrigger>
                        <TabsTrigger value="chart">Chart</TabsTrigger>
                        <TabsTrigger value="audio" className="flex items-center gap-1.5">
                            <Mic className="h-3.5 w-3.5" />
                            Audio
                        </TabsTrigger>
                        <TabsTrigger value="table">Table</TabsTrigger>
                    </TabsList>

                    {/* Gauges View */}
                    <TabsContent value="gauges">
                        {displayedChannels.length > 0 ? (
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                                {displayedChannels.map(({ name, data, config }) => {
                                    // Use config label, or derive from channel name
                                    const displayLabel = config.label || name.replace('chan_', 'Ch ').replace(/_/g, ' ');
                                    const displayUnits = config.units || inferUnits(name, data.value);
                                    const quantizedValue = quantizeToDecimals(data.value, config.decimals ?? 1);

                                    return (
                                        <LiveLinkGauge
                                            key={name}
                                            name={displayLabel}
                                            value={quantizedValue}
                                            units={displayUnits}
                                            min={config.min}
                                            max={config.max}
                                            decimals={config.decimals}
                                            color={config.color}
                                            warningThreshold={config.warning}
                                            criticalThreshold={config.critical}
                                        />
                                    );
                                })}
                            </div>
                        ) : (
                            <Card>
                                <CardContent className="py-8 text-center text-muted-foreground">
                                    {isCapturing ? 'Waiting for data...' : 'Click "Start Capture" to view live gauges'}
                                </CardContent>
                            </Card>
                        )}
                    </TabsContent>

                    {/* Wideband AFR View */}
                    <TabsContent value="wideband">
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                            <InnovateAFRPanel
                                apiUrl={apiUrl}
                                defaultPort="COM5"
                                afrTarget={14.7}
                                showChart={true}
                            />
                            <Card className="bg-gray-900/50 border-gray-700">
                                <CardHeader>
                                    <CardTitle className="text-lg flex items-center gap-2">
                                        <Gauge className="h-5 w-5 text-blue-500" />
                                        AFR Tuning Guide
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-3 text-sm">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <div className="font-medium text-green-400">Target Zones</div>
                                            <div className="text-gray-400 space-y-1 mt-1">
                                                <div>Idle: 14.0 - 14.7</div>
                                                <div>Cruise: 14.7 - 15.5</div>
                                                <div>WOT: 12.5 - 13.2</div>
                                            </div>
                                        </div>
                                        <div>
                                            <div className="font-medium text-orange-400">Status Colors</div>
                                            <div className="text-gray-400 space-y-1 mt-1">
                                                <div className="flex items-center gap-2">
                                                    <div className="w-3 h-3 rounded bg-green-500" />
                                                    On Target (±3%)
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <div className="w-3 h-3 rounded bg-yellow-500" />
                                                    Close (±10%)
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <div className="w-3 h-3 rounded bg-red-500" />
                                                    Off Target ({'>'}15%)
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="pt-2 border-t border-gray-700">
                                        <div className="font-medium text-blue-400">Sensor Setup</div>
                                        <div className="text-gray-400 mt-1">
                                            Sensor A = Front Cylinder | Sensor B = Rear Cylinder
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    </TabsContent>

                    {/* Chart View */}
                    <TabsContent value="chart">
                        <Card>
                            <CardHeader className="pb-2">
                                <div className="flex items-center justify-between">
                                    <CardTitle>Real-time Chart</CardTitle>
                                    <Select value={chartChannel} onValueChange={setChartChannel}>
                                        <SelectTrigger className="w-[200px]">
                                            <SelectValue placeholder="Select channel" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {Object.keys(channels).map(name => (
                                                <SelectItem key={name} value={name}>
                                                    {JETDRIVE_CHANNEL_CONFIG[name]?.label || name}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {chartData.length > 0 ? (
                                    <LiveLinkChart
                                        title={JETDRIVE_CHANNEL_CONFIG[chartChannel]?.label || chartChannel}
                                        data={chartData}
                                        color={JETDRIVE_CHANNEL_CONFIG[chartChannel]?.color || '#4ade80'}
                                        units={JETDRIVE_CHANNEL_CONFIG[chartChannel]?.units || ''}
                                        yMin={JETDRIVE_CHANNEL_CONFIG[chartChannel]?.min}
                                        yMax={JETDRIVE_CHANNEL_CONFIG[chartChannel]?.max}
                                        height={300}
                                    />
                                ) : (
                                    <div className="h-[300px] flex items-center justify-center text-muted-foreground">
                                        {isCapturing ? 'Collecting data...' : 'Start capture to view chart'}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Audio View */}
                    <TabsContent value="audio">
                        <AudioCapturePanel
                            isDynoCapturing={isCapturing}
                            onRecordingStop={handleAudioRecorded}
                        />
                    </TabsContent>

                    {/* Table View */}
                    <TabsContent value="table">
                        <Card>
                            <CardHeader>
                                <CardTitle>All Channels</CardTitle>
                                <CardDescription>
                                    {Object.keys(channels).length} channels streaming
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="overflow-x-auto">
                                    <table className="w-full">
                                        <thead>
                                            <tr className="border-b border-border">
                                                <th className="text-left p-3 font-medium">Channel</th>
                                                <th className="text-right p-3 font-medium">Value</th>
                                                <th className="text-left p-3 font-medium">Units</th>
                                                <th className="text-right p-3 font-medium">Last Update</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-border">
                                            {Object.entries(channels).map(([name, ch]) => {
                                                const config = getChannelConfig(name);
                                                const displayLabel = config?.label || name.replace('chan_', 'Channel ').replace(/_/g, ' ');
                                                const displayUnits = config?.units || inferUnits(name, ch.value);
                                                const decimals = config?.decimals ?? 2;
                                                const color = config?.color || '#888';

                                                return (
                                                    <tr key={name} className="hover:bg-muted/30">
                                                        <td className="p-3 font-medium">
                                                            {displayLabel}
                                                            <span className="text-xs text-muted-foreground ml-2">({name})</span>
                                                        </td>
                                                        <td className="p-3 text-right font-mono text-lg" style={{ color }}>
                                                            {ch.value.toFixed(decimals)}
                                                        </td>
                                                        <td className="p-3 text-muted-foreground">
                                                            {displayUnits}
                                                        </td>
                                                        <td className="p-3 text-right text-muted-foreground text-xs">
                                                            {new Date(ch.timestamp).toLocaleTimeString()}
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>
            )}
        </div>
    );
}

export default JetDriveLiveDashboard;

