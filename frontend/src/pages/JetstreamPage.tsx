/**
 * Jetstream Live Feed page
 */

import { useState } from 'react';
import { RefreshCw, Settings, Loader2, Radio, Activity } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '../components/ui/sheet';
import { JetstreamStatus, JetstreamFeed, JetstreamConfig } from '../components/jetstream';
import { useJetstreamSync } from '../hooks/useJetstream';
import { toast } from 'sonner';

export default function JetstreamPage() {
  const [configOpen, setConfigOpen] = useState(false);
  const syncMutation = useJetstreamSync();

  const handleSync = () => {
    syncMutation.mutate(undefined, {
      onSuccess: (data) => {
        if (data.new_runs_found > 0) {
          toast.success(`Found ${data.new_runs_found} new runs`);
        } else {
          toast.info('No new runs found');
        }
      },
      onError: (error) => {
        toast.error(`Sync failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      },
    });
  };

  return (
    <div className="space-y-6 p-4 md:p-6 max-w-7xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Page header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border/40 pb-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-mono uppercase flex items-center gap-3">
            <Radio className="h-6 w-6 text-primary" />
            Jetstream Data Link
          </h1>
          <p className="text-muted-foreground font-mono text-sm uppercase tracking-wider flex items-center gap-2 mt-1">
            <span className="inline-block w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
            Cloud Telemetry Ingestion Active
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Status indicator */}
          <div className="hidden md:block">
            <JetstreamStatus />
          </div>

          {/* Sync button */}
          <Button
            variant="outline"
            onClick={handleSync}
            disabled={syncMutation.isPending}
            className="font-mono uppercase tracking-wider border-primary/20 hover:border-primary/50 hover:bg-primary/5"
          >
            {syncMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Initiate Sync
          </Button>

          {/* Config button */}
          <Sheet open={configOpen} onOpenChange={setConfigOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" size="icon" className="border-primary/20 hover:border-primary/50 hover:bg-primary/5">
                <Settings className="h-4 w-4" />
              </Button>
            </SheetTrigger>
            <SheetContent className="w-[400px] sm:w-[540px] bg-background/95 backdrop-blur-sm border-l border-border/50">
              <JetstreamConfig />
            </SheetContent>
          </Sheet>
        </div>
      </div>

      {/* Feed */}
      <JetstreamFeed />
    </div>
  );
}
