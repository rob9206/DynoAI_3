/**
 * ComponentBrowser - Engine Analyzer Component Library Browser
 *
 * Tabbed interface for browsing engine components:
 * - Heads (cylinder heads with flow data)
 * - Cams (camshaft specifications)
 * - Intakes (intake manifolds)
 * - Short Blocks (bottom end specs)
 * - Complete Engines (full builds)
 *
 * Features:
 * - Search and filter
 * - Component detail view
 * - Flow curve visualization for heads
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Search,
  Database,
  RefreshCw,
  ChevronRight,
  Gauge,
  Settings2,
  Box,
  Layers,
  Car,
  AlertCircle,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { ScrollArea } from '../ui/scroll-area';
import { Skeleton } from '../ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';

// Types matching backend schemas
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
  intake_valve_angle?: number;
  exhaust_valve_angle?: number;
  intake_flow: HeadFlowPoint[];
  exhaust_flow: HeadFlowPoint[];
  peak_intake_cfm: number;
  peak_exhaust_cfm: number;
  flow_ratio: number;
  notes?: string;
  source_file?: string;
}

interface CamSpec {
  name: string;
  intake_duration_050: number;
  exhaust_duration_050: number;
  intake_lift: number;
  exhaust_lift: number;
  lobe_separation: number;
  advance: number;
  rocker_ratio_int: number;
  rocker_ratio_exh: number;
  overlap: number;
  intake_centerline: number;
  exhaust_centerline: number;
  notes?: string;
  source_file?: string;
}

interface IntakeSpec {
  name: string;
  runner_length_in?: number;
  runner_dia_in?: number;
  throttle_body_dia_in?: number;
  throttle_body_cfm?: number;
  manifold_type?: string;
  notes?: string;
  source_file?: string;
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
  rod_ratio: number;
  notes?: string;
  source_file?: string;
}

interface CompleteEngineSpec {
  name: string;
  short_block: ShortBlockSpec;
  heads: HeadSpec;
  cam: CamSpec;
  intake?: IntakeSpec;
  displacement_ci: number;
  displacement_cc: number;
  summary: string;
  source_file?: string;
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

type ComponentType = 'heads' | 'cams' | 'intakes' | 'short_blocks' | 'engines';

interface ComponentBrowserProps {
  onSelectEngine?: (engine: CompleteEngineSpec) => void;
  onSelectComponents?: (components: {
    head?: HeadSpec;
    cam?: CamSpec;
    intake?: IntakeSpec;
    shortBlock?: ShortBlockSpec;
  }) => void;
}

export function ComponentBrowser({
  onSelectEngine,
  onSelectComponents,
}: ComponentBrowserProps) {
  const [activeTab, setActiveTab] = useState<ComponentType>('engines');
  const [searchQuery, setSearchQuery] = useState('');
  const [stats, setStats] = useState<LibraryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Component lists
  const [heads, setHeads] = useState<HeadSpec[]>([]);
  const [cams, setCams] = useState<CamSpec[]>([]);
  const [intakes, setIntakes] = useState<IntakeSpec[]>([]);
  const [shortBlocks, setShortBlocks] = useState<ShortBlockSpec[]>([]);
  const [engines, setEngines] = useState<CompleteEngineSpec[]>([]);

  // Detail dialog
  const [selectedHead, setSelectedHead] = useState<HeadSpec | null>(null);
  const [selectedCam, setSelectedCam] = useState<CamSpec | null>(null);
  const [selectedEngine, setSelectedEngine] = useState<CompleteEngineSpec | null>(null);

  // Fetch library stats
  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch('/api/ea/library');
      const data = await response.json();
      if (data.stats) {
        setStats(data.stats);
      }
      setError(null);
    } catch (err) {
      setError('Failed to load library');
      console.error('Error fetching EA library:', err);
    }
  }, []);

  // Fetch components by type
  const fetchComponents = useCallback(async (type: ComponentType, search?: string) => {
    setLoading(true);
    try {
      const url = search
        ? `/api/ea/library/${type.replace('_', '-')}?search=${encodeURIComponent(search)}`
        : `/api/ea/library/${type.replace('_', '-')}`;
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
  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await fetch('/api/ea/library/refresh', { method: 'POST' });
      await fetchStats();
      await fetchComponents(activeTab, searchQuery);
    } catch (err) {
      setError('Failed to refresh library');
    } finally {
      setRefreshing(false);
    }
  }, [activeTab, searchQuery, fetchStats, fetchComponents]);

  // Initial load
  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // Load components when tab changes
  useEffect(() => {
    fetchComponents(activeTab, searchQuery);
  }, [activeTab, fetchComponents, searchQuery]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery) {
        fetchComponents(activeTab, searchQuery);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, activeTab, fetchComponents]);

  // Filter helpers
  const filteredHeads = useMemo(() => {
    if (!searchQuery) return heads;
    const q = searchQuery.toLowerCase();
    return heads.filter((h) => h.name.toLowerCase().includes(q));
  }, [heads, searchQuery]);

  const filteredCams = useMemo(() => {
    if (!searchQuery) return cams;
    const q = searchQuery.toLowerCase();
    return cams.filter((c) => c.name.toLowerCase().includes(q));
  }, [cams, searchQuery]);

  const filteredIntakes = useMemo(() => {
    if (!searchQuery) return intakes;
    const q = searchQuery.toLowerCase();
    return intakes.filter((i) => i.name.toLowerCase().includes(q));
  }, [intakes, searchQuery]);

  const filteredShortBlocks = useMemo(() => {
    if (!searchQuery) return shortBlocks;
    const q = searchQuery.toLowerCase();
    return shortBlocks.filter((s) => s.name.toLowerCase().includes(q));
  }, [shortBlocks, searchQuery]);

  const filteredEngines = useMemo(() => {
    if (!searchQuery) return engines;
    const q = searchQuery.toLowerCase();
    return engines.filter((e) => e.name.toLowerCase().includes(q));
  }, [engines, searchQuery]);

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Engine Analyzer Library
            </CardTitle>
            <CardDescription>
              Browse and select engine components for builds and predictions
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {stats && (
              <Badge variant="secondary">
                {stats.total_components} components
              </Badge>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={refreshing}
            >
              <RefreshCw className={`h-4 w-4 mr-1 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {/* Search */}
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search components..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>

        {error && (
          <div className="flex items-center gap-2 p-3 mb-4 bg-destructive/10 text-destructive rounded-md">
            <AlertCircle className="h-4 w-4" />
            {error}
          </div>
        )}

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as ComponentType)}>
          <TabsList className="grid grid-cols-5 w-full">
            <TabsTrigger value="engines" className="flex items-center gap-1">
              <Car className="h-4 w-4" />
              <span className="hidden sm:inline">Engines</span>
              {stats && <Badge variant="outline" className="ml-1 hidden md:inline">{stats.engines_count}</Badge>}
            </TabsTrigger>
            <TabsTrigger value="heads" className="flex items-center gap-1">
              <Layers className="h-4 w-4" />
              <span className="hidden sm:inline">Heads</span>
              {stats && <Badge variant="outline" className="ml-1 hidden md:inline">{stats.heads_count}</Badge>}
            </TabsTrigger>
            <TabsTrigger value="cams" className="flex items-center gap-1">
              <Settings2 className="h-4 w-4" />
              <span className="hidden sm:inline">Cams</span>
              {stats && <Badge variant="outline" className="ml-1 hidden md:inline">{stats.cams_count}</Badge>}
            </TabsTrigger>
            <TabsTrigger value="intakes" className="flex items-center gap-1">
              <Gauge className="h-4 w-4" />
              <span className="hidden sm:inline">Intakes</span>
              {stats && <Badge variant="outline" className="ml-1 hidden md:inline">{stats.intakes_count}</Badge>}
            </TabsTrigger>
            <TabsTrigger value="short_blocks" className="flex items-center gap-1">
              <Box className="h-4 w-4" />
              <span className="hidden sm:inline">Blocks</span>
              {stats && <Badge variant="outline" className="ml-1 hidden md:inline">{stats.short_blocks_count}</Badge>}
            </TabsTrigger>
          </TabsList>

          {/* Engines Tab */}
          <TabsContent value="engines">
            <ScrollArea className="h-[400px]">
              {loading ? (
                <div className="space-y-2">
                  {[...Array(5)].map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : filteredEngines.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No engines found
                </div>
              ) : (
                <div className="space-y-2">
                  {filteredEngines.map((engine, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-3 border rounded-lg hover:bg-accent cursor-pointer"
                      onClick={() => setSelectedEngine(engine)}
                    >
                      <div>
                        <div className="font-medium">{engine.name}</div>
                        <div className="text-sm text-muted-foreground">
                          {engine.displacement_ci.toFixed(0)}ci ({(engine.displacement_cc / 1000).toFixed(1)}L) - {engine.summary}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {onSelectEngine && (
                          <Button
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelectEngine(engine);
                            }}
                          >
                            Select
                          </Button>
                        )}
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
            <ScrollArea className="h-[400px]">
              {loading ? (
                <div className="space-y-2">
                  {[...Array(5)].map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : filteredHeads.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No heads found
                </div>
              ) : (
                <div className="space-y-2">
                  {filteredHeads.map((head, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-3 border rounded-lg hover:bg-accent cursor-pointer"
                      onClick={() => setSelectedHead(head)}
                    >
                      <div>
                        <div className="font-medium">{head.name}</div>
                        <div className="text-sm text-muted-foreground">
                          {head.intake_valve_dia}/{head.exhaust_valve_dia}" valves
                          {head.peak_intake_cfm > 0 && ` • ${head.peak_intake_cfm.toFixed(0)} CFM peak`}
                          {head.intake_port_cc && ` • ${head.intake_port_cc}cc ports`}
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
            <ScrollArea className="h-[400px]">
              {loading ? (
                <div className="space-y-2">
                  {[...Array(5)].map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : filteredCams.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No cams found
                </div>
              ) : (
                <div className="space-y-2">
                  {filteredCams.map((cam, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-3 border rounded-lg hover:bg-accent cursor-pointer"
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
            <ScrollArea className="h-[400px]">
              {loading ? (
                <div className="space-y-2">
                  {[...Array(5)].map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : filteredIntakes.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No intakes found
                </div>
              ) : (
                <div className="space-y-2">
                  {filteredIntakes.map((intake, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-3 border rounded-lg hover:bg-accent"
                    >
                      <div>
                        <div className="font-medium">{intake.name}</div>
                        <div className="text-sm text-muted-foreground">
                          {intake.throttle_body_cfm && `${intake.throttle_body_cfm} CFM TB`}
                          {intake.runner_length_in && ` • ${intake.runner_length_in}" runners`}
                        </div>
                      </div>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </TabsContent>

          {/* Short Blocks Tab */}
          <TabsContent value="short_blocks">
            <ScrollArea className="h-[400px]">
              {loading ? (
                <div className="space-y-2">
                  {[...Array(5)].map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : filteredShortBlocks.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No short blocks found
                </div>
              ) : (
                <div className="space-y-2">
                  {filteredShortBlocks.map((block, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-3 border rounded-lg hover:bg-accent"
                    >
                      <div>
                        <div className="font-medium">{block.name}</div>
                        <div className="text-sm text-muted-foreground">
                          {block.bore}x{block.stroke}" • {block.displacement_ci.toFixed(0)}ci
                          • {block.cylinders} cyl
                          {block.compression_ratio && ` • ${block.compression_ratio}:1`}
                        </div>
                      </div>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </CardContent>

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
                        className="flex-1 bg-primary/80 rounded-t"
                        style={{
                          height: `${(point.cfm / selectedHead.peak_intake_cfm) * 100}%`,
                        }}
                        title={`${point.lift_inches}" lift: ${point.cfm} CFM`}
                      />
                    ))}
                  </div>
                  <div className="flex justify-between text-xs text-muted-foreground mt-1">
                    <span>{selectedHead.intake_flow[0]?.lift_inches}"</span>
                    <span>{selectedHead.intake_flow[selectedHead.intake_flow.length - 1]?.lift_inches}"</span>
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
              <div>
                <div className="text-sm font-medium text-muted-foreground">Rocker Ratio (Int)</div>
                <div className="text-lg">{selectedCam.rocker_ratio_int}:1</div>
              </div>
              <div>
                <div className="text-sm font-medium text-muted-foreground">Rocker Ratio (Exh)</div>
                <div className="text-lg">{selectedCam.rocker_ratio_exh}:1</div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Engine Detail Dialog */}
      <Dialog open={!!selectedEngine} onOpenChange={() => setSelectedEngine(null)}>
        <DialogContent className="max-w-2xl">
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
                <div>
                  <div className="text-sm font-medium text-muted-foreground">Bore x Stroke</div>
                  <div className="text-lg">
                    {selectedEngine.short_block.bore}" x {selectedEngine.short_block.stroke}"
                  </div>
                </div>
              </div>

              <div className="border-t pt-4">
                <div className="text-sm font-medium mb-2">Components</div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Heads:</span>
                    <span>{selectedEngine.heads.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Cam:</span>
                    <span>
                      {selectedEngine.cam.intake_duration_050}/{selectedEngine.cam.exhaust_duration_050} @ {selectedEngine.cam.lobe_separation}
                    </span>
                  </div>
                  {selectedEngine.intake && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Intake:</span>
                      <span>{selectedEngine.intake.name}</span>
                    </div>
                  )}
                </div>
              </div>

              {onSelectEngine && (
                <div className="flex justify-end pt-4 border-t">
                  <Button onClick={() => {
                    onSelectEngine(selectedEngine);
                    setSelectedEngine(null);
                  }}>
                    Use This Build
                  </Button>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </Card>
  );
}

export default ComponentBrowser;
