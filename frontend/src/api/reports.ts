/**
 * DynoAI Reports API Client
 * 
 * Handles communication with the report generation backend.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5001';

export interface ShopBranding {
  shop_name: string;
  tagline: string;
  address: string;
  phone: string;
  email: string;
  website: string;
  logo_path: string | null;
  primary_color: string;
  secondary_color: string;
  accent_color: string;
}

export interface ReportPreview {
  peak_hp: number;
  peak_hp_rpm: number;
  peak_tq: number;
  peak_tq_rpm: number;
  zones_corrected: number;
  confidence_score: number | null;
  has_power_curve: boolean;
  has_ve_data: boolean;
  has_afr_data: boolean;
  timestamp: string;
}

export interface ReportableRun {
  run_id: string;
  created_at: string;
  peak_hp: number;
  peak_tq: number;
  report_exists: boolean;
}

export interface GenerateReportOptions {
  customer_name?: string;
  vehicle_info?: string;
  tuner_notes?: string;
  baseline_run_id?: string;
}

/**
 * Get current shop branding configuration
 */
export async function getShopBranding(): Promise<ShopBranding> {
  const response = await fetch(`${API_BASE}/api/reports/branding`);
  const data = await response.json();
  
  if (!data.success) {
    throw new Error(data.error || 'Failed to fetch branding');
  }
  
  return data.branding;
}

/**
 * Update shop branding configuration
 */
export async function updateShopBranding(branding: Partial<ShopBranding>): Promise<ShopBranding> {
  const response = await fetch(`${API_BASE}/api/reports/branding`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(branding),
  });
  
  const data = await response.json();
  
  if (!data.success) {
    throw new Error(data.error || 'Failed to update branding');
  }
  
  return data.branding;
}

/**
 * Get report preview data for a run
 */
export async function getReportPreview(runId: string): Promise<ReportPreview & { report_exists: boolean }> {
  const response = await fetch(`${API_BASE}/api/reports/preview/${runId}`);
  const data = await response.json();
  
  if (!data.success) {
    throw new Error(data.error || 'Failed to fetch preview');
  }
  
  return {
    ...data.preview,
    report_exists: data.report_exists,
  };
}

/**
 * Generate a PDF report for a run
 */
export async function generateReport(
  runId: string, 
  options: GenerateReportOptions = {}
): Promise<{ download_url: string; report_path: string }> {
  const response = await fetch(`${API_BASE}/api/reports/generate/${runId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
  });
  
  const data = await response.json();
  
  if (!data.success) {
    throw new Error(data.error || 'Failed to generate report');
  }
  
  return {
    download_url: `${API_BASE}${data.download_url}`,
    report_path: data.report_path,
  };
}

/**
 * Download a generated PDF report
 */
export function getReportDownloadUrl(runId: string): string {
  return `${API_BASE}/api/reports/download/${runId}`;
}

/**
 * Generate and download report directly
 */
export async function generateAndDownloadReport(
  runId: string,
  options: GenerateReportOptions = {}
): Promise<void> {
  // First generate the report
  await generateReport(runId, options);
  
  // Then trigger download
  const downloadUrl = getReportDownloadUrl(runId);
  window.open(downloadUrl, '_blank');
}

/**
 * List all runs that can have reports generated
 */
export async function listReportableRuns(
  limit: number = 20, 
  offset: number = 0
): Promise<{ runs: ReportableRun[]; total: number }> {
  const response = await fetch(
    `${API_BASE}/api/reports/list-runs?limit=${limit}&offset=${offset}`
  );
  const data = await response.json();
  
  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/c4f84577-4e75-4160-830d-a50a3d6aea34',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'reports.ts:listReportableRuns',message:'Raw API response',data:{success:data.success,total:data.total,runs:data.runs?.map((r:ReportableRun)=>({run_id:r.run_id,run_id_type:typeof r.run_id,run_id_empty:r.run_id==='',run_id_null:r.run_id===null,run_id_undef:r.run_id===undefined}))},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'A,D'})}).catch(()=>{});
  // #endregion
  
  if (!data.success) {
    throw new Error(data.error || 'Failed to fetch runs');
  }
  
  return {
    runs: data.runs,
    total: data.total,
  };
}
