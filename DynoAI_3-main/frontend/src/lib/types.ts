export interface ManifestData {
  timestamp: string;
  inputFile: string;
  rowsProcessed: number;
  correctionsApplied: number;
  runId?: string;  // Optional run ID for real API integration
  outputFiles: {
    name: string;
    type: string;
    url: string;
  }[];
  analysisMetrics: {
    avgCorrection: number;
    maxCorrection: number;
    targetAFR: number;
    iterations: number;
  };
}

export interface AnalysisStatus {
  stage: 'idle' | 'parsing' | 'analyzing' | 'generating' | 'complete' | 'error';
  progress: number;
  message: string;
}

export interface VEData {
  rpm: number[];
  load: number[];
  before: number[][];
  after: number[][];
}
