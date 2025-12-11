import { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Activity, History, Home, Radio, Zap, Sparkles, Gauge } from 'lucide-react';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();

  const isActive = (path: string) => {
    return location.pathname === path || location.pathname.startsWith(path + '/');
  };

  return (
    <div className="min-h-screen bg-background text-foreground font-sans">
      {/* Header */}
      <header className="border-b border-border bg-background/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="bg-primary/10 p-2 rounded-md">
                <Activity className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-foreground tracking-tight">DynoAI</h1>
                <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">AI-Powered Dyno Tuning</p>
              </div>
            </div>

            {/* Navigation */}
            <nav className="flex space-x-2">
              <Link
                to="/jetstream"
                className={`flex items-center space-x-2 px-4 py-3 rounded-lg transition-all duration-200 font-medium ${isActive('/jetstream') || isActive('/runs')
                  ? 'bg-primary text-primary-foreground shadow-md'
                  : 'text-muted-foreground hover:bg-secondary hover:text-secondary-foreground'
                  }`}
              >
                <Radio className="h-5 w-5" />
                <span>Live Feed</span>
              </Link>
              <Link
                to="/dashboard"
                className={`flex items-center space-x-2 px-4 py-3 rounded-lg transition-all duration-200 font-medium ${isActive('/dashboard')
                  ? 'bg-primary text-primary-foreground shadow-md'
                  : 'text-muted-foreground hover:bg-secondary hover:text-secondary-foreground'
                  }`}
              >
                <Home className="h-5 w-5" />
                <span>Control Center</span>
              </Link>
              <Link
                to="/livelink"
                className={`flex items-center space-x-2 px-4 py-3 rounded-lg transition-all duration-200 font-medium ${isActive('/livelink')
                  ? 'bg-primary text-primary-foreground shadow-md'
                  : 'text-muted-foreground hover:bg-secondary hover:text-secondary-foreground'
                  }`}
              >
                <Zap className="h-5 w-5" />
                <span>LiveLink</span>
              </Link>
              <Link
                to="/jetdrive"
                className={`flex items-center space-x-2 px-4 py-3 rounded-lg transition-all duration-200 font-medium ${isActive('/jetdrive')
                  ? 'bg-gradient-to-r from-orange-600 to-red-500 text-white shadow-md shadow-orange-500/25'
                  : 'text-muted-foreground hover:bg-orange-500/10 hover:text-orange-300'
                  }`}
              >
                <Gauge className="h-5 w-5" />
                <span>JetDrive</span>
              </Link>
              <Link
                to="/wizards"
                className={`flex items-center space-x-2 px-4 py-3 rounded-lg transition-all duration-200 font-medium ${isActive('/wizards')
                  ? 'bg-gradient-to-r from-orange-500 to-amber-500 text-white shadow-md shadow-orange-500/25'
                  : 'text-muted-foreground hover:bg-orange-500/10 hover:text-orange-300'
                  }`}
              >
                <Sparkles className="h-5 w-5" />
                <span>Wizards</span>
              </Link>
              <Link
                to="/history"
                className={`flex items-center space-x-2 px-4 py-3 rounded-lg transition-all duration-200 font-medium ${isActive('/history')
                  ? 'bg-primary text-primary-foreground shadow-md'
                  : 'text-muted-foreground hover:bg-secondary hover:text-secondary-foreground'
                  }`}
              >
                <History className="h-5 w-5" />
                <span>History</span>
              </Link>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-muted/30 mt-auto">
        <div className="container mx-auto px-4 py-6">
          <div className="text-center text-sm text-muted-foreground">
            <p className="font-medium">DynoAI v1.2 - AI-Powered Dyno Tuning Toolkit</p>
            <p className="mt-1 opacity-80">
              Analyze WinPEP logs and generate VE & spark corrections
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
