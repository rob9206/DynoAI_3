/**
 * JetDriveLiveDashboard - Real-time dashboard for JetDrive dyno data
 * 
 * Reuses LiveLink gauge and chart components with JetDrive data source.
 * Shows atmospheric data (humidity, temp, pressure) alongside dyno channels.
 */

import { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
    Activity, Gauge, Flame, Thermometer, Zap, Wind, Battery,
    Droplets, Radio, Play, Square, RefreshCw, Settings2
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Badge } from '../ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { LiveLinkGauge } from '../livelink/LiveLinkGauge';
import { LiveLinkChart } from '../livelink/LiveLinkChart';
import { useJetDriveLive, JETDRIVE_CHANNEL_CONFIG, type JetDriveChannel } from '../../hooks/useJetDriveLive';

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
    dyno: ['Digital RPM 1', 'Digital RPM 2', 'Force Drum 1', 'Acceleration'],
    afr: ['Air/Fuel Ratio 1', 'Air/Fuel Ratio 2', 'Lambda 1', 'Lambda 2'],
    all: Object.keys(JETDRIVE_CHANNEL_CONFIG),
};

interface JetDriveLiveDashboardProps {
    apiUrl?: string;
    autoStart?: boolean;
}

export function JetDriveLiveDashboard({
    apiUrl = 'http://127.0.0.1:5001/api/jetdrive',
    autoStart = false,
}: JetDriveLiveDashboardProps) {
    const [selectedPreset, setSelectedPreset] = useState<keyof typeof CHANNEL_PRESETS>('all');
    const [chartChannel, setChartChannel] = useState<string>('');

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
                config: JETDRIVE_CHANNEL_CONFIG[name] || {
                    label: name,
                    units: '',
                    min: 0,
                    max: 100,
                    decimals: 2,
                    color: '#888',
                },
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

    return (
        <div className="space-y-6">
            {/* Header with status */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                        <span className="font-medium">
                            {isConnected ? providerName || 'Connected' : 'Disconnected'}
                        </span>
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
                        <TabsTrigger value="chart">Chart</TabsTrigger>
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
                                    
                                    return (
                                        <LiveLinkGauge
                                            key={name}
                                            name={displayLabel}
                                            value={data.value}
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
                                                const config = JETDRIVE_CHANNEL_CONFIG[name];
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

