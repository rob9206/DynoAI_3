/**
 * HardwareTab - JetDrive hardware & instrumentation panels
 *
 * Keeps JetDriveAutoTunePage lean by composing existing hardware-facing panels:
 * - Preflight check (validates setup before starting)
 * - Mapping confidence (pre-capture readiness check)
 * - Channel mapping (configure canonical channel names)
 * - Dyno configuration (Dynoware RT / drum specs)
 * - Ingestion health (data pipeline status)
 * - Innovate wideband (optional)
 */

import { DynoConfigPanel } from "./DynoConfigPanel";
import { IngestionHealthPanel } from "./IngestionHealthPanel";
import { InnovateAFRPanel } from "./InnovateAFRPanel";
import { PreflightCheckPanel } from "./PreflightCheckPanel";
import { ChannelMappingPanel } from "./ChannelMappingPanel";
import { MappingConfidencePanel } from "./MappingConfidencePanel";

interface HardwareTabProps {
  apiUrl?: string;
}

export function HardwareTab({ apiUrl = "http://127.0.0.1:5001/api/jetdrive" }: HardwareTabProps) {
  return (
    <div className="space-y-8">
      {/* Header Section - Quick Status Overview */}
      <div className="bg-gradient-to-br from-slate-900/90 via-slate-800/80 to-slate-900/90 rounded-xl border border-slate-700/50 p-6 backdrop-blur-sm">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
              Hardware Configuration
            </h2>
            <p className="text-slate-400 text-sm">
              Configure and validate your dyno setup for optimal data capture
            </p>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/30">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-slate-300">System Ready</span>
            </div>
          </div>
        </div>
      </div>

      {/* Preflight Check - Prominent at top with enhanced styling */}
      <div className="relative">
        <div className="absolute -inset-1 bg-gradient-to-r from-blue-600/20 to-cyan-600/20 rounded-xl blur-sm opacity-50" />
        <div className="relative">
          <PreflightCheckPanel apiUrl={apiUrl} />
        </div>
      </div>
      
      {/* Mapping Confidence - Enhanced with better visual hierarchy */}
      <div className="relative">
        <div className="absolute -inset-1 bg-gradient-to-r from-emerald-600/20 to-teal-600/20 rounded-xl blur-sm opacity-50" />
        <div className="relative">
          <MappingConfidencePanel apiUrl={apiUrl} />
        </div>
      </div>

      {/* Configuration Grid - Enhanced spacing and visual separation */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="space-y-8">
          <div className="relative">
            <div className="absolute -inset-1 bg-gradient-to-r from-violet-600/20 to-purple-600/20 rounded-xl blur-sm opacity-50" />
            <div className="relative">
              <ChannelMappingPanel apiUrl={apiUrl} />
            </div>
          </div>
          <div className="relative">
            <div className="absolute -inset-1 bg-gradient-to-r from-amber-600/20 to-orange-600/20 rounded-xl blur-sm opacity-50" />
            <div className="relative">
              <DynoConfigPanel apiUrl={apiUrl} />
            </div>
          </div>
        </div>
        <div className="space-y-8">
          <div className="relative">
            <div className="absolute -inset-1 bg-gradient-to-r from-rose-600/20 to-pink-600/20 rounded-xl blur-sm opacity-50" />
            <div className="relative">
              <IngestionHealthPanel />
            </div>
          </div>
          <div className="relative">
            <div className="absolute -inset-1 bg-gradient-to-r from-indigo-600/20 to-blue-600/20 rounded-xl blur-sm opacity-50" />
            <div className="relative">
              <InnovateAFRPanel apiUrl={apiUrl} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


