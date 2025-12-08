/**
 * LiveLinkStatus - Connection status indicator for LiveLink WebSocket
 */

import { Wifi, WifiOff, Loader2, Radio } from 'lucide-react';
import { Badge } from '../ui/badge';

interface LiveLinkStatusProps {
    isConnected: boolean;
    isConnecting: boolean;
    mode: string | null;
    error: string | null;
    onConnect?: () => void;
    onDisconnect?: () => void;
}

export function LiveLinkStatus({
    isConnected,
    isConnecting,
    mode,
    error,
    onConnect,
    onDisconnect,
}: LiveLinkStatusProps) {
    const getModeLabel = (m: string | null) => {
        switch (m) {
            case 'wcf': return 'Power Core Live';
            case 'poll': return 'Log Polling';
            case 'simulation': return 'Simulation';
            default: return 'Unknown';
        }
    };

    const getModeColor = (m: string | null) => {
        switch (m) {
            case 'wcf': return 'bg-green-500/20 text-green-400 border-green-500/30';
            case 'poll': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
            case 'simulation': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
            default: return 'bg-muted text-muted-foreground';
        }
    };

    return (
        <div className="flex items-center gap-3">
            {/* Connection Status */}
            <div
                className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-all ${isConnected
                    ? 'bg-green-500/10 border-green-500/30 hover:bg-green-500/20'
                    : error
                        ? 'bg-red-500/10 border-red-500/30 hover:bg-red-500/20'
                        : 'bg-muted/50 border-border hover:bg-muted'
                    }`}
                onClick={isConnected ? onDisconnect : onConnect}
                title={isConnected ? 'Click to disconnect' : 'Click to connect'}
            >
                {isConnecting ? (
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                ) : isConnected ? (
                    <Wifi className="h-4 w-4 text-green-500" />
                ) : (
                    <WifiOff className="h-4 w-4 text-muted-foreground" />
                )}
                <span className="text-sm font-medium">
                    {isConnecting ? 'Connecting...' : isConnected ? 'Connected' : error ? 'Error' : 'Disconnected'}
                </span>
            </div>

            {/* Mode Badge */}
            {isConnected && mode && (
                <Badge variant="outline" className={getModeColor(mode)}>
                    <Radio className="h-3 w-3 mr-1" />
                    {getModeLabel(mode)}
                </Badge>
            )}

            {/* Error Message */}
            {error && !isConnected && (
                <span className="text-xs text-red-400 max-w-[200px] truncate" title={error}>
                    {error}
                </span>
            )}
        </div>
    );
}

export default LiveLinkStatus;

