import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Loader2, CheckCircle, Settings } from 'lucide-react';
import FileUpload from '../components/FileUpload';
import { uploadAndAnalyze, pollJobStatus, handleApiError, AnalysisParams } from '../lib/api';

export default function Dashboard() {
  const navigate = useNavigate();
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisMessage, setAnalysisMessage] = useState('');
  const [currentFile, setCurrentFile] = useState<File | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  // Tuning parameters
  const [params, setParams] = useState<AnalysisParams>({
    smoothPasses: 2,
    clamp: 15.0,
    rearBias: 0.0,
    rearRuleDeg: 2.0,
    hotExtra: -1.0,
  });

  const handleFileSelect = (file: File) => {
    setCurrentFile(file);
  };

  const startAnalysis = async () => {
    if (!currentFile) {
      toast.error('Please select a file first');
      return;
    }

    setIsAnalyzing(true);
    setAnalysisProgress(0);
    setAnalysisMessage('Uploading file...');

    try {
      // Upload file and start analysis
      const { runId } = await uploadAndAnalyze(currentFile, params);
      
      setAnalysisMessage('Analysis started...');

      // Poll for status
      await pollJobStatus(
        runId,
        (status) => {
          setAnalysisProgress(status.progress);
          setAnalysisMessage(status.message);
        }
      );

      toast.success('Analysis completed successfully!');
      navigate(`/results/${runId}`);
    } catch (error) {
      console.error('Analysis error:', error);
      toast.error(handleApiError(error));
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      {/* Hero Section */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-white mb-4">
          Welcome to DynoAI
        </h1>
        <p className="text-lg text-gray-400">
          Upload your dyno log to generate VE corrections and spark timing suggestions
        </p>
      </div>

      {/* Upload Section */}
      <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl p-8 border border-gray-700 mb-8">
        <h2 className="text-2xl font-semibold text-white mb-6">
          Upload Dyno Log
        </h2>
        
        <FileUpload onFileSelect={handleFileSelect} />

        {/* Advanced Parameters */}
        {currentFile && !isAnalyzing && (
          <div className="mt-6">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center space-x-2 text-gray-400 hover:text-white transition-colors mb-4"
            >
              <Settings className="h-4 w-4" />
              <span>Advanced Parameters</span>
            </button>

            {showAdvanced && (
              <div className="bg-gray-900/50 rounded-lg p-6 space-y-4 mb-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Smoothing Passes
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="5"
                      value={params.smoothPasses}
                      onChange={(e) => setParams({ ...params, smoothPasses: parseInt(e.target.value) })}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">Number of smoothing iterations (0-5)</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Clamp (%)
                    </label>
                    <input
                      type="number"
                      min="5"
                      max="20"
                      step="0.5"
                      value={params.clamp}
                      onChange={(e) => setParams({ ...params, clamp: parseFloat(e.target.value) })}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">Maximum correction percentage (5-20%)</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Rear Bias (%)
                    </label>
                    <input
                      type="number"
                      min="-5"
                      max="5"
                      step="0.5"
                      value={params.rearBias}
                      onChange={(e) => setParams({ ...params, rearBias: parseFloat(e.target.value) })}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">Rear cylinder bias adjustment (-5 to 5%)</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Rear Rule (deg)
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="5"
                      step="0.5"
                      value={params.rearRuleDeg}
                      onChange={(e) => setParams({ ...params, rearRuleDeg: parseFloat(e.target.value) })}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">Rear cylinder timing retard (0-5 deg)</p>
                  </div>
                </div>
              </div>
            )}

            <button
              onClick={startAnalysis}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-6 rounded-lg transition-colors flex items-center justify-center space-x-2"
            >
              <span>Start Analysis</span>
            </button>
          </div>
        )}
      </div>

      {/* Progress Section */}
      {isAnalyzing && (
        <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl p-8 border border-gray-700">
          <h2 className="text-2xl font-semibold text-white mb-6">
            Analysis in Progress
          </h2>

          {/* Analysis Progress */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-400">{analysisMessage}</span>
              <span className="text-sm text-gray-400">{analysisProgress}%</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${analysisProgress}%` }}
              />
            </div>
          </div>

          {/* Status Messages */}
          <div className="space-y-3">
            <div className="flex items-center space-x-3 text-gray-300">
              {analysisProgress > 0 ? (
                <CheckCircle className="h-5 w-5 text-green-500" />
              ) : (
                <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
              )}
              <span>File upload</span>
            </div>
            <div className="flex items-center space-x-3 text-gray-300">
              {analysisProgress > 10 && analysisProgress < 100 ? (
                <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
              ) : analysisProgress === 100 ? (
                <CheckCircle className="h-5 w-5 text-green-500" />
              ) : (
                <div className="h-5 w-5 rounded-full border-2 border-gray-600" />
              )}
              <span>Data analysis</span>
            </div>
            <div className="flex items-center space-x-3 text-gray-300">
              {analysisProgress === 100 ? (
                <CheckCircle className="h-5 w-5 text-green-500" />
              ) : (
                <div className="h-5 w-5 rounded-full border-2 border-gray-600" />
              )}
              <span>Generating results</span>
            </div>
          </div>
        </div>
      )}

      {/* Features Section */}
      {!isAnalyzing && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-12">
          <div className="bg-gray-800/30 rounded-lg p-6 border border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-2">
              VE Corrections
            </h3>
            <p className="text-sm text-gray-400">
              Adaptive kernel smoothing with automatic clamping for safe tuning
            </p>
          </div>
          <div className="bg-gray-800/30 rounded-lg p-6 border border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-2">
              Spark Timing
            </h3>
            <p className="text-sm text-gray-400">
              Knock-aware suggestions with temperature compensation
            </p>
          </div>
          <div className="bg-gray-800/30 rounded-lg p-6 border border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-2">
              Diagnostics
            </h3>
            <p className="text-sm text-gray-400">
              Anomaly detection and data quality analysis
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
