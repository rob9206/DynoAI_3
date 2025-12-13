/**
 * JetDriveAutoTunePage - JetDrive Auto-Tune Analysis
 * 
 * Provides a complete interface for:
 * - Running simulated or real JetDrive dyno captures
 * - 2D RPM × MAP grid AFR analysis
 * - VE correction calculation and export
 * - Power Vision PVV XML generation
 * - Hardware diagnostics and connection monitoring
 */

import { useState, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
    Gauge, Play, FileDown, Upload, RefreshCw,
    CheckCircle2, XCircle, AlertCircle, Grid3X3,
    FileText, Download, Zap, Radio, Wifi, WifiOff,
    Activity, Server, MonitorCheck, Settings, Search,
    Thermometer, Droplets, Wind
} from 'lucide-react';
import { toast } from 'sonner';

import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { JetDriveLiveDashboard, QuickTunePanel } from '../components/jetdrive';

// API base URL
const API_BASE = 'http://127.0.0.1:5001/api/jetdrive';

interface AnalysisResult {
    success: boolean;
    run_id: string;
    output_dir: string;
    analysis: {
        total_samples: number;
        duration_ms: number;
        peak_hp: number;
        peak_hp_rpm: number;
        peak_tq: number;
        peak_tq_rpm: number;
        overall_status: string;
        lean_cells: number;
        rich_cells: number;
        ok_cells: number;
        no_data_cells: number;
    };
    grid: {
        rpm_bins: number[];
        map_bins: number[];
    };
    ve_grid: { rpm: number; values: number[] }[];
}

interface RunInfo {
    run_id: string;
    timestamp: string;
    peak_hp: number;
    peak_tq: number;
    status: string;
}

interface DiagnosticsCheck {
    name: string;
    status: 'ok' | 'warning' | 'error';
    message: string;
    details: any;
}

interface DiagnosticsResult {
    timestamp: string;
    overall_status: 'ok' | 'error';
    error_count?: number;
    checks: DiagnosticsCheck[];
}

interface Provider {
    provider_id: number;
    provider_id_hex: string;
    name: string;
    host: string;
    port: number;
    channels: { id: number; name: string; unit: number }[];
    channel_count: number;
}

interface MonitorStatus {
    running: boolean;
    last_check: string | null;
    providers: { provider_id: number; name: string; host: string; channel_count: number }[];
    connected: boolean;
    history: { timestamp: string; connected: boolean; provider_count: number }[];
}

interface LiveChannel {
    id: number;
    name: string;
    value: number;
    timestamp: number;
}

interface LiveData {
    capturing: boolean;
    last_update: string | null;
    channels: Record<string, LiveChannel>;
    channel_count: number;
}

// Channel name mappings for display
const CHANNEL_LABELS: Record<string, { label: string; unit: string; icon: string }> = {
    // Atmospheric
    'Humidity': { label: '💧 Humidity', unit: '%', icon: '💧' },
    'Pressure': { label: '🌬️ Pressure', unit: 'kPa', icon: '🌬️' },
    'Temperature 1': { label: '🌡️ Temp 1', unit: '°C', icon: '🌡️' },
    'Temperature 2': { label: '🌡️ Temp 2', unit: '°C', icon: '🌡️' },
    // Dyno
    'Force Drum 1': { label: '⚡ Force', unit: 'lbs', icon: '⚡' },
    'Acceleration': { label: '📈 Accel', unit: 'g', icon: '📈' },
    'Digital RPM 1': { label: '🔄 RPM 1', unit: 'rpm', icon: '🔄' },
    'Digital RPM 2': { label: '🔄 RPM 2', unit: 'rpm', icon: '🔄' },
    // AFR
    'Air/Fuel Ratio 1': { label: '⛽ AFR 1', unit: ':1', icon: '⛽' },
    'Air/Fuel Ratio 2': { label: '⛽ AFR 2', unit: ':1', icon: '⛽' },
    'Lambda 1': { label: 'λ Lambda 1', unit: '', icon: 'λ' },
    'Lambda 2': { label: 'λ Lambda 2', unit: '', icon: 'λ' },
};

// VE Heatmap cell color based on correction value
function getCellColor(value: number): string {
    const delta = (value - 1) * 100;
    if (Math.abs(delta) < 0.5) return 'bg-green-500/20 text-green-400';
    if (delta > 5) return 'bg-red-500/40 text-red-300';
    if (delta > 2) return 'bg-orange-500/30 text-orange-300';
    if (delta < -5) return 'bg-blue-500/40 text-blue-300';
    if (delta < -2) return 'bg-cyan-500/30 text-cyan-300';
    return 'bg-yellow-500/20 text-yellow-300';
}

// Status badge
function StatusBadge({ status }: { status: string }) {
    const colors: Record<string, string> = {
        'LEAN': 'bg-red-500/20 text-red-400 border-red-500/30',
        'RICH': 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        'BALANCED': 'bg-green-500/20 text-green-400 border-green-500/30',
        'OK': 'bg-green-500/20 text-green-400 border-green-500/30',
    };
    return (
        <Badge variant="outline" className={colors[status] || 'bg-muted'}>
            {status}
        </Badge>
    );
}

// Hardware Diagnostics Component
function HardwareTab() {
    const [isDiscovering, setIsDiscovering] = useState(false);
    const [providers, setProviders] = useState<Provider[]>([]);

    // Fetch diagnostics
    const { data: diagnostics, refetch: refetchDiagnostics, isLoading: diagLoading, isError: diagError } = useQuery<DiagnosticsResult>({
        queryKey: ['jetdrive-diagnostics'],
        queryFn: async () => {
            const res = await fetch(`${API_BASE}/hardware/diagnostics`);
            if (!res.ok) {
                throw new Error('Diagnostics endpoint not available');
            }
            return res.json();
        },
        refetchOnWindowFocus: false,
        enabled: false, // Only fetch when user clicks
        retry: 1,
    });

    // Fetch monitor status
    const { data: monitorStatus, refetch: refetchMonitor, isError: monitorError } = useQuery<MonitorStatus>({
        queryKey: ['jetdrive-monitor'],
        queryFn: async () => {
            const res = await fetch(`${API_BASE}/hardware/monitor/status`);
            if (!res.ok) {
                throw new Error('Monitor endpoint not available');
            }
            return res.json();
        },
        refetchInterval: (query) => query.state.data?.running ? 2000 : 5000,
        retry: 1,
    });

    // Fetch live data
    const { data: liveData } = useQuery<LiveData>({
        queryKey: ['jetdrive-live'],
        queryFn: async () => {
            const res = await fetch(`${API_BASE}/hardware/live/data`);
            if (!res.ok) {
                throw new Error('Live data endpoint not available');
            }
            return res.json();
        },
        refetchInterval: (query) => query.state.data?.capturing ? 1000 : false,
        retry: 1,
    });

    // Toggle live capture
    const toggleLiveCapture = async () => {
        const action = liveData?.capturing ? 'stop' : 'start';
        try {
            const res = await fetch(`${API_BASE}/hardware/live/${action}`, { method: 'POST' });
            if (!res.ok) {
                throw new Error(`Failed to ${action} live capture`);
            }
            toast.success(`Live capture ${action}ed`);
        } catch (err) {
            toast.error(`Failed to ${action} live capture`);
        }
    };

    // Discover providers
    const handleDiscover = async () => {
        setIsDiscovering(true);
        try {
            const res = await fetch(`${API_BASE}/hardware/discover?timeout=5`);
            if (!res.ok) {
                throw new Error('Discovery endpoint not available');
            }
            const data = await res.json();
            setProviders(data.providers ?? []);
            if (data.providers_found > 0) {
                toast.success(`Found ${data.providers_found} provider(s)`);
            } else {
                toast.warning('No providers found');
            }
        } catch (err) {
            toast.error('Discovery failed - restart backend server');
            console.error('Discovery error:', err);
        } finally {
            setIsDiscovering(false);
        }
    };

    // Toggle monitor
    const toggleMonitor = async () => {
        const action = monitorStatus?.running ? 'stop' : 'start';
        try {
            const res = await fetch(`${API_BASE}/hardware/monitor/${action}`, { method: 'POST' });
            if (!res.ok) {
                throw new Error(`Failed to ${action} monitor`);
            }
            const data = await res.json();
            toast.success(`Monitor ${data.status}`);
            // Wait a bit then refetch
            setTimeout(() => {
                refetchMonitor();
            }, 500);
        } catch (err) {
            toast.error(`Failed to ${action} monitor - restart backend server`);
            console.error('Monitor toggle error:', err);
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'ok': return <CheckCircle2 className="h-4 w-4 text-green-500" />;
            case 'warning': return <AlertCircle className="h-4 w-4 text-yellow-500" />;
            case 'error': return <XCircle className="h-4 w-4 text-red-500" />;
            default: return null;
        }
    };

    return (
        <div className="space-y-6">
            {/* Backend restart warning */}
            {monitorError && (
                <Alert className="bg-yellow-500/10 border-yellow-500/30">
                    <AlertCircle className="h-4 w-4 text-yellow-500" />
                    <AlertTitle>Backend Restart Required</AlertTitle>
                    <AlertDescription>
                        The hardware diagnostics endpoints are not available. Please restart the backend server
                        to enable hardware testing features.
                    </AlertDescription>
                </Alert>
            )}

            {/* Connection Status Banner */}
            <div className={`p-4 rounded-lg border ${monitorStatus?.connected
                ? 'bg-green-500/10 border-green-500/30'
                : 'bg-muted/30 border-border'
                }`}>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        {monitorStatus?.connected ? (
                            <Wifi className="h-6 w-6 text-green-500 animate-pulse" />
                        ) : (
                            <WifiOff className="h-6 w-6 text-muted-foreground" />
                        )}
                        <div>
                            <h3 className="font-semibold">
                                {monitorStatus?.connected
                                    ? `Connected to ${monitorStatus.providers.length} provider(s)`
                                    : 'Not Connected'}
                            </h3>
                            <p className="text-sm text-muted-foreground">
                                {monitorStatus?.last_check
                                    ? `Last check: ${new Date(monitorStatus.last_check).toLocaleTimeString()}`
                                    : 'Monitor not running'}
                            </p>
                        </div>
                    </div>
                    <Button
                        variant={monitorStatus?.running ? "destructive" : "default"}
                        size="sm"
                        onClick={() => void toggleMonitor()}
                        disabled={monitorError}
                    >
                        <Activity className={`h-4 w-4 mr-2 ${monitorStatus?.running ? 'animate-pulse' : ''}`} />
                        {monitorStatus?.running ? 'Stop Monitor' : 'Start Monitor'}
                    </Button>
                </div>

                {/* Connected Providers */}
                {monitorStatus?.connected && monitorStatus.providers.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-green-500/20">
                        {monitorStatus.providers.map((p) => (
                            <div key={p.provider_id} className="flex items-center gap-2 text-sm">
                                <Server className="h-4 w-4 text-green-500" />
                                <span className="font-medium">{p.name}</span>
                                <span className="text-muted-foreground">({p.host})</span>
                                <Badge variant="secondary" className="ml-auto">
                                    {p.channel_count} channels
                                </Badge>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Live Data Display */}
            {monitorStatus?.connected && (
                <Card className="border-primary/30">
                    <CardHeader className="pb-3">
                        <div className="flex items-center justify-between">
                            <CardTitle className="flex items-center gap-2 text-lg">
                                <Activity className="h-5 w-5 text-primary" />
                                Live Data
                            </CardTitle>
                            <Button
                                variant={liveData?.capturing ? "destructive" : "default"}
                                size="sm"
                                onClick={() => void toggleLiveCapture()}
                            >
                                <Radio className={`h-4 w-4 mr-2 ${liveData?.capturing ? 'animate-pulse' : ''}`} />
                                {liveData?.capturing ? 'Stop Capture' : 'Start Capture'}
                            </Button>
                        </div>
                        {liveData?.last_update && (
                            <CardDescription>
                                Last update: {new Date(liveData.last_update).toLocaleTimeString()} • {liveData.channel_count} channels
                            </CardDescription>
                        )}
                    </CardHeader>
                    <CardContent>
                        {liveData?.capturing && liveData.channel_count > 0 ? (
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                                {Object.values(liveData.channels).map((channel) => {
                                    const config = CHANNEL_LABELS[channel.name] || { label: channel.name, unit: '', icon: '📊' };
                                    return (
                                        <div
                                            key={channel.id}
                                            className="p-3 rounded-lg bg-muted/40 border border-border hover:border-primary/30 transition-colors"
                                        >
                                            <div className="text-xs text-muted-foreground mb-1 truncate">
                                                {config.icon} {config.label}
                                            </div>
                                            <div className="text-xl font-mono font-bold">
                                                {channel.value.toFixed(2)}
                                                <span className="text-xs font-normal text-muted-foreground ml-1">
                                                    {config.unit}
                                                </span>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        ) : liveData?.capturing ? (
                            <div className="text-center py-6 text-muted-foreground">
                                <Radio className="h-8 w-8 mx-auto mb-2 animate-pulse text-primary" />
                                <p>Waiting for data...</p>
                            </div>
                        ) : (
                            <div className="text-center py-6 text-muted-foreground">
                                <Activity className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                <p>Click "Start Capture" to view live channel data</p>
                                <p className="text-xs mt-1">Including humidity, temperature, pressure, AFR, and more</p>
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Diagnostics Card */}
                <Card>
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <CardTitle className="flex items-center gap-2">
                                <MonitorCheck className="h-5 w-5" />
                                System Diagnostics
                            </CardTitle>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                    refetchDiagnostics().catch(() => {
                                        toast.error('Diagnostics failed - restart backend server');
                                    });
                                }}
                                disabled={diagLoading}
                            >
                                <RefreshCw className={`h-4 w-4 mr-2 ${diagLoading ? 'animate-spin' : ''}`} />
                                Run
                            </Button>
                        </div>
                        {diagnostics && (
                            <CardDescription>
                                Status: {diagnostics.overall_status === 'ok' ? (
                                    <span className="text-green-500">All Checks Passed</span>
                                ) : (
                                    <span className="text-red-500">{diagnostics.error_count} Error(s)</span>
                                )}
                            </CardDescription>
                        )}
                    </CardHeader>
                    <CardContent>
                        {diagError ? (
                            <div className="text-center py-8 text-muted-foreground">
                                <XCircle className="h-12 w-12 mx-auto mb-3 text-red-500/50" />
                                <p className="text-red-400">Backend server needs restart</p>
                                <p className="text-xs mt-2">New endpoints are not available</p>
                            </div>
                        ) : diagnostics ? (
                            <div className="space-y-3">
                                {diagnostics.checks.map((check) => (
                                    <div
                                        key={check.name}
                                        className="p-3 rounded-lg bg-muted/30 border border-border"
                                    >
                                        <div className="flex items-center gap-2 mb-1">
                                            {getStatusIcon(check.status)}
                                            <span className="font-medium capitalize">
                                                {check.name.replace(/_/g, ' ')}
                                            </span>
                                        </div>
                                        <p className="text-sm text-muted-foreground">{check.message}</p>

                                        {/* Network interfaces detail */}
                                        {check.name === 'network_interfaces' && Array.isArray(check.details) && (
                                            <div className="mt-2 text-xs space-y-1">
                                                {check.details.map((iface: { ip: string; name: string; is_loopback: boolean }) => (
                                                    <div key={iface.ip} className="flex items-center gap-2">
                                                        <div className={`w-2 h-2 rounded-full ${iface.is_loopback ? 'bg-yellow-500' : 'bg-green-500'}`} />
                                                        <span className="font-mono">{iface.ip}</span>
                                                        <span className="text-muted-foreground">({iface.name})</span>
                                                    </div>
                                                ))}
                                            </div>
                                        )}

                                        {/* Environment config detail */}
                                        {check.name === 'environment' && check.details && (
                                            <div className="mt-2 text-xs font-mono space-y-1">
                                                {Object.entries(check.details as Record<string, unknown>).map(([key, val]) => (
                                                    <div key={key} className="flex gap-2">
                                                        <span className="text-muted-foreground">{key}:</span>
                                                        <span>{String(val)}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-8 text-muted-foreground">
                                <MonitorCheck className="h-12 w-12 mx-auto mb-3 opacity-30" />
                                <p>Click "Run" to check system configuration</p>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Provider Discovery Card */}
                <Card>
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <CardTitle className="flex items-center gap-2">
                                <Search className="h-5 w-5" />
                                Provider Discovery
                            </CardTitle>
                            <Button
                                onClick={handleDiscover}
                                disabled={isDiscovering}
                                className="bg-orange-600 hover:bg-orange-700"
                            >
                                <Radio className={`h-4 w-4 mr-2 ${isDiscovering ? 'animate-pulse' : ''}`} />
                                {isDiscovering ? 'Scanning...' : 'Discover'}
                            </Button>
                        </div>
                        <CardDescription>
                            Scan network for JetDrive providers (dynos)
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        {isDiscovering ? (
                            <div className="text-center py-8">
                                <Radio className="h-12 w-12 mx-auto mb-3 text-orange-500 animate-pulse" />
                                <p className="text-muted-foreground">Scanning for JetDrive providers...</p>
                                <Progress value={66} className="h-2 mt-4 max-w-xs mx-auto" />
                            </div>
                        ) : providers.length > 0 ? (
                            <div className="space-y-4">
                                {providers.map((provider) => (
                                    <div
                                        key={provider.provider_id}
                                        className="p-4 rounded-lg bg-green-500/10 border border-green-500/30"
                                    >
                                        <div className="flex items-center justify-between mb-2">
                                            <div className="flex items-center gap-2">
                                                <Server className="h-5 w-5 text-green-500" />
                                                <span className="font-semibold">{provider.name}</span>
                                            </div>
                                            <Badge variant="outline" className="font-mono">
                                                {provider.provider_id_hex}
                                            </Badge>
                                        </div>
                                        <p className="text-sm text-muted-foreground mb-3">
                                            {provider.host}:{provider.port}
                                        </p>

                                        <div className="border-t border-green-500/20 pt-3">
                                            <p className="text-xs font-medium mb-2">
                                                Channels ({provider.channel_count}):
                                            </p>
                                            <div className="flex flex-wrap gap-1">
                                                {provider.channels.slice(0, 8).map((ch) => (
                                                    <Badge key={ch.id} variant="secondary" className="text-xs">
                                                        {ch.name}
                                                    </Badge>
                                                ))}
                                                {provider.channels.length > 8 && (
                                                    <Badge variant="secondary" className="text-xs">
                                                        +{provider.channels.length - 8} more
                                                    </Badge>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-8 text-muted-foreground">
                                <Search className="h-12 w-12 mx-auto mb-3 opacity-30" />
                                <p>Click "Discover" to scan for JetDrive providers</p>
                                <p className="text-xs mt-2">
                                    Make sure Power Core is running with JetDrive enabled
                                </p>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Troubleshooting Guide */}
            <Alert className="bg-blue-500/10 border-blue-500/30">
                <Settings className="h-4 w-4 text-blue-500" />
                <AlertTitle>Setup Guide</AlertTitle>
                <AlertDescription className="mt-2">
                    <ol className="list-decimal list-inside space-y-1 text-sm">
                        <li>Ensure Dynojet Power Core is running</li>
                        <li>Enable JetDrive in Power Core settings</li>
                        <li>Configure channels: RPM, Torque, AFR, TPS, MAP</li>
                        <li>Run diagnostics to verify network connectivity</li>
                        <li>Use "Discover" to find your dyno on the network</li>
                    </ol>
                </AlertDescription>
            </Alert>
        </div>
    );
}

export default function JetDriveAutoTunePage() {
    const [activeMainTab, setActiveMainTab] = useState('autotune');
    const [runId, setRunId] = useState(`run_${Date.now()}`);
    const [selectedRun, setSelectedRun] = useState<string | null>(null);
    const [pvvContent, setPvvContent] = useState<string>('');
    const [textExportContent, setTextExportContent] = useState<string>('');

    // Fetch available runs
    const { data: statusData, refetch: refetchStatus } = useQuery({
        queryKey: ['jetdrive-status'],
        queryFn: async () => {
            const res = await fetch(`${API_BASE}/status`);
            return res.json();
        },
        refetchInterval: 10000,
    });

    // Fetch selected run details
    const { data: runData, isLoading: runLoading } = useQuery({
        queryKey: ['jetdrive-run', selectedRun],
        queryFn: async () => {
            if (!selectedRun) return null;
            const res = await fetch(`${API_BASE}/run/${selectedRun}`);
            return res.json();
        },
        enabled: !!selectedRun,
    });

    // Run analysis mutation
    const analyzeMutation = useMutation({
        mutationFn: async ({ mode, csvPath }: { mode: string; csvPath?: string }) => {
            const res = await fetch(`${API_BASE}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    run_id: runId,
                    mode,
                    csv_path: csvPath,
                }),
            });
            return res.json();
        },
        onSuccess: (data) => {
            if (data.success) {
                toast.success(`Analysis complete: ${data.run_id}`, {
                    description: `Peak HP: ${data.analysis.peak_hp.toFixed(1)} @ ${data.analysis.peak_hp_rpm} RPM`
                });
                setSelectedRun(data.run_id);
                refetchStatus();
            } else {
                toast.error('Analysis failed', { description: data.error });
            }
        },
        onError: (err) => {
            toast.error('Analysis error', { description: String(err) });
        },
    });

    // Fetch PVV content
    const fetchPvv = async (rid: string) => {
        const res = await fetch(`${API_BASE}/run/${rid}/pvv`);
        const data = await res.json();
        setPvvContent(data.content);
    };

    // Fetch text export content
    const fetchTextExport = async (rid: string) => {
        const res = await fetch(`${API_BASE}/run/${rid}/export-text`);
        const data = await res.json();
        setTextExportContent(data.content);
    };

    // Download PVV file
    const downloadPvv = () => {
        if (!pvvContent || !selectedRun) return;
        const blob = new Blob([pvvContent], { type: 'application/xml' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `VE_Correction_${selectedRun}.pvv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    // Download text export file
    const downloadTextExport = () => {
        if (!textExportContent || !selectedRun) return;
        const blob = new Blob([textExportContent], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `DynoAI_Analysis_${selectedRun}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    };

    useEffect(() => {
        if (selectedRun) {
            fetchPvv(selectedRun);
            fetchTextExport(selectedRun);
        }
    }, [selectedRun]);

    const runs: RunInfo[] = statusData?.runs || [];
    const analysis = runData?.manifest?.analysis;
    const grid = runData?.manifest?.grid;
    const veGrid = runData?.ve_grid || [];

    return (
        <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 p-4 md:p-6">
            {/* Page Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
                        <Gauge className="h-8 w-8 text-orange-500" />
                        JetDrive Auto-Tune
                    </h1>
                    <p className="text-muted-foreground">
                        Hardware diagnostics, capture, and VE correction analysis
                    </p>
                </div>

                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => refetchStatus()}
                    >
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Refresh
                    </Button>
                </div>
            </div>

            {/* Quick Tune Panel - Maximum Automation */}
            <div className="mb-6">
                <QuickTunePanel apiUrl={API_BASE} />
            </div>

            {/* Main Tabs */}
            <Tabs value={activeMainTab} onValueChange={setActiveMainTab} className="w-full">
                <TabsList className="grid w-full grid-cols-3 max-w-lg">
                    <TabsTrigger value="hardware" className="flex items-center gap-2">
                        <Radio className="h-4 w-4" />
                        Hardware
                    </TabsTrigger>
                    <TabsTrigger value="live" className="flex items-center gap-2">
                        <Activity className="h-4 w-4" />
                        Live
                    </TabsTrigger>
                    <TabsTrigger value="autotune" className="flex items-center gap-2">
                        <Zap className="h-4 w-4" />
                        Auto-Tune
                    </TabsTrigger>
                </TabsList>

                {/* Hardware Tab */}
                <TabsContent value="hardware" className="mt-6">
                    <HardwareTab />
                </TabsContent>

                {/* Live Dashboard Tab */}
                <TabsContent value="live" className="mt-6">
                    <JetDriveLiveDashboard apiUrl={API_BASE} />
                </TabsContent>

                {/* Auto-Tune Tab */}
                <TabsContent value="autotune" className="mt-6">
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Left Column - Controls */}
                        <div className="space-y-4">
                            {/* New Analysis Card */}
                            <Card className="border-orange-500/30 bg-gradient-to-br from-orange-500/5 to-transparent">
                                <CardHeader>
                                    <CardTitle className="text-lg flex items-center gap-2">
                                        <Play className="h-5 w-5 text-orange-500" />
                                        New Analysis
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="space-y-2">
                                        <Label htmlFor="run-id">Run ID</Label>
                                        <Input
                                            id="run-id"
                                            value={runId}
                                            onChange={(e) => setRunId(e.target.value)}
                                            placeholder="my_dyno_run"
                                        />
                                    </div>

                                    <div className="grid grid-cols-2 gap-2">
                                        <Button
                                            onClick={() => analyzeMutation.mutate({ mode: 'simulate' })}
                                            disabled={analyzeMutation.isPending}
                                            className="bg-orange-600 hover:bg-orange-700"
                                        >
                                            {analyzeMutation.isPending ? (
                                                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                                            ) : (
                                                <Zap className="h-4 w-4 mr-2" />
                                            )}
                                            Simulate
                                        </Button>
                                        <Button
                                            variant="outline"
                                            disabled={true}
                                            title="Upload CSV first"
                                        >
                                            <Upload className="h-4 w-4 mr-2" />
                                            CSV
                                        </Button>
                                    </div>

                                    {analyzeMutation.isPending && (
                                        <div className="space-y-2">
                                            <Progress value={66} className="h-2" />
                                            <p className="text-xs text-muted-foreground text-center">
                                                Running analysis...
                                            </p>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>

                            {/* Recent Runs */}
                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-lg flex items-center gap-2">
                                        <Grid3X3 className="h-5 w-5" />
                                        Recent Runs
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    {runs.length === 0 ? (
                                        <p className="text-sm text-muted-foreground">No runs yet</p>
                                    ) : (
                                        <div className="space-y-2 max-h-64 overflow-y-auto">
                                            {runs.map((run) => (
                                                <button
                                                    key={run.run_id}
                                                    onClick={() => setSelectedRun(run.run_id)}
                                                    className={`w-full text-left p-3 rounded-lg border transition-all ${selectedRun === run.run_id
                                                        ? 'border-orange-500 bg-orange-500/10'
                                                        : 'border-border hover:border-orange-500/50 hover:bg-muted/50'
                                                        }`}
                                                >
                                                    <div className="flex items-center justify-between">
                                                        <span className="font-medium text-sm">{run.run_id}</span>
                                                        <StatusBadge status={run.status} />
                                                    </div>
                                                    <div className="text-xs text-muted-foreground mt-1">
                                                        {run.peak_hp > 0 && `${run.peak_hp.toFixed(0)} HP`}
                                                        {run.peak_tq > 0 && ` / ${run.peak_tq.toFixed(0)} ft-lb`}
                                                    </div>
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </div>

                        {/* Right Column - Results */}
                        <div className="lg:col-span-2 space-y-4">
                            {selectedRun && runData ? (
                                <>
                                    {/* Analysis Summary */}
                                    <Card>
                                        <CardHeader>
                                            <div className="flex items-center justify-between">
                                                <CardTitle className="flex items-center gap-2">
                                                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                                                    {selectedRun}
                                                </CardTitle>
                                                <StatusBadge status={analysis?.overall_status || 'Unknown'} />
                                            </div>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                                <div className="text-center p-3 bg-muted/30 rounded-lg">
                                                    <div className="text-2xl font-bold text-orange-500">
                                                        {analysis?.peak_hp?.toFixed(1)}
                                                    </div>
                                                    <div className="text-xs text-muted-foreground">
                                                        Peak HP @ {analysis?.peak_hp_rpm} RPM
                                                    </div>
                                                </div>
                                                <div className="text-center p-3 bg-muted/30 rounded-lg">
                                                    <div className="text-2xl font-bold text-blue-500">
                                                        {analysis?.peak_tq?.toFixed(1)}
                                                    </div>
                                                    <div className="text-xs text-muted-foreground">
                                                        Peak TQ @ {analysis?.peak_tq_rpm} RPM
                                                    </div>
                                                </div>
                                                <div className="text-center p-3 bg-muted/30 rounded-lg">
                                                    <div className="text-2xl font-bold">
                                                        {analysis?.total_samples}
                                                    </div>
                                                    <div className="text-xs text-muted-foreground">
                                                        Samples
                                                    </div>
                                                </div>
                                                <div className="text-center p-3 bg-muted/30 rounded-lg">
                                                    <div className="flex justify-center gap-1">
                                                        <span className="text-green-500">{analysis?.ok_cells}</span>
                                                        <span className="text-muted-foreground">/</span>
                                                        <span className="text-red-500">{analysis?.lean_cells}</span>
                                                        <span className="text-muted-foreground">/</span>
                                                        <span className="text-blue-500">{analysis?.rich_cells}</span>
                                                    </div>
                                                    <div className="text-xs text-muted-foreground">
                                                        OK / Lean / Rich
                                                    </div>
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>

                                    {/* Tabs for Grid and Export */}
                                    <Tabs defaultValue="grid" className="w-full">
                                        <TabsList className="grid w-full grid-cols-4">
                                            <TabsTrigger value="grid">
                                                <Grid3X3 className="h-4 w-4 mr-2" />
                                                VE Grid
                                            </TabsTrigger>
                                            <TabsTrigger value="pvv">
                                                <FileDown className="h-4 w-4 mr-2" />
                                                PVV Export
                                            </TabsTrigger>
                                            <TabsTrigger value="text">
                                                <FileText className="h-4 w-4 mr-2" />
                                                Text Export
                                            </TabsTrigger>
                                            <TabsTrigger value="report">
                                                <FileText className="h-4 w-4 mr-2" />
                                                JSON
                                            </TabsTrigger>
                                        </TabsList>

                                        {/* VE Correction Grid */}
                                        <TabsContent value="grid">
                                            <Card>
                                                <CardHeader>
                                                    <CardTitle className="text-sm">
                                                        VE Correction Grid (% change)
                                                    </CardTitle>
                                                    <CardDescription>
                                                        {grid?.rpm_bins?.length} RPM × {grid?.map_bins?.length} MAP bins
                                                    </CardDescription>
                                                </CardHeader>
                                                <CardContent>
                                                    <div className="overflow-x-auto">
                                                        <table className="w-full text-xs">
                                                            <thead>
                                                                <tr>
                                                                    <th className="p-2 text-left bg-muted/50">RPM \ MAP</th>
                                                                    {grid?.map_bins?.map((m: number) => (
                                                                        <th key={m} className="p-2 text-center bg-muted/50 min-w-[60px]">
                                                                            {m} kPa
                                                                        </th>
                                                                    ))}
                                                                </tr>
                                                            </thead>
                                                            <tbody>
                                                                {veGrid.map((row, i) => (
                                                                    <tr key={row.rpm}>
                                                                        <td className="p-2 font-medium bg-muted/30">
                                                                            {row.rpm}
                                                                        </td>
                                                                        {row.values.map((val, j) => {
                                                                            const delta = ((val - 1) * 100);
                                                                            return (
                                                                                <td
                                                                                    key={j}
                                                                                    className={`p-2 text-center font-mono ${getCellColor(val)}`}
                                                                                >
                                                                                    {delta === 0 ? '—' : `${delta > 0 ? '+' : ''}${delta.toFixed(1)}%`}
                                                                                </td>
                                                                            );
                                                                        })}
                                                                    </tr>
                                                                ))}
                                                            </tbody>
                                                        </table>
                                                    </div>

                                                    <div className="mt-4 flex items-center justify-center gap-4 text-xs">
                                                        <div className="flex items-center gap-1">
                                                            <div className="w-4 h-4 bg-red-500/40 rounded" />
                                                            <span>Lean (+)</span>
                                                        </div>
                                                        <div className="flex items-center gap-1">
                                                            <div className="w-4 h-4 bg-green-500/20 rounded" />
                                                            <span>OK</span>
                                                        </div>
                                                        <div className="flex items-center gap-1">
                                                            <div className="w-4 h-4 bg-blue-500/40 rounded" />
                                                            <span>Rich (−)</span>
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        </TabsContent>

                                        {/* PVV Export */}
                                        <TabsContent value="pvv">
                                            <Card>
                                                <CardHeader>
                                                    <div className="flex items-center justify-between">
                                                        <div>
                                                            <CardTitle className="text-sm">Power Vision PVV Export</CardTitle>
                                                            <CardDescription>
                                                                Import directly into Power Core
                                                            </CardDescription>
                                                        </div>
                                                        <Button onClick={downloadPvv} size="sm">
                                                            <Download className="h-4 w-4 mr-2" />
                                                            Download .pvv
                                                        </Button>
                                                    </div>
                                                </CardHeader>
                                                <CardContent>
                                                    <pre className="bg-muted/50 p-4 rounded-lg text-xs overflow-x-auto max-h-96">
                                                        {pvvContent || 'Loading...'}
                                                    </pre>
                                                </CardContent>
                                            </Card>
                                        </TabsContent>

                                        {/* Text Export */}
                                        <TabsContent value="text">
                                            <Card>
                                                <CardHeader>
                                                    <div className="flex items-center justify-between">
                                                        <div>
                                                            <CardTitle className="text-sm">Text Export for AI Analysis</CardTitle>
                                                            <CardDescription>
                                                                Comprehensive text report for sharing with ChatGPT or other AI assistants
                                                            </CardDescription>
                                                        </div>
                                                        <Button onClick={downloadTextExport} size="sm">
                                                            <Download className="h-4 w-4 mr-2" />
                                                            Download .txt
                                                        </Button>
                                                    </div>
                                                </CardHeader>
                                                <CardContent>
                                                    <pre className="bg-muted/50 p-4 rounded-lg text-xs overflow-x-auto max-h-96 whitespace-pre-wrap">
                                                        {textExportContent || 'Loading...'}
                                                    </pre>
                                                </CardContent>
                                            </Card>
                                        </TabsContent>

                                        {/* Report */}
                                        <TabsContent value="report">
                                            <Card>
                                                <CardHeader>
                                                    <CardTitle className="text-sm">JSON Manifest</CardTitle>
                                                    <CardDescription>
                                                        Raw JSON data from analysis
                                                    </CardDescription>
                                                </CardHeader>
                                                <CardContent>
                                                    <div className="bg-muted/50 p-4 rounded-lg text-xs font-mono whitespace-pre-wrap max-h-96 overflow-y-auto">
                                                        {runData?.manifest ? (
                                                            JSON.stringify(runData.manifest, null, 2)
                                                        ) : (
                                                            'Loading...'
                                                        )}
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        </TabsContent>
                                    </Tabs>
                                </>
                            ) : (
                                <Card className="h-full flex items-center justify-center min-h-[400px]">
                                    <CardContent className="text-center">
                                        <Gauge className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" />
                                        <h3 className="text-lg font-medium mb-2">No Run Selected</h3>
                                        <p className="text-sm text-muted-foreground mb-4">
                                            Run a simulation or select a previous run to view results
                                        </p>
                                        <Button
                                            onClick={() => analyzeMutation.mutate({ mode: 'simulate' })}
                                            className="bg-orange-600 hover:bg-orange-700"
                                        >
                                            <Zap className="h-4 w-4 mr-2" />
                                            Run Simulation
                                        </Button>
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                    </div>

                    {/* Info Alert */}
                    <Alert className="bg-orange-500/10 border-orange-500/30">
                        <AlertCircle className="h-4 w-4 text-orange-500" />
                        <AlertTitle>JetDrive Auto-Tune</AlertTitle>
                        <AlertDescription>
                            This tool analyzes dyno captures using a 2D RPM × MAP grid and calculates
                            VE corrections using DynoAI's "7% per AFR point" formula. Export corrections
                            directly to Power Vision PVV format for immediate application.
                        </AlertDescription>
                    </Alert>
                </TabsContent>
            </Tabs>
        </div>
    );
}

