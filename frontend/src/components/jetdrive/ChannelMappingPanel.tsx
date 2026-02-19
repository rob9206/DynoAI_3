/**
 * ChannelMappingPanel - JetDrive Channel Mapping Configuration
 *
 * Allows users to:
 * - View provider's available channels
 * - Map source channels to canonical names (RPM, AFR, MAP, etc.)
 * - Configure value transforms (Lambda→AFR, Nm→ft-lb, etc.)
 * - Save/load mappings per provider
 * - Use templates for quick setup
 */

import { useState, useEffect, useCallback } from "react";
import {
  Check,
  X,
  Save,
  RefreshCw,
  Loader2,
  ChevronDown,
  ChevronUp,
  Settings2,
  Zap,
  AlertTriangle,
  Info,
  Trash2,
  FileDown,
  Wand2,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../ui/card";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "../ui/collapsible";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../ui/tooltip";
import { cn } from "../../lib/utils";

// =============================================================================
// Types
// =============================================================================

interface SourceChannel {
  id: number;
  name: string;
}

interface ChannelMapping {
  source_id: number;
  source_name: string;
  transform: string;
  enabled: boolean;
}

interface ProviderMapping {
  version: string;
  provider_signature: string;
  provider_id: number;
  provider_name: string;
  host: string;
  created_at: string;
  updated_at: string;
  channels: Record<string, ChannelMapping>;
}

interface Template {
  id: string;
  name: string;
  description: string;
  builtin: boolean;
  channel_count: number;
}

interface Transform {
  id: string;
  name: string;
  description: string;
}

interface ChannelMappingPanelProps {
  apiUrl?: string;
  className?: string;
}

// =============================================================================
// Constants
// =============================================================================

// Canonical channel definitions with descriptions
const CANONICAL_CHANNELS: Record<
  string,
  { name: string; description: string; required: boolean }
> = {
  rpm: { name: "Engine RPM", description: "Engine speed", required: true },
  afr_front: { name: "AFR Front", description: "Front cylinder AFR", required: true },
  afr_rear: { name: "AFR Rear", description: "Rear cylinder AFR", required: false },
  afr_combined: { name: "AFR Combined", description: "Combined AFR", required: false },
  lambda_front: { name: "Lambda Front", description: "Front Lambda (auto-converts to AFR)", required: false },
  lambda_rear: { name: "Lambda Rear", description: "Rear Lambda (auto-converts to AFR)", required: false },
  map_kpa: { name: "MAP (kPa)", description: "Manifold pressure", required: false },
  tps: { name: "TPS (%)", description: "Throttle position", required: false },
  torque: { name: "Torque", description: "Wheel torque", required: false },
  power: { name: "Power", description: "Wheel horsepower", required: false },
  ect: { name: "ECT", description: "Engine coolant temp", required: false },
  iat: { name: "IAT", description: "Intake air temp", required: false },
  spark: { name: "Spark Advance", description: "Ignition timing", required: false },
  knock: { name: "Knock Retard", description: "Knock sensor data", required: false },
};

// =============================================================================
// Sub-Components
// =============================================================================

const ChannelMappingRow = ({
  canonicalName,
  mapping,
  sourceChannels,
  transforms,
  onUpdate,
  onRemove,
}: {
  canonicalName: string;
  mapping: ChannelMapping;
  sourceChannels: SourceChannel[];
  transforms: Transform[];
  onUpdate: (field: string, value: string | number | boolean) => void;
  onRemove: () => void;
}) => {
  const canonicalInfo = CANONICAL_CHANNELS[canonicalName];

  return (
    <div className="flex items-center gap-2 p-2 bg-muted/30 rounded-lg">
      <div className="flex-1 min-w-[120px]">
        <div className="flex items-center gap-1">
          <span className="font-medium text-sm">
            {canonicalInfo?.name || canonicalName}
          </span>
          {canonicalInfo?.required && (
            <Badge variant="outline" className="text-xs px-1 py-0">
              Required
            </Badge>
          )}
        </div>
        <span className="text-xs text-muted-foreground">
          {canonicalInfo?.description}
        </span>
      </div>

      <div className="flex-1">
        <Select
          value={mapping.source_id.toString()}
          onValueChange={(v) => onUpdate("source_id", parseInt(v))}
        >
          <SelectTrigger className="h-8 text-sm">
            <SelectValue placeholder="Select source channel" />
          </SelectTrigger>
          <SelectContent>
            {sourceChannels.map((ch) => (
              <SelectItem key={ch.id} value={ch.id.toString()}>
                {ch.name} (ID: {ch.id})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="w-[140px]">
        <Select
          value={mapping.transform}
          onValueChange={(v) => onUpdate("transform", v)}
        >
          <SelectTrigger className="h-8 text-sm">
            <SelectValue placeholder="Transform" />
          </SelectTrigger>
          <SelectContent>
            {transforms.map((t) => (
              <SelectItem key={t.id} value={t.id}>
                {t.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0 text-red-500 hover:text-red-600"
              onClick={onRemove}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Remove mapping</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
};

const AddMappingRow = ({
  sourceChannels,
  transforms,
  mappedSourceIds,
  onAdd,
}: {
  sourceChannels: SourceChannel[];
  transforms: Transform[];
  mappedSourceIds: Set<number>;
  onAdd: (canonicalName: string, sourceId: number, transform: string) => void;
}) => {
  const [selectedCanonical, setSelectedCanonical] = useState<string>("");
  const [selectedSource, setSelectedSource] = useState<string>("");
  const [selectedTransform, setSelectedTransform] = useState<string>("identity");

  // Filter out already-mapped channels
  const availableChannels = CANONICAL_CHANNELS;
  const availableSources = sourceChannels.filter(
    (ch) => !mappedSourceIds.has(ch.id)
  );

  const handleAdd = () => {
    if (selectedCanonical && selectedSource) {
      onAdd(selectedCanonical, parseInt(selectedSource), selectedTransform);
      setSelectedCanonical("");
      setSelectedSource("");
      setSelectedTransform("identity");
    }
  };

  return (
    <div className="flex items-center gap-2 p-2 border border-dashed border-muted-foreground/30 rounded-lg">
      <div className="flex-1">
        <Select value={selectedCanonical} onValueChange={setSelectedCanonical}>
          <SelectTrigger className="h-8 text-sm">
            <SelectValue placeholder="Canonical channel" />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(availableChannels).map(([key, info]) => (
              <SelectItem key={key} value={key}>
                {info.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex-1">
        <Select value={selectedSource} onValueChange={setSelectedSource}>
          <SelectTrigger className="h-8 text-sm">
            <SelectValue placeholder="Source channel" />
          </SelectTrigger>
          <SelectContent>
            {availableSources.map((ch) => (
              <SelectItem key={ch.id} value={ch.id.toString()}>
                {ch.name} (ID: {ch.id})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="w-[140px]">
        <Select value={selectedTransform} onValueChange={setSelectedTransform}>
          <SelectTrigger className="h-8 text-sm">
            <SelectValue placeholder="Transform" />
          </SelectTrigger>
          <SelectContent>
            {transforms.map((t) => (
              <SelectItem key={t.id} value={t.id}>
                {t.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Button
        variant="outline"
        size="sm"
        className="h-8"
        onClick={handleAdd}
        disabled={!selectedCanonical || !selectedSource}
      >
        <Check className="h-4 w-4" />
      </Button>
    </div>
  );
};

// =============================================================================
// Main Component
// =============================================================================

export function ChannelMappingPanel({
  apiUrl = "http://127.0.0.1:5001/api/jetdrive",
  className,
}: ChannelMappingPanelProps) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [mapping, setMapping] = useState<ProviderMapping | null>(null);
  const [sourceChannels, setSourceChannels] = useState<SourceChannel[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [transforms, setTransforms] = useState<Transform[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Fetch transforms
  useEffect(() => {
    fetch(`${apiUrl}/mapping/transforms`)
      .then((r) => r.json())
      .then((data) => setTransforms(data.transforms || []))
      .catch((e) => console.error("Failed to fetch transforms:", e));
  }, [apiUrl]);

  // Fetch templates
  useEffect(() => {
    fetch(`${apiUrl}/mapping/templates`)
      .then((r) => r.json())
      .then((data) => setTemplates(data.templates || []))
      .catch((e) => console.error("Failed to fetch templates:", e));
  }, [apiUrl]);

    // Auto-detect mapping from connected provider
    const autoDetect = useCallback(async () => {
        setLoading(true);
        setError(null);
        setSuccess(null);

        try {
            const response = await fetch(`${apiUrl}/mapping/auto-detect`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({}),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "Auto-detect failed");
            }

            setMapping(data.mapping);
            setSourceChannels(data.provider_channels || []);

            const mappedCount = Object.keys(data.mapping.channels).length;
            const missingRequired = data.missing_required || [];

            if (missingRequired.length > 0) {
                setError(`Missing required channels: ${missingRequired.join(", ")}`);
            } else {
                setSuccess(`Auto-detected ${mappedCount} channel mappings with confidence scoring`);
            }
        } catch (e) {
            setError(e instanceof Error ? e.message : "Auto-detect failed");
        } finally {
            setLoading(false);
        }
    }, [apiUrl]);

  // Load from template
  const loadTemplate = useCallback(
    async (templateId: string) => {
      setLoading(true);
      setError(null);
      setSuccess(null);

      try {
        const response = await fetch(`${apiUrl}/mapping/from-template`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ template_id: templateId }),
        });

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.error || "Failed to load template");
        }

        setMapping(data.mapping);
        setSourceChannels(data.provider_channels || []);
        setSuccess(`Loaded template: ${templateId}`);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load template");
      } finally {
        setLoading(false);
      }
    },
    [apiUrl]
  );

  // Save mapping
  const saveMapping = useCallback(async () => {
    if (!mapping) return;

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetch(
        `${apiUrl}/mapping/${mapping.provider_signature}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(mapping),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Failed to save mapping");
      }

      setMapping(data);
      setSuccess("Mapping saved successfully");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save mapping");
    } finally {
      setSaving(false);
    }
  }, [apiUrl, mapping]);

  // Update a channel mapping
  const updateChannelMapping = useCallback(
    (canonicalName: string, field: string, value: string | number | boolean) => {
      if (!mapping) return;

      setMapping({
        ...mapping,
        channels: {
          ...mapping.channels,
          [canonicalName]: {
            ...mapping.channels[canonicalName],
            [field]: value,
            // Update source_name when source_id changes
            ...(field === "source_id"
              ? {
                  source_name:
                    sourceChannels.find((c) => c.id === value)?.name || "",
                }
              : {}),
          },
        },
      });
    },
    [mapping, sourceChannels]
  );

  // Remove a channel mapping
  const removeChannelMapping = useCallback(
    (canonicalName: string) => {
      if (!mapping) return;

      const newChannels = { ...mapping.channels };
      delete newChannels[canonicalName];

      setMapping({
        ...mapping,
        channels: newChannels,
      });
    },
    [mapping]
  );

  // Add a new channel mapping
  const addChannelMapping = useCallback(
    (canonicalName: string, sourceId: number, transform: string) => {
      if (!mapping) return;

      const sourceName =
        sourceChannels.find((c) => c.id === sourceId)?.name || "";

      setMapping({
        ...mapping,
        channels: {
          ...mapping.channels,
          [canonicalName]: {
            source_id: sourceId,
            source_name: sourceName,
            transform,
            enabled: true,
          },
        },
      });
    },
    [mapping, sourceChannels]
  );

  // Get mapped source IDs
  const mappedSourceIds = new Set(
    mapping
      ? Object.values(mapping.channels).map((m) => m.source_id)
      : []
  );

  // Check for missing required channels
  const missingRequired = mapping
    ? Object.entries(CANONICAL_CHANNELS)
        .filter(([key, info]) => info.required && !mapping.channels[key])
        .map(([key]) => key)
    : [];

  return (
    <Card className={cn("", className)}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Settings2 className="h-5 w-5 text-blue-500" />
              Channel Mapping
            </CardTitle>
            <CardDescription>
              Map dyno channels to canonical names for analysis
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={autoDetect}
              disabled={loading}
              className="gap-1"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Wand2 className="h-4 w-4" />
              )}
              Auto-Detect
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={saveMapping}
              disabled={saving || !mapping}
              className="gap-1"
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              Save
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Error/Success messages */}
        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-500">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {success && (
          <div className="flex items-center gap-2 p-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-500">
            <Check className="h-4 w-4 shrink-0" />
            <span className="text-sm">{success}</span>
          </div>
        )}

        {/* Templates */}
        {templates.length > 0 && !mapping && (
          <div className="p-3 bg-muted/30 rounded-lg">
            <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
              <FileDown className="h-4 w-4" />
              Quick Start from Template
            </h4>
            <div className="flex flex-wrap gap-2">
              {templates.map((t) => (
                <Button
                  key={t.id}
                  variant="outline"
                  size="sm"
                  onClick={() => loadTemplate(t.id)}
                  disabled={loading}
                >
                  {t.name}
                </Button>
              ))}
            </div>
          </div>
        )}

        {/* No mapping state */}
        {!mapping && !loading && (
          <div className="text-center py-8 text-muted-foreground">
            <Settings2 className="h-12 w-12 mx-auto mb-3 opacity-50" />
            <p>No channel mapping configured</p>
            <p className="text-sm mt-1">
              Click "Auto-Detect" or select a template to get started
            </p>
          </div>
        )}

        {/* Mapping info */}
        {mapping && (
          <>
            <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
              <div>
                <div className="font-medium">{mapping.provider_name}</div>
                <div className="text-sm text-muted-foreground">
                  {mapping.host} • ID: 0x{mapping.provider_id.toString(16).toUpperCase()}
                </div>
              </div>
              <div className="text-right text-sm text-muted-foreground">
                <div>{Object.keys(mapping.channels).length} channels mapped</div>
                {mapping.updated_at && (
                  <div>
                    Updated: {new Date(mapping.updated_at).toLocaleDateString()}
                  </div>
                )}
              </div>
            </div>

            {/* Missing required warning */}
            {missingRequired.length > 0 && (
              <div className="flex items-center gap-2 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-yellow-500">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span className="text-sm">
                  Missing required channels:{" "}
                  {missingRequired.map((k) => CANONICAL_CHANNELS[k]?.name || k).join(", ")}
                </span>
              </div>
            )}

            {/* Channel mappings */}
            <div className="space-y-2">
              <h4 className="text-sm font-medium flex items-center gap-2">
                <Zap className="h-4 w-4" />
                Channel Mappings
              </h4>

              {Object.entries(mapping.channels).map(([name, ch]) => (
                <ChannelMappingRow
                  key={name}
                  canonicalName={name}
                  mapping={ch}
                  sourceChannels={sourceChannels}
                  transforms={transforms}
                  onUpdate={(field, value) =>
                    updateChannelMapping(name, field, value)
                  }
                  onRemove={() => removeChannelMapping(name)}
                />
              ))}

              {/* Add new mapping */}
              <AddMappingRow
                sourceChannels={sourceChannels}
                transforms={transforms}
                mappedSourceIds={mappedSourceIds}
                onAdd={addChannelMapping}
              />
            </div>

            {/* Advanced options */}
            <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
              <CollapsibleTrigger asChild>
                <Button variant="ghost" className="w-full justify-between">
                  <span className="flex items-center gap-2">
                    <Info className="h-4 w-4" />
                    Advanced Options
                  </span>
                  {showAdvanced ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="space-y-2 mt-2">
                <div className="p-3 bg-muted/30 rounded-lg text-sm">
                  <div className="font-medium mb-1">Provider Signature</div>
                  <code className="text-xs text-muted-foreground break-all">
                    {mapping.provider_signature}
                  </code>
                  <p className="text-xs text-muted-foreground mt-2">
                    If channels change in Power Core, a new signature will be generated
                    and you'll need to re-map.
                  </p>
                </div>
              </CollapsibleContent>
            </Collapsible>
          </>
        )}
      </CardContent>
    </Card>
  );
}

export default ChannelMappingPanel;
