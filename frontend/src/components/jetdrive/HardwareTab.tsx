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
    <div className="space-y-6">
      {/* Preflight Check - Prominent at top */}
      <PreflightCheckPanel apiUrl={apiUrl} />
      
      {/* Mapping Confidence - Pre-capture readiness */}
      <MappingConfidencePanel apiUrl={apiUrl} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <ChannelMappingPanel apiUrl={apiUrl} />
          <DynoConfigPanel apiUrl={apiUrl} />
        </div>
        <div className="space-y-6">
          <IngestionHealthPanel />
          <InnovateAFRPanel apiUrl={apiUrl} />
        </div>
      </div>
    </div>
  );
}


