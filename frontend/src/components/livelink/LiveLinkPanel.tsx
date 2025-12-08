/**
 * LiveLinkPanel - Main dashboard panel for real-time dyno data
 */

import { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Activity, Gauge, Flame, Thermometer, Zap, Wind, Battery, Settings2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Switch } from '../ui/switch';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { LiveLinkStatus } from './LiveLinkStatus';
import { LiveLinkGauge } from './LiveLinkGauge';
import { LiveLinkChart } from './LiveLinkChart';
import { useLiveLink, type LiveLinkChannel } from '../../hooks/useLiveLink';

// Channel configuration with display settings
const CHANNEL_CONFIG: Record<string, {
    icon: typeof Activity;
    color: string;
    min: number;
    max: number;
    warning?: number;
    critical?: number;
    decimals: number;
    target?: number;
}> = {
    'Engine RPM': { icon: Gauge, color: '#4ade80', min: 0, max: 7000, warning: 5500, critical: 6500, decimals: 0 },
    'MAP kPa': { icon: Wind, color: '#60a5fa', min: 20, max: 105, decimals: 1 },
    'TPS': { icon: Activity, color: '#a78bfa', min: 0, max: 100, decimals: 1 },
    'AFR Meas F': { icon: Flame, color: '#f472b6', min: 10, max: 18, warning: 15.5, critical: 16.5, decimals: 2, target: 14.7 },
    'AFR Meas R': { icon: Flame, color: '#fb923c', min: 10, max: 18, warning: 15.5, critical: 16.5, decimals: 2, target: 14.7 },
    'Engine Temp': { icon: Thermometer, color: '#f97316', min: 100, max: 280, warning: 240, critical: 260, decimals: 0 },
    'VBatt': { icon: Battery, color: '#22d3ee', min: 11, max: 15, warning: 12, decimals: 2 },
    'Spark Adv F': { icon: Zap, color: '#facc15', min: 0, max: 45, decimals: 1 },
};

// Gauge presets
const GAUGE_PRESETS = {
    essential: ['Engine RPM', 'AFR Meas F', 'AFR Meas R', 'TPS'],
    full: Object.keys(CHANNEL_CONFIG),
    afr: ['AFR Meas F', 'AFR Meas R', 'Engine RPM', 'MAP kPa'],
    engine: ['Engine RPM', 'Engine Temp', 'VBatt', 'Spark Adv F'],
};

interface LiveLinkPanelProps {
    serverUrl?: string;
    defaultMode?: 'wcf' | 'poll' | 'simulation' | 'auto';
}

export function LiveLinkPanel({
    serverUrl = 'http://127.0.0.1:5003',
    defaultMode = 'simulation',
}: LiveLinkPanelProps) {
    const [selectedChannels, setSelectedChannels] = useState<string[]>(GAUGE_PRESETS.essential);
    const [chartChannel, setChartChannel] = useState<string>('Engine RPM');
    const [showSettings, setShowSettings] = useState(false);

    const {
        isConnected,
        isConnecting,
        connectionError,
        mode,
        channels,
        history,
        connect,
        disconnect,
        requestSnapshot,
        clearHistory,
    } = useLiveLink({
        serverUrl,
        mode: defaultMode,
        autoConnect: false,
    });

    // Get displayed channels with their config
    const displayedChannels = useMemo(() => {
        return selectedChannels
            .filter(name => channels[name] || CHANNEL_CONFIG[name])
            .map(name => ({
                name,
                data: channels[name] || { name, value: 0, units: '', timestamp: 0 },
                config: CHANNEL_CONFIG[name] || { icon: Activity, color: '#888', min: 0, max: 100, decimals: 1 },
            }));
    }, [selectedChannels, channels]);

    // Chart data for selected channel
    const chartData = useMemo(() => {
        return history[chartChannel] || [];
    }, [history, chartChannel]);

    const handlePresetChange = (preset: keyof typeof GAUGE_PRESETS) => {
        setSelectedChannels(GAUGE_PRESETS[preset]);
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
                        <Activity className="h-6 w-6 text-primary" />
                        LiveLink Dashboard
                    </h2>
                    <p className="text-sm text-muted-foreground">
                        Real-time dyno data streaming from Power Core
                    </p>
                </div>

                <div className="flex items-center gap-3">
                    <LiveLinkStatus
                        isConnected={isConnected}
                        isConnecting={isConnecting}
                        mode={mode}
                        error={connectionError}
                        onConnect={connect}
                        onDisconnect={disconnect}
                    />

                    <Button
                        variant="outline"
                        size="icon"
                        onClick={() => setShowSettings(!showSettings)}
                        className={showSettings ? 'bg-primary/10' : ''}
                    >
                        <Settings2 className="h-4 w-4" />
                    </Button>
                </div>
            </div>

            {/* Settings Panel */}
            {showSettings && (
                <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                >
                    <Card className="border-primary/20 bg-primary/5">
                        <CardHeader className="pb-3">
                            <CardTitle className="text-sm">Display Settings</CardTitle>
                        </CardHeader>
                        <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div className="space-y-2">
                                <Label>Gauge Preset</Label>
                                <Select defaultValue="essential" onValueChange={(v) => handlePresetChange(v as keyof typeof GAUGE_PRESETS)}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="essential">Essential (4 gauges)</SelectItem>
                                        <SelectItem value="full">All Channels</SelectItem>
                                        <SelectItem value="afr">AFR Focus</SelectItem>
                                        <SelectItem value="engine">Engine Status</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="space-y-2">
                                <Label>Chart Channel</Label>
                                <Select value={chartChannel} onValueChange={setChartChannel}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {Object.keys(CHANNEL_CONFIG).map(ch => (
                                            <SelectItem key={ch} value={ch}>{ch}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="flex items-center gap-4">
                                <Button variant="outline" size="sm" onClick={requestSnapshot}>
                                    Refresh Data
                                </Button>
                                <Button variant="outline" size="sm" onClick={clearHistory}>
                                    Clear History
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </motion.div>
            )}

            {/* Main Content */}
            <Tabs defaultValue="gauges" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="gauges">Gauges</TabsTrigger>
                    <TabsTrigger value="chart">Live Chart</TabsTrigger>
                    <TabsTrigger value="table">Data Table</TabsTrigger>
                </TabsList>

                {/* Gauges View */}
                <TabsContent value="gauges" className="space-y-4">
                    {!isConnected ? (
                        <Card className="border-dashed">
                            <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                                <Activity className="h-12 w-12 text-muted-foreground mb-4" />
                                <h3 className="text-lg font-medium mb-2">Not Connected</h3>
                                <p className="text-sm text-muted-foreground mb-4 max-w-md">
                                    Connect to LiveLink to start streaming real-time dyno data from Power Core.
                                </p>
                                <Button onClick={connect} disabled={isConnecting}>
                                    {isConnecting ? 'Connecting...' : 'Connect to LiveLink'}
                                </Button>
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            {displayedChannels.map(({ name, data, config }) => (
                                <LiveLinkGauge
                                    key={name}
                                    name={name}
                                    value={data.value}
                                    units={data.units || ''}
                                    min={config.min}
                                    max={config.max}
                                    warningThreshold={config.warning}
                                    criticalThreshold={config.critical}
                                    decimals={config.decimals}
                                    color={config.color}
                                />
                            ))}
                        </div>
                    )}
                </TabsContent>

                {/* Chart View */}
                <TabsContent value="chart">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <LiveLinkChart
                            title={chartChannel}
                            data={chartData}
                            color={CHANNEL_CONFIG[chartChannel]?.color || '#4ade80'}
                            units={channels[chartChannel]?.units || ''}
                            yMin={CHANNEL_CONFIG[chartChannel]?.min}
                            yMax={CHANNEL_CONFIG[chartChannel]?.max}
                            targetValue={CHANNEL_CONFIG[chartChannel]?.target}
                            height={250}
                        />

                        {/* AFR Comparison Chart */}
                        <Card className="border-border/50">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-muted-foreground">
                                    Front vs Rear AFR
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="text-center">
                                        <div className="text-3xl font-mono font-bold text-pink-400">
                                            {(channels['AFR Meas F']?.value || 0).toFixed(2)}
                                        </div>
                                        <div className="text-xs text-muted-foreground">Front Cylinder</div>
                                    </div>
                                    <div className="text-center">
                                        <div className="text-3xl font-mono font-bold text-orange-400">
                                            {(channels['AFR Meas R']?.value || 0).toFixed(2)}
                                        </div>
                                        <div className="text-xs text-muted-foreground">Rear Cylinder</div>
                                    </div>
                                </div>
                                <div className="mt-4 text-center">
                                    <div className="text-sm text-muted-foreground">Difference</div>
                                    <div className="text-xl font-mono font-bold">
                                        {Math.abs((channels['AFR Meas F']?.value || 0) - (channels['AFR Meas R']?.value || 0)).toFixed(2)}
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </TabsContent>

                {/* Data Table View */}
                <TabsContent value="table">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-sm">All Channel Data</CardTitle>
                            <CardDescription>
                                Raw data from all available channels
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="border rounded-lg overflow-hidden">
                                <table className="w-full text-sm">
                                    <thead className="bg-muted/50">
                                        <tr>
                                            <th className="text-left p-3 font-medium">Channel</th>
                                            <th className="text-right p-3 font-medium">Value</th>
                                            <th className="text-left p-3 font-medium">Units</th>
                                            <th className="text-right p-3 font-medium">Last Update</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border">
                                        {Object.values(channels).map((channel: LiveLinkChannel) => (
                                            <tr key={channel.name} className="hover:bg-muted/30">
                                                <td className="p-3 font-medium">{channel.name}</td>
                                                <td className="p-3 text-right font-mono">
                                                    {channel.value.toFixed(CHANNEL_CONFIG[channel.name]?.decimals || 2)}
                                                </td>
                                                <td className="p-3 text-muted-foreground">{channel.units}</td>
                                                <td className="p-3 text-right text-muted-foreground text-xs">
                                                    {new Date(channel.timestamp).toLocaleTimeString()}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}

export default LiveLinkPanel;

