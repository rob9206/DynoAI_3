/**
 * V3TuningTab — Accelerated Calibration session UI
 *
 * Self-contained tab that plugs into JetDriveAutoTunePage.
 * Sections: Setup, Session Dashboard, Next-Pull Advisor, Uncertainty
 * Heatmap, Pull History, Overlay Status.
 */

import { useState, useCallback, useMemo } from "react";
import {
  Zap, Target, BarChart3, ShieldCheck, Play, FastForward,
  ChevronRight, AlertTriangle, CheckCircle2, XCircle
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

import { useV3Session } from "@/hooks/useV3Session";
import type { HardwareConfig, PullRecommendation } from "@/api/v3Session";

// ---------------------------------------------------------------------------
// Engine family options
// ---------------------------------------------------------------------------
const ENGINE_FAMILIES = [
  { value: "m8_107", label: "M8 107 (Air-Cooled)" },
  { value: "m8_114", label: "M8 114 (Air-Cooled)" },
  { value: "m8_117", label: "M8 117 (Air-Cooled)" },
  { value: "m8_131", label: "M8 131 (Oil-Cooled)" },
  { value: "tc_88", label: "TC 88 (Air-Cooled)" },
  { value: "tc_96", label: "TC 96 (Air-Cooled)" },
  { value: "tc_103", label: "TC 103 (Air-Cooled)" },
  { value: "tc_110", label: "TC 110 (Air-Cooled)" },
  { value: "revmax_1250", label: "RevMax 1250 (Liquid)" },
  { value: "evo_1200", label: "Evo 1200 (Air-Cooled)" },
] as const;

const CAM_OPTIONS = [
  "stock", "s&s_475", "s&s_510", "s&s_585",
  "feuling_574", "wood_tw777", "other",
];

const EXHAUST_OPTIONS = [
  "stock", "slip_on", "2into1", "open",
];

const AIR_CLEANER_OPTIONS = [
  "stock", "high_flow", "velocity_stack", "other",
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
    air_cleaner: "stock",
  });
  const [simMode, setSimMode] = useState<"quick" | "realistic">("realistic");

  const v3 = useV3Session(sessionId);

  // ---- Handlers ----
  const handleStartSession = useCallback(async () => {
    try {
      const result = await v3.startSession(config);
      setSessionId(result.session_id);
      const matchLabel = result.template_match
        ? `Template match: ${(result.template_match.similarity_score * 100).toFixed(0)}%`
        : "No template match (fresh session)";
      toast.success(`Session started: ${result.engine_family} — ${matchLabel}`);
    } catch (err) {
      toast.error("Failed to start session");
    }
  }, [config, v3]);

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

  const handleFinalize = useCallback(async () => {
    if (!v3.uncertaintyMap?.ve_map) {
      toast.error("No VE map available to finalize");
      return;
    }
    try {
      const result = await v3.finalize({
        ve_table_front: v3.uncertaintyMap.ve_map,
        operator: "user",
      });
      toast.success(`Session finalized! Template ${result.template_id} saved.`);
    } catch (err) {
      toast.error("Failed to finalize session");
    }
  }, [v3]);

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

            <div className="space-y-2">
              <Label>Air Cleaner</Label>
              <Select
                value={config.air_cleaner ?? "stock"}
                onValueChange={(v) => setConfig((c) => ({ ...c, air_cleaner: v }))}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {AIR_CLEANER_OPTIONS.map((o) => (
                    <SelectItem key={o} value={o}>{o}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
  const convergencePct = useMemo(() => {
    if (!v3.convergence) return 0;
    return Math.round(
      ((v3.convergence.total_cells - v3.convergence.cells_above_threshold) /
        Math.max(v3.convergence.total_cells, 1)) *
        100
    );
  }, [v3.convergence]);

  const uncertaintyMapCard = useMemo(() => {
    const um = v3.uncertaintyMap;
    if (!um) return null;

    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-purple-500" />
            Uncertainty Map
            <span className="text-xs font-normal text-muted-foreground ml-auto">
              {um.predict_time_ms.toFixed(0)}ms GP predict
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr>
                  <th className="text-left p-1 text-muted-foreground">RPM\MAP</th>
                  {um.map_bins.map((m) => (
                    <th key={m} className="p-1 text-center text-muted-foreground">{m}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {um.rpm_bins.map((rpm, ri) => (
                  <tr key={rpm}>
                    <td className="p-1 font-medium text-muted-foreground">{rpm}</td>
                    {um.uncertainty_map[ri].map((unc, ci) => {
                      const bg =
                        unc < 0.5 ? "bg-green-900/40" :
                        unc < 1.0 ? "bg-yellow-900/40" :
                        unc < 2.0 ? "bg-orange-900/40" :
                        "bg-red-900/40";
                      return (
                        <td
                          key={ci}
                          className={cn("p-1 text-center rounded-sm", bg)}
                          title={`VE: ${um.ve_map[ri][ci].toFixed(1)}% | Unc: ${unc.toFixed(2)}`}
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
    );
  }, [v3.uncertaintyMap]);

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
      {uncertaintyMapCard}

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

      {/* Finalize Session (when converged) */}
      {v3.isConverged && v3.sessionPhase !== "complete" && (
        <Card className="border-green-800">
          <CardContent className="pt-6">
            <div className="text-center space-y-3">
              <CheckCircle2 className="h-6 w-6 text-green-500 mx-auto" />
              <h4 className="font-semibold">Session Converged</h4>
              <p className="text-sm text-muted-foreground">
                The VE map has reached target accuracy. Finalize to save as a template.
              </p>
              <Button
                onClick={handleFinalize}
                disabled={v3.isFinalizing || !v3.uncertaintyMap}
                className="w-full"
                variant="default"
              >
                {v3.isFinalizing ? "Saving..." : "Finalize & Save Template"}
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
    </div>
  );
}
