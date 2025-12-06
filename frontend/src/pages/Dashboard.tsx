import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Loader2, CheckCircle, Play, Activity, FileText, Clock, AlertCircle } from 'lucide-react';
import FileUpload from '../components/FileUpload';
import { uploadAndAnalyze, pollJobStatus, handleApiError, AnalysisParams } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/progress';
import { TuningConfiguration } from '../components/TuningConfiguration';
import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert';

export default function Dashboard() {
  const navigate = useNavigate();
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisMessage, setAnalysisMessage] = useState('');
  const [currentFile, setCurrentFile] = useState<File | null>(null);
  
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
    <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 p-4 md:p-6">
      
      {/* Header / Status Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Control Center</h1>
          <p className="text-muted-foreground">System Ready. Waiting for log data.</p>
        </div>
        <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-card rounded-md border shadow-sm">
                <Activity className="h-4 w-4 text-green-500" />
                <span className="font-medium">Engine: Idle</span>
            </div>
             <div className="flex items-center gap-2 px-3 py-1.5 bg-card rounded-md border shadow-sm">
                <Clock className="h-4 w-4 text-primary" />
                <span className="font-medium">{new Date().toLocaleDateString()}</span>
            </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        
        {/* LEFT COLUMN: Upload & Action */}
        <div className="lg:col-span-2 space-y-6">
            <Card className="border-border/50 shadow-sm h-full">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <FileText className="h-5 w-5 text-primary" />
                        Log File Import
                    </CardTitle>
                    <CardDescription>
                        Select a WinPEP, PowerVision, or Generic CSV log file.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    <FileUpload onFileSelect={handleFileSelect} />
                    
                    {currentFile && !isAnalyzing && (
                        <div className="animate-in fade-in slide-in-from-top-2 duration-300">
                             <Button
                                onClick={startAnalysis}
                                size="lg"
                                className="w-full text-lg font-semibold h-14 shadow-md transition-all hover:scale-[1.01] active:scale-[0.99]"
                            >
                                <Play className="mr-2 h-6 w-6 fill-current" />
                                Start Analysis
                            </Button>
                            <p className="text-center text-xs text-muted-foreground mt-2">
                                Process using current configuration
                            </p>
                        </div>
                    )}
                    
                     {/* Progress Section */}
                    {isAnalyzing && (
                        <div className="space-y-6 pt-4 border-t">
                            <div className="space-y-2">
                            <div className="flex justify-between text-sm font-medium">
                                <span className="text-primary">{analysisMessage}</span>
                                <span className="font-mono">{analysisProgress}%</span>
                            </div>
                            <Progress value={analysisProgress} className="h-3" />
                            </div>

                            <div className="grid grid-cols-3 gap-2">
                            <div className={`flex flex-col items-center p-3 rounded border ${analysisProgress > 0 ? 'bg-primary/10 border-primary/20' : 'bg-muted/50 border-transparent'}`}>
                                {analysisProgress > 0 ? <CheckCircle className="h-5 w-5 text-green-500 mb-1" /> : <Loader2 className="h-5 w-5 text-muted-foreground animate-spin mb-1" />}
                                <span className="text-xs font-medium">Upload</span>
                            </div>
                             <div className={`flex flex-col items-center p-3 rounded border ${analysisProgress > 10 ? 'bg-primary/10 border-primary/20' : 'bg-muted/50 border-transparent'}`}>
                                {analysisProgress > 10 && analysisProgress < 100 ? <Loader2 className="h-5 w-5 text-primary animate-spin mb-1" /> : analysisProgress === 100 ? <CheckCircle className="h-5 w-5 text-green-500 mb-1" /> : <Activity className="h-5 w-5 text-muted-foreground mb-1" />}
                                <span className="text-xs font-medium">Analysis</span>
                            </div>
                             <div className={`flex flex-col items-center p-3 rounded border ${analysisProgress === 100 ? 'bg-primary/10 border-primary/20' : 'bg-muted/50 border-transparent'}`}>
                                {analysisProgress === 100 ? <CheckCircle className="h-5 w-5 text-green-500 mb-1" /> : <FileText className="h-5 w-5 text-muted-foreground mb-1" />}
                                <span className="text-xs font-medium">Report</span>
                            </div>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>
            
            {/* Information / Hints Panel */}
            {!isAnalyzing && !currentFile && (
                 <Alert className="bg-muted/30 border-primary/10">
                    <AlertCircle className="h-4 w-4 text-primary" />
                    <AlertTitle>Operator Note</AlertTitle>
                    <AlertDescription>
                        Ensure log files contain RPM, MAP (kPa), and Torque/HP channels. For best results, log at 20Hz or higher.
                    </AlertDescription>
                </Alert>
            )}
        </div>

        {/* RIGHT COLUMN: Configuration */}
        <div className="lg:col-span-1">
            <TuningConfiguration 
                params={params} 
                setParams={setParams} 
                disabled={isAnalyzing} 
            />
        </div>

      </div>
    </div>
  );
}
