import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../ui/sheet';
import { ChannelMappingPanel } from './ChannelMappingPanel';
import { DynoConfigPanel } from './DynoConfigPanel';
import { IngestionHealthPanel } from './IngestionHealthPanel';
import { InnovateAFRPanel } from './InnovateAFRPanel';
import { MappingConfidencePanel } from './MappingConfidencePanel';
import { PreflightCheckPanel } from './PreflightCheckPanel';
import { CollapsibleSection } from './CollapsibleSection';

interface HardwareSlideOverProps {
  apiUrl?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function HardwareSlideOver({
  apiUrl = 'http://127.0.0.1:5001/api/jetdrive',
  open,
  onOpenChange,
}: HardwareSlideOverProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-[400px] sm:max-w-[400px] bg-zinc-800 border-l border-zinc-700 backdrop-blur-sm"
      >
        <SheetHeader>
          <SheetTitle>Hardware Configuration</SheetTitle>
        </SheetHeader>

        <div className="mt-4 space-y-4 overflow-y-auto pb-6">
          <CollapsibleSection title="Preflight Check" defaultOpen>
            <PreflightCheckPanel apiUrl={apiUrl} />
          </CollapsibleSection>

          <CollapsibleSection title="Mapping Confidence" defaultOpen={false}>
            <MappingConfidencePanel apiUrl={apiUrl} />
          </CollapsibleSection>

          <CollapsibleSection title="Channel Mapping" defaultOpen={false}>
            <ChannelMappingPanel apiUrl={apiUrl} />
          </CollapsibleSection>

          <CollapsibleSection title="Dyno Config" defaultOpen={false}>
            <DynoConfigPanel apiUrl={apiUrl} />
          </CollapsibleSection>

          <CollapsibleSection title="Ingestion Health" defaultOpen={false}>
            <IngestionHealthPanel />
          </CollapsibleSection>

          <CollapsibleSection title="Innovate AFR" defaultOpen={false}>
            <InnovateAFRPanel apiUrl={apiUrl} />
          </CollapsibleSection>
        </div>
      </SheetContent>
    </Sheet>
  );
}
