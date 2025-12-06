import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Loader2, CheckCircle, Settings, Play, Activity, Zap, FileSearch, Sparkles } from 'lucide-react';
import FileUpload from '../components/FileUpload';
import { uploadAndAnalyze, pollJobStatus, handleApiError, AnalysisParams } from '../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Progress } from '../components/ui/progress';
import { Switch } from '../components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';

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

  // Decel management parameters
  const [decelManagement, setDecelManagement] = useState(false);
  const [decelSeverity, setDecelSeverity] = useState<'low' | 'medium' | 'high'>('medium');
  const [decelRpmMin, setDecelRpmMin] = useState(1500);
  const [decelRpmMax, setDecelRpmMax] = useState(5500);

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
      // Combine params with decel options
      const allParams: AnalysisParams = {
        ...params,
        decelManagement,
        decelSeverity,
        decelRpmMin,
        decelRpmMax,
      };

      // Upload file and start analysis
      const { runId } = await uploadAndAnalyze(currentFile, allParams);
      
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
    <div className="max-w-5xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Hero Section */}
      <div className="text-center py-8 space-y-4">
        <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight">
          Precision Dyno Tuning
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          AI-powered analysis for WinPEP logs. Generate VE corrections and spark timing suggestions in seconds.
        </p>
      </div>

      {/* Upload Section */}
      <Card className="border-primary/10 shadow-lg">
        <CardHeader>
          <CardTitle className="text-2xl flex items-center gap-2">
            <FileSearch className="h-6 w-6 text-primary" />
            Upload Log File
          </CardTitle>
          <CardDescription>
            Upload your CSV log file to begin analysis.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <FileUpload onFileSelect={handleFileSelect} />

          {/* Advanced Parameters */}
          {currentFile && !isAnalyzing && (
            <div className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center gap-2 text-muted-foreground hover:text-foreground"
              >
                <Settings className="h-4 w-4" />
                <span>{showAdvanced ? 'Hide' : 'Show'} Advanced Parameters</span>
              </Button>

              {showAdvanced && (
                <div className="space-y-6 p-6 bg-muted/30 rounded-lg border border-border">
                  {/* VE Correction Parameters */}
                  <div className="space-y-4">
                    <h4 className="font-semibold text-sm text-foreground">VE Correction Parameters</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <Label htmlFor="smoothPasses">Smoothing Passes (0-5)</Label>
                        <Input
                          id="smoothPasses"
                          type="number"
                          min="0"
                          max="5"
                          value={params.smoothPasses}
                          onChange={(e) => setParams({ ...params, smoothPasses: parseInt(e.target.value) })}
                        />
                        <p className="text-xs text-muted-foreground">Iterations of kernel smoothing to apply.</p>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="clamp">Clamp (%)</Label>
                        <Input
                          id="clamp"
                          type="number"
                          min="5"
                          max="20"
                          step="0.5"
                          value={params.clamp}
                          onChange={(e) => setParams({ ...params, clamp: parseFloat(e.target.value) })}
                        />
                        <p className="text-xs text-muted-foreground">Maximum allowed correction percentage.</p>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="rearBias">Rear Bias (%)</Label>
                        <Input
                          id="rearBias"
                          type="number"
                          min="-5"
                          max="5"
                          step="0.5"
                          value={params.rearBias}
                          onChange={(e) => setParams({ ...params, rearBias: parseFloat(e.target.value) })}
                        />
                        <p className="text-xs text-muted-foreground">Offset applied to rear cylinder corrections.</p>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="rearRuleDeg">Rear Rule (deg)</Label>
                        <Input
                          id="rearRuleDeg"
                          type="number"
                          min="0"
                          max="5"
                          step="0.5"
                          value={params.rearRuleDeg}
                          onChange={(e) => setParams({ ...params, rearRuleDeg: parseFloat(e.target.value) })}
                        />
                        <p className="text-xs text-muted-foreground">Timing retard for rear cylinder heat management.</p>
                      </div>
                    </div>
                  </div>

                  {/* Decel Fuel Management */}
                  <div className="space-y-4 pt-4 border-t border-border">
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <h4 className="font-semibold text-sm text-foreground flex items-center gap-2">
                          <Sparkles className="h-4 w-4 text-orange-500" />
                          Decel Fuel Management
                        </h4>
                        <p className="text-xs text-muted-foreground">
                          Automatically eliminate exhaust popping during deceleration.
                        </p>
                      </div>
                      <Switch
                        id="decel-management"
                        checked={decelManagement}
                        onCheckedChange={setDecelManagement}
                      />
                    </div>

                    {decelManagement && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pl-6 pt-2 animate-in fade-in slide-in-from-top-2 duration-300">
                        <div className="space-y-2">
                          <Label htmlFor="decel-severity">Enrichment Severity</Label>
                          <Select
                            value={decelSeverity}
                            onValueChange={(value: 'low' | 'medium' | 'high') => setDecelSeverity(value)}
                          >
                            <SelectTrigger id="decel-severity">
                              <SelectValue placeholder="Select severity" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="low">Low (Minimal)</SelectItem>
                              <SelectItem value="medium">Medium (Balanced)</SelectItem>
                              <SelectItem value="high">High (Aggressive)</SelectItem>
                            </SelectContent>
                          </Select>
                          <p className="text-xs text-muted-foreground">
                            Adjust fuel enrichment intensity during deceleration.
                          </p>
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
                          <p className="text-xs text-muted-foreground">
                            Minimum RPM for decel zone.
                          </p>
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
                          <p className="text-xs text-muted-foreground">
                            Maximum RPM for decel zone.
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <Button
                onClick={startAnalysis}
                size="lg"
                className="w-full text-lg font-semibold shadow-md transition-all hover:scale-[1.01]"
              >
                <Play className="mr-2 h-5 w-5" />
                Start Analysis
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Progress Section */}
      {isAnalyzing && (
        <Card className="animate-in fade-in slide-in-from-bottom-4 duration-500 border-primary/20 bg-primary/5">
          <CardHeader>
            <CardTitle>Analysis in Progress</CardTitle>
            <CardDescription>Processing your data, please wait...</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">{analysisMessage}</span>
                <span className="font-mono font-medium text-primary">{analysisProgress}%</span>
              </div>
              <Progress value={analysisProgress} className="h-2" />
            </div>

            <div className="grid gap-3">
              <div className="flex items-center gap-3 text-sm">
                {analysisProgress > 0 ? (
                  <CheckCircle className="h-4 w-4 text-green-500" />
                ) : (
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                )}
                <span className={analysisProgress > 0 ? 'text-foreground' : 'text-muted-foreground'}>
                  File upload
                </span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                {analysisProgress > 10 && analysisProgress < 100 ? (
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                ) : analysisProgress === 100 ? (
                  <CheckCircle className="h-4 w-4 text-green-500" />
                ) : (
                  <div className="h-4 w-4 rounded-full border border-muted-foreground/30" />
                )}
                <span className={analysisProgress > 10 ? 'text-foreground' : 'text-muted-foreground'}>
                  Data analysis
                </span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                {analysisProgress === 100 ? (
                  <CheckCircle className="h-4 w-4 text-green-500" />
                ) : (
                  <div className="h-4 w-4 rounded-full border border-muted-foreground/30" />
                )}
                <span className={analysisProgress === 100 ? 'text-foreground' : 'text-muted-foreground'}>
                  Generating results
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Features Section */}
      {!isAnalyzing && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="bg-card/50 hover:bg-card transition-colors hover:shadow-md">
            <CardHeader>
              <Activity className="h-8 w-8 text-primary mb-2" />
              <CardTitle>VE Corrections</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground text-sm leading-relaxed">
                Adaptive kernel smoothing with automatic clamping ensures safe, accurate Volumetric Efficiency adjustments.
              </p>
            </CardContent>
          </Card>
          
          <Card className="bg-card/50 hover:bg-card transition-colors hover:shadow-md">
            <CardHeader>
              <Zap className="h-8 w-8 text-accent mb-2" />
              <CardTitle>Spark Timing</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground text-sm leading-relaxed">
                Knock-aware spark timing suggestions with intelligent temperature compensation for optimal power.
              </p>
            </CardContent>
          </Card>
          
          <Card className="bg-card/50 hover:bg-card transition-colors hover:shadow-md">
            <CardHeader>
              <FileSearch className="h-8 w-8 text-secondary-foreground mb-2" />
              <CardTitle>Diagnostics</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground text-sm leading-relaxed">
                Comprehensive anomaly detection and data quality analysis to identify sensor issues before tuning.
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
