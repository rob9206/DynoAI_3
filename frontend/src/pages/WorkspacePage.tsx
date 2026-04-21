/**
 * Workspace index.
 *
 * Lists all vehicles + their tuning sessions. Launch point for the
 * per-session dropzone page.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { FlaskConical, Plus, Loader2, ChevronRight } from 'lucide-react';

import { toast } from '@/lib/toast';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';

import {
  useCreateSession,
  useCreateVehicle,
  useSessions,
  useVehicles,
} from '../hooks/useTuningWorkspace';

export default function WorkspacePage() {
  const vehicles = useVehicles();
  const createVehicle = useCreateVehicle();

  const [newVehicleOpen, setNewVehicleOpen] = useState(false);
  const [name, setName] = useState('');
  const [year, setYear] = useState('');
  const [make, setMake] = useState('');
  const [model, setModel] = useState('');
  const [displacement, setDisplacement] = useState('');

  const submitNewVehicle = async () => {
    if (!name.trim()) {
      toast.error('Name required');
      return;
    }
    try {
      await createVehicle.mutateAsync({
        name: name.trim(),
        year: year ? Number(year) : undefined,
        make: make.trim(),
        model: model.trim(),
        displacement_ci: displacement ? Number(displacement) : undefined,
      });
      toast.success('Vehicle added');
      setNewVehicleOpen(false);
      setName('');
      setYear('');
      setMake('');
      setModel('');
      setDisplacement('');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'create failed');
    }
  };

  return (
    <div className="container mx-auto py-6 space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <FlaskConical className="h-6 w-6 text-primary" />
            Tuning Workspace
          </h1>
          <p className="text-sm text-muted-foreground">
            One place per bike. Drop pulls and tunes, let DynoAI route them.
          </p>
        </div>
        <Dialog open={newVehicleOpen} onOpenChange={setNewVehicleOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-1" />
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
            <div className="space-y-3">
              <div className="space-y-1">
                <Label htmlFor="v-name">Name *</Label>
                <Input
                  id="v-name"
                  placeholder="Racile 2006 Dyna 88ci"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="v-year">Year</Label>
                  <Input
                    id="v-year"
                    type="number"
                    placeholder="2006"
                    value={year}
                    onChange={(e) => setYear(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="v-disp">Displacement (ci)</Label>
                  <Input
                    id="v-disp"
                    type="number"
                    placeholder="88"
                    value={displacement}
                    onChange={(e) => setDisplacement(e.target.value)}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="v-make">Make</Label>
                  <Input
                    id="v-make"
                    placeholder="Harley-Davidson"
                    value={make}
                    onChange={(e) => setMake(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="v-model">Model</Label>
                  <Input
                    id="v-model"
                    placeholder="Dyna"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                  />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setNewVehicleOpen(false)}>
                Cancel
              </Button>
              <Button onClick={submitNewVehicle} disabled={createVehicle.isPending}>
                {createVehicle.isPending && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
                Create
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {vehicles.isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : vehicles.data && vehicles.data.length > 0 ? (
        <div className="space-y-4">
          {vehicles.data.map((v) => (
            <VehicleCard key={v.id} vehicleId={v.id} name={v.name} summary={summaryOf(v)} />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-sm text-muted-foreground">
              No vehicles yet. Add one to get started.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
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

  const startSession = async () => {
    try {
      const s = await createSession.mutateAsync({});
      toast.success(`Started session ${s.id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'create failed');
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>{name}</CardTitle>
            {summary && <CardDescription>{summary}</CardDescription>}
          </div>
          <Button variant="outline" size="sm" onClick={startSession} disabled={createSession.isPending}>
            <Plus className="h-4 w-4 mr-1" />
            New session
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {sessions.isLoading ? (
          <Skeleton className="h-8 w-full" />
        ) : sessions.data && sessions.data.length > 0 ? (
          <ul className="divide-y">
            {sessions.data.map((s) => (
              <li key={s.id}>
                <Link
                  to={`/workspace/${encodeURIComponent(vehicleId)}/sessions/${encodeURIComponent(s.id)}`}
                  className="flex items-center justify-between py-2 group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="font-mono text-sm truncate">{s.id}</span>
                    {s.active_iteration_id && (
                      <Badge variant="secondary">{s.active_iteration_id}</Badge>
                    )}
                  </div>
                  <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground" />
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground italic">No sessions yet.</p>
        )}
      </CardContent>
    </Card>
  );
}
