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
      <div className="flex flex-wrap items-center justify-between gap-4 pb-6 relative">
        {/* Subtle gradient accent line */}
        <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-cyan-500/40 to-transparent" />

        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight font-mono uppercase flex items-center gap-3 text-foreground/95">
            <div className="relative">
              <Radio className="h-6 w-6 text-cyan-400" />
              <div className="absolute inset-0 h-6 w-6 text-cyan-400 blur-md opacity-30" />
            </div>
            <span className="bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text">
              Jetstream Data Link
            </span>
          </h1>
          <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.2em] flex items-center gap-2 mt-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-50"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
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
            className="font-mono uppercase tracking-[0.15em] text-xs border-cyan-500/30 hover:border-cyan-400/60 hover:bg-cyan-500/10 hover:text-cyan-300 transition-all duration-300"
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
              <Button variant="outline" size="icon" className="border-border/40 hover:border-cyan-500/50 hover:bg-cyan-500/5 transition-all duration-300">
                <Settings className="h-4 w-4" />
              </Button>
            </SheetTrigger>
            <SheetContent className="w-[400px] sm:w-[540px] bg-background/98 backdrop-blur-xl border-l border-cyan-500/20">
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
