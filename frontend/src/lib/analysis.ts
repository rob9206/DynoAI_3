import type { ManifestData, VEData } from './types';

export function parseCSV(csvText: string): number[][] {
  const lines = csvText.trim().split('\n');
  const data: number[][] = [];
  
  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',').map(v => parseFloat(v.trim()));
    if (values.some(v => !isNaN(v))) {
      data.push(values);
    }
  }
  
  return data;
}

export async function simulateAnalysis(
  csvData: number[][],
  onProgress: (progress: number, message: string) => void
): Promise<ManifestData> {
  await delay(500);
  onProgress(25, 'Parsing CSV data...');
  
  await delay(800);
  onProgress(50, 'Applying AFR corrections...');
  
  await delay(1000);
  onProgress(75, 'Generating output files...');
  
  await delay(600);
  onProgress(100, 'Analysis complete');
  
  const rowsProcessed = csvData.length;
  const correctionsApplied = Math.floor(rowsProcessed * 0.73);
  
  const manifest: ManifestData = {
    timestamp: new Date().toISOString(),
    inputFile: 'dyno_run.csv',
    rowsProcessed,
    correctionsApplied,
    outputFiles: [
      { name: 'corrected_ve_table.csv', type: 'VE Table', url: '#' },
      { name: 'afr_corrections.csv', type: 'AFR Data', url: '#' },
      { name: 'analysis_report.txt', type: 'Report', url: '#' }
    ],
    analysisMetrics: {
      avgCorrection: parseFloat((Math.random() * 5 + 2).toFixed(2)),
      maxCorrection: parseFloat((Math.random() * 10 + 5).toFixed(2)),
      targetAFR: 14.7,
      iterations: Math.floor(Math.random() * 5 + 3)
    }
  };
  
  return manifest;
}

export function generateVEData(): VEData {
  const rpmPoints = [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000];
  const loadPoints = [20, 30, 40, 50, 60, 70, 80, 90, 100];
  
  const before: number[][] = [];
  const after: number[][] = [];
  
  for (let i = 0; i < rpmPoints.length; i++) {
    before[i] = [];
    after[i] = [];
    
    for (let j = 0; j < loadPoints.length; j++) {
      const baseVE = 75 + Math.sin(i * 0.5) * 15 + Math.cos(j * 0.4) * 10;
      const noise = (Math.random() - 0.5) * 8;
      before[i][j] = baseVE + noise;
      
      const improvement = 2 + Math.random() * 4;
      after[i][j] = Math.min(100, before[i][j] + improvement);
    }
  }
  
  return {
    rpm: rpmPoints,
    load: loadPoints,
    before,
    after
  };
}

export function downloadFile(content: string, filename: string, type = 'text/plain') {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
