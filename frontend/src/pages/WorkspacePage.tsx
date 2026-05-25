/**
 * Workspace index (standalone route).
 *
 * The canonical home for the workspace is now JetDrive Command Center →
 * Tuning. This standalone page remains available so existing
 * /workspace bookmarks and the "Back to Workspace" link from a session
 * deep-link still resolve.
 *
 * Real rendering lives in `WorkspaceBrowser` so both paths share one
 * implementation.
 */

import { ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { WorkspaceBrowser } from '@/components/workspace/WorkspaceBrowser';

export default function WorkspacePage() {
  return (
    <div className="container mx-auto flex max-w-5xl flex-col gap-4 py-6">
      <div>
        <Button variant="ghost" size="sm" asChild>
          <Link to="/jetdrive?view=tuning">
            <ArrowLeft data-icon="inline-start" />
            JetDrive Command Center
          </Link>
        </Button>
      </div>
      <WorkspaceBrowser />
    </div>
  );
}
