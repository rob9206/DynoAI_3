/**
 * VE Table Time Machine Page
 * 
 * Full session replay with timeline, VE visualization, and diff view.
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Clock, Layers, GitCompare, RefreshCw, Download, Keyboard } from 'lucide-react';
import { toast } from '@/lib/toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Timeline } from '@/components/timeline';
import { DiffView } from '@/components/timeline/DiffView';
import TimelineErrorBoundary from '@/components/timeline/TimelineErrorBoundary';
import VEHeatmap from '@/components/VEHeatmap';
import { useTimeline } from '@/hooks/useTimeline';
import { downloadSnapshot, getEventTypeLabel, exportTimelineAsJSON } from '@/api/timeline';
import { sanitizeDownloadName } from '@/lib/sanitize';

export default function TimeMachinePage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [compareFromStep, setCompareFromStep] = useState<number | null>(null);
  const [showKeyboardHelp, setShowKeyboardHelp] = useState(false);

  const {
    timeline,
    currentStep,
    totalSteps,
    currentReplay,
    diff,
    isLoading,
    isLoadingReplay,
    isLoadingDiff,
    timelineHasMore,
    timelineLoadedEvents,
    isLoadingMoreTimeline,
    error,
    goToStep,
    nextStep,
    prevStep,
    firstStep,
    lastStep,
    isPlaying,
    togglePlayback,
    compareSteps,
    clearDiff,
    refresh,
    loadMoreTimeline,
  } = useTimeline({
    runId: runId ?? '',
    autoPlayInterval: 1500,
    enabled: !!runId,
  });

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      switch (e.key) {
        case 'ArrowLeft':
          e.preventDefault();
          prevStep();
          break;
        case 'ArrowRight':
          e.preventDefault();
          nextStep();
          break;
        case ' ':
          e.preventDefault();
          togglePlayback();
          break;
        case 'Home':
          e.preventDefault();
          firstStep();
          break;
        case 'End':
          e.preventDefault();
          lastStep();
          break;
        case 'r':
        case 'R':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            refresh();
          }
          break;
        case 'd':
        case 'D':
          if (diff) {
            clearDiff();
          }
          break;
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [prevStep, nextStep, togglePlayback, firstStep, lastStep, refresh, diff, clearDiff]);

  // Handle compare mode
  const handleCompareClick = () => {
    if (compareFromStep === null) {
      // Start compare mode
      setCompareFromStep(currentStep);
      toast.info('Select another step to compare', {
        description: 'Navigate to a different step and click Compare again',
      });
    } else {
      // Complete comparison
      if (compareFromStep !== currentStep) {
        void compareSteps(compareFromStep, currentStep);
      }
      setCompareFromStep(null);
    }
  };

  const handleCancelCompare = () => {
    setCompareFromStep(null);
    clearDiff();
  };

  // Download current snapshot
  const handleDownloadSnapshot = async () => {
    const currentEvent = timeline?.events[currentStep - 1];
    const snapshotId = currentEvent?.snapshot_after?.id;
    
    if (!runId || !snapshotId) return;
    
    try {
      const blob = await downloadSnapshot(runId, snapshotId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = sanitizeDownloadName(
        `VE_Snapshot_Step${currentStep}_${snapshotId}.csv`,
        've_snapshot.csv'
      );
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success('Snapshot downloaded');
    } catch (err) {
      toast.error('Failed to download snapshot');
    }
  };

  // Export entire timeline as JSON
  const handleExportTimeline = () => {
    if (!timeline || !runId) return;
    
    try {
      exportTimelineAsJSON(timeline, runId);
      toast.success('Timeline exported');
    } catch (err) {
      toast.error('Failed to export timeline');
    }
  };

  if (!runId) {
    navigate('/');
    return null;
  }

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in">
        <Skeleton className="h-12 w-64" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Skeleton className="h-[600px]" />
          <Skeleton className="h-[600px] lg:col-span-2" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto text-center py-12 space-y-6">
        <Clock className="h-16 w-16 mx-auto text-muted-foreground" />
        <h1 className="text-2xl font-bold">Timeline Not Available</h1>
        <p className="text-muted-foreground">
          {error.message || 'This run does not have a recorded session timeline yet.'}
        </p>
        <Button variant="link" onClick={() => navigate(`/results/${runId}`)}>
          Return to Results
        </Button>
      </div>
    );
  }

  if (!timeline || timeline.events.length === 0) {
    return (
      <div className="max-w-4xl mx-auto text-center py-12 space-y-6">
        <Clock className="h-16 w-16 mx-auto text-muted-foreground" />
        <h1 className="text-2xl font-bold">No Timeline Events</h1>
        <p className="text-muted-foreground">
          This session hasn't recorded any operations yet. Apply or rollback VE corrections to start building your timeline.
        </p>
        <Button variant="link" onClick={() => navigate(`/results/${runId}`)}>
          Return to Results
        </Button>
      </div>
    );
  }

  const currentEvent = currentReplay?.event ?? timeline.events[currentStep - 1];

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            onClick={() => navigate(`/results/${runId}`)}
            className="flex items-center gap-2 pl-0 hover:pl-2 transition-all"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Back to Results</span>
          </Button>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={refresh}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={() => setShowKeyboardHelp(!showKeyboardHelp)}>
            <Keyboard className="h-4 w-4 mr-2" />
            Shortcuts
          </Button>
          <Button variant="outline" size="sm" onClick={handleExportTimeline}>
            <Download className="h-4 w-4 mr-2" />
            Export Timeline
          </Button>
          {currentReplay?.snapshot && (
            <Button variant="outline" size="sm" onClick={handleDownloadSnapshot}>
              <Download className="h-4 w-4 mr-2" />
              Download Snapshot
            </Button>
          )}
        </div>
      </div>

      {/* Title */}
      <div className="flex items-center gap-3">
        <div className="p-3 bg-primary/10 rounded-lg">
          <Clock className="h-6 w-6 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">VE Table Time Machine</h1>
          <p className="text-muted-foreground">
            Replay your tuning session step by step
          </p>
        </div>
      </div>

      {/* Compare Mode Banner */}
      {compareFromStep !== null && (
        <Card className="border-primary bg-primary/5">
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <GitCompare className="h-5 w-5 text-primary" />
                <span className="font-medium">Compare Mode</span>
                <Badge variant="secondary">
                  Comparing from Step {compareFromStep}
                </Badge>
              </div>
              <div className="flex items-center gap-2">
                <Button size="sm" onClick={handleCompareClick} disabled={compareFromStep === currentStep}>
                  Compare to Step {currentStep}
                </Button>
                <Button size="sm" variant="ghost" onClick={handleCancelCompare}>
                  Cancel
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Keyboard Shortcuts Help */}
      {showKeyboardHelp && (
        <Card className="border-blue-500 bg-blue-50 dark:bg-blue-950/20">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Keyboard className="h-4 w-4" />
                Keyboard Shortcuts
              </CardTitle>
              <Button variant="ghost" size="sm" onClick={() => setShowKeyboardHelp(false)}>
                ×
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
              <div className="flex items-center gap-2">
                <kbd className="px-2 py-1 bg-background border rounded font-mono">←</kbd>
                <span>Previous step</span>
              </div>
              <div className="flex items-center gap-2">
                <kbd className="px-2 py-1 bg-background border rounded font-mono">→</kbd>
                <span>Next step</span>
              </div>
              <div className="flex items-center gap-2">
                <kbd className="px-2 py-1 bg-background border rounded font-mono">Space</kbd>
                <span>Play/Pause</span>
              </div>
              <div className="flex items-center gap-2">
                <kbd className="px-2 py-1 bg-background border rounded font-mono">Home</kbd>
                <span>First step</span>
              </div>
              <div className="flex items-center gap-2">
                <kbd className="px-2 py-1 bg-background border rounded font-mono">End</kbd>
                <span>Last step</span>
              </div>
              <div className="flex items-center gap-2">
                <kbd className="px-2 py-1 bg-background border rounded font-mono">Ctrl+R</kbd>
                <span>Refresh</span>
              </div>
              <div className="flex items-center gap-2">
                <kbd className="px-2 py-1 bg-background border rounded font-mono">D</kbd>
                <span>Clear diff</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Timeline Sidebar */}
        <div className="lg:col-span-1">
          <TimelineErrorBoundary>
            <Timeline
              timeline={timeline}
              currentStep={currentStep}
              onStepChange={goToStep}
              isPlaying={isPlaying}
              onPlayPause={togglePlayback}
              totalSteps={totalSteps}
              hasMore={timelineHasMore}
              isLoadingMore={isLoadingMoreTimeline}
              onLoadMore={() => void loadMoreTimeline()}
            />
          </TimelineErrorBoundary>
        </div>

        {/* Main View */}
        <div className="lg:col-span-2 space-y-6">
          <TimelineErrorBoundary>
          {/* Current Step Info */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Layers className="h-5 w-5 text-primary" />
                    Step {currentStep}: {currentEvent ? getEventTypeLabel(currentEvent.type) : 'Unknown'}
                  </CardTitle>
                  {currentEvent && (
                    <CardDescription className="mt-1">
                      {currentEvent.description}
                    </CardDescription>
                  )}
                </div>
                {!compareFromStep && (
                  <Button variant="outline" size="sm" onClick={handleCompareClick}>
                    <GitCompare className="h-4 w-4 mr-2" />
                    Compare
                  </Button>
                )}
              </div>
            </CardHeader>
          </Card>

          {/* Tabs for different views */}
          <Tabs defaultValue="snapshot" className="w-full">
            <TabsList className="grid w-full grid-cols-2 max-w-md">
              <TabsTrigger value="snapshot">VE Snapshot</TabsTrigger>
              <TabsTrigger value="diff" disabled={!diff}>
                Diff View {diff && <Badge variant="secondary" className="ml-2">{diff.summary.cells_changed}</Badge>}
              </TabsTrigger>
            </TabsList>

            {/* Snapshot Tab */}
            <TabsContent value="snapshot" className="mt-4">
              {isLoadingReplay ? (
                <Card>
                  <CardHeader>
                    <div className="space-y-2">
                      <Skeleton className="h-6 w-48" />
                      <Skeleton className="h-4 w-64" />
                    </div>
                  </CardHeader>
                  <CardContent>
                    <Skeleton className="h-[500px] w-full" />
                    <div className="mt-4 flex justify-between">
                      <Skeleton className="h-4 w-32" />
                      <Skeleton className="h-4 w-32" />
                    </div>
                  </CardContent>
                </Card>
              ) : currentReplay?.snapshot ? (
                <VEHeatmap
                  data={currentReplay.snapshot.data}
                  rpm={currentReplay.snapshot.rpm}
                  load={currentReplay.snapshot.load}
                  title={`VE Table at Step ${currentStep}`}
                />
              ) : (
                <Card className="py-12">
                  <CardContent className="text-center">
                    <p className="text-muted-foreground">
                      No VE snapshot available for this step
                    </p>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* Diff Tab */}
            <TabsContent value="diff" className="mt-4">
              {isLoadingDiff ? (
                <Card>
                  <CardContent className="py-12">
                    <div className="flex items-center justify-center">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
                    </div>
                  </CardContent>
                </Card>
              ) : diff ? (
                <DiffView diff={diff} />
              ) : (
                <Card className="py-12">
                  <CardContent className="text-center">
                    <GitCompare className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                    <p className="text-muted-foreground">
                      Use the Compare button to see differences between steps
                    </p>
                  </CardContent>
                </Card>
              )}
            </TabsContent>
          </Tabs>
          </TimelineErrorBoundary>

          {/* Event Metadata */}
          {currentEvent && Object.keys(currentEvent.metadata).length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Event Details</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                  {Object.entries(currentEvent.metadata).map(([key, value]) => (
                    <div key={key}>
                      <p className="text-muted-foreground capitalize">
                        {key.replace(/_/g, ' ')}
                      </p>
                      <p className="font-mono">
                        {typeof value === 'number' ? value.toFixed(2) : String(value)}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

