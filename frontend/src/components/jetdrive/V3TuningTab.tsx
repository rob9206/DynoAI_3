/**
 * V3TuningTab — Accelerated Calibration session UI
 *
 * Self-contained tab that plugs into JetDriveAutoTunePage.
 * Sections: Setup, Session Dashboard, Next-Pull Advisor, Uncertainty
 * Heatmap, Pull History, Overlay Status.
 */

import { useState, useCallback, useEffect, useRef } from "react";
import {
  Zap, Target, BarChart3, ShieldCheck, Play, FastForward,
  ChevronRight, AlertTriangle, CheckCircle2, XCircle, Upload
} from "lucide-react";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import {
  Card, CardContent, CardHeader, CardTitle, CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";

import { useV3Session } from "@/hooks/useV3Session";
import type { HardwareConfig, PullRecommendation } from "@/api/v3Session";
import { TuneImport, VEPreviewTable, type TuneImportResult } from "@/components/jetdrive/TuneImport";
import { parsePVV, tableToGrid, type PVVTable } from "@/utils/pvvParser";
import { parseDynoAICSV, parseDynoAIJSON } from "@/utils/veImportParser";

// ---------------------------------------------------------------------------
// Engine family options
// ---------------------------------------------------------------------------
const ENGINE_FAMILIES = [
  { value: "m8_107", label: "M8 107 (Air-Cooled)" },
  { value: "m8_114", label: "M8 114 (Air-Cooled)" },
  { value: "m8_117", label: "M8 117 (Air-Cooled)" },
  { value: "m8_131", label: "M8 131 (Oil-Cooled)" },
  { value: "revmax_975", label: "RevMax 975 (Nightster)" },
  { value: "revmax_1250", label: "RevMax 1250 (Sportster S / Pan America)" },
  { value: "evo_1200", label: "Evo 1200 (Air-Cooled)" },
] as const;

const CAM_OPTIONS = [
  "stock", "s&s_475", "s&s_510", "s&s_585",
  "feuling_574", "wood_tw777", "other",
];

const EXHAUST_OPTIONS = [
  "stock", "slip_on", "2into1", "open",
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function V3TuningTab() {
  // ---- Local form state ----
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [config, setConfig] = useState<HardwareConfig>({
    engine_family: "m8_114",
    displacement_ci: 114,
    cam_spec: "stock",
    exhaust_type: "stock",
  });
  const [baseVeSeed, setBaseVeSeed] = useState<{
    veTable: number[][];
    rpmBins: number[];
    mapBins: number[];
    sourceName: string;
  } | null>(null);
  const [baseVeSeedPending, setBaseVeSeedPending] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importPreview, setImportPreview] = useState<{
    corrections: number[][];
    rpmBins: number[];
    mapBins: number[];
    format: "multiplier" | "percentage";
    sourceName: string;
  } | null>(null);
  const importFileRef = useRef<HTMLInputElement>(null);
  const [simMode, setSimMode] = useState<"quick" | "realistic">("realistic");
  const baseVeImportedForSessionRef = useRef<string | null>(null);

  const v3 = useV3Session(sessionId);

  // ---- Effects ----
  useEffect(() => {
    if (!sessionId || !baseVeSeed || !baseVeSeedPending) return;
    // Only import once per session; clear pending immediately so re-runs (e.g. from v3 ref change) bail out
    if (baseVeImportedForSessionRef.current === sessionId) return;
    baseVeImportedForSessionRef.current = sessionId;
    setBaseVeSeedPending(false);

    const veTable = baseVeSeed.veTable;
    const rpmBins = baseVeSeed.rpmBins;
    const mapBins = baseVeSeed.mapBins;
    const sourceName = baseVeSeed.sourceName;

    (async () => {
      try {
        await v3.importVE({
          ve_table: veTable,
          rpm_bins: rpmBins,
          map_bins: mapBins,
        });
        toast.success(`Base VE imported from ${sourceName}`);
      } catch (err) {
        toast.error("Failed to import base VE table");
        baseVeImportedForSessionRef.current = null; // allow retry
      }
    })();
  }, [sessionId, baseVeSeed, baseVeSeedPending, v3]);

  // ---- Handlers ----
  const handleStartSession = useCallback(async () => {
    try {
      const result = await v3.startSession(config);
      setSessionId(result.session_id);
      if (baseVeSeed) {
        setBaseVeSeedPending(true);
      }
      const matchLabel = result.template_match
        ? `Template match: ${(result.template_match.similarity_score * 100).toFixed(0)}%`
        : "No template match (fresh session)";
      toast.success(`Session started: ${result.engine_family} — ${matchLabel}`);
    } catch (err) {
      toast.error("Failed to start session");
    }
  }, [config, v3, baseVeSeed]);

  const handleVeto = useCallback(
    (rec: PullRecommendation) => {
      v3.veto({ rpm: rec.rpm, map_kpa: rec.map_kpa, reason: "Operator override" });
      toast.info(`Vetoed: ${rec.rpm} RPM / ${rec.map_kpa} kPa`);
    },
    [v3]
  );

  const handleSimulatePull = useCallback(async () => {
    try {
      const result = await v3.simulate({ mode: simMode });
      const base = `Pull #${result.pull_number}: ${result.observations_added} obs at ${result.target_rpm.toFixed(0)} RPM / ${result.target_map_kpa.toFixed(0)} kPa`;
      if (result.afr_metrics) {
        const m = result.afr_metrics;
        toast.success(
          `${base} — ${m.zones_corrected} zones corrected (max VE ${m.max_ve_correction_pct.toFixed(1)}%, AFR err ${m.mean_afr_error.toFixed(2)})`
        );
      } else {
        toast.success(base);
      }
    } catch (err) {
      toast.error("Failed to simulate pull");
    }
  }, [v3, simMode]);

  const handleBaseVeImport = useCallback((result: TuneImportResult) => {
    const engineFamily = result.inferredEngineFamily && ENGINE_FAMILIES.some((e) => e.value === result.inferredEngineFamily)
      ? result.inferredEngineFamily
      : undefined;
    const displacementCi = result.engineDisplacementCid;
    setConfig((c) => ({
      ...c,
      ...(engineFamily && { engine_family: engineFamily }),
      ...(displacementCi != null && displacementCi > 0 && { displacement_ci: displacementCi }),
      rpm_bins: result.rpmBins,
      map_bins: result.mapBins,
    }));

    const frontGrid = result.veFront
      ? tableToGrid(result.veFront, result.rpmBins, result.mapBins)
      : null;
    const rearGrid = result.veRear
      ? tableToGrid(result.veRear, result.rpmBins, result.mapBins)
      : null;

    if (!frontGrid && !rearGrid) {
      setBaseVeSeed(null);
      return;
    }

    let combined = frontGrid ?? rearGrid ?? [];
    if (frontGrid && rearGrid) {
      combined = frontGrid.map((row, i) =>
        row.map((value, j) => (value + rearGrid[i][j]) / 2)
      );
    }

    setBaseVeSeed({
      veTable: combined,
      rpmBins: result.rpmBins,
      mapBins: result.mapBins,
      sourceName: result.sourceName,
    });
  }, []);

  const buildPreviewTable = useCallback((): PVVTable | null => {
    if (!importPreview) return null;
    const values = importPreview.format === "multiplier"
      ? importPreview.corrections.map((row) =>
          row.map((value) => (value - 1) * 100)
        )
      : importPreview.corrections;
    return {
      name: "Corrections",
      units: "%",
      columnUnits: "Kilopascals",
      rowUnits: "RPM",
      columns: importPreview.mapBins,
      rows: importPreview.rpmBins,
      values,
    };
  }, [importPreview]);

  const handleCorrectionsFile = useCallback(async (file: File) => {
    setImportError(null);
    setImportPreview(null);

    const lower = file.name.toLowerCase();
    try {
      if (lower.endsWith(".json")) {
        const parsed = parseDynoAIJSON(await file.text());
        setImportPreview({ ...parsed, sourceName: file.name });
        return;
      }

      if (lower.endsWith(".csv")) {
        const parsed = parseDynoAICSV(await file.text());
        setImportPreview({ ...parsed, sourceName: file.name });
        return;
      }

      if (lower.endsWith(".pvv")) {
        const parsed = parsePVV(await file.text());
        const baseTable = parsed.veFront ?? parsed.veRear;
        if (!baseTable) {
          throw new Error("PVV file missing VE correction tables");
        }

        const rpmBins = baseTable.rows;
        const mapBins = baseTable.columns;
        const frontGrid = parsed.veFront
          ? tableToGrid(parsed.veFront, rpmBins, mapBins)
          : null;
        const rearGrid = parsed.veRear
          ? tableToGrid(parsed.veRear, rpmBins, mapBins)
          : null;

        let combined = frontGrid ?? rearGrid ?? [];
        if (frontGrid && rearGrid) {
          combined = frontGrid.map((row, i) =>
            row.map((value, j) => (value + rearGrid[i][j]) / 2)
          );
        }

        setImportPreview({
          corrections: combined,
          rpmBins,
          mapBins,
          format: "percentage",
          sourceName: file.name,
        });
        return;
      }

      throw new Error("Unsupported file type (use .json, .csv, or .pvv)");
    } catch (err) {
      setImportError(err instanceof Error ? err.message : "Failed to parse file");
    }
  }, []);

  const handleImportCorrections = useCallback(async () => {
    if (!importPreview) return;
    try {
      await v3.importSessionCorrections({
        corrections: importPreview.corrections,
        rpm_bins: importPreview.rpmBins,
        map_bins: importPreview.mapBins,
        format: importPreview.format,
      });
      toast.success(`Corrections imported from ${importPreview.sourceName}`);
      setImportDialogOpen(false);
    } catch (err) {
      toast.error("Failed to import corrections");
    }
  }, [importPreview, v3]);

  const handleAutoSimulate = useCallback(async () => {
    try {
      toast.info("Auto-running simulation to convergence...");
      const result = await v3.runAutoSimulate({ mode: simMode, max_pulls: 25 });
      if (result.converged) {
        toast.success(`Converged after ${result.pulls_completed} pulls!`);
      } else {
        toast.warning(
          `Reached ${result.pulls_completed} pulls without full convergence`
        );
      }
    } catch (err) {
      toast.error("Auto-simulation failed");
    }
  }, [v3, simMode]);

  // ---- Render: Idle / Setup ----
  if (v3.sessionPhase === "idle") {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-amber-500" />
              Accelerated Calibration — Setup
            </CardTitle>
            <CardDescription>
              Enter the bike&apos;s hardware configuration to start an intelligent
              tuning session. The system will find the best template match and
              generate a test plan.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Engine family */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Engine Family</Label>
                <Select
                  value={config.engine_family}
                  onValueChange={(v) =>
                    setConfig((c) => ({
                      ...c,
                      engine_family: v,
                      displacement_ci: parseInt(v.split("_")[1]) || 114,
                    }))
                  }
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {ENGINE_FAMILIES.map((f) => (
                      <SelectItem key={f.value} value={f.value}>
                        {f.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Displacement (ci)</Label>
                <Input
                  type="number"
                  value={config.displacement_ci}
                  onChange={(e) =>
                    setConfig((c) => ({ ...c, displacement_ci: Number(e.target.value) }))
                  }
                />
              </div>
            </div>

            {/* Cam / Exhaust */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Cam Spec</Label>
                <Select
                  value={config.cam_spec ?? "stock"}
                  onValueChange={(v) => setConfig((c) => ({ ...c, cam_spec: v }))}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {CAM_OPTIONS.map((o) => (
                      <SelectItem key={o} value={o}>{o}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Exhaust Type</Label>
                <Select
                  value={config.exhaust_type ?? "stock"}
                  onValueChange={(v) => setConfig((c) => ({ ...c, exhaust_type: v }))}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {EXHAUST_OPTIONS.map((o) => (
                      <SelectItem key={o} value={o}>{o}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Base VE Import */}
            <div className="space-y-2">
              <Label>Base VE Import (optional)</Label>
              <TuneImport compact onImport={handleBaseVeImport} />
              {baseVeSeed && (
                <p className="text-xs text-muted-foreground">
                  Using base VE from {baseVeSeed.sourceName}
                </p>
              )}
            </div>

            <Button
              onClick={handleStartSession}
              disabled={v3.isCreating}
              className="w-full"
              size="lg"
            >
              {v3.isCreating ? "Initializing..." : (
                <>
                  <Play className="h-4 w-4 mr-2" />
                  Start Accelerated Session
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Template library info */}
        {v3.templates && (
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">
                Template Library: <span className="font-medium text-foreground">{v3.templates.total_templates}</span> templates available
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    );
  }

  // ---- Render: Active session ----
  const convergencePct = v3.convergence
    ? Math.round(
        ((v3.convergence.total_cells - v3.convergence.cells_above_threshold) /
          Math.max(v3.convergence.total_cells, 1)) *
          100
      )
    : 0;

  const previewTable = buildPreviewTable();

  return (
    <div className="space-y-6">
      {/* Session header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Zap className="h-5 w-5 text-amber-500" />
          <div>
            <h3 className="font-semibold">
              Session {sessionId?.slice(0, 8)}
            </h3>
            <p className="text-xs text-muted-foreground">
              {v3.sessionStatus?.engine_family} — {v3.pullCount} pulls — {v3.sessionPhase}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {v3.isConverged ? (
            <Badge variant="default" className="bg-green-600">
              <CheckCircle2 className="h-3 w-3 mr-1" /> Converged
            </Badge>
          ) : (
            <Badge variant="secondary">
              {v3.convergence?.estimated_pulls_remaining ?? "?"} pulls remaining
            </Badge>
          )}
          {v3.initResult?.template_match && (
            <Badge variant="outline">
              Template {(v3.initResult.template_match.similarity_score * 100).toFixed(0)}%
            </Badge>
          )}
          {(v3.sessionPhase === "ready" || v3.sessionPhase === "tuning") && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setImportDialogOpen(true)}
            >
              <Upload className="h-3 w-3 mr-1" />
              Import Corrections
            </Button>
          )}
        </div>
      </div>

      {/* Convergence progress */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Map Convergence</span>
            <span className="text-sm text-muted-foreground">{convergencePct}%</span>
          </div>
          <Progress value={convergencePct} className="h-2" />
          {v3.convergence && (
            <p className="text-xs text-muted-foreground mt-2">
              {v3.convergence.cells_above_threshold} / {v3.convergence.total_cells} cells
              still above uncertainty threshold
              {" "}&bull;{" "}Mean uncertainty: {v3.convergence.mean_uncertainty.toFixed(2)}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Next Pull Advisor */}
      {v3.nextPull && (v3.sessionPhase === "ready" || v3.sessionPhase === "tuning") && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Target className="h-4 w-4 text-blue-500" />
              Next Pull Recommendation
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="space-y-1 flex-1">
                <div className="flex items-center gap-4">
                  <div>
                    <span className="text-2xl font-bold">{v3.nextPull.rpm.toFixed(0)}</span>
                    <span className="text-sm text-muted-foreground ml-1">RPM</span>
                  </div>
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <span className="text-2xl font-bold">{v3.nextPull.map_kpa.toFixed(0)}</span>
                    <span className="text-sm text-muted-foreground ml-1">kPa</span>
                  </div>
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <span className="text-2xl font-bold">{v3.nextPull.throttle_pct.toFixed(0)}%</span>
                    <span className="text-sm text-muted-foreground ml-1">throttle</span>
                  </div>
                  <Badge variant="outline">Gear {v3.nextPull.gear}</Badge>
                </div>
                <p className="text-xs text-muted-foreground">{v3.nextPull.reason}</p>
              </div>
              <div className="flex flex-col gap-2 items-end">
                <div className="flex gap-2">
                  <Select value={simMode} onValueChange={(v) => setSimMode(v as "quick" | "realistic")}>
                    <SelectTrigger className="w-[120px] h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="quick">Quick</SelectItem>
                      <SelectItem value="realistic">Realistic</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button
                    onClick={handleSimulatePull}
                    disabled={v3.isSimulating || v3.isAutoSimulating}
                    size="sm"
                  >
                    <Play className="h-4 w-4 mr-1" />
                    {v3.isSimulating ? "Running..." : "Simulate Pull"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleVeto(v3.nextPull!)}
                  >
                    <XCircle className="h-4 w-4 mr-1" /> Veto
                  </Button>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleAutoSimulate}
                  disabled={v3.isSimulating || v3.isAutoSimulating}
                  className="w-full"
                >
                  <FastForward className="h-4 w-4 mr-1" />
                  {v3.isAutoSimulating ? "Auto-Running..." : "Auto-Run to Convergence"}
                </Button>
              </div>
            </div>

            {/* Alternatives */}
            {v3.nextPull.alternatives.length > 0 && (
              <div className="mt-3 pt-3 border-t">
                <p className="text-xs text-muted-foreground mb-2">Alternatives:</p>
                <div className="flex gap-2">
                  {v3.nextPull.alternatives.map((alt, i) => (
                    <Badge key={i} variant="secondary" className="text-xs">
                      {alt.rpm.toFixed(0)} / {alt.map_kpa.toFixed(0)} kPa
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Uncertainty map preview */}
      {v3.uncertaintyMap && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-purple-500" />
              Uncertainty Map
              <span className="text-xs font-normal text-muted-foreground ml-auto">
                {v3.uncertaintyMap.predict_time_ms.toFixed(0)}ms GP predict
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr>
                    <th className="text-left p-1 text-muted-foreground">RPM\MAP</th>
                    {v3.uncertaintyMap.map_bins.map((m) => (
                      <th key={m} className="p-1 text-center text-muted-foreground">{m}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {v3.uncertaintyMap.rpm_bins.map((rpm, ri) => (
                    <tr key={rpm}>
                      <td className="p-1 font-medium text-muted-foreground">{rpm}</td>
                      {v3.uncertaintyMap!.uncertainty_map[ri].map((unc, ci) => {
                        const bg =
                          unc < 0.5 ? "bg-green-900/40" :
                          unc < 1.0 ? "bg-yellow-900/40" :
                          unc < 2.0 ? "bg-orange-900/40" :
                          "bg-red-900/40";
                        return (
                          <td
                            key={ci}
                            className={cn("p-1 text-center rounded-sm", bg)}
                            title={`VE: ${v3.uncertaintyMap!.ve_map[ri][ci].toFixed(1)}% | Unc: ${unc.toFixed(2)}`}
                          >
                            {unc.toFixed(1)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex gap-3 mt-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-green-900/40" /> &lt;0.5 (High)</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-yellow-900/40" /> 0.5-1.0 (Med)</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-orange-900/40" /> 1.0-2.0 (Low)</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-900/40" /> &gt;2.0 (Skip)</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Overlay / Safety */}
      {v3.overlay && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-green-500" />
              Safety Envelope
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground">Max Fuel Correction</p>
                <p className="font-medium">&plusmn;{v3.overlay.max_fuel_correction_pct.toFixed(1)}%</p>
              </div>
              <div>
                <p className="text-muted-foreground">Max Timing Offset</p>
                <p className="font-medium">&plusmn;{v3.overlay.max_timing_correction_deg.toFixed(1)}&deg;</p>
              </div>
              <div>
                <p className="text-muted-foreground">ECT Enrichment Trigger</p>
                <p className="font-medium">{v3.overlay.ect_enrichment_trigger_f.toFixed(0)}&deg;F</p>
              </div>
            </div>
            <div className="mt-4">
              <Button
                variant="destructive"
                size="sm"
                onClick={() => {
                  v3.killSwitch();
                  toast.warning("Kill switch activated");
                }}
              >
                <AlertTriangle className="h-4 w-4 mr-1" />
                Kill Switch
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Session complete */}
      {v3.sessionPhase === "complete" && (
        <Card className="border-green-800">
          <CardContent className="pt-6 text-center space-y-2">
            <CheckCircle2 className="h-8 w-8 text-green-500 mx-auto" />
            <h3 className="font-semibold">Session Complete</h3>
            <p className="text-sm text-muted-foreground">
              {v3.pullCount} pulls &bull; Template stored for future sessions
            </p>
          </CardContent>
        </Card>
      )}

      <Dialog open={importDialogOpen} onOpenChange={setImportDialogOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-white">Import VE Corrections</DialogTitle>
            <DialogDescription className="text-zinc-400">
              Load a DynoAI corrections export (CSV/JSON) or a PVV correction file.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <input
                ref={importFileRef}
                type="file"
                accept=".csv,.json,.pvv"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    handleCorrectionsFile(file);
                  }
                }}
                className="hidden"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => importFileRef.current?.click()}
              >
                <Upload className="h-3 w-3 mr-1" />
                Choose File
              </Button>
              {importPreview && (
                <Badge variant="outline" className="text-green-400 border-green-500/30">
                  {importPreview.sourceName}
                </Badge>
              )}
            </div>

            {importError && (
              <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/30 rounded p-2">
                {importError}
              </div>
            )}

            {importPreview && (
              <div className="space-y-3">
                <div className="text-xs text-zinc-400">
                  Grid: {importPreview.rpmBins.length} RPM × {importPreview.mapBins.length} MAP
                  {" "}• Format: {importPreview.format}
                </div>
                {previewTable && (
                  <VEPreviewTable
                    table={previewTable}
                    title="Corrections (%)"
                    maxRows={6}
                    maxCols={8}
                  />
                )}
              </div>
            )}

            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setImportDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleImportCorrections}
                disabled={!importPreview || v3.isImportingCorrections}
              >
                {v3.isImportingCorrections ? "Importing..." : "Import Corrections"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
