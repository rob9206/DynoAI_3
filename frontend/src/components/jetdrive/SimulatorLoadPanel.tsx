/**
 * SimulatorLoadPanel — Manual load mode controls for the JetDrive simulator.
 *
 * Provides mode selector (Inertia / Eddy Brake / Road Load),
 * eddy brake load target slider + RPM hold toggle,
 * and live load-state readout polling GET /simulator/load-state.
 *
 * Mounted only when the simulator is active.
 */

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { Gauge, Zap, Car, ChevronDown, ChevronRight } from "lucide-react";

import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type LoadMode = "inertia" | "eddy_brake" | "road_load";

interface LoadState {
  mode: LoadMode;
  load_target: number;
  current_load: number;
  brake_torque: number;
  road_load_torque: number;
  rpm_hold_active: boolean;
  rpm_hold_target: number;
  speed_mph: number;
}

interface SimulatorLoadPanelProps {
  /** API base URL e.g. http://127.0.0.1:5001/api/jetdrive */
  apiUrl: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const MODE_LABELS: Record<LoadMode, string> = {
  inertia: "Inertia Only",
  eddy_brake: "Eddy Brake",
  road_load: "Road Load (SAE J2264)",
};

const MODE_DESCRIPTIONS: Record<LoadMode, string> = {
  inertia: "No external load — pure inertia dyno",
  eddy_brake: "Eddy current brake with load control and RPM hold",
  road_load: "SAE J2264 road load simulation (A + Bv + Cv\u00B2)",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SimulatorLoadPanel({ apiUrl }: SimulatorLoadPanelProps) {
  // Local UI state (optimistic; load-state poll reconciles)
  const [selectedMode, setSelectedMode] = useState<LoadMode>("inertia");
  const [loadTarget, setLoadTarget] = useState(0);
  const [rpmHoldActive, setRpmHoldActive] = useState(false);
  const [rpmHoldTarget, setRpmHoldTarget] = useState(3500);
  const [roadConfigOpen, setRoadConfigOpen] = useState(false);

  // ---- Poll load-state from backend ----
  const { data: loadState } = useQuery<LoadState>({
    queryKey: ["simulator-load-state"],
    queryFn: async () => {
      const res = await fetch(`${apiUrl}/simulator/load-state`);
      if (!res.ok) throw new Error(`load-state ${res.status}`);
      const json = await res.json();
      return json.load as LoadState;
    },
    refetchInterval: 500,
  });

  // Reconcile backend state into local selectors (one-way read)
  const liveMode = loadState?.mode ?? selectedMode;
  const liveLoad = loadState?.current_load ?? 0;
  const liveBrakeTorque = loadState?.brake_torque ?? 0;
  const liveRoadTorque = loadState?.road_load_torque ?? 0;
  const liveSpeedMph = loadState?.speed_mph ?? 0;
  const liveRpmHoldActive = loadState?.rpm_hold_active ?? rpmHoldActive;
  const liveRpmHoldTarget = loadState?.rpm_hold_target ?? rpmHoldTarget;

  // ---- API helpers (fire-and-forget) ----
  const postJson = useCallback(
    async (path: string, body: Record<string, unknown>) => {
      try {
        await fetch(`${apiUrl}/simulator${path}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } catch {
        // swallow — load-state poll will show stale data
      }
    },
    [apiUrl],
  );

  const handleModeChange = useCallback(
    (mode: LoadMode) => {
      setSelectedMode(mode);
      postJson("/load-mode", { mode });
    },
    [postJson],
  );

  const handleLoadTargetCommit = useCallback(
    (value: number) => {
      setLoadTarget(value);
      postJson("/load-target", { load_pct: value });
    },
    [postJson],
  );

  const handleRpmHoldToggle = useCallback(
    (active: boolean) => {
      setRpmHoldActive(active);
      postJson("/rpm-hold", { active, target_rpm: rpmHoldTarget });
    },
    [postJson, rpmHoldTarget],
  );

  const handleRpmHoldTargetChange = useCallback(
    (rpm: number) => {
      const clamped = Math.max(1500, Math.min(6500, rpm));
      setRpmHoldTarget(clamped);
      if (rpmHoldActive) {
        postJson("/rpm-hold", { active: true, target_rpm: clamped });
      }
    },
    [postJson, rpmHoldActive],
  );

  // ---- Render ----
  return (
    <div className="mt-3 p-3 rounded-md bg-zinc-950/40 border border-zinc-800 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="text-xs text-zinc-400 font-medium flex items-center gap-1.5">
          <Gauge className="w-3.5 h-3.5" />
          Load Control
        </div>
        <Badge
          variant="outline"
          className={cn(
            "text-[10px]",
            liveMode === "inertia" && "border-zinc-600 text-zinc-400",
            liveMode === "eddy_brake" && "border-cyan-500/40 text-cyan-400",
            liveMode === "road_load" && "border-amber-500/40 text-amber-400",
          )}
        >
          {MODE_LABELS[liveMode]}
        </Badge>
      </div>

      {/* Mode selector */}
      <div className="space-y-1">
        <Label className="text-[10px] text-zinc-500">Mode</Label>
        <Select value={selectedMode} onValueChange={(v) => handleModeChange(v as LoadMode)}>
          <SelectTrigger className="h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(MODE_LABELS) as LoadMode[]).map((m) => (
              <SelectItem key={m} value={m}>
                <span className="flex items-center gap-2">
                  {m === "inertia" && <Zap className="w-3 h-3" />}
                  {m === "eddy_brake" && <Gauge className="w-3 h-3" />}
                  {m === "road_load" && <Car className="w-3 h-3" />}
                  {MODE_LABELS[m]}
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-[10px] text-zinc-500">{MODE_DESCRIPTIONS[selectedMode]}</p>
      </div>

      {/* ---- Eddy Brake Controls ---- */}
      {liveMode === "eddy_brake" && (
        <div className="space-y-3 pt-1 border-t border-zinc-800">
          {/* Load target slider */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <Label className="text-[10px] text-zinc-500">Load Target</Label>
              <span className="text-xs font-mono text-zinc-200 tabular-nums">
                {loadTarget}%
              </span>
            </div>
            <Slider
              value={[loadTarget]}
              onValueChange={(v) => setLoadTarget(v?.[0] ?? 0)}
              onValueCommit={(v) => handleLoadTargetCommit(v?.[0] ?? 0)}
              min={0}
              max={100}
              step={1}
            />
          </div>

          {/* RPM Hold */}
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Switch
                checked={rpmHoldActive}
                onCheckedChange={handleRpmHoldToggle}
              />
              <Label className="text-xs text-zinc-300">RPM Hold</Label>
            </div>
            <div className="flex items-center gap-1.5">
              <Input
                type="number"
                value={rpmHoldTarget}
                onChange={(e) => handleRpmHoldTargetChange(Number(e.target.value))}
                className="w-20 h-7 text-xs text-right"
                min={1500}
                max={6500}
                step={100}
                disabled={!rpmHoldActive}
              />
              <span className="text-[10px] text-zinc-500">RPM</span>
            </div>
          </div>

          {/* Live readout */}
          <div className="grid grid-cols-3 gap-2">
            <ReadoutCell
              label="Current Load"
              value={`${liveLoad.toFixed(1)}%`}
              color="cyan"
            />
            <ReadoutCell
              label="Brake Torque"
              value={`${liveBrakeTorque.toFixed(0)} ft-lb`}
              color="cyan"
            />
            <ReadoutCell
              label="RPM Hold"
              value={
                liveRpmHoldActive
                  ? `${liveRpmHoldTarget.toFixed(0)} RPM`
                  : "Off"
              }
              color={liveRpmHoldActive ? "green" : "zinc"}
            />
          </div>
        </div>
      )}

      {/* ---- Road Load Readout ---- */}
      {liveMode === "road_load" && (
        <div className="space-y-3 pt-1 border-t border-zinc-800">
          <div className="grid grid-cols-3 gap-2">
            <ReadoutCell
              label="Speed"
              value={`${liveSpeedMph.toFixed(1)} mph`}
              color="amber"
            />
            <ReadoutCell
              label="Road Load"
              value={`${liveRoadTorque.toFixed(0)} ft-lb`}
              color="amber"
            />
            <ReadoutCell
              label="Mode"
              value="SAE J2264"
              color="amber"
            />
          </div>

          {/* Advanced road load config (collapsed) */}
          <Collapsible open={roadConfigOpen} onOpenChange={setRoadConfigOpen}>
            <CollapsibleTrigger className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors">
              {roadConfigOpen ? (
                <ChevronDown className="w-3 h-3" />
              ) : (
                <ChevronRight className="w-3 h-3" />
              )}
              Road Load Coefficients
            </CollapsibleTrigger>
            <CollapsibleContent className="pt-2 text-[10px] text-zinc-500 space-y-1">
              <p>A (rolling): 80 lb &bull; B (speed): 0.6 lb/mph &bull; C (aero): 0.03 lb/mph&sup2;</p>
              <p>Vehicle: 850 lb &bull; Tire circ: 6.8 ft &bull; Grade: 0%</p>
              <p className="text-zinc-600 italic">
                Configure via POST /simulator/load-mode with road_load payload
              </p>
            </CollapsibleContent>
          </Collapsible>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: compact readout cell
// ---------------------------------------------------------------------------

function ReadoutCell({
  label,
  value,
  color = "zinc",
}: {
  label: string;
  value: string;
  color?: "cyan" | "amber" | "green" | "zinc";
}) {
  const colorClass = {
    cyan: "text-cyan-400",
    amber: "text-amber-400",
    green: "text-green-400",
    zinc: "text-zinc-400",
  }[color];

  return (
    <div className="bg-zinc-900/60 rounded px-2 py-1.5">
      <div className="text-[10px] text-zinc-500 truncate">{label}</div>
      <div className={cn("text-xs font-mono tabular-nums", colorClass)}>
        {value}
      </div>
    </div>
  );
}
