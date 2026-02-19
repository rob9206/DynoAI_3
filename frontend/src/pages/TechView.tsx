import { Button } from '@/components/ui/button';
import { AllRunsTable } from '@/components/portal/AllRunsTable';

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

export default TechView;
