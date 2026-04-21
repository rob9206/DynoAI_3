import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/sonner';
import { ThemeProvider } from 'next-themes';
import { lazy, Suspense, useState, useEffect, type ReactNode } from 'react';
import Layout from './components/common/Layout';
import LoadingSpinner from './components/common/LoadingSpinner';
import { toast } from '@/lib/toast';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';

// Code-split routes for better initial load performance
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Results = lazy(() => import('./pages/Results'));
const History = lazy(() => import('./pages/History'));
const VEHeatmapDemo = lazy(() => import('./pages/VEHeatmapDemo'));
const JetstreamPage = lazy(() => import('./pages/JetstreamPage'));
const RunDetailPage = lazy(() => import('./pages/RunDetailPage'));
const TimeMachinePage = lazy(() => import('./pages/TimeMachinePage'));
const TuningWizardsPage = lazy(() => import('./pages/TuningWizardsPage'));
const JetDriveAutoTunePage = lazy(() => import('./pages/JetDriveAutoTunePage'));
const OperatorTrainingPage = lazy(() => import('./pages/OperatorTrainingPage'));
const AutoTuneDemo = lazy(() => import('./pages/AutoTuneDemo'));
const EngineAnalyzerPage = lazy(() => import('./pages/EngineAnalyzerPage'));
const TechViewPage = lazy(() => import('./pages/TechView'));
const AdminViewPage = lazy(() => import('./pages/AdminView'));
const WorkspacePage = lazy(() => import('./pages/WorkspacePage'));
const TuningSessionPage = lazy(() => import('./pages/TuningSessionPage'));

// ---------------------------------------------------------------------------
// Portal auth guard
// Reads token and user name from localStorage and injects them as props.
// Redirects to the main app if no token is found.
// ---------------------------------------------------------------------------

function PortalGuard({ render }: { render: (token: string, user: { name: string; role: string }, onLogout: () => void) => ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<{ name: string; role: string } | null>(null);

  useEffect(() => {
    const storedToken = localStorage.getItem('portal_token');
    const storedUser = localStorage.getItem('portal_user');
    
    if (storedToken && storedUser) {
      try {
        const userData = JSON.parse(storedUser);
        setToken(storedToken);
        setUser({ name: userData.name || 'User', role: userData.role || 'customer' });
      } catch {
        localStorage.removeItem('portal_token');
        localStorage.removeItem('portal_user');
      }
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('portal_token');
    localStorage.removeItem('portal_user');
    setToken(null);
    setUser(null);
    window.location.href = '/jetdrive';
  };

  if (!token || !user) {
    return <Navigate to="/jetdrive" replace />;
  }

  return <>{render(token, user, handleLogout)}</>;
}

/** Matches the shape returned by GET /api/runs */
interface Run {
  runId: string
  userId: string | null
  userEmail?: string | null
  userName?: string | null
  status: string
  inputFile: string | null
  createdAt: string | null
  completedAt?: string | null
  rowsProcessed?: number | null
  correctionsApplied?: number | null
  analysisMetrics?: {
    avgCorrection?: number | null
    maxCorrection?: number | null
  }
  outputFiles?: string[]
}

/** Matches the shape returned by GET /api/users */
interface User {
  id: string
  email: string
  name: string
  role: 'owner' | 'tech' | 'customer'
  active?: boolean
  created_at: string | null
}

// ---------------------------------------------------------------------------
// Constants / helpers
// ---------------------------------------------------------------------------

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:5001';

const authHeaders = (token: string) => ({ Authorization: `Bearer ${token}` });

// ---------------------------------------------------------------------------
// Shared component: AllRunsTable
// ---------------------------------------------------------------------------

function AllRunsTable({ token, onLogout }: { token: string; onLogout: () => void }) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/runs`, { headers: authHeaders(token) });
        if (res.status === 401) { onLogout(); return; }
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
          <TableHead>Customer</TableHead>
          <TableHead>File</TableHead>
          <TableHead>Corrections</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Downloads</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => (
          <TableRow key={run.runId}>
            <TableCell>{run.createdAt ? new Date(run.createdAt).toLocaleString() : '—'}</TableCell>
            <TableCell>{run.userName ?? run.userEmail ?? run.userId ?? '—'}</TableCell>
            <TableCell className="font-mono text-sm">{run.inputFile ?? '—'}</TableCell>
            <TableCell>{run.correctionsApplied ?? '—'}</TableCell>
            <TableCell>
              <Badge variant={run.status === 'completed' ? 'default' : run.status === 'error' ? 'destructive' : 'secondary'}>
                {run.status}
              </Badge>
            </TableCell>
            <TableCell>
              {run.status === 'completed' && run.outputFiles && run.outputFiles.length > 0 && run.outputFiles.map((f) => (
                <a
                  key={f}
                  href={`${API_BASE}/api/download/${run.runId}/${f}`}
                  className="text-blue-500 underline mr-2 text-sm"
                  target="_blank"
                  rel="noreferrer"
                >
                  {f}
                </a>
              ))}
            </TableCell>
          </TableRow>
        ))}
        {runs.length === 0 && (
          <TableRow>
            <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
              No runs found
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}

// ---------------------------------------------------------------------------
// TechView
// ---------------------------------------------------------------------------

export function TechView({ user, token, onLogout }: { user: { name: string }; token: string; onLogout: () => void }) {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Tech Dashboard — {user.name}</h1>
        <Button variant="ghost" onClick={onLogout}>Logout</Button>
      </header>
      <main className="p-6">
        <AllRunsTable token={token} onLogout={onLogout} />
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AdminView
// ---------------------------------------------------------------------------

export function AdminView({ user, token, onLogout }: { user: { name: string }; token: string; onLogout: () => void }) {
  // --- Users tab state ---
  const [users, setUsers] = useState<User[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<{ name: string; role: string }>({ name: '', role: '' });
  const [createForm, setCreateForm] = useState<{ name: string; email: string; password: string; role: string }>({
    name: '', email: '', password: '', role: 'customer',
  });
  const [creating, setCreating] = useState(false);

  const refreshUsers = async () => {
    const res = await fetch(`${API_BASE}/api/users`, { headers: authHeaders(token) });
    if (res.status === 401) { onLogout(); return; }
    const data = (await res.json()) as { users?: User[] };
    setUsers(data.users ?? []);
  };

  useEffect(() => {
    setUsersLoading(true);
    void refreshUsers().finally(() => setUsersLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startEdit = (u: User) => {
    setEditingId(u.id);
    setEditForm({ name: u.name, role: u.role });
  };

  const saveEdit = async (userId: string) => {
    const res = await fetch(`${API_BASE}/api/users/${userId}`, {
      method: 'PUT',
      headers: { ...authHeaders(token), 'Content-Type': 'application/json' },
      body: JSON.stringify(editForm),
    });
    if (res.status === 401) { onLogout(); return; }
    if (!res.ok) { toast.error('Failed to update user'); return; }
    await refreshUsers();
    setEditingId(null);
    toast.success('User updated');
  };

  const toggleActive = async (u: User) => {
    const res = await fetch(`${API_BASE}/api/users/${u.id}`, {
      method: 'PUT',
      headers: { ...authHeaders(token), 'Content-Type': 'application/json' },
      body: JSON.stringify({ active: !u.active }),
    });
    if (res.status === 401) { onLogout(); return; }
    if (!res.ok) { toast.error('Failed to update user'); return; }
    await refreshUsers();
    toast.success(u.active ? 'User deactivated' : 'User activated');
  };

  const createUser = async () => {
    setCreating(true);
    try {
      const res = await fetch(`${API_BASE}/api/users`, {
        method: 'POST',
        headers: { ...authHeaders(token), 'Content-Type': 'application/json' },
        body: JSON.stringify(createForm),
      });
      if (res.status === 401) { onLogout(); return; }
      if (res.status === 409) { toast.error('Email already exists'); return; }
      if (!res.ok) { toast.error('Failed to create user'); return; }
      await refreshUsers();
      setCreateForm({ name: '', email: '', password: '', role: 'customer' });
      toast.success('User created');
    } finally {
      setCreating(false);
    }
  };

  const roleBadgeClass = (role: string) =>
    ({ owner: 'bg-violet-600 text-white', tech: 'bg-blue-600 text-white', customer: 'bg-muted text-muted-foreground' }[role] ?? '');

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Owner Dashboard — {user.name}</h1>
        <Button variant="ghost" onClick={onLogout}>Logout</Button>
      </header>

      <main className="p-6">
        <Tabs defaultValue="users">
          <TabsList>
            <TabsTrigger value="users">Users</TabsTrigger>
            <TabsTrigger value="runs">All Runs</TabsTrigger>
          </TabsList>

          {/* -------- Users tab -------- */}
          <TabsContent value="users" className="space-y-6">
            {usersLoading ? (
              <Skeleton className="h-64 w-full" />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                    {users.some(u => u.active !== undefined) && <TableHead>Status</TableHead>}
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((u) => (
                    <TableRow key={u.id}>
                      {/* Name */}
                      <TableCell>
                        {editingId === u.id ? (
                          <Input
                            value={editForm.name}
                            onChange={(e) => setEditForm((p) => ({ ...p, name: e.target.value }))}
                            className="h-8"
                          />
                        ) : (
                          u.name
                        )}
                      </TableCell>

                      {/* Email */}
                      <TableCell>{u.email}</TableCell>

                      {/* Role */}
                      <TableCell>
                        {editingId === u.id ? (
                          <Select value={editForm.role} onValueChange={(v) => setEditForm((p) => ({ ...p, role: v }))}>
                            <SelectTrigger className="h-8 w-32"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="customer">Customer</SelectItem>
                              <SelectItem value="tech">Tech</SelectItem>
                              <SelectItem value="owner">Owner</SelectItem>
                            </SelectContent>
                          </Select>
                        ) : (
                          <Badge className={roleBadgeClass(u.role)}>{u.role}</Badge>
                        )}
                      </TableCell>

                      {/* Status */}
                      {u.active !== undefined && (
                        <TableCell>
                          <Badge variant={u.active ? 'default' : 'destructive'}>
                            {u.active ? 'Active' : 'Inactive'}
                          </Badge>
                        </TableCell>
                      )}

                      {/* Actions */}
                      <TableCell className="space-x-1">
                        {editingId === u.id ? (
                          <>
                            <Button size="sm" onClick={() => void saveEdit(u.id)}>Save</Button>
                            <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>Cancel</Button>
                          </>
                        ) : (
                          <>
                            <Button size="sm" variant="ghost" onClick={() => startEdit(u)}>Edit</Button>
                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <Button size="sm" variant="ghost" className={u.active !== undefined && u.active ? 'text-destructive' : ''}>
                                  {u.active !== undefined ? (u.active ? 'Deactivate' : 'Activate') : 'Delete'}
                                </Button>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>
                                    {u.active !== undefined ? `${u.active ? 'Deactivate' : 'Activate'} ${u.name}?` : `Delete ${u.name}?`}
                                  </AlertDialogTitle>
                                  <AlertDialogDescription>
                                    {u.active !== undefined
                                      ? (u.active
                                        ? 'They will lose access to the customer portal.'
                                        : 'They will regain access to the customer portal.')
                                      : 'This action cannot be undone. The user will be permanently removed.'}
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                                  <AlertDialogAction onClick={() => u.active !== undefined ? void toggleActive(u) : void Promise.resolve()}>
                                    Confirm
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          </>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}

            {/* Create user card */}
            <Card>
              <CardHeader><CardTitle>Create New User</CardTitle></CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Name</Label>
                    <Input
                      value={createForm.name}
                      onChange={(e) => setCreateForm((p) => ({ ...p, name: e.target.value }))}
                      placeholder="Full name"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Email</Label>
                    <Input
                      type="email"
                      value={createForm.email}
                      onChange={(e) => setCreateForm((p) => ({ ...p, email: e.target.value }))}
                      placeholder="email@example.com"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Password</Label>
                    <Input
                      type="password"
                      value={createForm.password}
                      onChange={(e) => setCreateForm((p) => ({ ...p, password: e.target.value }))}
                      placeholder="Password"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Role</Label>
                    <Select value={createForm.role} onValueChange={(v) => setCreateForm((p) => ({ ...p, role: v }))}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="customer">Customer</SelectItem>
                        <SelectItem value="tech">Tech</SelectItem>
                        <SelectItem value="owner">Owner</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <Button
                  onClick={() => void createUser()}
                  disabled={creating || !createForm.name || !createForm.email || !createForm.password}
                  className="mt-4"
                >
                  {creating ? 'Creating...' : 'Create User'}
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* -------- Runs tab -------- */}
          <TabsContent value="runs">
            <AllRunsTable token={token} onLogout={onLogout} />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
        <Router>
          <Layout>
            <Suspense fallback={<LoadingSpinner />}>
              <Routes>
                <Route path="/" element={<Navigate to="/jetdrive" replace />} />
                <Route path="/jetdrive" element={<JetDriveAutoTunePage />} />
                <Route path="/jetstream" element={<JetstreamPage />} />
                <Route path="/runs/:runId" element={<RunDetailPage />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/workspace" element={<WorkspacePage />} />
                <Route
                  path="/workspace/:vehicleId/sessions/:sessionId"
                  element={<TuningSessionPage />}
                />
                <Route path="/results/:runId" element={<Results />} />
                <Route path="/time-machine/:runId" element={<TimeMachinePage />} />
                <Route path="/history" element={<History />} />
                <Route path="/wizards" element={<TuningWizardsPage />} />
                <Route path="/training" element={<OperatorTrainingPage />} />
                <Route path="/engine-analyzer" element={<EngineAnalyzerPage />} />
                <Route path="/ve-heatmap-demo" element={<VEHeatmapDemo />} />
                <Route path="/autotune-demo" element={<AutoTuneDemo />} />
                <Route path="/portal/tech" element={
                  <PortalGuard render={(token, user, onLogout) => <TechViewPage user={user} token={token} onLogout={onLogout} />} />
                } />
                <Route path="/portal/admin" element={
                  <PortalGuard render={(token, user, onLogout) => <AdminViewPage user={user} token={token} onLogout={onLogout} />} />
                } />
                <Route path="*" element={<Navigate to="/jetdrive" replace />} />
              </Routes>
            </Suspense>
          </Layout>
        </Router>
        <Toaster position="top-right" richColors duration={3000} visibleToasts={3} />
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
