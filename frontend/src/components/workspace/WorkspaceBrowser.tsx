/**
 * Workspace browser.
 *
 * Vehicle + session list rendered as a reusable block. Used in two places:
 *   - Embedded inside the JetDrive Command Center → Tuning view.
 *   - Standalone fallback page at /workspace (legacy deep link).
 *
 * Session row links continue to point at /workspace/<vid>/sessions/<sid>
 * so existing routes and deep links remain valid.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ChevronRight,
  FlaskConical,
  Folder,
  Plus,
} from 'lucide-react';

import { toast } from '@/lib/toast';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty';
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';

import {
  useCreateSession,
  useCreateVehicle,
  useSessions,
  useVehicles,
} from '@/hooks/useTuningWorkspace';

interface WorkspaceBrowserProps {
  /**
   * Show the page-level header (title + subtitle + new vehicle button).
   * Set to false when embedded in a host that already provides chrome.
   */
  showHeader?: boolean;
}

export function WorkspaceBrowser({ showHeader = true }: WorkspaceBrowserProps) {
  const vehicles = useVehicles();
  const [newVehicleOpen, setNewVehicleOpen] = useState(false);

  return (
    <div className="flex flex-col gap-6">
      {showHeader ? (
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
              <FlaskConical className="size-6 text-primary" />
              Tuning Workspace
            </h1>
            <p className="text-sm text-muted-foreground">
              One place per bike. Drop pulls and tunes, let DynoAI route them.
            </p>
          </div>
          <NewVehicleDialog open={newVehicleOpen} onOpenChange={setNewVehicleOpen} />
        </header>
      ) : (
        <div className="flex justify-end">
          <NewVehicleDialog open={newVehicleOpen} onOpenChange={setNewVehicleOpen} />
        </div>
      )}

      {vehicles.isLoading ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : vehicles.data && vehicles.data.length > 0 ? (
        <div className="flex flex-col gap-4">
          {vehicles.data.map((v) => (
            <VehicleCard
              key={v.id}
              vehicleId={v.id}
              name={v.name}
              summary={summaryOf(v)}
            />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent>
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <FlaskConical />
                </EmptyMedia>
                <EmptyTitle>No vehicles yet</EmptyTitle>
                <EmptyDescription>
                  Add a vehicle to start collecting tuning sessions, pulls, and
                  patches in one place.
                </EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button onClick={() => setNewVehicleOpen(true)}>
                  <Plus data-icon="inline-start" />
                  Add vehicle
                </Button>
              </EmptyContent>
            </Empty>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function NewVehicleDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const createVehicle = useCreateVehicle();
  const [name, setName] = useState('');
  const [year, setYear] = useState('');
  const [make, setMake] = useState('');
  const [model, setModel] = useState('');
  const [displacement, setDisplacement] = useState('');

  const reset = () => {
    setName('');
    setYear('');
    setMake('');
    setModel('');
    setDisplacement('');
  };

  const submit = () => {
    if (!name.trim()) {
      toast.error('Name required');
      return;
    }
    void (async () => {
      try {
        await createVehicle.mutateAsync({
          name: name.trim(),
          year: year ? Number(year) : undefined,
          make: make.trim(),
          model: model.trim(),
          displacement_ci: displacement ? Number(displacement) : undefined,
        });
        toast.success('Vehicle added');
        onOpenChange(false);
        reset();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'create failed');
      }
    })();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <Plus data-icon="inline-start" />
          Add vehicle
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New vehicle</DialogTitle>
          <DialogDescription>
            A vehicle record survives across all tuning sessions for that bike.
          </DialogDescription>
        </DialogHeader>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="v-name">Name</FieldLabel>
            <Input
              id="v-name"
              placeholder="Racile 2006 Dyna 88ci"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <FieldDescription>
              Used as the display name across the workspace.
            </FieldDescription>
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field>
              <FieldLabel htmlFor="v-year">Year</FieldLabel>
              <Input
                id="v-year"
                type="number"
                placeholder="2006"
                value={year}
                onChange={(e) => setYear(e.target.value)}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="v-disp">Displacement (ci)</FieldLabel>
              <Input
                id="v-disp"
                type="number"
                placeholder="88"
                value={displacement}
                onChange={(e) => setDisplacement(e.target.value)}
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field>
              <FieldLabel htmlFor="v-make">Make</FieldLabel>
              <Input
                id="v-make"
                placeholder="Harley-Davidson"
                value={make}
                onChange={(e) => setMake(e.target.value)}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="v-model">Model</FieldLabel>
              <Input
                id="v-model"
                placeholder="Dyna"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              />
            </Field>
          </div>
        </FieldGroup>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={createVehicle.isPending}>
            {createVehicle.isPending ? (
              <Spinner data-icon="inline-start" />
            ) : null}
            Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function summaryOf(v: {
  year?: number | null;
  make: string;
  model: string;
  displacement_ci?: number | null;
}) {
  const parts: string[] = [];
  if (v.year) parts.push(String(v.year));
  if (v.make) parts.push(v.make);
  if (v.model) parts.push(v.model);
  if (v.displacement_ci) parts.push(`${v.displacement_ci} ci`);
  return parts.join(' ');
}

function VehicleCard({
  vehicleId,
  name,
  summary,
}: {
  vehicleId: string;
  name: string;
  summary: string;
}) {
  const sessions = useSessions(vehicleId);
  const createSession = useCreateSession(vehicleId);

  const startSession = () => {
    void (async () => {
      try {
        const s = await createSession.mutateAsync({});
        toast.success(`Started session ${s.id}`);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'create failed');
      }
    })();
  };

  const sessionList = sessions.data ?? [];
  const hasSessions = !sessions.isLoading && sessionList.length > 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <CardTitle>{name}</CardTitle>
            {summary ? <CardDescription>{summary}</CardDescription> : null}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={startSession}
            disabled={createSession.isPending}
          >
            {createSession.isPending ? (
              <Spinner data-icon="inline-start" />
            ) : (
              <Plus data-icon="inline-start" />
            )}
            New session
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {sessions.isLoading ? (
          <Skeleton className="h-8 w-full" />
        ) : hasSessions ? (
          <ul className="flex flex-col">
            {sessionList.map((s, i) => (
              <li key={s.id}>
                {i > 0 ? <Separator /> : null}
                <Link
                  to={`/workspace/${encodeURIComponent(vehicleId)}/sessions/${encodeURIComponent(s.id)}`}
                  className="group flex items-center justify-between gap-3 py-3"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <Folder className="size-4 shrink-0 text-muted-foreground" />
                    <span className="truncate font-mono text-sm">{s.id}</span>
                    {s.active_iteration_id ? (
                      <Badge variant="secondary">{s.active_iteration_id}</Badge>
                    ) : null}
                  </div>
                  <ChevronRight className="size-4 text-muted-foreground transition-colors group-hover:text-foreground" />
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <Empty className="border-0 p-0 md:p-0">
            <EmptyHeader>
              <EmptyTitle>No sessions yet</EmptyTitle>
              <EmptyDescription>
                Start a session to drop pulls and tunes for this bike.
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button
                variant="outline"
                size="sm"
                onClick={startSession}
                disabled={createSession.isPending}
              >
                {createSession.isPending ? (
                  <Spinner data-icon="inline-start" />
                ) : (
                  <Plus data-icon="inline-start" />
                )}
                Start session
              </Button>
            </EmptyContent>
          </Empty>
        )}
      </CardContent>
    </Card>
  );
}
