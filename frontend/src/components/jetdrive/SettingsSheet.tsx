/**
 * SettingsSheet - Optimized settings slide-out panel
 * 
 * Clean tabbed interface replacing the inline collapsible settings:
 * - Targets: AFR targets & run detection
 * - Build: Stage & cam presets (decel fix)
 * - Analysis: Transient fuel, Virtual ECU, Closed-loop tuning
 */

import { useState } from 'react';
import { Settings2, Target, Wrench, FlaskConical, X } from 'lucide-react';
import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
    SheetDescription,
} from '../ui/sheet';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
import { Slider } from '../ui/slider';
import { Button } from '../ui/button';
import { ScrollArea } from '../ui/scroll-area';
import { AFRTargetTable } from './AFRTargetTable';
import { StageConfigPanel } from './StageConfigPanel';
import { TransientFuelPanel } from './TransientFuelPanel';
import { VirtualECUPanel, type VEScenario } from './VirtualECUPanel';
import { ClosedLoopTuningPanel } from './ClosedLoopTuningPanel';

interface SettingsSheetProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;

    // AFR & Detection settings
    afrTargets: Record<number, number>;
    onAfrTargetsChange: (targets: Record<number, number>) => void;
    rpmThreshold: number;
    onRpmThresholdChange: (rpm: number) => void;
    runId: string;
    onRunIdChange: (id: string) => void;
    currentMap?: number;
    currentRpm?: number;

    // Transient Fuel settings
    transientFuelEnabled: boolean;
    onTransientFuelEnabledChange: (enabled: boolean) => void;
    selectedRun?: string | null;
    isCapturing?: boolean;
    currentTps?: number;
    currentTargetAfr?: number;

    // Virtual ECU settings
    virtualECUEnabled: boolean;
    onVirtualECUEnabledChange: (enabled: boolean) => void;
    veScenario: VEScenario;
    onVeScenarioChange: (scenario: VEScenario) => void;
    veErrorPct: number;
    onVeErrorPctChange: (pct: number) => void;
    veErrorStd: number;
    onVeErrorStdChange: (std: number) => void;

    // Closed-loop settings
    selectedProfile: string;
}

export function SettingsSheet({
    open,
    onOpenChange,
    afrTargets,
    onAfrTargetsChange,
    rpmThreshold,
    onRpmThresholdChange,
    runId,
    onRunIdChange,
    currentMap,
    currentRpm,
    transientFuelEnabled,
    onTransientFuelEnabledChange,
    selectedRun,
    isCapturing,
    currentTps,
    currentTargetAfr,
    virtualECUEnabled,
    onVirtualECUEnabledChange,
    veScenario,
    onVeScenarioChange,
    veErrorPct,
    onVeErrorPctChange,
    veErrorStd,
    onVeErrorStdChange,
    selectedProfile,
}: SettingsSheetProps) {
    const [activeTab, setActiveTab] = useState('targets');

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent
                side="right"
                className="!w-full sm:!w-[700px] md:!w-[900px] lg:!w-[1000px] sm:!max-w-[700px] md:!max-w-[900px] lg:!max-w-[1000px] max-w-[90vw] p-0 bg-zinc-950/98 border-l border-zinc-800/60 backdrop-blur-xl"
            >
                <div className="flex flex-col h-full">
                    {/* Header */}
                    <SheetHeader className="px-6 py-4 border-b border-zinc-800/60 bg-gradient-to-r from-zinc-900/80 to-zinc-950/80">
                        <div className="flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
                                <Settings2 className="h-5 w-5 text-cyan-400" />
                            </div>
                            <div>
                                <SheetTitle className="text-lg font-semibold text-zinc-100">
                                    Tune Settings
                                </SheetTitle>
                                <SheetDescription className="text-xs text-zinc-500">
                                    Configure AFR targets, presets & analysis
                                </SheetDescription>
                            </div>
                        </div>
                    </SheetHeader>

                    {/* Tabs */}
                    <Tabs
                        value={activeTab}
                        onValueChange={setActiveTab}
                        className="flex-1 flex flex-col min-h-0"
                    >
                        <div className="px-6 pt-4 pb-2 border-b border-zinc-800/40">
                            <TabsList className="grid w-full grid-cols-3 bg-zinc-900/60 p-1">
                                <TabsTrigger
                                    value="targets"
                                    className="flex items-center gap-1.5 text-xs data-[state=active]:bg-cyan-500/20 data-[state=active]:text-cyan-300"
                                >
                                    <Target className="h-3.5 w-3.5" />
                                    Targets
                                </TabsTrigger>
                                <TabsTrigger
                                    value="build"
                                    className="flex items-center gap-1.5 text-xs data-[state=active]:bg-orange-500/20 data-[state=active]:text-orange-300"
                                >
                                    <Wrench className="h-3.5 w-3.5" />
                                    Build
                                </TabsTrigger>
                                <TabsTrigger
                                    value="analysis"
                                    className="flex items-center gap-1.5 text-xs data-[state=active]:bg-violet-500/20 data-[state=active]:text-violet-300"
                                >
                                    <FlaskConical className="h-3.5 w-3.5" />
                                    Analysis
                                </TabsTrigger>
                            </TabsList>
                        </div>

                        <ScrollArea className="flex-1">
                            {/* Targets Tab */}
                            <TabsContent value="targets" className="mt-0 p-6 space-y-6">
                                {/* AFR Target Table */}
                                <div>
                                    <h3 className="text-sm font-medium text-zinc-200 mb-3 flex items-center gap-2">
                                        <Target className="h-4 w-4 text-cyan-400" />
                                        AFR Targets by MAP
                                    </h3>
                                    <div className="overflow-x-auto -mx-2 px-2">
                                        <AFRTargetTable
                                            targets={afrTargets}
                                            onChange={onAfrTargetsChange}
                                            compact={false}
                                            currentMap={currentMap}
                                            currentRpm={currentRpm}
                                        />
                                    </div>
                                </div>

                                {/* Run Detection Settings */}
                                <div className="space-y-4 pt-4 border-t border-zinc-800/50">
                                    <h3 className="text-sm font-medium text-zinc-200">Run Detection</h3>

                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label className="text-xs text-zinc-400">
                                                WOT Detection RPM
                                            </Label>
                                            <div className="flex items-center gap-3">
                                                <Slider
                                                    value={[rpmThreshold]}
                                                    onValueChange={([v]) => onRpmThresholdChange(v)}
                                                    min={1000}
                                                    max={4000}
                                                    step={100}
                                                    className="flex-1"
                                                />
                                                <span className="text-sm font-mono font-bold text-cyan-400 w-14 text-right">
                                                    {rpmThreshold}
                                                </span>
                                            </div>
                                            <p className="text-[10px] text-zinc-600">
                                                RPM threshold to detect WOT pull start
                                            </p>
                                        </div>

                                        <div className="space-y-2">
                                            <Label className="text-xs text-zinc-400">Run ID</Label>
                                            <Input
                                                value={runId}
                                                onChange={(e) => onRunIdChange(e.target.value)}
                                                className="h-9 bg-zinc-900/60 border-zinc-800 text-sm"
                                                placeholder="my_dyno_run"
                                            />
                                            <p className="text-[10px] text-zinc-600">
                                                Identifier for this capture session
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </TabsContent>

                            {/* Build Tab */}
                            <TabsContent value="build" className="mt-0 p-6">
                                <StageConfigPanel
                                    afrTargets={afrTargets}
                                    onAfrTargetsChange={onAfrTargetsChange}
                                    runId={runId}
                                    compact={false}
                                />
                            </TabsContent>

                            {/* Analysis Tab */}
                            <TabsContent value="analysis" className="mt-0 p-6 space-y-6">
                                {/* Transient Fuel */}
                                <TransientFuelPanel
                                    enabled={transientFuelEnabled}
                                    onEnabledChange={onTransientFuelEnabledChange}
                                    runId={selectedRun || runId}
                                    isCapturing={isCapturing}
                                    currentRpm={currentRpm}
                                    currentMap={currentMap}
                                    currentTps={currentTps}
                                    targetAfr={currentTargetAfr}
                                    compact={false}
                                />

                                {/* Virtual ECU */}
                                <div className="pt-4 border-t border-zinc-800/50">
                                    <VirtualECUPanel
                                        enabled={virtualECUEnabled}
                                        onEnabledChange={onVirtualECUEnabledChange}
                                        scenario={veScenario}
                                        onScenarioChange={onVeScenarioChange}
                                        veErrorPct={veErrorPct}
                                        onVeErrorChange={onVeErrorPctChange}
                                        veErrorStd={veErrorStd}
                                        onVeErrorStdChange={onVeErrorStdChange}
                                    />
                                </div>

                                {/* Closed-Loop Tuning */}
                                <div className="pt-4 border-t border-zinc-800/50">
                                    <ClosedLoopTuningPanel
                                        engineProfile={selectedProfile}
                                        baseScenario={veScenario}
                                        maxIterations={10}
                                        convergenceThreshold={0.3}
                                    />
                                </div>
                            </TabsContent>
                        </ScrollArea>
                    </Tabs>
                </div>
            </SheetContent>
        </Sheet>
    );
}

export default SettingsSheet;

