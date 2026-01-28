/**
 * MappingConfidencePanel - Pre-Capture Mapping Confidence Report
 *
 * Displays confidence scores for channel mappings before starting capture:
 * - Overall readiness indicator
 * - Per-channel confidence scores with visual indicators
 * - Missing required channels
 * - Low-confidence warnings
 * - Import/Export functionality
 */

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
    CheckCircle, AlertTriangle, XCircle, Download, Upload,
    RefreshCw, Loader2, TrendingUp, Activity, Info
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { Alert, AlertDescription } from '../ui/alert';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from '../ui/tooltip';
import { cn } from '../../lib/utils';

// =============================================================================
// Types
// =============================================================================

interface MappingConfidence {
    canonical_name: string;
    source_id: number;
    source_name: string;
    confidence: number;
    reasons: string[];
    warnings: string[];
    transform: string;
}

interface ConfidenceReport {
    success: boolean;
    provider_signature: string;
    provider_id: number;
    provider_name: string;
    overall_confidence: number;
    ready_for_capture: boolean;
    mappings: MappingConfidence[];
    unmapped_required: string[];
    unmapped_recommended: string[];
    low_confidence: MappingConfidence[];
    suspected_mislabels: any[];
    has_existing_mapping: boolean;
}

interface MappingConfidencePanelProps {
    apiUrl?: string;
    onReadyChange?: (ready: boolean) => void;
}

// =============================================================================
// Helper Components
// =============================================================================

function ConfidenceBadge({ confidence }: { confidence: number }) {
    const percentage = Math.round(confidence * 100);
    
    let variant: 'default' | 'secondary' | 'destructive' = 'default';
    let className = '';
    
    if (percentage >= 80) {
        className = 'bg-green-500/20 text-green-400 border-green-500/30';
    } else if (percentage >= 50) {
        className = 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    } else {
        className = 'bg-red-500/20 text-red-400 border-red-500/30';
    }
    
    return (
        <Badge variant="outline" className={className}>
            {percentage}%
        </Badge>
    );
}

function ReadinessIndicator({ ready, confidence }: { ready: boolean; confidence: number }) {
    if (ready) {
        return (
            <div className="flex items-center gap-2 p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
                <CheckCircle className="h-5 w-5 text-green-400" />
                <div>
                    <div className="font-medium text-green-400">Ready for Capture</div>
                    <div className="text-sm text-muted-foreground">
                        Overall confidence: {Math.round(confidence * 100)}%
                    </div>
                </div>
            </div>
        );
    }
    
    return (
        <div className="flex items-center gap-2 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <AlertTriangle className="h-5 w-5 text-yellow-400" />
            <div>
                <div className="font-medium text-yellow-400">Review Required</div>
                <div className="text-sm text-muted-foreground">
                    Check warnings below before starting capture
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export function MappingConfidencePanel({
    apiUrl = 'http://127.0.0.1:5001/api/jetdrive',
    onReadyChange,
}: MappingConfidencePanelProps) {
    const queryClient = useQueryClient();
    const [selectedFile, setSelectedFile] = useState<File | null>(null);

    const buildErrorMessage = async (res: Response, fallback: string) => {
        const statusLabel = res.statusText ? `${res.status} ${res.statusText}` : `${res.status}`;
        const base = `${fallback} (${statusLabel})`;

        try {
            const contentType = res.headers.get('content-type') ?? '';
            if (contentType.includes('application/json')) {
                const payload: unknown = await res.json();
                const errorValue =
                    payload &&
                    typeof payload === 'object' &&
                    'error' in payload
                        ? (payload as { error?: unknown }).error
                        : payload;

                if (typeof errorValue === 'string' && errorValue.trim().length > 0) {
                    return `${base}: ${errorValue}`;
                }

                if (errorValue && typeof errorValue === 'object' && 'message' in errorValue) {
                    const message = (errorValue as { message?: unknown }).message;
                    if (typeof message === 'string' && message.trim().length > 0) {
                        return `${base}: ${message}`;
                    }
                }

                if (errorValue != null) {
                    return `${base}: ${JSON.stringify(errorValue)}`;
                }
            }

            const text = await res.text();
            return text.trim().length > 0 ? `${base}: ${text}` : base;
        } catch {
            return base;
        }
    };

    // Fetch confidence report
    const { data: report, isLoading, error, refetch } = useQuery<ConfidenceReport>({
        queryKey: ['jetdrive-mapping-confidence', apiUrl],
        queryFn: async () => {
            const res = await fetch(`${apiUrl}/mapping/confidence`);
            if (!res.ok) {
                throw new Error(await buildErrorMessage(res, 'Failed to fetch confidence report'));
            }
            return res.json();
        },
        refetchInterval: false, // Manual refresh only
    });

    // Notify parent of readiness changes
    useEffect(() => {
        if (report && onReadyChange) {
            onReadyChange(report.ready_for_capture);
        }
    }, [report?.ready_for_capture, onReadyChange]);

    // Export mapping
    const handleExport = async () => {
        if (!report) return;
        
        try {
            const res = await fetch(`${apiUrl}/mapping/export/${report.provider_signature}`);
            if (!res.ok) throw new Error('Export failed');
            
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `jetdrive_mapping_${report.provider_signature.slice(0, 8)}.json`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (e) {
            console.error('Export failed:', e);
        }
    };

    // Import mapping
    const importMutation = useMutation({
        mutationFn: async (file: File) => {
            const formData = new FormData();
            formData.append('file', file);
            
            const res = await fetch(`${apiUrl}/mapping/import`, {
                method: 'POST',
                body: formData,
            });
            
            if (!res.ok) throw new Error('Import failed');
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['jetdrive-mapping-confidence'] });
            setSelectedFile(null);
        },
    });

    const handleImport = () => {
        if (selectedFile) {
            importMutation.mutate(selectedFile);
        }
    };

    if (isLoading) {
        return (
            <Card>
                <CardContent className="py-8 flex items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </CardContent>
            </Card>
        );
    }

    if (error || !report?.success) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <XCircle className="h-5 w-5 text-red-500" />
                        Confidence Check Failed
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <Alert variant="destructive">
                        <AlertDescription>
                            {error?.message || 'Failed to load confidence report'}
                        </AlertDescription>
                    </Alert>
                    <Button onClick={() => refetch()} className="mt-4" variant="outline">
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Retry
                    </Button>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2">
                            <TrendingUp className="h-5 w-5 text-blue-500" />
                            Mapping Confidence
                        </CardTitle>
                        <CardDescription>
                            {report.provider_name} (0x{report.provider_id.toString(16).toUpperCase()})
                        </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleExport}
                            disabled={!report.has_existing_mapping}
                        >
                            <Download className="h-4 w-4 mr-1" />
                            Export
                        </Button>
                        <input
                            type="file"
                            accept=".json"
                            onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                            className="hidden"
                            id="import-mapping"
                        />
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => document.getElementById('import-mapping')?.click()}
                        >
                            <Upload className="h-4 w-4 mr-1" />
                            Import
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => refetch()}
                        >
                            <RefreshCw className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            </CardHeader>

            <CardContent className="space-y-4">
                {/* Import file preview */}
                {selectedFile && (
                    <Alert>
                        <AlertDescription className="flex items-center justify-between">
                            <span>{selectedFile.name}</span>
                            <Button
                                size="sm"
                                onClick={handleImport}
                                disabled={importMutation.isPending}
                            >
                                {importMutation.isPending ? 'Importing...' : 'Import Now'}
                            </Button>
                        </AlertDescription>
                    </Alert>
                )}

                {/* Readiness Indicator */}
                <ReadinessIndicator
                    ready={report.ready_for_capture}
                    confidence={report.overall_confidence}
                />

                {/* Overall Confidence */}
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">Overall Confidence</span>
                        <ConfidenceBadge confidence={report.overall_confidence} />
                    </div>
                    <Progress
                        value={report.overall_confidence * 100}
                        className={cn(
                            "h-2",
                            report.overall_confidence >= 0.8 ? '[&>div]:bg-green-500' :
                            report.overall_confidence >= 0.5 ? '[&>div]:bg-yellow-500' :
                            '[&>div]:bg-red-500'
                        )}
                    />
                </div>

                {/* Missing Required Channels */}
                {report.unmapped_required.length > 0 && (
                    <Alert variant="destructive">
                        <XCircle className="h-4 w-4" />
                        <AlertDescription>
                            <div className="font-medium mb-1">Missing Required Channels</div>
                            <div className="text-sm">
                                {report.unmapped_required.join(', ')}
                            </div>
                            <div className="text-xs mt-2 opacity-80">
                                Enable these channels in Power Core JetDrive settings
                            </div>
                        </AlertDescription>
                    </Alert>
                )}

                {/* Channel Mappings */}
                <div className="space-y-2">
                    <h4 className="text-sm font-medium flex items-center gap-2">
                        <Activity className="h-4 w-4" />
                        Channel Mappings ({report.mappings.length})
                    </h4>
                    <div className="space-y-1">
                        {report.mappings.map((mapping) => (
                            <TooltipProvider key={mapping.canonical_name}>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <div className="flex items-center gap-2 p-2 bg-muted/30 rounded hover:bg-muted/50 cursor-help">
                                            <div className="flex-1 min-w-0">
                                                <div className="font-medium text-sm truncate">
                                                    {mapping.canonical_name}
                                                </div>
                                                <div className="text-xs text-muted-foreground truncate">
                                                    {mapping.source_name} (ID: {mapping.source_id})
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {mapping.warnings.length > 0 && (
                                                    <AlertTriangle className="h-4 w-4 text-yellow-400" />
                                                )}
                                                <ConfidenceBadge confidence={mapping.confidence} />
                                            </div>
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent className="max-w-xs">
                                        <div className="space-y-1">
                                            <div className="font-medium">Reasons:</div>
                                            {mapping.reasons.map((reason, i) => (
                                                <div key={i} className="text-xs">• {reason}</div>
                                            ))}
                                            {mapping.warnings.length > 0 && (
                                                <>
                                                    <div className="font-medium mt-2">Warnings:</div>
                                                    {mapping.warnings.map((warning, i) => (
                                                        <div key={i} className="text-xs text-yellow-400">• {warning}</div>
                                                    ))}
                                                </>
                                            )}
                                            {mapping.transform !== 'identity' && (
                                                <div className="text-xs mt-2 text-blue-400">
                                                    Transform: {mapping.transform}
                                                </div>
                                            )}
                                        </div>
                                    </TooltipContent>
                                </Tooltip>
                            </TooltipProvider>
                        ))}
                    </div>
                </div>

                {/* Low Confidence Warnings */}
                {report.low_confidence.length > 0 && (
                    <Alert>
                        <AlertTriangle className="h-4 w-4" />
                        <AlertDescription>
                            <div className="font-medium mb-1">Low Confidence Mappings</div>
                            <div className="text-sm space-y-1">
                                {report.low_confidence.map((m) => (
                                    <div key={m.canonical_name}>
                                        {m.canonical_name}: {Math.round(m.confidence * 100)}%
                                    </div>
                                ))}
                            </div>
                            <div className="text-xs mt-2 opacity-80">
                                Review these mappings manually in Channel Mapping panel
                            </div>
                        </AlertDescription>
                    </Alert>
                )}

                {/* Unmapped Recommended */}
                {report.unmapped_recommended.length > 0 && (
                    <Alert>
                        <Info className="h-4 w-4" />
                        <AlertDescription>
                            <div className="font-medium mb-1">Recommended Channels</div>
                            <div className="text-sm">
                                Consider enabling: {report.unmapped_recommended.join(', ')}
                            </div>
                        </AlertDescription>
                    </Alert>
                )}

                {/* Mapping Status */}
                {!report.has_existing_mapping && (
                    <div className="text-sm text-muted-foreground text-center py-2">
                        <Info className="h-4 w-4 inline mr-1" />
                        Auto-detected mapping - save in Channel Mapping panel to persist
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

export default MappingConfidencePanel;
