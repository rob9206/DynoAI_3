import { useState, useEffect } from 'react';
import { toast } from '@/lib/toast';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { AllRunsTable } from '@/components/portal/AllRunsTable';
import type { User } from '@/types/portal';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:5001';
const authHeaders = (token: string) => ({ Authorization: `Bearer ${token}` });

export function AdminView({ user, token, onLogout }: { user: { name: string }; token: string; onLogout: () => void }) {
  const [users, setUsers] = useState<User[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<{ name: string; role: string }>({ name: '', role: '' });
  const [createForm, setCreateForm] = useState<{ name: string; email: string; password: string; role: string }>({
    name: '', email: '', password: '', role: 'customer',
  });
  const [creating, setCreating] = useState(false);

  const refreshUsers = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/users`, { headers: authHeaders(token) });
      if (res.status === 401) { onLogout(); return; }
      if (!res.ok) { toast.error('Failed to load users'); return; }
      const data = (await res.json()) as { users?: User[] };
      setUsers(data.users ?? []);
    } catch {
      toast.error('Failed to load users');
    }
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

  const deleteUser = async (u: User) => {
    const res = await fetch(`${API_BASE}/api/users/${u.id}`, {
      method: 'DELETE',
      headers: authHeaders(token),
    });
    if (res.status === 401) { onLogout(); return; }
    if (!res.ok) { toast.error('Failed to delete user'); return; }
    await refreshUsers();
    toast.success('User deleted');
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

  const roleBadgeClass = (role: 'owner' | 'tech' | 'customer') =>
    ({ owner: 'bg-violet-600 text-white', tech: 'bg-blue-600 text-white', customer: 'bg-muted text-muted-foreground' }[role]);

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
                                <Button size="sm" variant="ghost" className="text-destructive">
                                  Delete
                                </Button>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>
                                    Delete {u.name}?
                                  </AlertDialogTitle>
                                  <AlertDialogDescription>
                                    This action cannot be undone. The user will be permanently removed.
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                                  <AlertDialogAction onClick={() => void deleteUser(u)}>Confirm</AlertDialogAction>
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

export default AdminView;
