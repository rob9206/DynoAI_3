/**
 * UnifiedTuningTab — Single "Tuning" tab with Wizard | Manual | Accelerated modes.
 * Orchestrates TuningWizard, manual section-based UI, and V3 accelerated session.
 * State (live data, imported tune, session) persists across mode switches.
 */

import { useState, useEffect } from "react";
import { Zap, Settings, Gauge } from "lucide-react";
import { cn } from "@/lib/utils";
import type { TuneImportResult } from "./TuneImport";
import { V3TuningTab } from "./V3TuningTab";

export type TuningMode = "wizard" | "manual" | "accelerated";

export interface UnifiedTuningTabProps {
  /** Wizard mode: SmartPromptBanner + TuningWizard (same props as before). */
  renderWizardContent: () => React.ReactNode;
  /** Manual mode: classic gauges + VE table + results (section-based or legacy block). */
  renderManualContent: () => React.ReactNode;
  /** Shared: seed accelerated session or show in tune import. */
  importedTune?: TuneImportResult | null;
  /** Notify parent when mode changes (e.g. to keep useAIAssistant enabled only in wizard). */
  onTuningModeChange?: (mode: TuningMode) => void;
}

const MODES: { value: TuningMode; label: string; icon: typeof Zap }[] = [
  { value: "wizard", label: "Wizard", icon: Zap },
  { value: "manual", label: "Manual", icon: Gauge },
  { value: "accelerated", label: "Accelerated", icon: Zap },
];

export function UnifiedTuningTab({
  renderWizardContent,
  renderManualContent,
  importedTune = null,
  onTuningModeChange,
}: UnifiedTuningTabProps) {
  const [tuningMode, setTuningMode] = useState<TuningMode>("wizard");

  const setMode = (mode: TuningMode) => {
    setTuningMode(mode);
    onTuningModeChange?.(mode);
  };

  useEffect(() => {
    onTuningModeChange?.(tuningMode);
    // Sync initial mode only on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-4">
      {/* Mode selector: Wizard | Manual | Accelerated */}
      <div className="flex items-center justify-between gap-2">
        <div
          className="inline-flex rounded-lg border border-zinc-700 bg-zinc-800/50 p-0.5"
          role="tablist"
          aria-label="Tuning mode"
        >
          {MODES.map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tuningMode === value}
              onClick={() => setMode(value)}
              className={cn(
                "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
                tuningMode === value
                  ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                  : "text-zinc-400 border border-transparent hover:text-zinc-300 hover:bg-zinc-700/50"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Content: keep all mounted so state persists across mode switches */}
      <div className="relative">
        <div
          className={tuningMode === "wizard" ? "block" : "hidden"}
          aria-hidden={tuningMode !== "wizard"}
        >
          {renderWizardContent()}
        </div>
        <div
          className={tuningMode === "manual" ? "block" : "hidden"}
          aria-hidden={tuningMode !== "manual"}
        >
          {renderManualContent()}
        </div>
        <div
          className={tuningMode === "accelerated" ? "block" : "hidden"}
          aria-hidden={tuningMode !== "accelerated"}
        >
          <V3TuningTab importedTune={importedTune} />
        </div>
      </div>
    </div>
  );
}
