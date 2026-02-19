import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/sonner';
import { ThemeProvider } from 'next-themes';
import { lazy, Suspense, useState, type ReactNode } from 'react';
import Layout from './components/common/Layout';
import LoadingSpinner from './components/common/LoadingSpinner';

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

// ---------------------------------------------------------------------------
// Portal auth guard
// Reads token and user name from localStorage and injects them as props.
// Redirects to the main app if no token is found.
// ---------------------------------------------------------------------------

/** Matches the shape returned by GET /api/runs */
interface Run {
  id: string
  userId: string
  userEmail?: string
  userName?: string
  fileName: string
  status: 'queued' | 'running' | 'completed' | 'error'
  correctionsApplied: number
  outputFiles: string[]
  created_at: string
}

/** Matches the shape returned by GET /api/users */
interface User {
  id: string
  email: string
  name: string
  role: 'owner' | 'tech' | 'customer'
  active: boolean
  created_at: string
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
          <TableRow key={run.id}>
            <TableCell>{new Date(run.created_at).toLocaleString()}</TableCell>
            <TableCell>{run.userName ?? run.userEmail ?? 'Unknown'}</TableCell>
            <TableCell className="font-mono text-sm">{run.fileName}</TableCell>
            <TableCell>{run.correctionsApplied}</TableCell>
            <TableCell>
              <Badge variant={run.status === 'completed' ? 'default' : run.status === 'error' ? 'destructive' : 'secondary'}>
                {run.status}
              </Badge>
            </TableCell>
            <TableCell>
              {run.status === 'completed' && run.outputFiles?.map((f) => (
                <a
                  key={f}
                  href={`${API_BASE}/api/download/${run.id}/${f}`}
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

  if (!token) return <Navigate to="/jetdrive" replace />;

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
                    <TableHead>Status</TableHead>
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
                      <TableCell>
                        <Badge variant={u.active ? 'default' : 'destructive'}>
                          {u.active ? 'Active' : 'Inactive'}
                        </Badge>
                      </TableCell>

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
                                <Button size="sm" variant="ghost" className={u.active ? 'text-destructive' : ''}>
                                  {u.active ? 'Deactivate' : 'Activate'}
                                </Button>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>
                                    {u.active ? 'Deactivate' : 'Activate'} {u.name}?
                                  </AlertDialogTitle>
                                  <AlertDialogDescription>
                                    {u.active
                                      ? 'They will lose access to the customer portal.'
                                      : 'They will regain access to the customer portal.'}
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                                  <AlertDialogAction onClick={() => void toggleActive(u)}>Confirm</AlertDialogAction>
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
