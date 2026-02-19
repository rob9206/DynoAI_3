import { useState, useEffect } from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import type { Run } from '@/types/portal';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:5001';
const authHeaders = (token: string) => ({ Authorization: `Bearer ${token}` });

export function AllRunsTable({ token, onLogout }: { token: string; onLogout: () => void }) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setError('');
    void (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/runs`, { headers: authHeaders(token) });
        if (res.status === 401) { onLogout(); return; }
        if (!res.ok) { setError(`Failed to load runs (status ${res.status})`); return; }
        const data = (await res.json()) as { runs?: Run[] };
        setRuns(data.runs ?? []);
      } catch {
        setError('Failed to load runs');
      } finally {
        setLoading(false);
      }
    })();
  }, [token, onLogout]);

  if (loading) return <Skeleton className="h-64 w-full" />;
  if (error) return <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>;

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Date</TableHead>
          <TableHead>Run ID</TableHead>
          <TableHead>Input File</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => (
          <TableRow key={run.runId}>
            <TableCell>{run.timestamp ? new Date(run.timestamp).toLocaleString() : '—'}</TableCell>
            <TableCell className="font-mono text-sm">{run.runId}</TableCell>
            <TableCell className="font-mono text-sm">{run.inputFile ?? '—'}</TableCell>
          </TableRow>
        ))}
        {runs.length === 0 && (
          <TableRow>
            <TableCell colSpan={3} className="text-center text-muted-foreground py-8">
              No runs found
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
