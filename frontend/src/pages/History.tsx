import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Clock, FileText, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';
import apiService from '../lib/api';

interface Run {
  runId: string;
  timestamp: string;
  inputFile: string;
}

export default function History() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const data = await apiService.listRuns();
      setRuns(data.runs);
    } catch (error: any) {
      console.error('Error loading history:', error);
      toast.error('Failed to load history');
    } finally {
      setLoading(false);
    }
  };

  const viewResults = (runId: string) => {
    navigate(`/results/${runId}`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-400">Loading history...</p>
        </div>
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-white mb-8">Analysis History</h1>
        
        <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl p-12 border border-gray-700 text-center">
          <Clock className="h-16 w-16 text-gray-600 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-white mb-2">No Analysis History</h2>
          <p className="text-gray-400 mb-6">
            You haven't run any analyses yet. Upload a dyno log to get started.
          </p>
          <button
            onClick={() => navigate('/')}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg transition-colors"
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold text-white mb-8">Analysis History</h1>
      
      <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl border border-gray-700 overflow-hidden">
        <div className="divide-y divide-gray-700">
          {runs.map((run) => (
            <div
              key={run.runId}
              onClick={() => viewResults(run.runId)}
              className="p-6 hover:bg-gray-700/30 cursor-pointer transition-colors group"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <div className="p-3 bg-blue-500/10 rounded-lg">
                    <FileText className="h-6 w-6 text-blue-500" />
                  </div>
                  
                  <div>
                    <h3 className="text-lg font-medium text-white group-hover:text-blue-400 transition-colors">
                      {run.inputFile}
                    </h3>
                    <div className="flex items-center space-x-2 mt-1">
                      <Clock className="h-4 w-4 text-gray-500" />
                      <span className="text-sm text-gray-400">
                        {new Date(run.timestamp).toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
                
                <ChevronRight className="h-5 w-5 text-gray-500 group-hover:text-blue-400 transition-colors" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
