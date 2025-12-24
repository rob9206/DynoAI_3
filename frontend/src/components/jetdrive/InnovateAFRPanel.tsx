/**
 * InnovateAFRPanel - Real-time AFR display for Innovate DLG-1/LC-2 wideband
 * 
 * Shows dual-channel AFR gauges with history charts, connection controls,
 * and AFR target comparison. Designed for integration with JetDrive dashboard.
 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Flame, Plug, PlugZap, RefreshCw, Settings2, TrendingUp,
    AlertTriangle, CheckCircle2, XCircle, Gauge
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Slider } from '../ui/slider';
import { useInnovateLive, type InnovateChannelData } from '../../hooks/useInnovateLive';

// AFR color coding based on target
function getAFRColor(afr: number, target: number = 14.7): string {
    const deviation = Math.abs(afr - target);
    const percent = deviation / target;
    
    if (percent < 0.03) return '#22c55e';      // Green - within 3%
    if (percent < 0.07) return '#84cc16';      // Lime - within 7%
    if (percent < 0.10) return '#eab308';      // Yellow - within 10%
    if (percent < 0.15) return '#f97316';      // Orange - within 15%
    return '#ef4444';                           // Red - >15% off
}

// AFR status text
function getAFRStatus(afr: number, target: number = 14.7): { text: string; color: string } {
    const deviation = afr - target;
    const percent = (deviation / target) * 100;
    
    if (Math.abs(percent) < 3) return { text: 'ON TARGET', color: 'text-green-500' };
    if (deviation < 0) return { text: `${Math.abs(percent).toFixed(0)}% RICH`, color: 'text-orange-500' };
    return { text: `${percent.toFixed(0)}% LEAN`, color: 'text-blue-500' };
}

// Gauge component
interface AFRGaugeProps {
    value: number;
    target: number;
    label: string;
    connected: boolean;
    size?: 'sm' | 'md' | 'lg';
}

function AFRGauge({ value, target, label, connected, size = 'md' }: AFRGaugeProps) {
    const sizeMap = { sm: 100, md: 140, lg: 180 };
    const diameter = sizeMap[size];
    const radius = diameter / 2 - 10;
    const circumference = 2 * Math.PI * radius;
    
    // Map AFR to gauge position (10-20 AFR range)
    const minAFR = 10;
    const maxAFR = 20;
    const normalizedValue = Math.max(0, Math.min(1, (value - minAFR) / (maxAFR - minAFR)));
    const strokeDashoffset = circumference * (1 - normalizedValue * 0.75); // 270° arc
    
    const color = connected ? getAFRColor(value, target) : '#6b7280';
    const status = connected ? getAFRStatus(value, target) : { text: 'NO SIGNAL', color: 'text-gray-500' };
    
    return (
        <div className="flex flex-col items-center relative">
            <div className="relative" style={{ width: diameter, height: diameter }}>
                <svg width={diameter} height={diameter} className="transform -rotate-135">
                    {/* Background arc */}
                    <circle
                        cx={diameter / 2}
                        cy={diameter / 2}
                        r={radius}
                        fill="none"
                        stroke="#374151"
                        strokeWidth="8"
                        strokeDasharray={`${circumference * 0.75} ${circumference}`}
                        strokeLinecap="round"
                    />
                    {/* Value arc */}
                    <motion.circle
                        cx={diameter / 2}
                        cy={diameter / 2}
                        r={radius}
                        fill="none"
                        stroke={color}
                        strokeWidth="8"
                        strokeDasharray={`${circumference * 0.75} ${circumference}`}
                        strokeDashoffset={strokeDashoffset}
                        strokeLinecap="round"
                        initial={{ strokeDashoffset: circumference }}
                        animate={{ strokeDashoffset }}
                        transition={{ duration: 0.3 }}
                    />
                    {/* Target marker */}
                    {connected && (
                        <circle
                            cx={diameter / 2}
                            cy={diameter / 2}
                            r={radius}
                            fill="none"
                            stroke="#ffffff"
                            strokeWidth="2"
                            strokeDasharray={`2 ${circumference - 2}`}
                            strokeDashoffset={circumference * (1 - ((target - minAFR) / (maxAFR - minAFR)) * 0.75)}
                            opacity={0.5}
                        />
                    )}
                </svg>
                
                {/* Center display - absolutely positioned over SVG */}
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                    <span className="text-2xl font-bold font-mono" style={{ color }}>
                        {connected ? value.toFixed(1) : '--.-'}
                    </span>
                    <span className="text-xs text-gray-400">AFR</span>
                </div>
            </div>
            
            {/* Label and status */}
            <div className="mt-2 text-center">
                <div className="text-sm font-medium text-gray-300">{label}</div>
                <div className={`text-xs ${status.color}`}>{status.text}</div>
            </div>
        </div>
    );
}

// Mini chart for AFR history
interface AFRChartProps {
    data: { time: number; afr: number }[];
    target: number;
    height?: number;
}

function AFRMiniChart({ data, target, height = 60 }: AFRChartProps) {
    if (data.length < 2) {
        return (
            <div className="flex items-center justify-center h-16 text-gray-500 text-sm">
                Collecting data...
            </div>
        );
    }
    
    const width = 200;
    const padding = 5;
    const chartWidth = width - 2 * padding;
    const chartHeight = height - 2 * padding;
    
    // Calculate bounds
    const afrs = data.map(d => d.afr);
    const minAFR = Math.min(...afrs, target - 2);
    const maxAFR = Math.max(...afrs, target + 2);
    const range = maxAFR - minAFR || 1;
    
    // Generate path
    const points = data.map((d, i) => {
        const x = padding + (i / (data.length - 1)) * chartWidth;
        const y = padding + (1 - (d.afr - minAFR) / range) * chartHeight;
        return `${x},${y}`;
    });
    
    const targetY = padding + (1 - (target - minAFR) / range) * chartHeight;
    
    return (
        <svg width={width} height={height} className="w-full">
            {/* Target line */}
            <line
                x1={padding}
                y1={targetY}
                x2={width - padding}
                y2={targetY}
                stroke="#22c55e"
                strokeWidth="1"
                strokeDasharray="4 2"
                opacity={0.5}
            />
            
            {/* AFR line */}
            <polyline
                fill="none"
                stroke="#f97316"
                strokeWidth="2"
                points={points.join(' ')}
            />
            
            {/* Current value dot */}
            {data.length > 0 && (
                <circle
                    cx={width - padding}
                    cy={padding + (1 - (data[data.length - 1].afr - minAFR) / range) * chartHeight}
                    r="4"
                    fill="#f97316"
                />
            )}
        </svg>
    );
}

// Main panel props
interface InnovateAFRPanelProps {
    apiUrl?: string;
    defaultPort?: string;
    afrTarget?: number;
    showChart?: boolean;
    compact?: boolean;
    onAFRUpdate?: (channelA: InnovateChannelData | null, channelB: InnovateChannelData | null) => void;
}

export function InnovateAFRPanel({
    apiUrl = 'http://127.0.0.1:5001/api/jetdrive',
    defaultPort = 'COM5',
    afrTarget = 14.7,
    showChart = true,
    compact = false,
    onAFRUpdate,
}: InnovateAFRPanelProps) {
    const [showSettings, setShowSettings] = useState(false);
    const [selectedPort, setSelectedPort] = useState(defaultPort);
    const [target, setTarget] = useState(afrTarget);
    
    const {
        isConnected,
        isStreaming,
        port,
        error,
        availablePorts,
        channelA,
        channelB,
        historyA,
        historyB,
        connect,
        disconnect,
        refreshPorts,
        clearHistory,
    } = useInnovateLive({ apiUrl, autoConnect: false });

    // Notify parent of AFR updates
    useEffect(() => {
        if (onAFRUpdate) {
            onAFRUpdate(channelA, channelB);
        }
    }, [channelA, channelB, onAFRUpdate]);

    // Refresh ports on mount
    useEffect(() => {
        refreshPorts();
    }, [refreshPorts]);

    const handleConnect = async () => {
        if (isConnected) {
            await disconnect();
        } else {
            await connect(selectedPort, 'DLG-1');
        }
    };

    if (compact) {
        // Compact view for sidebar or small spaces
        return (
            <Card className="bg-gray-900/50 border-gray-700">
                <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Flame className="h-4 w-4 text-orange-500" />
                            <CardTitle className="text-sm">Wideband AFR</CardTitle>
                        </div>
                        <Badge variant={isConnected ? 'default' : 'secondary'} className="text-xs">
                            {isConnected ? (isStreaming ? 'Live' : 'Connected') : 'Disconnected'}
                        </Badge>
                    </div>
                </CardHeader>
                <CardContent className="pt-0">
                    <div className="grid grid-cols-2 gap-4">
                        <div className="text-center">
                            <div className="text-2xl font-mono font-bold" style={{ color: channelA?.connected ? getAFRColor(channelA.afr, target) : '#6b7280' }}>
                                {channelA?.connected ? channelA.afr.toFixed(1) : '--.-'}
                            </div>
                            <div className="text-xs text-gray-400">Sensor A</div>
                        </div>
                        <div className="text-center">
                            <div className="text-2xl font-mono font-bold" style={{ color: channelB?.connected ? getAFRColor(channelB.afr, target) : '#6b7280' }}>
                                {channelB?.connected ? channelB.afr.toFixed(1) : '--.-'}
                            </div>
                            <div className="text-xs text-gray-400">Sensor B</div>
                        </div>
                    </div>
                    {!isConnected && (
                        <Button
                            size="sm"
                            variant="outline"
                            className="w-full mt-2"
                            onClick={handleConnect}
                        >
                            <Plug className="h-3 w-3 mr-1" />
                            Connect DLG-1
                        </Button>
                    )}
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="bg-gray-900/50 border-gray-700">
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Flame className="h-5 w-5 text-orange-500" />
                        <div>
                            <CardTitle className="text-lg">Innovate Wideband AFR</CardTitle>
                            <CardDescription>DLG-1 Dual Lambda Gauge</CardDescription>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <Badge 
                            variant={isConnected ? (isStreaming ? 'default' : 'secondary') : 'destructive'}
                            className="flex items-center gap-1"
                        >
                            {isConnected ? (
                                isStreaming ? (
                                    <><CheckCircle2 className="h-3 w-3" /> Streaming</>
                                ) : (
                                    <><PlugZap className="h-3 w-3" /> Connected</>
                                )
                            ) : (
                                <><XCircle className="h-3 w-3" /> Disconnected</>
                            )}
                        </Badge>
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setShowSettings(!showSettings)}
                        >
                            <Settings2 className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            </CardHeader>
            
            <CardContent className="space-y-4">
                {/* Settings panel */}
                <AnimatePresence>
                    {showSettings && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                        >
                            <div className="p-3 bg-gray-800/50 rounded-lg space-y-3 mb-4">
                                {/* Port selection */}
                                <div className="flex items-center gap-2">
                                    <Select value={selectedPort} onValueChange={setSelectedPort}>
                                        <SelectTrigger className="flex-1">
                                            <SelectValue placeholder="Select COM port" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {availablePorts.length > 0 ? (
                                                availablePorts.map(p => (
                                                    <SelectItem key={p.port} value={p.port}>
                                                        {p.port} - {p.description}
                                                    </SelectItem>
                                                ))
                                            ) : (
                                                <SelectItem value={defaultPort}>{defaultPort}</SelectItem>
                                            )}
                                        </SelectContent>
                                    </Select>
                                    <Button variant="outline" size="icon" onClick={refreshPorts}>
                                        <RefreshCw className="h-4 w-4" />
                                    </Button>
                                </div>
                                
                                {/* Target AFR slider */}
                                <div className="space-y-1">
                                    <div className="flex justify-between text-xs text-gray-400">
                                        <span>Target AFR</span>
                                        <span className="font-mono">{target.toFixed(1)}</span>
                                    </div>
                                    <Slider
                                        value={[target]}
                                        onValueChange={([v]) => setTarget(v)}
                                        min={10}
                                        max={18}
                                        step={0.1}
                                        className="py-2"
                                    />
                                </div>
                                
                                {/* Connect/Disconnect */}
                                <Button
                                    variant={isConnected ? 'destructive' : 'default'}
                                    className="w-full"
                                    onClick={handleConnect}
                                >
                                    {isConnected ? (
                                        <><XCircle className="h-4 w-4 mr-2" /> Disconnect</>
                                    ) : (
                                        <><Plug className="h-4 w-4 mr-2" /> Connect to {selectedPort}</>
                                    )}
                                </Button>
                                
                                {error && (
                                    <div className="flex items-center gap-2 text-red-400 text-sm">
                                        <AlertTriangle className="h-4 w-4" />
                                        {error}
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
                
                {/* AFR Gauges */}
                <div className="grid grid-cols-2 gap-4">
                    <div className="flex flex-col items-center">
                        <AFRGauge
                            value={channelA?.afr ?? 0}
                            target={target}
                            label="Sensor A (Front)"
                            connected={channelA?.connected ?? false}
                        />
                    </div>
                    <div className="flex flex-col items-center">
                        <AFRGauge
                            value={channelB?.afr ?? 0}
                            target={target}
                            label="Sensor B (Rear)"
                            connected={channelB?.connected ?? false}
                        />
                    </div>
                </div>
                
                {/* History charts */}
                {showChart && isConnected && (
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-1 text-xs text-gray-400">
                                <TrendingUp className="h-3 w-3" />
                                AFR History
                            </div>
                            <Button variant="ghost" size="sm" onClick={clearHistory} className="text-xs h-6">
                                Clear
                            </Button>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-2">
                            <div className="bg-gray-800/30 rounded p-2">
                                <div className="text-xs text-gray-500 mb-1">Sensor A</div>
                                <AFRMiniChart data={historyA} target={target} />
                            </div>
                            <div className="bg-gray-800/30 rounded p-2">
                                <div className="text-xs text-gray-500 mb-1">Sensor B</div>
                                <AFRMiniChart data={historyB} target={target} />
                            </div>
                        </div>
                    </div>
                )}
                
                {/* Quick connect button when not connected */}
                {!isConnected && !showSettings && (
                    <Button
                        variant="outline"
                        className="w-full"
                        onClick={handleConnect}
                    >
                        <Plug className="h-4 w-4 mr-2" />
                        Connect DLG-1 ({selectedPort})
                    </Button>
                )}
            </CardContent>
        </Card>
    );
}

export default InnovateAFRPanel;

