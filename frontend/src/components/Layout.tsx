import { ReactNode, memo } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { History, Home, Radio, Sparkles, Gauge, Volume2 } from 'lucide-react';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();

  const isActive = (path: string) => {
    return location.pathname === path || location.pathname.startsWith(path + '/');
  };

  // Check if we're on JetDrive (main page)
  const isJetDrivePage = isActive('/jetdrive');

  return (
    <div className="min-h-screen bg-background text-foreground font-sans">
      {/* Header */}
      <header className={`border-b sticky top-0 z-50 transition-colors ${isJetDrivePage
        ? 'bg-zinc-950/95 backdrop-blur-md border-zinc-800'
        : 'bg-background/80 backdrop-blur-sm border-border'
        }`}>
        <div className="container mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <Link to="/jetdrive" className="flex items-center space-x-3 group">
              <div className={`p-2 rounded-lg transition-all ${isJetDrivePage
                ? 'bg-gradient-to-br from-orange-500 to-red-600 shadow-lg shadow-orange-500/20'
                : 'bg-primary/10'
                }`}>
                <Gauge className={`h-6 w-6 ${isJetDrivePage ? 'text-white' : 'text-primary'}`} />
              </div>
              <div>
                <h1 className="text-xl font-bold text-foreground tracking-tight flex items-center gap-1">
                  DynoAI
                  <span className="text-xs font-normal text-orange-500 bg-orange-500/10 px-1.5 py-0.5 rounded ml-1">v1.2</span>
                </h1>
                <p className="text-[10px] text-muted-foreground uppercase tracking-widest font-medium">
                  JetDrive Command Center
                </p>
              </div>
            </Link>

            {/* Navigation */}
            <nav className="flex items-center space-x-1">
              {/* Primary: JetDrive */}
              <Link
                to="/jetdrive"
                className={`flex items-center space-x-2 px-4 py-2.5 rounded-lg transition-all duration-200 font-medium ${isActive('/jetdrive')
                  ? 'bg-gradient-to-r from-orange-600 to-red-500 text-white shadow-md shadow-orange-500/25'
                  : 'text-zinc-400 hover:bg-orange-500/10 hover:text-orange-300'
                  }`}
              >
                <Gauge className="h-4 w-4" />
                <span>Command Center</span>
              </Link>

              <div className="w-px h-6 bg-border mx-2" />

              {/* Secondary Navigation */}
              <Link
                to="/jetstream"
                className={`flex items-center space-x-2 px-3 py-2 rounded-lg transition-all duration-200 text-sm ${isActive('/jetstream') || isActive('/runs')
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:bg-secondary hover:text-secondary-foreground'
                  }`}
              >
                <Radio className="h-4 w-4" />
                <span>Live Feed</span>
              </Link>
              <Link
                to="/dashboard"
                className={`flex items-center space-x-2 px-3 py-2 rounded-lg transition-all duration-200 text-sm ${isActive('/dashboard')
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:bg-secondary hover:text-secondary-foreground'
                  }`}
              >
                <Home className="h-4 w-4" />
                <span>Control</span>
              </Link>
              <Link
                to="/wizards"
                className={`flex items-center space-x-2 px-3 py-2 rounded-lg transition-all duration-200 text-sm ${isActive('/wizards')
                  ? 'bg-gradient-to-r from-orange-500 to-amber-500 text-white shadow-sm'
                  : 'text-muted-foreground hover:bg-orange-500/10 hover:text-orange-300'
                  }`}
              >
                <Sparkles className="h-4 w-4" />
                <span>Wizards</span>
              </Link>
              <Link
                to="/history"
                className={`flex items-center space-x-2 px-3 py-2 rounded-lg transition-all duration-200 text-sm ${isActive('/history')
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:bg-secondary hover:text-secondary-foreground'
                  }`}
              >
                <History className="h-4 w-4" />
                <span>History</span>
              </Link>

              <div className="w-px h-6 bg-border mx-2" />

              {/* Audio Demo - Special styling */}
              <Link
                to="/audio-demo"
                className={`flex items-center space-x-2 px-3 py-2 rounded-lg transition-all duration-200 text-sm ${isActive('/audio-demo')
                  ? 'bg-gradient-to-r from-cyan-600 to-blue-600 text-white shadow-sm shadow-cyan-500/25'
                  : 'text-muted-foreground hover:bg-cyan-500/10 hover:text-cyan-300'
                  }`}
              >
                <Volume2 className="h-4 w-4" />
                <span>Audio Demo</span>
              </Link>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8 animate-in fade-in slide-in-from-bottom-4 duration-500 contain-layout">
        {children}
      </main>

      {/* Footer */}
      <footer className={`border-t mt-auto ${isJetDrivePage
        ? 'bg-zinc-950 border-zinc-800'
        : 'bg-muted/30 border-border'
        }`}>
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <div className="flex items-center gap-4">
              <p className="font-medium">DynoAI v1.2</p>
              <span className="text-zinc-600">•</span>
              <p className="text-xs">JetDrive • Power Vision Ready</p>
            </div>
            <div className="text-xs text-zinc-600">
              Real-time dyno capture • VE correction • PVV export
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
