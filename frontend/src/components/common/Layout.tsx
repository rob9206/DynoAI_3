import { ReactNode, memo, useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { History, Home, Radio, Sparkles, Gauge, Volume2, VolumeX, Shield, Database, FlaskConical } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getUiSoundsEnabled, toggleUiSoundsEnabled } from '@/lib/ui-sounds';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const [uiSoundsEnabled, setUiSoundsEnabled] = useState(() => getUiSoundsEnabled());

  useEffect(() => {
    const onChanged = (e: Event) => {
      const ce = e as CustomEvent<{ enabled?: boolean }>;
      if (typeof ce.detail?.enabled === 'boolean') {
        setUiSoundsEnabled(ce.detail.enabled);
      } else {
        setUiSoundsEnabled(getUiSoundsEnabled());
      }
    };

    window.addEventListener('dynoai:ui-sounds', onChanged);
    return () => window.removeEventListener('dynoai:ui-sounds', onChanged);
  }, []);

  const isActive = (path: string) => {
    return location.pathname === path || location.pathname.startsWith(path + '/');
  };

  // Check if we're on JetDrive (main page)
  const isJetDrivePage = isActive('/jetdrive');

  return (
    <div className="min-h-screen bg-background text-foreground font-sans">
      {/* JetDrive hides the full nav; surface Workspace here so Analyze (session page) is discoverable */}
      {isJetDrivePage && (
        <Link
          to="/workspace"
          className="fixed top-3 right-3 z-[100] inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-950/90 px-3 py-2 text-sm font-medium text-zinc-100 shadow-lg backdrop-blur-sm hover:bg-zinc-900 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500"
          title="Open tuning workspace — upload files and run Analyze on a session"
        >
          <FlaskConical className="h-4 w-4 shrink-0 text-orange-400" aria-hidden />
          Workspace
        </Link>
      )}
      {!isJetDrivePage && (
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

              <nav className="flex items-center space-x-1">
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
                  to="/workspace"
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg transition-all duration-200 text-sm ${isActive('/workspace')
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:bg-secondary hover:text-secondary-foreground'
                    }`}
                >
                  <FlaskConical className="h-4 w-4" />
                  <span>Workspace</span>
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
                <Link
                  to="/training"
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg transition-all duration-200 text-sm ${isActive('/training')
                    ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-sm'
                    : 'text-muted-foreground hover:bg-amber-500/10 hover:text-amber-300'
                    }`}
                >
                  <Shield className="h-4 w-4" />
                  <span>Training</span>
                </Link>
                <Link
                  to="/engine-analyzer"
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg transition-all duration-200 text-sm ${isActive('/engine-analyzer')
                    ? 'bg-gradient-to-r from-cyan-500 to-blue-500 text-white shadow-sm'
                    : 'text-muted-foreground hover:bg-cyan-500/10 hover:text-cyan-300'
                    }`}
                >
                  <Database className="h-4 w-4" />
                  <span>EA Library</span>
                </Link>

                <div className="w-px h-6 bg-border mx-2" />

                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="text-muted-foreground hover:bg-secondary hover:text-secondary-foreground"
                  aria-label={uiSoundsEnabled ? 'Mute UI sounds' : 'Enable UI sounds'}
                  onClick={() => setUiSoundsEnabled(toggleUiSoundsEnabled())}
                >
                  {uiSoundsEnabled ? (
                    <Volume2 className="h-4 w-4" />
                  ) : (
                    <VolumeX className="h-4 w-4" />
                  )}
                </Button>
              </nav>
            </div>
          </div>
        </header>
      )}

      <main
        className={isJetDrivePage
          ? 'h-screen w-full p-0'
          : 'container mx-auto px-4 py-8 animate-in fade-in slide-in-from-bottom-4 duration-500 contain-layout'
        }
      >
        {children}
      </main>

      {!isJetDrivePage && (
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
      )}
    </div>
  );
}
