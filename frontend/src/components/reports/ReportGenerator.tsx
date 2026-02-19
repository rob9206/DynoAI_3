/**
 * ReportGenerator Component
 * 
 * A slide-out panel for generating professional PDF reports.
 * Includes:
 * - Report preview with key metrics
 * - Customer/vehicle info input
 * - Tuner notes
 * - Baseline run selection for comparison
 * - Shop branding preview
 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileText,
  Download,
  X,
  User,
  Car,
  MessageSquare,
  Gauge,
  TrendingUp,
  Activity,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ChevronDown,
  Palette,
  Building2,
} from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
  SheetFooter,
} from '../ui/sheet';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '../ui/collapsible';
import {
  getReportPreview,
  generateAndDownloadReport,
  getShopBranding,
  listReportableRuns,
  type ShopBranding,
  type ReportPreview,
  type ReportableRun,
  type GenerateReportOptions,
} from '../../api/reports';

interface ReportGeneratorProps {
  /** Current run ID to generate report for */
  runId: string;
  /** Callback when report is generated */
  onReportGenerated?: (downloadUrl: string) => void;
  /** Custom trigger button (optional) */
  trigger?: React.ReactNode;
}

export function ReportGenerator({ 
  runId, 
  onReportGenerated,
  trigger 
}: ReportGeneratorProps) {
  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/c4f84577-4e75-4160-830d-a50a3d6aea34',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ReportGenerator.tsx:mount',message:'Component mounted/rendered',data:{runId,runIdType:typeof runId,runIdEmpty:runId===''||!runId},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'A'})}).catch(()=>{});
  // #endregion
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  
  // Report preview data
  const [preview, setPreview] = useState<ReportPreview | null>(null);
  const [reportExists, setReportExists] = useState(false);
  
  // Shop branding
  const [branding, setBranding] = useState<ShopBranding | null>(null);
  const [showBranding, setShowBranding] = useState(false);
  
  // Available baseline runs
  const [baselineRuns, setBaselineRuns] = useState<ReportableRun[]>([]);
  
  // Form state
  const [customerName, setCustomerName] = useState('');
  const [vehicleInfo, setVehicleInfo] = useState('');
  const [tunerNotes, setTunerNotes] = useState('');
  const [baselineRunId, setBaselineRunId] = useState<string>('');

  // Load data when opened
  useEffect(() => {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/c4f84577-4e75-4160-830d-a50a3d6aea34',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ReportGenerator.tsx:useEffect',message:'useEffect triggered',data:{open,runId,runIdType:typeof runId,runIdEmpty:runId==='',willLoadData:open&&runId},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'A,B'})}).catch(()=>{});
    // #endregion
    if (open && runId) {
      loadData();
    }
  }, [open, runId]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Load preview, branding, and baseline runs in parallel
      const [previewData, brandingData, runsData] = await Promise.all([
        getReportPreview(runId),
        getShopBranding(),
        listReportableRuns(10),
      ]);
      
      // #region agent log
      console.log('[DEBUG ReportGenerator] API data received:', {runsDataRaw:runsData.runs.map(r=>({run_id:r.run_id,run_id_repr:JSON.stringify(r.run_id),type:typeof r.run_id,isEmpty:r.run_id==='',isNull:r.run_id===null,trimmedEmpty:typeof r.run_id==='string'&&r.run_id.trim()===''})),totalRuns:runsData.runs.length});
      // #endregion
      
      setPreview(previewData);
      setReportExists(previewData.report_exists);
      setBranding(brandingData);
      // Filter out current run and any runs with empty IDs (including whitespace-only)
      const filteredRuns = runsData.runs.filter(r => r.run_id && r.run_id.trim() !== '' && r.run_id !== runId);
      // #region agent log
      console.log('[DEBUG ReportGenerator] Filtered baseline runs:', {filteredRuns:filteredRuns.map(r=>({run_id:r.run_id,run_id_repr:JSON.stringify(r.run_id)})),filteredCount:filteredRuns.length,hasEmptyAfterFilter:filteredRuns.some(r=>!r.run_id||r.run_id.trim()==='')});
      // #endregion
      setBaselineRuns(filteredRuns);
    } catch (err) {
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/c4f84577-4e75-4160-830d-a50a3d6aea34',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ReportGenerator.tsx:loadData:error',message:'Error loading data',data:{error:err instanceof Error?err.message:String(err)},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'E'})}).catch(()=>{});
      // #endregion
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    setSuccess(false);
    
    const options: GenerateReportOptions = {};
    if (customerName.trim()) options.customer_name = customerName.trim();
    if (vehicleInfo.trim()) options.vehicle_info = vehicleInfo.trim();
    if (tunerNotes.trim()) options.tuner_notes = tunerNotes.trim();
    if (baselineRunId) options.baseline_run_id = baselineRunId;
    
    try {
      await generateAndDownloadReport(runId, options);
      setSuccess(true);
      setReportExists(true);
      onReportGenerated?.(`/api/reports/download/${runId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate report');
    } finally {
      setGenerating(false);
    }
  };

  const defaultTrigger = (
    <Button variant="outline" className="gap-2">
      <FileText className="w-4 h-4" />
      Generate Report
    </Button>
  );

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        {trigger || defaultTrigger}
      </SheetTrigger>
      
      <SheetContent className="w-[450px] sm:max-w-[450px] flex flex-col bg-zinc-950 border-zinc-800">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2 text-amber-400">
            <FileText className="w-5 h-5" />
            Generate Report
          </SheetTitle>
          <SheetDescription>
            Create a professional PDF report for this dyno run
          </SheetDescription>
        </SheetHeader>

        <div className="py-6 space-y-6 flex-1 overflow-y-auto">
          {/* Loading state */}
          {loading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
            </div>
          )}

          {/* Error state */}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-red-500/10 border border-red-500/30 rounded-lg p-4"
            >
              <div className="flex items-center gap-2 text-red-400">
                <AlertCircle className="w-5 h-5" />
                <span>{error}</span>
              </div>
            </motion.div>
          )}

          {/* Success state */}
          <AnimatePresence>
            {success && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4"
              >
                <div className="flex items-center gap-2 text-emerald-400">
                  <CheckCircle2 className="w-5 h-5" />
                  <span>Report generated successfully!</span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Preview Section */}
          {!loading && preview && (
            <>
              {/* Performance Preview */}
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
                  <Gauge className="w-4 h-4" />
                  Performance Summary
                </h3>
                
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-zinc-900/50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-amber-400">
                      {preview.peak_hp.toFixed(1)}
                    </p>
                    <p className="text-xs text-zinc-500">Peak HP @ {preview.peak_hp_rpm.toFixed(0)} RPM</p>
                  </div>
                  <div className="bg-zinc-900/50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-emerald-400">
                      {preview.peak_tq.toFixed(1)}
                    </p>
                    <p className="text-xs text-zinc-500">Peak TQ @ {preview.peak_tq_rpm.toFixed(0)} RPM</p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  {preview.has_power_curve && (
                    <Badge variant="outline" className="text-emerald-400 border-emerald-600">
                      <TrendingUp className="w-3 h-3 mr-1" />
                      Power Curve
                    </Badge>
                  )}
                  {preview.has_ve_data && (
                    <Badge variant="outline" className="text-cyan-400 border-cyan-600">
                      <Activity className="w-3 h-3 mr-1" />
                      VE Data
                    </Badge>
                  )}
                  {preview.zones_corrected > 0 && (
                    <Badge variant="outline" className="text-violet-400 border-violet-600">
                      {preview.zones_corrected} zones
                    </Badge>
                  )}
                  {preview.confidence_score !== null && (
                    <Badge variant="outline" className="text-pink-400 border-pink-600">
                      {preview.confidence_score.toFixed(0)}% confidence
                    </Badge>
                  )}
                </div>
              </div>

              {/* Customer Info Section */}
              <div className="space-y-4">
                <h3 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
                  <User className="w-4 h-4" />
                  Customer Information
                </h3>
                
                <div className="space-y-3">
                  <div>
                    <Label htmlFor="customer_name" className="text-xs text-zinc-500">
                      Customer Name
                    </Label>
                    <Input
                      id="customer_name"
                      placeholder="John Doe"
                      value={customerName}
                      onChange={(e) => setCustomerName(e.target.value)}
                      className="mt-1 bg-zinc-900 border-zinc-700"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="vehicle_info" className="text-xs text-zinc-500">
                      Vehicle Description
                    </Label>
                    <Input
                      id="vehicle_info"
                      placeholder="2021 Road Glide - Stage 2 Build"
                      value={vehicleInfo}
                      onChange={(e) => setVehicleInfo(e.target.value)}
                      className="mt-1 bg-zinc-900 border-zinc-700"
                    />
                  </div>
                </div>
              </div>

              {/* Baseline Comparison */}
              {baselineRuns.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4" />
                    Compare to Baseline
                  </h3>
                  {/* #region agent log */}
                  {(() => { console.log('[DEBUG ReportGenerator] Rendering Select with baselineRuns:', {baselineRunIds:baselineRuns.map(r=>r.run_id),hasEmptyIds:baselineRuns.some(r=>!r.run_id||r.run_id===''||r.run_id.trim()==='')}); return null; })()}
                  {/* #endregion */}
                  <Select 
                    value={baselineRunId || "none"} 
                    onValueChange={(val) => setBaselineRunId(val === "none" ? "" : val)}
                  >
                    <SelectTrigger className="bg-zinc-900 border-zinc-700">
                      <SelectValue placeholder="Select baseline run (optional)" />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-900 border-zinc-700">
                      <SelectItem value="none">No comparison</SelectItem>
                      {baselineRuns.map((run) => (
                        <SelectItem key={run.run_id} value={run.run_id}>
                          {run.run_id} ({run.peak_hp.toFixed(1)} HP)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  
                  <p className="text-xs text-zinc-500">
                    Shows before/after comparison in the report
                  </p>
                </div>
              )}

              {/* Tuner Notes */}
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
                  <MessageSquare className="w-4 h-4" />
                  Tuner Notes
                </h3>
                
                <textarea
                  placeholder="Add notes or recommendations for the customer..."
                  value={tunerNotes}
                  onChange={(e) => setTunerNotes(e.target.value)}
                  rows={4}
                  className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-md text-sm resize-none focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                />
              </div>

              {/* Shop Branding Preview */}
              {branding && (
                <Collapsible open={showBranding} onOpenChange={setShowBranding}>
                  <CollapsibleTrigger className="flex items-center justify-between w-full py-2 text-sm font-medium text-zinc-400 hover:text-zinc-200">
                    <span className="flex items-center gap-2">
                      <Building2 className="w-4 h-4" />
                      Shop Branding
                    </span>
                    <ChevronDown className={`w-4 h-4 transition-transform ${showBranding ? 'rotate-180' : ''}`} />
                  </CollapsibleTrigger>
                  
                  <CollapsibleContent className="pt-3 space-y-3">
                    <div className="bg-zinc-900/50 rounded-lg p-4">
                      <p className="font-semibold text-lg" style={{ color: branding.primary_color }}>
                        {branding.shop_name}
                      </p>
                      {branding.tagline && (
                        <p className="text-sm text-zinc-400 italic">{branding.tagline}</p>
                      )}
                      
                      <div className="flex gap-2 mt-3">
                        <div 
                          className="w-6 h-6 rounded" 
                          style={{ backgroundColor: branding.primary_color }}
                          title="Primary Color"
                        />
                        <div 
                          className="w-6 h-6 rounded" 
                          style={{ backgroundColor: branding.secondary_color }}
                          title="Secondary Color"
                        />
                        <div 
                          className="w-6 h-6 rounded" 
                          style={{ backgroundColor: branding.accent_color }}
                          title="Accent Color"
                        />
                      </div>
                    </div>
                    
                    <p className="text-xs text-zinc-500">
                      Edit branding in Settings → Shop Branding
                    </p>
                  </CollapsibleContent>
                </Collapsible>
              )}

              {/* Report Exists Notice */}
              {reportExists && (
                <div className="bg-zinc-800/50 rounded-lg p-3 flex items-center gap-2 text-sm text-zinc-400">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  <span>A report already exists for this run. Generating will replace it.</span>
                </div>
              )}
            </>
          )}
        </div>

        <SheetFooter className="gap-2 sm:gap-2 pt-4 pb-2 border-t border-zinc-800 mt-auto flex-shrink-0">
          <Button 
            variant="outline" 
            onClick={() => setOpen(false)}
            className="flex-1"
          >
            Cancel
          </Button>
          <Button
            onClick={handleGenerate}
            disabled={loading || generating}
            className="flex-1 bg-amber-600 hover:bg-amber-500 text-white"
          >
            {generating ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Download className="w-4 h-4 mr-2" />
                Generate & Download
              </>
            )}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

export default ReportGenerator;
