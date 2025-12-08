/**
 * LiveLinkPage - Real-time dyno data streaming page
 * 
 * Provides a dashboard for monitoring real-time data from Dynojet Power Core
 * via the LiveLink WebSocket integration.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, Info, ExternalLink, Zap } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { LiveLinkPanel } from '../components/livelink';

// Get server URL from environment or use default
const getServerUrl = () => {
    // Check for runtime config
    if (typeof window !== 'undefined' && (window as unknown as { RUNTIME_CONFIG?: { LIVELINK_URL?: string } }).RUNTIME_CONFIG?.LIVELINK_URL) {
        return (window as unknown as { RUNTIME_CONFIG: { LIVELINK_URL: string } }).RUNTIME_CONFIG.LIVELINK_URL;
    }
    // Default to localhost
    return 'http://127.0.0.1:5003';
};

export default function LiveLinkPage() {
    const [showHelp, setShowHelp] = useState(false);
    const serverUrl = getServerUrl();

    return (
        <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 p-4 md:p-6">
            {/* Page Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
                        <Zap className="h-8 w-8 text-yellow-500" />
                        LiveLink
                    </h1>
                    <p className="text-muted-foreground">
                        Real-time data streaming from Dynojet Power Core
                    </p>
                </div>

                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={() => setShowHelp(!showHelp)}>
                        <Info className="h-4 w-4 mr-2" />
                        {showHelp ? 'Hide Help' : 'Show Help'}
                    </Button>
                    <Button variant="outline" size="sm" asChild>
                        <Link to="/dashboard">
                            <Activity className="h-4 w-4 mr-2" />
                            Control Center
                        </Link>
                    </Button>
                </div>
            </div>

            {/* Help Section */}
            {showHelp && (
                <Alert className="bg-blue-500/10 border-blue-500/30">
                    <Info className="h-4 w-4 text-blue-500" />
                    <AlertTitle>Getting Started with LiveLink</AlertTitle>
                    <AlertDescription className="mt-2 space-y-3">
                        <p>
                            LiveLink connects to Dynojet Power Core to stream real-time engine data
                            directly to your browser. It supports three modes:
                        </p>
                        <ul className="list-disc list-inside space-y-1 text-sm">
                            <li><strong>Power Core Live (WCF)</strong> - Direct connection to Power Core's LiveLinkService</li>
                            <li><strong>Log Polling</strong> - Monitors Power Vision log files for updates</li>
                            <li><strong>Simulation</strong> - Generates synthetic data for testing</li>
                        </ul>
                        <div className="flex items-center gap-2 mt-3">
                            <Button variant="outline" size="sm" asChild>
                                <a href="https://www.dynojet.com/power-core/" target="_blank" rel="noopener noreferrer">
                                    <ExternalLink className="h-3 w-3 mr-1" />
                                    Power Core Docs
                                </a>
                            </Button>
                        </div>
                    </AlertDescription>
                </Alert>
            )}

            {/* Server Status Card */}
            <Card className="border-border/50 bg-muted/20">
                <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                        <CardTitle className="text-sm font-medium">WebSocket Server</CardTitle>
                        <code className="text-xs bg-muted px-2 py-1 rounded">{serverUrl}</code>
                    </div>
                </CardHeader>
                <CardContent>
                    <p className="text-xs text-muted-foreground">
                        Ensure the LiveLink WebSocket server is running. Start it with:
                        <code className="ml-2 bg-muted px-2 py-0.5 rounded">
                            python scripts/start-livelink-ws.py --port 5003
                        </code>
                    </p>
                </CardContent>
            </Card>

            {/* Main LiveLink Panel */}
            <LiveLinkPanel serverUrl={serverUrl} defaultMode="simulation" />

            {/* Feature Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
                <Card className="border-border/50 hover:border-primary/30 transition-colors">
                    <CardHeader>
                        <CardTitle className="text-sm flex items-center gap-2">
                            <Activity className="h-4 w-4 text-green-500" />
                            Real-Time Monitoring
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <CardDescription>
                            Monitor engine RPM, AFR, MAP, TPS, and more in real-time
                            with sub-second latency.
                        </CardDescription>
                    </CardContent>
                </Card>

                <Card className="border-border/50 hover:border-primary/30 transition-colors">
                    <CardHeader>
                        <CardTitle className="text-sm flex items-center gap-2">
                            <Zap className="h-4 w-4 text-yellow-500" />
                            Auto-Tune Integration
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <CardDescription>
                            Use live AFR data to calculate VE corrections on-the-fly
                            for immediate tuning feedback.
                        </CardDescription>
                    </CardContent>
                </Card>

                <Card className="border-border/50 hover:border-primary/30 transition-colors">
                    <CardHeader>
                        <CardTitle className="text-sm flex items-center gap-2">
                            <ExternalLink className="h-4 w-4 text-blue-500" />
                            Power Core Export
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <CardDescription>
                            Export VE corrections directly to Power Core TuneLab
                            or PVV format for immediate application.
                        </CardDescription>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

