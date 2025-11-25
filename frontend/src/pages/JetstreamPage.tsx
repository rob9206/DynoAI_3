/**
 * Jetstream Live Feed page
 */

import { useState } from 'react';
import { RefreshCw, Settings, Loader2 } from 'lucide-react';
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
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Jetstream Live Feed</h1>
          <p className="text-muted-foreground">
            Auto-ingested dyno runs from Jetstream cloud service
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Status indicator */}
          <JetstreamStatus />

          {/* Sync button */}
          <Button
            variant="outline"
            onClick={handleSync}
            disabled={syncMutation.isPending}
          >
            {syncMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Sync Now
          </Button>

          {/* Config button */}
          <Sheet open={configOpen} onOpenChange={setConfigOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" size="icon">
                <Settings className="h-4 w-4" />
              </Button>
            </SheetTrigger>
            <SheetContent className="w-[400px] sm:w-[540px]">
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
