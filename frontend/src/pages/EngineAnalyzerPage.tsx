/**
 * EngineAnalyzerPage - Engine Analyzer Pro Integration
 *
 * Browse component library, build engines, and get performance predictions
 * based on Engine Analyzer Pro data.
 */

import { useState, useEffect, useCallback } from 'react';
import { toast } from '@/lib/toast';
import {
    Database,
    Search,
    RefreshCw,
    ChevronRight,
    Zap,
    Layers,
    Settings2,
    Box,
    Car,
    AlertCircle,
    Loader2,
    TrendingUp,
    Gauge,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
import { Skeleton } from '../components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '../components/ui/dialog';

// Types
interface HeadFlowPoint {
    lift_inches: number;
    cfm: number;
}

interface HeadSpec {
    name: string;
    intake_valve_dia: number;
    exhaust_valve_dia: number;
    intake_port_cc?: number;
    exhaust_port_cc?: number;
    chamber_cc?: number;
    intake_flow: HeadFlowPoint[];
    exhaust_flow: HeadFlowPoint[];
    peak_intake_cfm: number;
    peak_exhaust_cfm: number;
    flow_ratio: number;
    notes?: string;
}

interface CamSpec {
    name: string;
    intake_duration_050: number;
    exhaust_duration_050: number;
    intake_lift: number;
    exhaust_lift: number;
    lobe_separation: number;
    overlap: number;
    notes?: string;
}

interface IntakeSpec {
    name: string;
    runner_length_in?: number;
    runner_dia_in?: number;
    throttle_body_dia_in?: number;
    throttle_body_cfm?: number;
    notes?: string;
}

interface ShortBlockSpec {
    name: string;
    bore: number;
    stroke: number;
    rod_length: number;
    cylinders: number;
    compression_ratio?: number;
    displacement_ci: number;
    displacement_cc: number;
    notes?: string;
}

interface CompleteEngineSpec {
    name: string;
    displacement_ci: number;
    displacement_cc: number;
    summary: string;
}

interface LibraryStats {
    total_components: number;
    heads_count: number;
    cams_count: number;
    intakes_count: number;
    short_blocks_count: number;
    engines_count: number;
    skipped_files: number;
    cache_loaded: boolean;
    last_scan_time?: string;
}

interface PredictionResult {
    build_name: string;
    displacement_ci: number;
    compression_ratio?: number;
    rpm_bins: number[];
    map_bins: number[];
    ve_table_front: number[][];
    peak_hp?: number;
    peak_hp_rpm?: number;
    peak_tq?: number;
    peak_tq_rpm?: number;
    prediction_notes: string[];
    confidence_level?: string;
}

type ComponentType = 'engines' | 'heads' | 'cams' | 'intakes' | 'short_blocks';

export default function EngineAnalyzerPage() {
    const [activeTab, setActiveTab] = useState<ComponentType>('engines');
    const [searchQuery, setSearchQuery] = useState('');
    const [stats, setStats] = useState<LibraryStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Component lists
    const [heads, setHeads] = useState<HeadSpec[]>([]);
    const [cams, setCams] = useState<CamSpec[]>([]);
    const [intakes, setIntakes] = useState<IntakeSpec[]>([]);
    const [shortBlocks, setShortBlocks] = useState<ShortBlockSpec[]>([]);
    const [engines, setEngines] = useState<CompleteEngineSpec[]>([]);

    // Selected items for details
    const [selectedHead, setSelectedHead] = useState<HeadSpec | null>(null);
    const [selectedCam, setSelectedCam] = useState<CamSpec | null>(null);
    const [selectedEngine, setSelectedEngine] = useState<CompleteEngineSpec | null>(null);

    // Prediction
    const [prediction, setPrediction] = useState<PredictionResult | null>(null);
    const [predictionLoading, setPredictionLoading] = useState(false);

    // Fetch library stats
    const fetchStats = useCallback(async () => {
        try {
            const response = await fetch('/api/ea/library');
            const data = await response.json();
            if (data.available === false) {
                setError('Engine Analyzer library not found. Check ENALYZER_LIB_DIR configuration.');
                setStats(null);
            } else if (data.stats) {
                setStats(data.stats);
                setError(null);
            }
        } catch (err) {
            setError('Failed to connect to Engine Analyzer API');
            console.error('Error fetching EA library:', err);
        }
    }, []);

    // Fetch components by type
    const fetchComponents = useCallback(async (type: ComponentType, search?: string) => {
        setLoading(true);
        try {
            const endpoint = type.replace('_', '-');
            const url = search
                ? `/api/ea/library/${endpoint}?search=${encodeURIComponent(search)}`
                : `/api/ea/library/${endpoint}`;
            const response = await fetch(url);
            const data = await response.json();

            switch (type) {
                case 'heads':
                    setHeads(data.heads || []);
                    break;
                case 'cams':
                    setCams(data.cams || []);
                    break;
                case 'intakes':
                    setIntakes(data.intakes || []);
                    break;
                case 'short_blocks':
                    setShortBlocks(data.short_blocks || []);
                    break;
                case 'engines':
                    setEngines(data.engines || []);
                    break;
            }
            setError(null);
        } catch (err) {
            setError(`Failed to load ${type}`);
            console.error(`Error fetching ${type}:`, err);
        } finally {
            setLoading(false);
        }
    }, []);

    // Refresh library
    const handleRefresh = async () => {
        setRefreshing(true);
        try {
            await fetch('/api/ea/library/refresh', { method: 'POST' });
            await fetchStats();
            await fetchComponents(activeTab, searchQuery);
            toast.success('Library refreshed');
        } catch (err) {
            toast.error('Failed to refresh library');
        } finally {
            setRefreshing(false);
        }
    };

    // Get prediction for engine
    const getPrediction = async (engineName: string) => {
        setPredictionLoading(true);
        try {
            const response = await fetch('/api/ea/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ engine_name: engineName }),
            });
            const data = await response.json();
            setPrediction(data);
            toast.success(`Prediction generated for ${data.build_name}`);
        } catch (err) {
            toast.error('Failed to generate prediction');
            console.error('Prediction error:', err);
        } finally {
            setPredictionLoading(false);
        }
    };

    // Initial load
    useEffect(() => {
        fetchStats();
    }, [fetchStats]);

    // Load components when tab changes
    useEffect(() => {
        fetchComponents(activeTab, searchQuery);
    }, [activeTab, fetchComponents]);

    // Debounced search
    useEffect(() => {
        const timer = setTimeout(() => {
            fetchComponents(activeTab, searchQuery);
        }, 300);
        return () => clearTimeout(timer);
    }, [searchQuery, activeTab, fetchComponents]);

    return (
        <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Hero Header */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-cyan-500/20 via-blue-500/10 to-purple-500/20 border border-cyan-500/20 p-8">
                <div className="absolute inset-0 bg-grid-white/5 [mask-image:radial-gradient(ellipse_at_center,transparent_20%,black)]" />
                <div className="relative">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-cyan-500/20 rounded-xl">
                                <Database className="h-8 w-8 text-cyan-400" />
                            </div>
                            <div>
                                <h1 className="text-3xl font-bold tracking-tight">Engine Analyzer</h1>
                                <p className="text-muted-foreground">
                                    Browse components, build engines, predict performance
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            {stats && (
                                <Badge variant="secondary" className="text-lg px-4 py-2">
                                    {stats.total_components} components
                                </Badge>
                            )}
                            <Button
                                variant="outline"
                                onClick={handleRefresh}
                                disabled={refreshing}
                            >
                                <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
                                Refresh
                            </Button>
                        </div>
                    </div>

                    {/* Stats badges */}
                    {stats && (
                        <div className="flex flex-wrap gap-2 mt-6">
                            <Badge variant="outline" className="bg-cyan-500/10 text-cyan-300 border-cyan-500/30">
                                <Car className="h-3 w-3 mr-1" /> {stats.engines_count} Engines
                            </Badge>
                            <Badge variant="outline" className="bg-blue-500/10 text-blue-300 border-blue-500/30">
                                <Layers className="h-3 w-3 mr-1" /> {stats.heads_count} Heads
                            </Badge>
                            <Badge variant="outline" className="bg-purple-500/10 text-purple-300 border-purple-500/30">
                                <Settings2 className="h-3 w-3 mr-1" /> {stats.cams_count} Cams
                            </Badge>
                            <Badge variant="outline" className="bg-green-500/10 text-green-300 border-green-500/30">
                                <Gauge className="h-3 w-3 mr-1" /> {stats.intakes_count} Intakes
                            </Badge>
                            <Badge variant="outline" className="bg-orange-500/10 text-orange-300 border-orange-500/30">
                                <Box className="h-3 w-3 mr-1" /> {stats.short_blocks_count} Short Blocks
                            </Badge>
                            {stats.skipped_files > 0 && (
                                <Badge variant="outline" className="bg-yellow-500/10 text-yellow-300 border-yellow-500/30">
                                    <AlertCircle className="h-3 w-3 mr-1" /> {stats.skipped_files} skipped
                                </Badge>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Error Alert */}
            {error && (
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription>{error}</AlertDescription>
                </Alert>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Component Browser */}
                <Card className="lg:col-span-2">
                    <CardHeader className="pb-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle>Component Library</CardTitle>
                                <CardDescription>Browse and select engine components</CardDescription>
                            </div>
                        </div>
                        {/* Search */}
                        <div className="relative mt-4">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                            <Input
                                placeholder="Search components..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-9"
                            />
                        </div>
                    </CardHeader>
                    <CardContent>
                        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as ComponentType)}>
                            <TabsList className="grid grid-cols-5 w-full">
                                <TabsTrigger value="engines" className="text-xs">
                                    <Car className="h-3 w-3 mr-1" />
                                    Engines
                                </TabsTrigger>
                                <TabsTrigger value="heads" className="text-xs">
                                    <Layers className="h-3 w-3 mr-1" />
                                    Heads
                                </TabsTrigger>
                                <TabsTrigger value="cams" className="text-xs">
                                    <Settings2 className="h-3 w-3 mr-1" />
                                    Cams
                                </TabsTrigger>
                                <TabsTrigger value="intakes" className="text-xs">
                                    <Gauge className="h-3 w-3 mr-1" />
                                    Intakes
                                </TabsTrigger>
                                <TabsTrigger value="short_blocks" className="text-xs">
                                    <Box className="h-3 w-3 mr-1" />
                                    Blocks
                                </TabsTrigger>
                            </TabsList>

                            {/* Engines Tab */}
                            <TabsContent value="engines">
                                <ScrollArea className="h-[500px]">
                                    {loading ? (
                                        <div className="space-y-2">
                                            {[...Array(5)].map((_, i) => (
                                                <Skeleton key={i} className="h-16 w-full" />
                                            ))}
                                        </div>
                                    ) : engines.length === 0 ? (
                                        <div className="text-center py-12 text-muted-foreground">
                                            <Car className="h-12 w-12 mx-auto mb-4 opacity-50" />
                                            <p>No engines found</p>
                                        </div>
                                    ) : (
                                        <div className="space-y-2">
                                            {engines.map((engine, idx) => (
                                                <div
                                                    key={idx}
                                                    className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent cursor-pointer transition-colors"
                                                    onClick={() => setSelectedEngine(engine)}
                                                >
                                                    <div className="flex-1">
                                                        <div className="font-medium">{engine.name}</div>
                                                        <div className="text-sm text-muted-foreground">
                                                            {engine.displacement_ci.toFixed(0)}ci ({(engine.displacement_cc / 1000).toFixed(1)}L)
                                                            {engine.summary && ` • ${engine.summary}`}
                                                        </div>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <Button
                                                            size="sm"
                                                            variant="secondary"
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                getPrediction(engine.name);
                                                            }}
                                                            disabled={predictionLoading}
                                                        >
                                                            <Zap className="h-3 w-3 mr-1" />
                                                            Predict
                                                        </Button>
                                                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </ScrollArea>
                            </TabsContent>

                            {/* Heads Tab */}
                            <TabsContent value="heads">
                                <ScrollArea className="h-[500px]">
                                    {loading ? (
                                        <div className="space-y-2">
                                            {[...Array(5)].map((_, i) => (
                                                <Skeleton key={i} className="h-16 w-full" />
                                            ))}
                                        </div>
                                    ) : heads.length === 0 ? (
                                        <div className="text-center py-12 text-muted-foreground">
                                            <Layers className="h-12 w-12 mx-auto mb-4 opacity-50" />
                                            <p>No heads found</p>
                                        </div>
                                    ) : (
                                        <div className="space-y-2">
                                            {heads.map((head, idx) => (
                                                <div
                                                    key={idx}
                                                    className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent cursor-pointer transition-colors"
                                                    onClick={() => setSelectedHead(head)}
                                                >
                                                    <div>
                                                        <div className="font-medium">{head.name}</div>
                                                        <div className="text-sm text-muted-foreground">
                                                            {head.intake_valve_dia}/{head.exhaust_valve_dia}" valves
                                                            {head.peak_intake_cfm > 0 && ` • ${head.peak_intake_cfm.toFixed(0)} CFM`}
                                                            {head.intake_port_cc && ` • ${head.intake_port_cc}cc`}
                                                        </div>
                                                    </div>
                                                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </ScrollArea>
                            </TabsContent>

                            {/* Cams Tab */}
                            <TabsContent value="cams">
                                <ScrollArea className="h-[500px]">
                                    {loading ? (
                                        <div className="space-y-2">
                                            {[...Array(5)].map((_, i) => (
                                                <Skeleton key={i} className="h-16 w-full" />
                                            ))}
                                        </div>
                                    ) : cams.length === 0 ? (
                                        <div className="text-center py-12 text-muted-foreground">
                                            <Settings2 className="h-12 w-12 mx-auto mb-4 opacity-50" />
                                            <p>No cams found</p>
                                        </div>
                                    ) : (
                                        <div className="space-y-2">
                                            {cams.map((cam, idx) => (
                                                <div
                                                    key={idx}
                                                    className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent cursor-pointer transition-colors"
                                                    onClick={() => setSelectedCam(cam)}
                                                >
                                                    <div>
                                                        <div className="font-medium">{cam.name}</div>
                                                        <div className="text-sm text-muted-foreground">
                                                            {cam.intake_duration_050}/{cam.exhaust_duration_050} @ {cam.lobe_separation} LSA
                                                            • {cam.intake_lift}/{cam.exhaust_lift}" lift
                                                        </div>
                                                    </div>
                                                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </ScrollArea>
                            </TabsContent>

                            {/* Intakes Tab */}
                            <TabsContent value="intakes">
                                <ScrollArea className="h-[500px]">
                                    {loading ? (
                                        <div className="space-y-2">
                                            {[...Array(5)].map((_, i) => (
                                                <Skeleton key={i} className="h-16 w-full" />
                                            ))}
                                        </div>
                                    ) : intakes.length === 0 ? (
                                        <div className="text-center py-12 text-muted-foreground">
                                            <Gauge className="h-12 w-12 mx-auto mb-4 opacity-50" />
                                            <p>No intakes found</p>
                                        </div>
                                    ) : (
                                        <div className="space-y-2">
                                            {intakes.map((intake, idx) => (
                                                <div
                                                    key={idx}
                                                    className="p-4 border rounded-lg hover:bg-accent transition-colors"
                                                >
                                                    <div className="font-medium">{intake.name}</div>
                                                    <div className="text-sm text-muted-foreground">
                                                        {intake.throttle_body_cfm && `${intake.throttle_body_cfm} CFM TB`}
                                                        {intake.runner_length_in && ` • ${intake.runner_length_in}" runners`}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </ScrollArea>
                            </TabsContent>

                            {/* Short Blocks Tab */}
                            <TabsContent value="short_blocks">
                                <ScrollArea className="h-[500px]">
                                    {loading ? (
                                        <div className="space-y-2">
                                            {[...Array(5)].map((_, i) => (
                                                <Skeleton key={i} className="h-16 w-full" />
                                            ))}
                                        </div>
                                    ) : shortBlocks.length === 0 ? (
                                        <div className="text-center py-12 text-muted-foreground">
                                            <Box className="h-12 w-12 mx-auto mb-4 opacity-50" />
                                            <p>No short blocks found</p>
                                        </div>
                                    ) : (
                                        <div className="space-y-2">
                                            {shortBlocks.map((block, idx) => (
                                                <div
                                                    key={idx}
                                                    className="p-4 border rounded-lg hover:bg-accent transition-colors"
                                                >
                                                    <div className="font-medium">{block.name}</div>
                                                    <div className="text-sm text-muted-foreground">
                                                        {block.bore}x{block.stroke}" • {block.displacement_ci.toFixed(0)}ci
                                                        • {block.cylinders} cyl
                                                        {block.compression_ratio && ` • ${block.compression_ratio}:1`}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </ScrollArea>
                            </TabsContent>
                        </Tabs>
                    </CardContent>
                </Card>

                {/* Prediction Panel */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <TrendingUp className="h-5 w-5 text-cyan-400" />
                            Performance Prediction
                        </CardTitle>
                        <CardDescription>
                            Select an engine and click Predict
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        {predictionLoading ? (
                            <div className="flex flex-col items-center justify-center py-12">
                                <Loader2 className="h-8 w-8 animate-spin text-cyan-400 mb-4" />
                                <p className="text-muted-foreground">Calculating...</p>
                            </div>
                        ) : prediction ? (
                            <div className="space-y-6">
                                <div>
                                    <h3 className="font-semibold text-lg">{prediction.build_name}</h3>
                                    <p className="text-sm text-muted-foreground">
                                        {prediction.displacement_ci.toFixed(0)}ci
                                        {prediction.compression_ratio && ` • ${prediction.compression_ratio}:1`}
                                    </p>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    {prediction.peak_hp && (
                                        <div className="text-center p-4 bg-cyan-500/10 rounded-lg border border-cyan-500/20">
                                            <div className="text-3xl font-bold text-cyan-400">
                                                {prediction.peak_hp.toFixed(0)}
                                            </div>
                                            <div className="text-sm text-muted-foreground">
                                                HP @ {prediction.peak_hp_rpm}
                                            </div>
                                        </div>
                                    )}
                                    {prediction.peak_tq && (
                                        <div className="text-center p-4 bg-orange-500/10 rounded-lg border border-orange-500/20">
                                            <div className="text-3xl font-bold text-orange-400">
                                                {prediction.peak_tq.toFixed(0)}
                                            </div>
                                            <div className="text-sm text-muted-foreground">
                                                TQ @ {prediction.peak_tq_rpm}
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {prediction.confidence_level && (
                                    <Badge
                                        variant="outline"
                                        className={
                                            prediction.confidence_level === 'high'
                                                ? 'bg-green-500/10 text-green-400 border-green-500/30'
                                                : prediction.confidence_level === 'medium'
                                                    ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30'
                                                    : 'bg-red-500/10 text-red-400 border-red-500/30'
                                        }
                                    >
                                        {prediction.confidence_level} confidence
                                    </Badge>
                                )}

                                {prediction.prediction_notes.length > 0 && (
                                    <div className="space-y-2">
                                        <h4 className="text-sm font-medium text-muted-foreground">Notes</h4>
                                        <ul className="text-sm space-y-1">
                                            {prediction.prediction_notes.map((note, idx) => (
                                                <li key={idx} className="text-muted-foreground">• {note}</li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                                <Zap className="h-12 w-12 mb-4 opacity-50" />
                                <p>Select an engine and click Predict</p>
                                <p className="text-sm mt-2">to see estimated HP/TQ</p>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Head Detail Dialog */}
            <Dialog open={!!selectedHead} onOpenChange={() => setSelectedHead(null)}>
                <DialogContent className="max-w-2xl">
                    <DialogHeader>
                        <DialogTitle>{selectedHead?.name}</DialogTitle>
                        <DialogDescription>Cylinder Head Specifications</DialogDescription>
                    </DialogHeader>
                    {selectedHead && (
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <div className="text-sm font-medium text-muted-foreground">Intake Valve</div>
                                    <div className="text-lg">{selectedHead.intake_valve_dia}"</div>
                                </div>
                                <div>
                                    <div className="text-sm font-medium text-muted-foreground">Exhaust Valve</div>
                                    <div className="text-lg">{selectedHead.exhaust_valve_dia}"</div>
                                </div>
                                {selectedHead.intake_port_cc && (
                                    <div>
                                        <div className="text-sm font-medium text-muted-foreground">Intake Port</div>
                                        <div className="text-lg">{selectedHead.intake_port_cc}cc</div>
                                    </div>
                                )}
                                {selectedHead.chamber_cc && (
                                    <div>
                                        <div className="text-sm font-medium text-muted-foreground">Chamber</div>
                                        <div className="text-lg">{selectedHead.chamber_cc}cc</div>
                                    </div>
                                )}
                                <div>
                                    <div className="text-sm font-medium text-muted-foreground">Peak Intake Flow</div>
                                    <div className="text-lg">{selectedHead.peak_intake_cfm.toFixed(0)} CFM</div>
                                </div>
                                <div>
                                    <div className="text-sm font-medium text-muted-foreground">Flow Ratio</div>
                                    <div className="text-lg">{(selectedHead.flow_ratio * 100).toFixed(0)}%</div>
                                </div>
                            </div>

                            {selectedHead.intake_flow.length > 0 && (
                                <div>
                                    <div className="text-sm font-medium text-muted-foreground mb-2">Flow Curve</div>
                                    <div className="h-32 flex items-end gap-1">
                                        {selectedHead.intake_flow.map((point, idx) => (
                                            <div
                                                key={idx}
                                                className="flex-1 bg-cyan-500/80 rounded-t"
                                                style={{
                                                    height: `${(point.cfm / selectedHead.peak_intake_cfm) * 100}%`,
                                                }}
                                                title={`${point.lift_inches}" lift: ${point.cfm} CFM`}
                                            />
                                        ))}
                                    </div>
                                </div>
                            )}

                            {selectedHead.notes && (
                                <div>
                                    <div className="text-sm font-medium text-muted-foreground mb-1">Notes</div>
                                    <div className="text-sm whitespace-pre-wrap bg-muted p-2 rounded">
                                        {selectedHead.notes}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </DialogContent>
            </Dialog>

            {/* Cam Detail Dialog */}
            <Dialog open={!!selectedCam} onOpenChange={() => setSelectedCam(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{selectedCam?.name}</DialogTitle>
                        <DialogDescription>Camshaft Specifications</DialogDescription>
                    </DialogHeader>
                    {selectedCam && (
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <div className="text-sm font-medium text-muted-foreground">Intake Duration</div>
                                <div className="text-lg">{selectedCam.intake_duration_050}° @ .050"</div>
                            </div>
                            <div>
                                <div className="text-sm font-medium text-muted-foreground">Exhaust Duration</div>
                                <div className="text-lg">{selectedCam.exhaust_duration_050}° @ .050"</div>
                            </div>
                            <div>
                                <div className="text-sm font-medium text-muted-foreground">Intake Lift</div>
                                <div className="text-lg">{selectedCam.intake_lift}"</div>
                            </div>
                            <div>
                                <div className="text-sm font-medium text-muted-foreground">Exhaust Lift</div>
                                <div className="text-lg">{selectedCam.exhaust_lift}"</div>
                            </div>
                            <div>
                                <div className="text-sm font-medium text-muted-foreground">Lobe Separation</div>
                                <div className="text-lg">{selectedCam.lobe_separation}°</div>
                            </div>
                            <div>
                                <div className="text-sm font-medium text-muted-foreground">Overlap</div>
                                <div className="text-lg">{selectedCam.overlap.toFixed(1)}°</div>
                            </div>
                        </div>
                    )}
                </DialogContent>
            </Dialog>

            {/* Engine Detail Dialog */}
            <Dialog open={!!selectedEngine} onOpenChange={() => setSelectedEngine(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{selectedEngine?.name}</DialogTitle>
                        <DialogDescription>Complete Engine Build</DialogDescription>
                    </DialogHeader>
                    {selectedEngine && (
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <div className="text-sm font-medium text-muted-foreground">Displacement</div>
                                    <div className="text-lg">
                                        {selectedEngine.displacement_ci.toFixed(0)}ci / {(selectedEngine.displacement_cc / 1000).toFixed(1)}L
                                    </div>
                                </div>
                            </div>
                            {selectedEngine.summary && (
                                <div>
                                    <div className="text-sm font-medium text-muted-foreground">Summary</div>
                                    <div className="text-sm">{selectedEngine.summary}</div>
                                </div>
                            )}
                            <Button
                                className="w-full"
                                onClick={() => {
                                    getPrediction(selectedEngine.name);
                                    setSelectedEngine(null);
                                }}
                            >
                                <Zap className="h-4 w-4 mr-2" />
                                Get Performance Prediction
                            </Button>
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </div>
    );
}
