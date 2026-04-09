import { useMemo, useRef, type ChangeEvent } from "react";
import { Database, FileUp, FlaskConical, Loader2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { CollapsibleSection } from "@/components/jetdrive/CollapsibleSection";
import { toast } from "@/lib/toast";
import { handleApiError } from "@/lib/api";
import type { HardwareConfig } from "@/api/v3Session";
import { useCalibrationLibrary } from "@/hooks/useCalibrationLibrary";

interface CalibrationLibraryPanelProps {
  config: HardwareConfig;
}

const BLEND_MIN_SIMILARITY = 0.55;

export function CalibrationLibraryPanel({ config }: CalibrationLibraryPanelProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const library = useCalibrationLibrary(config.engine_family);

  const entries = library.list?.entries ?? [];
  const totalEntries = library.stats?.total_entries ?? 0;
  const familyCount = library.stats?.by_family?.[config.engine_family] ?? 0;

  const summaryBadge = useMemo(
    () => `${familyCount}/${totalEntries} for ${config.engine_family}`,
    [familyCount, totalEntries, config.engine_family]
  );

  const handleFilePick = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      await library.ingestCalibration({
        file,
        config,
        operator: "user",
        notes: `Imported from V3 setup for ${config.engine_family}`,
      });
      toast.success(`Calibration ingested: ${file.name}`);
    } catch (error) {
      toast.error(handleApiError(error));
    } finally {
      event.target.value = "";
    }
  };

  const handlePreviewBlend = async () => {
    try {
      const result = await library.previewBlend({
        config,
        topN: 5,
        minSimilarity: BLEND_MIN_SIMILARITY,
      });
      toast.success(`Blend preview generated from ${result.match_count} entries`);
    } catch (error) {
      toast.error(handleApiError(error));
    }
  };

  const handleDelete = async (calibrationId: string) => {
    try {
      await library.deleteCalibration(calibrationId);
      toast.success(`Deleted calibration ${calibrationId.slice(0, 8)}`);
    } catch (error) {
      toast.error(handleApiError(error));
    }
  };

  return (
    <CollapsibleSection
      title="Calibration Library"
      icon={Database}
      defaultOpen={false}
      badge={summaryBadge}
    >
      <div className="space-y-4">
        <div className="grid grid-cols-3 gap-2">
          <MetricBadge label="Total" value={String(totalEntries)} />
          <MetricBadge label="Family" value={String(familyCount)} />
          <MetricBadge label="Blend N" value="5" />
        </div>

        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            id="calibration-library-upload"
            type="file"
            accept=".pvv"
            className="hidden"
            aria-label="Upload calibration PVV file"
            onChange={handleFilePick}
          />
          <Button
            type="button"
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={library.isIngesting}
          >
            {library.isIngesting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Ingesting...
              </>
            ) : (
              <>
                <FileUp className="h-4 w-4 mr-2" />
                Upload PVV Calibration
              </>
            )}
          </Button>
          <Button
            type="button"
            onClick={handlePreviewBlend}
            disabled={library.isBlending}
          >
            {library.isBlending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Blending...
              </>
            ) : (
              <>
                <FlaskConical className="h-4 w-4 mr-2" />
                Preview Blend
              </>
            )}
          </Button>
        </div>

        <div className="space-y-2">
          <Label className="text-xs text-muted-foreground">
            Library Entries ({entries.length})
          </Label>
          <div className="max-h-40 overflow-y-auto border rounded-md p-2 space-y-2">
            {library.isLoadingList ? (
              <p className="text-xs text-muted-foreground">Loading entries...</p>
            ) : entries.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                No entries yet for this family. Upload a PVV to seed it.
              </p>
            ) : (
              entries.map((entry) => (
                <div
                  key={entry.calibration_id}
                  className="flex items-center justify-between rounded border p-2"
                >
                  <div className="min-w-0">
                    <p className="text-xs font-medium truncate">
                      {entry.source_file_name ?? entry.calibration_id}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      {entry.calibration_id.slice(0, 8)} •{" "}
                      {formatIngestedTime(entry.ingested_at)}
                      {typeof entry.ingest_count === "number" && entry.ingest_count > 1
                        ? ` • re-ingested x${entry.ingest_count}`
                        : ""}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => handleDelete(entry.calibration_id)}
                    disabled={library.isDeleting}
                    title="Delete calibration"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))
            )}
          </div>
        </div>

        {library.blendPreview && (
          <div className="space-y-2 border rounded-md p-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">
                Blend Preview ({library.blendPreview.match_count} matches)
              </p>
              <Badge variant="secondary">
                {library.blendPreview.engine_family}
              </Badge>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Preview only — not applied to session unless selected during session init.
            </p>
            <p className="text-xs text-muted-foreground">
              Top matches:{" "}
              {library.blendPreview.matches
                .map(
                  (match) =>
                    `${match.calibration_id.slice(0, 6)} (${(
                      match.similarity_score * 100
                    ).toFixed(0)}%)`
                )
                .join(", ")}
            </p>
            {library.blendPreview.matches.some(
              (match) => match.similarity_score < BLEND_MIN_SIMILARITY
            ) && (
              <p className="text-[11px] text-amber-400">
                Some matches are below the recommended similarity threshold (
                {(BLEND_MIN_SIMILARITY * 100).toFixed(0)}%).
              </p>
            )}
            <BlendGridPreview
              rpmBins={library.blendPreview.rpm_bins}
              mapBins={library.blendPreview.map_bins}
              values={library.blendPreview.ve_front}
            />
          </div>
        )}

        {library.blendError && (
          <p className="text-xs text-red-400">{handleApiError(library.blendError)}</p>
        )}
      </div>
    </CollapsibleSection>
  );
}

function MetricBadge({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border p-2">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-sm font-semibold">{value}</p>
    </div>
  );
}

function BlendGridPreview({
  rpmBins,
  mapBins,
  values,
}: {
  rpmBins: number[];
  mapBins: number[];
  values: number[][];
}) {
  const displayRpm = rpmBins.slice(0, 6);
  const displayMap = mapBins.slice(0, 6);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[11px]">
        <thead>
          <tr>
            <th className="text-left p-1">RPM\MAP</th>
            {displayMap.map((map) => (
              <th key={map} className="text-center p-1">
                {Math.round(map)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {displayRpm.map((rpm, rowIndex) => (
            <tr key={rpm}>
              <td className="p-1 text-muted-foreground">{Math.round(rpm)}</td>
              {displayMap.map((_, colIndex) => (
                <td key={`${rpm}-${colIndex}`} className="text-center p-1 font-mono">
                  {(values[rowIndex]?.[colIndex] ?? 0).toFixed(1)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1 text-[10px] text-muted-foreground">
        Showing 6x6 preview of blended front-cylinder VE surface
      </p>
    </div>
  );
}

function formatIngestedTime(epoch?: number): string {
  if (!epoch) return "unknown";
  return new Date(epoch * 1000).toLocaleString();
}
