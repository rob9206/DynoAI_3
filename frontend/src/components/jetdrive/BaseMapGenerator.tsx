import { useRef, useMemo, useState, type ChangeEvent } from "react";
import { AlertTriangle, Download, FileUp, FlaskConical, GitCompareArrows, Loader2, Map, ClipboardPaste, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/lib/toast";
import { handleApiError } from "@/lib/api";
import { blendCalibrationLibrary, type CalibrationLibraryBlendResponse } from "@/api/calibrationLibrary";
import { downloadFile } from "@/utils/veExport";
import { VEHeatmap } from "@/components/results/VEHeatmap";
import { parsePVV, tableToGrid, INHG_TO_KPA, normalizeMapColumns } from "@/utils/pvvParser";

const KPA_PER_INHG = INHG_TO_KPA;

const PC_RPM_BINS = [
  750, 1000, 1125, 1250, 1500, 1750, 2000, 2250, 2500, 2750,
  3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000, 7500, 8000,
];
const PC_MAP_INHG = [
  3.1, 4.5, 5.9, 7.4, 8.8, 10.4, 11.8, 13.3, 14.8, 16.2, 17.8, 19.2, 20.7, 22.1, 25.1, 28.0, 30.8,
];
const PC_MAP_KPA = PC_MAP_INHG.map((v) => Math.round(v * KPA_PER_INHG * 10) / 10);

const VALID_AFR_MIN = 10.0;
const VALID_AFR_MAX = 18.0;

const ENGINE_FAMILIES = [
  { value: "tc_88", label: "TC 88" },
  { value: "tc_96", label: "TC 96" },
  { value: "tc_103", label: "TC 103" },
  { value: "tc_110", label: "TC 110" },
  { value: "m8_107", label: "M8 107" },
  { value: "m8_114", label: "M8 114" },
  { value: "m8_117", label: "M8 117" },
  { value: "m8_131", label: "M8 131" },
  { value: "evo_1200", label: "Evo 1200" },
  { value: "revmax_1250", label: "RevMax 1250" },
] as const;

const DISPLACEMENT_BY_FAMILY: Record<string, { value: number; label: string }[]> = {
  tc_88:  [{ value: 0, label: "Any" }, { value: 88, label: "88 ci" }, { value: 95, label: "95 ci (big bore)" }],
  tc_96:  [{ value: 0, label: "Any" }, { value: 96, label: "96 ci" }, { value: 103, label: "103 ci (big bore)" }, { value: 107, label: "107 ci (big bore)" }],
  tc_103: [{ value: 0, label: "Any" }, { value: 103, label: "103 ci" }, { value: 107, label: "107 ci (big bore)" }, { value: 110, label: "110 ci (big bore)" }],
  tc_110: [{ value: 0, label: "Any" }, { value: 110, label: "110 ci" }, { value: 113, label: "113 ci (big bore)" }, { value: 117, label: "117 ci (big bore)" }],
  m8_107: [{ value: 0, label: "Any" }, { value: 107, label: "107 ci" }, { value: 114, label: "114 ci (big bore)" }],
  m8_114: [{ value: 0, label: "Any" }, { value: 114, label: "114 ci" }, { value: 117, label: "117 ci (big bore)" }],
  m8_117: [{ value: 0, label: "Any" }, { value: 117, label: "117 ci" }, { value: 124, label: "124 ci (big bore)" }, { value: 128, label: "128 ci (big bore)" }],
  m8_131: [{ value: 0, label: "Any" }, { value: 131, label: "131 ci" }],
  evo_1200: [{ value: 0, label: "Any" }, { value: 74, label: "74 ci (1200)" }, { value: 80, label: "80 ci (1340)" }],
  revmax_1250: [{ value: 0, label: "Any" }, { value: 76, label: "76 ci (1250)" }],
};

const CAM_OPTIONS = [
  { value: "stock", label: "Stock" },
  { value: "se_255", label: "SE 255" },
  { value: "se_257", label: "SE 257" },
  { value: "se_258", label: "SE 258" },
  { value: "se_259e", label: "SE 259E" },
  { value: "se_260", label: "SE 260" },
  { value: "se_264", label: "SE 264" },
  { value: "s&s_475", label: "S&S 475" },
  { value: "s&s_510", label: "S&S 510" },
  { value: "s&s_551", label: "S&S 551" },
  { value: "s&s_570", label: "S&S 570" },
  { value: "s&s_585", label: "S&S 585" },
  { value: "feuling_525", label: "Feuling 525" },
  { value: "feuling_543", label: "Feuling 543" },
  { value: "feuling_574", label: "Feuling 574" },
  { value: "wood_tw777", label: "Wood TW-777" },
  { value: "andrews_48h", label: "Andrews 48H" },
  { value: "andrews_54h", label: "Andrews 54H" },
  { value: "andrews_57h", label: "Andrews 57H" },
  { value: "tman_555", label: "T-Man 555" },
  { value: "tman_577", label: "T-Man 577" },
  { value: "tman_590", label: "T-Man 590" },
  { value: "tman_600", label: "T-Man 600" },
  { value: "tts_100", label: "TTS-100" },
  { value: "tts_150", label: "TTS-150" },
  { value: "maxcell_t905a", label: "Max-Cell T905a" },
  { value: "crusher_tc24d", label: "Crusher TC24D" },
  { value: "redshift_575", label: "RedShift 575" },
  { value: "other", label: "Other" },
];
const EXHAUST_OPTIONS = [
  { value: "stock", label: "Stock" },
  { value: "slip_on", label: "Slip-On Mufflers" },
  { value: "2into1", label: "2-into-1" },
  { value: "2into1_tunable", label: "2-into-1 Tunable" },
  { value: "true_duals", label: "True Duals" },
  { value: "open", label: "Open / Debaffled" },
];

export function BaseMapGenerator() {
  const [family, setFamily] = useState("tc_103");
  const [displacement, setDisplacement] = useState(0);
  const [cam, setCam] = useState("stock");
  const [exhaust, setExhaust] = useState("stock");
  const [isGenerating, setIsGenerating] = useState(false);
  const [result, setResult] = useState<CalibrationLibraryBlendResponse | null>(null);
  const [comparisonVE, setComparisonVE] = useState<number[][] | null>(null);
  const [comparisonLabel, setComparisonLabel] = useState("");
  const [csvText, setCsvText] = useState("");
  const [showCsvPaste, setShowCsvPaste] = useState(false);
  const compareFileRef = useRef<HTMLInputElement | null>(null);

  const validAfr = useMemo(() => {
    if (!result?.afr_targets) return { entries: [], hasBadData: false };
    const all = Object.entries(result.afr_targets).sort(([a], [b]) => Number(a) - Number(b));
    const good = all.filter(([, v]) => Number(v) >= VALID_AFR_MIN && Number(v) <= VALID_AFR_MAX);
    return { entries: good, hasBadData: good.length < all.length };
  }, [result]);

  const diffResult = useMemo(() => {
    if (!comparisonVE || !result?.ve_front) return null;
    const rows = Math.min(comparisonVE.length, result.ve_front.length);
    const cols = rows > 0 ? Math.min(comparisonVE[0].length, result.ve_front[0].length) : 0;
    const diff: number[][] = [];
    let sumAbs = 0;
    let maxPos = -Infinity;
    let maxNeg = Infinity;
    let count = 0;
    for (let r = 0; r < rows; r++) {
      const row: number[] = [];
      for (let c = 0; c < cols; c++) {
        const d = (comparisonVE[r]?.[c] ?? 0) - (result.ve_front[r]?.[c] ?? 0);
        row.push(d);
        sumAbs += Math.abs(d);
        if (d > maxPos) maxPos = d;
        if (d < maxNeg) maxNeg = d;
        count++;
      }
      diff.push(row);
    }
    return {
      grid: diff,
      meanAbsDiff: count > 0 ? sumAbs / count : 0,
      maxPositive: maxPos === -Infinity ? 0 : maxPos,
      maxNegative: maxNeg === Infinity ? 0 : maxNeg,
    };
  }, [comparisonVE, result]);

  const handlePvvImport = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const parsed = parsePVV(text);
      const table = parsed.veFront;
      if (!table) {
        toast.error("No front cylinder VE table found in PVV file.");
        return;
      }
      // Defensive: ensure columns are kPa even if an older parser path was used
      const maxCol = table.columns.length > 0 ? Math.max(...table.columns) : 0;
      if (maxCol > 0 && maxCol <= 35) {
        const fixed = normalizeMapColumns(table.columns, 'inhg');
        table.columns = fixed.columns;
        table.originalColumns = fixed.originalColumns;
        table.sourceColumnUnit = 'inhg';
      }
      const regridded = tableToGrid(table, PC_RPM_BINS, PC_MAP_KPA);
      setComparisonVE(regridded);
      setComparisonLabel(file.name);
      const unitNote = table.sourceColumnUnit === 'inhg' ? ' (inHg→kPa)' : '';
      toast.success(`Imported ${file.name} (${table.rows.length}×${table.columns.length} regridded to ${PC_RPM_BINS.length}×${PC_MAP_INHG.length})${unitNote}`);
    } catch (err) {
      toast.error(`Failed to parse PVV: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      event.target.value = "";
    }
  };

  const handleCsvParse = () => {
    try {
      const lines = csvText.trim().split("\n").map((l) => l.trim()).filter(Boolean);
      if (lines.length === 0) { toast.error("No data to parse."); return; }
      let startRow = 0;
      const firstCell = lines[0].split(/[,\t]/)[0].trim();
      if (isNaN(Number(firstCell))) startRow = 1;
      const grid: number[][] = [];
      for (let i = startRow; i < lines.length; i++) {
        const parts = lines[i].split(/[,\t]/).map((s) => s.trim());
        const firstNum = Number(parts[0]);
        const dataStart = !isNaN(firstNum) && firstNum > 100 ? 1 : 0;
        const row = parts.slice(dataStart).map(Number);
        if (row.some(isNaN)) { toast.error(`Row ${i + 1} contains non-numeric values.`); return; }
        grid.push(row);
      }
      if (grid.length !== PC_RPM_BINS.length || grid[0]?.length !== PC_MAP_INHG.length) {
        toast.error(`Expected ${PC_RPM_BINS.length} rows x ${PC_MAP_INHG.length} cols, got ${grid.length} x ${grid[0]?.length ?? 0}. Paste the VE values matching the Power Core grid.`);
        return;
      }
      setComparisonVE(grid);
      setComparisonLabel("Pasted CSV");
      setShowCsvPaste(false);
      setCsvText("");
      toast.success("CSV parsed successfully");
    } catch (err) {
      toast.error(`CSV parse error: ${err instanceof Error ? err.message : "Unknown error"}`);
    }
  };

  const handleGenerate = async () => {
    setIsGenerating(true);
    setResult(null);
    try {
      const blend = await blendCalibrationLibrary(
        {
          engine_family: family,
          displacement_ci: displacement,
          cam_spec: cam,
          exhaust_type: exhaust,
          rpm_bins: PC_RPM_BINS,
          map_bins: PC_MAP_KPA,
        },
        5,
        0.40,
      );
      setResult(blend);
      if (blend.match_count === 0) {
        toast.info("No matching calibrations found for this config.");
      } else {
        toast.success(`Base map generated from ${blend.match_count} calibrations`);
      }
    } catch (error) {
      toast.error(handleApiError(error));
    } finally {
      setIsGenerating(false);
    }
  };

  const handleExportCSV = () => {
    if (!result) return;
    const mapLabelsInhg = result.map_bins.map((kpa) => (kpa / KPA_PER_INHG).toFixed(1));
    const rows = [
      ["RPM\\MAP(inHg)", ...mapLabelsInhg].join(","),
      ...result.ve_front.map((row, i) =>
        [String(Math.round(result.rpm_bins[i])), ...row.map((v) => v.toFixed(1))].join(",")
      ),
    ];
    if (validAfr.entries.length > 0) {
      rows.push("");
      rows.push("AFR Targets");
      rows.push("MAP_kPa,Target_AFR");
      for (const [mapKpa, afr] of validAfr.entries) {
        rows.push(`${mapKpa},${Number(afr).toFixed(2)}`);
      }
    }
    const disp = displacement > 0 ? `_${displacement}ci` : "";
    downloadFile(rows.join("\n"), `base_map_${family}${disp}_${cam}_${exhaust}.csv`, "text/csv");
    toast.success("CSV downloaded");
  };

  const handleExportJSON = () => {
    if (!result) return;
    downloadFile(
      JSON.stringify(result, null, 2),
      `base_map_${family}${displacement > 0 ? `_${displacement}ci` : ""}_${cam}_${exhaust}.json`,
      "application/json",
    );
    toast.success("JSON downloaded");
  };

  const handleExportPVV = () => {
    if (!result) return;
    const mapInhg = result.map_bins.map((kpa) => (kpa / KPA_PER_INHG).toFixed(1));
    const rpmLabels = result.rpm_bins.map((r) => {
      const v = r / 1000;
      return v === Math.floor(v) ? String(v) : v.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
    });

    const buildItem = (name: string, units: string, colUnits: string, rowUnits: string, colLabels: string[], rowLabels: string[], values: number[][], decimals: number) => {
      const cols = colLabels.map((l) => `      <Col label="${l}" />`).join("\n");
      const rows = rowLabels.map((rl, ri) => {
        const cells = values[ri]?.map((v) => `        <Cell value="${v.toFixed(decimals)}" />`)?.join("\n") ?? "";
        return `      <Row label="${rl}">\n${cells}\n      </Row>`;
      }).join("\n");
      return `  <Item name="${name}" units="${units}">\n    <Columns units="${colUnits}">\n${cols}\n    </Columns>\n    <Rows units="${rowUnits}">\n${rows}\n    </Rows>\n  </Item>`;
    };

    const items: string[] = [];

    if (validAfr.entries.length > 0) {
      const afrMapInhg = validAfr.entries.map(([kpa]) => (Number(kpa) / KPA_PER_INHG).toFixed(1));
      const afrValues = rpmLabels.map(() => validAfr.entries.map(([, v]) => Number(v)));
      items.push(buildItem("Air-Fuel Ratio", "AFR", "Inches Of Mercury", "RPMx1000", afrMapInhg, rpmLabels, afrValues, 2));
    }

    items.push(buildItem("VE (MAP based/Front Cyl)", "%", "Inches Of Mercury", "RPMx1000", mapInhg, rpmLabels, result.ve_front, 1));

    if (result.ve_rear) {
      items.push(buildItem("VE (MAP based/Rear Cyl)", "%", "Inches Of Mercury", "RPMx1000", mapInhg, rpmLabels, result.ve_rear, 1));
    }

    const pvv = `<PVV>\n  <!--Generated by DynoAI Base Map Generator-->\n${items.join("\n")}\n</PVV>`;
    const disp = displacement > 0 ? `_${displacement}ci` : "";
    downloadFile(pvv, `base_map_${family}${disp}_${cam}_${exhaust}.pvv`, "application/xml");
    toast.success("PVV downloaded");
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Map className="h-5 w-5 text-orange-500" />
            Base Map Generator
          </CardTitle>
          <CardDescription>
            Select an engine config to auto-blend matching calibrations into a base VE map and AFR targets.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="space-y-2">
              <Label>Engine Family</Label>
              <Select value={family} onValueChange={(v) => { setFamily(v); setDisplacement(0); }}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ENGINE_FAMILIES.map((f) => (
                    <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Displacement</Label>
              <Select value={String(displacement)} onValueChange={(v) => setDisplacement(Number(v))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(DISPLACEMENT_BY_FAMILY[family] ?? [{ value: 0, label: "Any" }]).map((d) => (
                    <SelectItem key={d.value} value={String(d.value)}>{d.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Cam Spec</Label>
              <Select value={cam} onValueChange={setCam}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CAM_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Exhaust Type</Label>
              <Select value={exhaust} onValueChange={setExhaust}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {EXHAUST_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <Button onClick={handleGenerate} disabled={isGenerating} className="w-full" size="lg">
            {isGenerating ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <FlaskConical className="h-4 w-4 mr-2" />
                Generate Base Map
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {result && result.match_count > 0 && (
        <>
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">
                  Blended from {result.match_count} calibrations
                </CardTitle>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={handleExportPVV}>
                    <Download className="h-3.5 w-3.5 mr-1.5" />
                    PVV
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleExportCSV}>
                    <Download className="h-3.5 w-3.5 mr-1.5" />
                    CSV
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleExportJSON}>
                    <Download className="h-3.5 w-3.5 mr-1.5" />
                    JSON
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 mt-2">
                {result.matches.map((m) => (
                  <Badge key={m.calibration_id} variant="secondary" className="text-xs">
                    {m.source_file_name || m.calibration_id.slice(0, 8)} — {(m.similarity_score * 100).toFixed(0)}%
                  </Badge>
                ))}
              </div>
              <div className="flex items-center gap-4 mt-3 pt-3 border-t border-zinc-800 text-xs text-zinc-400">
                <div>
                  <span className="font-medium">Grid Coverage:</span>{" "}
                  {(typeof result.grid_coverage_pct === "number" ? result.grid_coverage_pct : 0).toFixed(1)}%
                </div>
                <div>
                  <span className="font-medium">Native Resolution:</span>{" "}
                  {typeof result.native_resolution_count === "number" ? result.native_resolution_count : 0} of {result.match_count}
                </div>
              </div>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">VE (MAP based/Front Cyl) (%)</CardTitle>
              <CardDescription>MAP [read-only] (in-hg)</CardDescription>
            </CardHeader>
            <CardContent>
              <VEHeatmap
                data={result.ve_front}
                rowLabels={result.rpm_bins.map((r) => (r / 1000).toFixed(3))}
                colLabels={result.map_bins.map((kpa) => (kpa / KPA_PER_INHG).toFixed(1))}
                colorMode="sequential"
                clampLimit={130}
                showClampIndicators={false}
                valueDecimals={1}
                valueLabel="VE %"
                tooltipLoadUnit="inHg"
                title=""
              />
            </CardContent>
          </Card>

          {result.ve_rear && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">VE (MAP based/Rear Cyl) (%)</CardTitle>
                <CardDescription>MAP [read-only] (in-hg)</CardDescription>
              </CardHeader>
              <CardContent>
                <VEHeatmap
                  data={result.ve_rear}
                  rowLabels={result.rpm_bins.map((r) => (r / 1000).toFixed(3))}
                  colLabels={result.map_bins.map((kpa) => (kpa / KPA_PER_INHG).toFixed(1))}
                  colorMode="sequential"
                  clampLimit={130}
                  showClampIndicators={false}
                  valueDecimals={1}
                  valueLabel="VE %"
                  tooltipLoadUnit="inHg"
                  title=""
                />
              </CardContent>
            </Card>
          )}

          {validAfr.entries.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">AFR Targets</CardTitle>
                {validAfr.hasBadData && (
                  <p className="text-xs text-amber-400 flex items-center gap-1.5 mt-1">
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                    Some source calibrations had invalid AFR data and were excluded from the blend.
                  </p>
                )}
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-2 pr-4 font-medium text-muted-foreground">MAP (kPa)</th>
                        <th className="text-left py-2 font-medium text-muted-foreground">Target AFR</th>
                      </tr>
                    </thead>
                    <tbody>
                      {validAfr.entries.map(([mapKpa, afr]) => (
                        <tr key={mapKpa} className="border-b last:border-0">
                          <td className="py-1.5 pr-4 font-mono">{mapKpa}</td>
                          <td className="py-1.5 font-mono">{Number(afr).toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {validAfr.entries.length === 0 && Object.keys(result.afr_targets).length > 0 && (
            <Card>
              <CardContent className="py-6">
                <p className="text-sm text-amber-400 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  AFR target data from source calibrations is outside valid range ({VALID_AFR_MIN}-{VALID_AFR_MAX}).
                  The raw lambda table values may not have been converted correctly during ingestion.
                </p>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Confidence Map</CardTitle>
              <CardDescription>Number of calibrations contributing to each cell</CardDescription>
            </CardHeader>
            <CardContent>
              <VEHeatmap
                data={result.confidence_map}
                rowLabels={result.rpm_bins.map((r) => (r / 1000).toFixed(3))}
                colLabels={result.map_bins.map((kpa) => (kpa / KPA_PER_INHG).toFixed(1))}
                colorMode="sequential"
                clampLimit={result.match_count}
                showClampIndicators={false}
                valueDecimals={0}
                valueLabel="count"
                tooltipLoadUnit="inHg"
                title=""
              />
            </CardContent>
          </Card>

          {/* Compare Your Tune */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <GitCompareArrows className="h-5 w-5 text-cyan-500" />
                Compare Your Tune
              </CardTitle>
              <CardDescription>
                Import your tune to see a side-by-side diff against the library blend.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {comparisonVE ? (
                <div className="flex items-center gap-3">
                  <Badge variant="secondary">{comparisonLabel}</Badge>
                  <Button variant="ghost" size="sm" onClick={() => { setComparisonVE(null); setComparisonLabel(""); }}>
                    <X className="h-3.5 w-3.5 mr-1" /> Clear
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <input
                    ref={compareFileRef}
                    type="file"
                    accept=".pvv"
                    className="hidden"
                    aria-label="Upload PVV file for comparison"
                    onChange={handlePvvImport}
                  />
                  <Button variant="outline" size="sm" onClick={() => compareFileRef.current?.click()}>
                    <FileUp className="h-3.5 w-3.5 mr-1.5" /> Import PVV
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => setShowCsvPaste((v) => !v)}>
                    <ClipboardPaste className="h-3.5 w-3.5 mr-1.5" /> Paste CSV
                  </Button>
                </div>
              )}
              {showCsvPaste && !comparisonVE && (
                <div className="space-y-2">
                  <Textarea
                    placeholder={`Paste ${PC_RPM_BINS.length} rows x ${PC_MAP_INHG.length} cols of VE values (comma or tab separated).\nOptional header row and RPM column will be auto-skipped.`}
                    value={csvText}
                    onChange={(e) => setCsvText(e.target.value)}
                    className="font-mono text-xs h-40"
                  />
                  <div className="flex gap-2">
                    <Button size="sm" onClick={handleCsvParse} disabled={!csvText.trim()}>Parse</Button>
                    <Button variant="ghost" size="sm" onClick={() => { setShowCsvPaste(false); setCsvText(""); }}>Cancel</Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {diffResult && comparisonVE && (
            <>
              <div className="grid grid-cols-3 gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Your Tune</CardTitle>
                    <CardDescription className="text-xs">{comparisonLabel}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <VEHeatmap
                      data={comparisonVE}
                      rowLabels={PC_RPM_BINS.map((r) => (r / 1000).toFixed(3))}
                      colLabels={PC_MAP_INHG.map((v) => v.toFixed(1))}
                      colorMode="sequential"
                      clampLimit={130}
                      showClampIndicators={false}
                      valueDecimals={1}
                      valueLabel="VE %"
                      tooltipLoadUnit="inHg"
                      title=""
                    />
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Library Blend</CardTitle>
                    <CardDescription className="text-xs">{result.match_count} calibrations</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <VEHeatmap
                      data={result.ve_front}
                      rowLabels={PC_RPM_BINS.map((r) => (r / 1000).toFixed(3))}
                      colLabels={PC_MAP_INHG.map((v) => v.toFixed(1))}
                      colorMode="sequential"
                      clampLimit={130}
                      showClampIndicators={false}
                      valueDecimals={1}
                      valueLabel="VE %"
                      tooltipLoadUnit="inHg"
                      title=""
                    />
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Difference</CardTitle>
                    <CardDescription className="text-xs">Your tune minus blend</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <VEHeatmap
                      data={diffResult.grid}
                      rowLabels={PC_RPM_BINS.map((r) => (r / 1000).toFixed(3))}
                      colLabels={PC_MAP_INHG.map((v) => v.toFixed(1))}
                      colorMode="diverging"
                      clampLimit={15}
                      showClampIndicators={false}
                      valueDecimals={1}
                      valueLabel="%"
                      tooltipLoadUnit="inHg"
                      title=""
                    />
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardContent className="py-4">
                  <div className="grid grid-cols-3 gap-6 text-center text-sm">
                    <div>
                      <p className="text-muted-foreground text-xs">Mean |Diff|</p>
                      <p className="font-mono font-semibold">{diffResult.meanAbsDiff.toFixed(1)}%</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground text-xs">Max Higher (yours)</p>
                      <p className="font-mono font-semibold text-green-400">+{diffResult.maxPositive.toFixed(1)}%</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground text-xs">Max Lower (yours)</p>
                      <p className="font-mono font-semibold text-red-400">{diffResult.maxNegative.toFixed(1)}%</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </>
      )}

      {result && result.match_count === 0 && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No matching calibrations found for {family} / {cam} / {exhaust}.
            Try a broader config (e.g. stock cam + stock exhaust).
          </CardContent>
        </Card>
      )}
    </div>
  );
}
