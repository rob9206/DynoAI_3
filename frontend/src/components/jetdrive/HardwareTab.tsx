/**
 * HardwareTab - JetDrive hardware & instrumentation panels
 *
 * Keeps JetDriveAutoTunePage lean by composing existing hardware-facing panels:
 * - Dyno configuration (Dynoware RT / drum specs)
 * - Ingestion health (data pipeline status)
 * - Innovate wideband (optional)
 */

import { DynoConfigPanel } from "./DynoConfigPanel";
import { IngestionHealthPanel } from "./IngestionHealthPanel";
import { InnovateAFRPanel } from "./InnovateAFRPanel";

interface HardwareTabProps {
  apiUrl?: string;
}

export function HardwareTab({ apiUrl = "http://127.0.0.1:5001/api/jetdrive" }: HardwareTabProps) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <DynoConfigPanel apiUrl={apiUrl} />
          <IngestionHealthPanel />
        </div>
        <div className="space-y-6">
          <InnovateAFRPanel apiUrl={apiUrl} />
        </div>
      </div>
    </div>
  );
}


