import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
    Clock,
    Filter,
    Download,
    Search,
    BarChart3,
    AlertCircle,
    Loader2,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../ui/select';
import { DecisionCard } from './DecisionCard';
import { getSessionReplay, type SessionReplayData } from '../../lib/api';
import { toast } from 'sonner';

interface SessionReplayViewerProps {
    runId: string;
}

export function SessionReplayViewer({ runId }: SessionReplayViewerProps) {
    const [actionFilter, setActionFilter] = useState<string>('all');
    const [searchQuery, setSearchQuery] = useState('');
    const [showStats, setShowStats] = useState(true);

    // Fetch session replay data
    const {
        data: replayData,
        isLoading,
        error,
    } = useQuery<SessionReplayData>({
        queryKey: ['session-replay', runId],
        queryFn: () => getSessionReplay(runId),
        retry: 1,
    });

    // Calculate statistics
    const stats = useMemo(() => {
        if (!replayData) return null;

        const actionCounts: Record<string, number> = {};
        replayData.decisions.forEach((decision) => {
            actionCounts[decision.action] = (actionCounts[decision.action] || 0) + 1;
        });

        const firstTimestamp = replayData.decisions[0]?.timestamp;
        const lastTimestamp = replayData.decisions[replayData.decisions.length - 1]?.timestamp;

        let duration = 0;
        if (firstTimestamp && lastTimestamp) {
            const start = new Date(firstTimestamp);
            const end = new Date(lastTimestamp);
            duration = end.getTime() - start.getTime();
        }

        return {
            totalDecisions: replayData.total_decisions,
            actionCounts,
            duration,
            generatedAt: replayData.generated_at,
        };
    }, [replayData]);

    // Filter decisions
    const filteredDecisions = useMemo(() => {
        if (!replayData) return [];

        let filtered = replayData.decisions;

        // Filter by action type
        if (actionFilter !== 'all') {
            filtered = filtered.filter((d) =>
                d.action.toUpperCase().includes(actionFilter.toUpperCase())
            );
        }

        // Filter by search query
        if (searchQuery) {
            const query = searchQuery.toLowerCase();
            filtered = filtered.filter(
                (d) =>
                    d.action.toLowerCase().includes(query) ||
                    d.reason.toLowerCase().includes(query) ||
                    JSON.stringify(d.values).toLowerCase().includes(query)
            );
        }

        return filtered;
    }, [replayData, actionFilter, searchQuery]);

    // Get unique action types for filter
    const actionTypes = useMemo(() => {
        if (!replayData) return [];
        const types = new Set(replayData.decisions.map((d) => d.action));
        return Array.from(types).sort();
    }, [replayData]);

    // Export to JSON
    const handleExport = () => {
        if (!replayData) return;

        const dataStr = JSON.stringify(
            {
                ...replayData,
                decisions: filteredDecisions,
            },
            null,
            2
        );
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `session-replay-${runId}.json`;
        link.click();
        URL.revokeObjectURL(url);
        toast.success('Session replay exported');
    };

    if (isLoading) {
        return (
            <Card>
                <CardContent className="flex items-center justify-center py-12">
                    <div className="flex flex-col items-center gap-3">
                        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                        <p className="text-sm text-muted-foreground">Loading session replay...</p>
                    </div>
                </CardContent>
            </Card>
        );
    }

    if (error) {
        return (
            <Card>
                <CardContent className="flex items-center justify-center py-12">
                    <div className="flex flex-col items-center gap-3 text-center">
                        <AlertCircle className="h-8 w-8 text-destructive" />
                        <div>
                            <p className="font-semibold">Session Replay Not Available</p>
                            <p className="text-sm text-muted-foreground mt-1">
                                This run may not have session replay data, or it was created before this feature was added.
                            </p>
                        </div>
                    </div>
                </CardContent>
            </Card>
        );
    }

    if (!replayData) {
        return null;
    }

    const startTime = replayData.decisions[0]?.timestamp;

    return (
        <div className="space-y-6">
            {/* Statistics Card */}
            {showStats && stats && (
                <Card>
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle className="flex items-center gap-2">
                                    <BarChart3 className="h-5 w-5" />
                                    Session Summary
                                </CardTitle>
                                <CardDescription>
                                    Run ID: {replayData.run_id}
                                </CardDescription>
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setShowStats(false)}
                            >
                                Hide
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div>
                                <p className="text-sm text-muted-foreground">Total Decisions</p>
                                <p className="text-2xl font-bold">{stats.totalDecisions}</p>
                            </div>
                            <div>
                                <p className="text-sm text-muted-foreground">Duration</p>
                                <p className="text-2xl font-bold">
                                    {stats.duration < 1000
                                        ? `${stats.duration.toFixed(1)}ms`
                                        : `${(stats.duration / 1000).toFixed(2)}s`}
                                </p>
                            </div>
                            <div>
                                <p className="text-sm text-muted-foreground">Action Types</p>
                                <p className="text-2xl font-bold">{Object.keys(stats.actionCounts).length}</p>
                            </div>
                            <div>
                                <p className="text-sm text-muted-foreground">Generated</p>
                                <p className="text-sm font-mono">
                                    {new Date(stats.generatedAt).toLocaleString()}
                                </p>
                            </div>
                        </div>

                        {/* Action Type Breakdown */}
                        <div className="mt-6">
                            <p className="text-sm font-semibold mb-3">Decisions by Action Type</p>
                            <div className="flex flex-wrap gap-2">
                                {Object.entries(stats.actionCounts)
                                    .sort((a, b) => b[1] - a[1])
                                    .map(([action, count]) => (
                                        <Badge
                                            key={action}
                                            variant="secondary"
                                            className="cursor-pointer hover:bg-secondary/80"
                                            onClick={() => setActionFilter(action)}
                                        >
                                            {action}: {count}
                                        </Badge>
                                    ))}
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Filters and Controls */}
            <Card>
                <CardContent className="pt-6">
                    <div className="flex flex-col md:flex-row gap-4">
                        {/* Search */}
                        <div className="flex-1">
                            <div className="relative">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                <Input
                                    placeholder="Search decisions..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    className="pl-9"
                                />
                            </div>
                        </div>

                        {/* Action Filter */}
                        <Select value={actionFilter} onValueChange={setActionFilter}>
                            <SelectTrigger className="w-full md:w-[250px]">
                                <Filter className="h-4 w-4 mr-2" />
                                <SelectValue placeholder="Filter by action" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All Actions</SelectItem>
                                {actionTypes.map((action) => (
                                    <SelectItem key={action} value={action}>
                                        {action}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>

                        {/* Export Button */}
                        <Button variant="outline" onClick={handleExport}>
                            <Download className="h-4 w-4 mr-2" />
                            Export
                        </Button>

                        {!showStats && (
                            <Button variant="outline" onClick={() => setShowStats(true)}>
                                <BarChart3 className="h-4 w-4 mr-2" />
                                Stats
                            </Button>
                        )}
                    </div>

                    {/* Results Count */}
                    <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
                        <Clock className="h-4 w-4" />
                        <span>
                            Showing {filteredDecisions.length} of {replayData.total_decisions} decisions
                        </span>
                    </div>
                </CardContent>
            </Card>

            {/* Decision Timeline */}
            <div className="space-y-4">
                {filteredDecisions.length === 0 ? (
                    <Card>
                        <CardContent className="flex items-center justify-center py-12">
                            <div className="text-center">
                                <AlertCircle className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
                                <p className="font-semibold">No decisions match your filters</p>
                                <p className="text-sm text-muted-foreground mt-1">
                                    Try adjusting your search or filter criteria
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                ) : (
                    filteredDecisions.map((decision, index) => (
                        <DecisionCard
                            key={index}
                            decision={decision}
                            index={index + 1}
                            startTime={startTime}
                        />
                    ))
                )}
            </div>
        </div>
    );
}

