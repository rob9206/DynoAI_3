import { ReactNode, memo, useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { History, Gauge, Volume2, VolumeX, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getUiSoundsEnabled, toggleUiSoundsEnabled } from '@/lib/ui-sounds';

interface LayoutProps {
  children: ReactNode;
}

function Layout({ children }: LayoutProps) {
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

  // JetDrive owns its own command-center top bar. Workspace pages live under
  // the JetDrive shell conceptually, so they also opt out of the legacy header
  // and provide their own back navigation back to /jetdrive?view=tuning.
  const isJetDrivePage = isActive('/jetdrive');
  const isWorkspaceRoute = isActive('/workspace');
  const hideLegacyChrome = isJetDrivePage || isWorkspaceRoute;

  return (
    <div className="min-h-screen bg-background text-foreground font-sans">
      {!hideLegacyChrome && (
        <header className="border-b sticky top-0 z-50 transition-colors bg-background/80 backdrop-blur-sm border-border">
          <div className="container mx-auto px-4 py-3">
            <div className="flex items-center justify-between">
              <Link to="/jetdrive" className="flex items-center space-x-3 group">
                <div className="p-2 rounded-lg transition-all bg-primary/10">
                  <Gauge className="h-6 w-6 text-primary" />
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
                  to="/hard-start-analyzer"
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg transition-all duration-200 text-sm ${isActive('/hard-start-analyzer')
                    ? 'bg-gradient-to-r from-red-500 to-orange-500 text-white shadow-sm'
                    : 'text-muted-foreground hover:bg-red-500/10 hover:text-red-300'
                    }`}
                >
                  <Zap className="h-4 w-4" />
                  <span>Hard Start</span>
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
          : hideLegacyChrome
            ? 'animate-in fade-in slide-in-from-bottom-4 duration-500 contain-layout'
            : 'container mx-auto px-4 py-8 animate-in fade-in slide-in-from-bottom-4 duration-500 contain-layout'
        }
      >
        {children}
      </main>

      {!hideLegacyChrome && (
        <footer className="border-t mt-auto bg-muted/30 border-border">
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

export default memo(Layout);
