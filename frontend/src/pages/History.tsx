import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Clock, FileText, ChevronRight, History as HistoryIcon } from 'lucide-react';
import { toast } from '@/lib/toast';
import apiService from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';

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
        <div className="text-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="text-muted-foreground">Loading history...</p>
        </div>
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="flex items-center space-x-4">
          <HistoryIcon className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold text-foreground tracking-tight">Analysis History</h1>
        </div>
        
        <Card className="text-center py-12 border-dashed">
          <CardContent className="space-y-6 pt-6">
            <div className="p-4 bg-muted rounded-full w-fit mx-auto">
              <Clock className="h-12 w-12 text-muted-foreground" />
            </div>
            <div className="space-y-2">
              <h2 className="text-xl font-semibold text-foreground">No Analysis History</h2>
              <p className="text-muted-foreground max-w-md mx-auto">
                You haven't run any analyses yet. Upload a dyno log on the dashboard to get started.
              </p>
            </div>
            <Button
              onClick={() => navigate('/')}
              className="font-medium"
            >
              Go to Dashboard
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center space-x-4">
        <HistoryIcon className="h-8 w-8 text-primary" />
        <h1 className="text-3xl font-bold text-foreground tracking-tight">Analysis History</h1>
      </div>
      
      <Card>
        <CardHeader>
          <CardTitle>Past Runs</CardTitle>
          <CardDescription>View results from your previous analysis sessions.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="divide-y divide-border">
            {runs.map((run) => (
              <div
                key={run.runId}
                onClick={() => viewResults(run.runId)}
                className="p-6 hover:bg-muted/50 cursor-pointer transition-colors group flex items-center justify-between"
              >
                <div className="flex items-center space-x-4">
                  <div className="p-3 bg-primary/10 rounded-lg group-hover:bg-primary/20 transition-colors">
                    <FileText className="h-6 w-6 text-primary" />
                  </div>
                  
                  <div>
                    <h3 className="text-lg font-medium text-foreground group-hover:text-primary transition-colors">
                      {run.inputFile}
                    </h3>
                    <div className="flex items-center space-x-2 mt-1 text-sm text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      <span className="font-mono">
                        {new Date(run.timestamp).toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
                
                <ChevronRight className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
