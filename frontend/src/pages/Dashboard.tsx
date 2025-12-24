import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { toast } from 'sonner';
import { Loader2, CheckCircle, Play, Activity, FileText, Clock, AlertCircle, Sparkles } from 'lucide-react';
import FileUpload from '../components/FileUpload';
import { uploadAndAnalyze, pollJobStatus, handleApiError, AnalysisParams, healthCheck } from '../lib/api';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/progress';
import { TuningConfiguration } from '../components/TuningConfiguration';
import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert';
import { Switch } from '../components/ui/switch';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';

export default function Dashboard() {
  const navigate = useNavigate();
  const location = useLocation();
  
  // #region agent log
  useEffect(() => {
    fetch('http://127.0.0.1:7243/ingest/37165f1d-9e5e-4804-b2ff-ca654a1191f3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'Dashboard.tsx:18',message:'Component mounted',data:{pathname:location.pathname},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // Test API connectivity
    healthCheck().then((result) => {
      fetch('http://127.0.0.1:7243/ingest/37165f1d-9e5e-4804-b2ff-ca654a1191f3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'Dashboard.tsx:20',message:'API health check succeeded',data:{status:result.status,version:result.version},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
    }).catch((error) => {
      fetch('http://127.0.0.1:7243/ingest/37165f1d-9e5e-4804-b2ff-ca654a1191f3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'Dashboard.tsx:22',message:'API health check failed',data:{error:error instanceof Error?error.message:String(error)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
    });
  }, [location.pathname]);
  // #endregion
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

  // Decel management parameters
  const [decelManagement, setDecelManagement] = useState(false);
  const [decelSeverity, setDecelSeverity] = useState<'low' | 'medium' | 'high'>('medium');
  const [decelRpmMin, setDecelRpmMin] = useState(1500);
  const [decelRpmMax, setDecelRpmMax] = useState(5500);
  
  // Cylinder balancing parameters
  const [balanceCylinders, setBalanceCylinders] = useState(false);
  const [balanceMode, setBalanceMode] = useState<'equalize' | 'match_front' | 'match_rear'>('equalize');
  const [balanceMaxCorrection, setBalanceMaxCorrection] = useState(3.0);

  const handleFileSelect = (file: File) => {
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/37165f1d-9e5e-4804-b2ff-ca654a1191f3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'Dashboard.tsx:44',message:'File selected',data:{fileName:file.name,fileSize:file.size,fileType:file.type},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
    // #endregion
    setCurrentFile(file);
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/37165f1d-9e5e-4804-b2ff-ca654a1191f3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'Dashboard.tsx:47',message:'State updated after file select',data:{currentFileSet:true},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
    // #endregion
  };

  const startAnalysis = async () => {
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/37165f1d-9e5e-4804-b2ff-ca654a1191f3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'Dashboard.tsx:48',message:'startAnalysis called',data:{hasCurrentFile:!!currentFile,fileName:currentFile?.name},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
    // #endregion
    if (!currentFile) {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/37165f1d-9e5e-4804-b2ff-ca654a1191f3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'Dashboard.tsx:50',message:'No file selected error',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
      // #endregion
      toast.error('Please select a file first');
      return;
    }

    setIsAnalyzing(true);
    setAnalysisProgress(0);
    setAnalysisMessage('Uploading file...');
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/37165f1d-9e5e-4804-b2ff-ca654a1191f3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'Dashboard.tsx:57',message:'Analysis state initialized',data:{isAnalyzing:true,progress:0},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
    // #endregion

    try {
      // Combine params with decel and balance options
      const allParams: AnalysisParams = {
        ...params,
        decelManagement,
        decelSeverity,
        decelRpmMin,
        decelRpmMax,
        balanceCylinders,
        balanceMode,
        balanceMaxCorrection,
      };
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/37165f1d-9e5e-4804-b2ff-ca654a1191f3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'Dashboard.tsx:71',message:'Before API call',data:{params:allParams,apiBase:import.meta.env.VITE_API_URL||'http://localhost:5001'},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion

      // Upload file and start analysis
      const { runId } = await uploadAndAnalyze(currentFile, allParams);
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/37165f1d-9e5e-4804-b2ff-ca654a1191f3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'Dashboard.tsx:74',message:'API call succeeded',data:{runId},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion
      
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
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/37165f1d-9e5e-4804-b2ff-ca654a1191f3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'Dashboard.tsx:87',message:'Before navigation',data:{targetPath:`/results/${runId}`},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
      // #endregion
      navigate(`/results/${runId}`);
    } catch (error) {
      // #region agent log
      let errorDetails: any = {error:error instanceof Error?error.message:String(error),errorType:error?.constructor?.name};
      if (axios.isAxiosError(error)) {
        const axiosError = error as any;
        errorDetails.responseStatus = axiosError.response?.status;
        errorDetails.responseData = axiosError.response?.data;
        errorDetails.responseHeaders = axiosError.response?.headers;
        errorDetails.requestUrl = axiosError.config?.url;
        errorDetails.requestMethod = axiosError.config?.method;
      }
      fetch('http://127.0.0.1:7243/ingest/37165f1d-9e5e-4804-b2ff-ca654a1191f3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'Dashboard.tsx:90',message:'API call failed',data:errorDetails,timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion
      console.error('Analysis error:', error);
      toast.error(handleApiError(error));
      setIsAnalyzing(false);
    }
  };

  // #region agent log
  useEffect(() => {
    fetch('http://127.0.0.1:7243/ingest/37165f1d-9e5e-4804-b2ff-ca654a1191f3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'Dashboard.tsx:96',message:'Component rendering',data:{isAnalyzing,hasCurrentFile:!!currentFile,analysisProgress},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
  }, [isAnalyzing, currentFile, analysisProgress]);
  // #endregion

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
          <Card className="border-border/50 shadow-sm">
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

          {/* Advanced Features Card */}
          {!isAnalyzing && (
            <Card className="border-border/50 shadow-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Sparkles className="h-5 w-5 text-orange-500" />
                  Advanced Features
                </CardTitle>
                <CardDescription>
                  Enable AI-powered tuning enhancements
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Decel Fuel Management */}
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label className="text-base font-medium">Decel Fuel Management</Label>
                      <p className="text-xs text-muted-foreground">
                        Automatically eliminate exhaust popping during deceleration
                      </p>
                    </div>
                    <Switch
                      checked={decelManagement}
                      onCheckedChange={setDecelManagement}
                    />
                  </div>

                  {decelManagement && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pl-4 border-l-2 border-orange-500/30 animate-in fade-in slide-in-from-top-2 duration-300">
                      <div className="space-y-2">
                        <Label htmlFor="decel-severity">Severity</Label>
                        <Select
                          value={decelSeverity}
                          onValueChange={(value: 'low' | 'medium' | 'high') => setDecelSeverity(value)}
                        >
                          <SelectTrigger id="decel-severity">
                            <SelectValue placeholder="Select severity" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="low">Low</SelectItem>
                            <SelectItem value="medium">Medium</SelectItem>
                            <SelectItem value="high">High</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="decel-rpm-min">Min RPM</Label>
                        <Input
                          id="decel-rpm-min"
                          type="number"
                          min={0}
                          max={10000}
                          value={decelRpmMin}
                          onChange={(e) => setDecelRpmMin(parseInt(e.target.value, 10))}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="decel-rpm-max">Max RPM</Label>
                        <Input
                          id="decel-rpm-max"
                          type="number"
                          min={0}
                          max={10000}
                          value={decelRpmMax}
                          onChange={(e) => setDecelRpmMax(parseInt(e.target.value, 10))}
                        />
                      </div>
                    </div>
                  )}
                </div>

                <div className="border-t pt-4">
                  {/* Per-Cylinder Auto-Balancing */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label className="text-base font-medium flex items-center gap-2">
                          <Activity className="h-4 w-4 text-blue-500" />
                          Per-Cylinder Auto-Balancing
                        </Label>
                        <p className="text-xs text-muted-foreground">
                          Automatically equalize AFR between front and rear cylinders
                        </p>
                      </div>
                      <Switch
                        checked={balanceCylinders}
                        onCheckedChange={setBalanceCylinders}
                      />
                    </div>

                    {balanceCylinders && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pl-4 border-l-2 border-blue-500/30 animate-in fade-in slide-in-from-top-2 duration-300">
                        <div className="space-y-2">
                          <Label htmlFor="balance-mode">Balance Mode</Label>
                          <Select
                            value={balanceMode}
                            onValueChange={(value: 'equalize' | 'match_front' | 'match_rear') => setBalanceMode(value)}
                          >
                            <SelectTrigger id="balance-mode">
                              <SelectValue placeholder="Select mode" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="equalize">Equalize (Both toward average)</SelectItem>
                              <SelectItem value="match_front">Match Front (Rear to front)</SelectItem>
                              <SelectItem value="match_rear">Match Rear (Front to rear)</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>

                        <div className="space-y-2">
                          <Label htmlFor="balance-max-correction">Max Correction (%)</Label>
                          <Input
                            id="balance-max-correction"
                            type="number"
                            min={1.0}
                            max={5.0}
                            step={0.5}
                            value={balanceMaxCorrection}
                            onChange={(e) => setBalanceMaxCorrection(parseFloat(e.target.value))}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
          
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
