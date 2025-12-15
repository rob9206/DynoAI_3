/**
 * SessionReplayPanel - Playback recorded dyno sessions
 * 
 * Provides smooth playback of recorded session data with:
 * - Play/pause/seek controls
 * - Adjustable playback speed
 * - Data interpolation for smooth visualization
 * - Progress tracking
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { Play, Pause, RotateCcw } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Slider } from '../ui/slider';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../ui/select';

interface DataPoint {
    timestamp: number; // seconds from start
    channels: Record<string, number>;
}

interface SessionData {
    run_id: string;
    duration_sec: number;
    data_points: DataPoint[];
}

interface PlaybackState {
    isPlaying: boolean;
    currentTime: number; // seconds from start
    playbackSpeed: number; // 1.0 = normal, 2.0 = 2x, etc.
    duration: number; // total session duration
    sessionData: DataPoint[];
}

interface SessionReplayPanelProps {
    apiUrl: string;
    sessionId: string;
    onDataUpdate?: (channels: Record<string, number>) => void;
}

function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function SessionReplayPanel({ apiUrl, sessionId, onDataUpdate }: SessionReplayPanelProps) {
    // Constants
    const FRAME_INTERVAL_MS = 16; // ~60 FPS
    
    const [playback, setPlayback] = useState<PlaybackState>({
        isPlaying: false,
        currentTime: 0,
        playbackSpeed: 1.0,
        duration: 0,
        sessionData: []
    });

    const [loading, setLoading] = useState(false);

    // Load session data
    const loadSession = useCallback(async () => {
        if (!sessionId) return;

        setLoading(true);
        try {
            const res = await fetch(`${apiUrl}/sessions/${sessionId}`);
            if (!res.ok) {
            const errorText = await res.text().catch(() => 'Unknown error');
            throw new Error(`Failed to load session (${res.status}): ${errorText}`);
        }

            const data: SessionData = await res.json();

            // Calculate duration if not provided
            const duration = data.duration_sec || 
                (data.data_points.length > 0 
                    ? data.data_points[data.data_points.length - 1].timestamp 
                    : 0);

            setPlayback({
                isPlaying: false,
                currentTime: 0,
                playbackSpeed: 1.0,
                duration,
                sessionData: data.data_points
            });

            toast.success('Session loaded', {
                description: `${data.data_points.length} data points, ${formatTime(duration)}`
            });
        } catch (err) {
            toast.error('Failed to load session', {
                description: err instanceof Error ? err.message : 'Unknown error'
            });
        } finally {
            setLoading(false);
        }
    }, [apiUrl, sessionId]);

    // Load session on mount or when sessionId changes
    useEffect(() => {
        loadSession();
    }, [loadSession]);

    // Get interpolated data at current time
    const getCurrentData = useCallback((): Record<string, number> | null => {
        if (playback.sessionData.length === 0) return null;

        const time = playback.currentTime;

        // Find surrounding data points
        let before: DataPoint | null = null;
        let after: DataPoint | null = null;

        for (let i = 0; i < playback.sessionData.length; i++) {
            const point = playback.sessionData[i];
            if (point.timestamp <= time) {
                before = point;
            } else {
                after = point;
                break;
            }
        }

        // Handle edge cases
        if (!before) return playback.sessionData[0].channels;
        if (!after) return playback.sessionData[playback.sessionData.length - 1].channels;

        // Linear interpolation
        const t = (time - before.timestamp) / (after.timestamp - before.timestamp);

        const interpolated: Record<string, number> = {};
        const allKeys = new Set([...Object.keys(before.channels), ...Object.keys(after.channels)]);

        for (const key of allKeys) {
            const v1 = before.channels[key] ?? 0;
            const v2 = after.channels[key] ?? 0;
            interpolated[key] = v1 + (v2 - v1) * t;
        }

        return interpolated;
    }, [playback.currentTime, playback.sessionData]);

    // Playback loop
    useEffect(() => {
        if (!playback.isPlaying || playback.sessionData.length === 0) return;

        const startTime = Date.now();
        const startPosition = playback.currentTime;

        const interval = setInterval(() => {
            const elapsed = (Date.now() - startTime) / 1000;
            const newTime = startPosition + (elapsed * playback.playbackSpeed);

            if (newTime >= playback.duration) {
                // End of session - stop playback
                setPlayback(prev => ({ 
                    ...prev, 
                    isPlaying: false, 
                    currentTime: prev.duration 
                }));
                toast.info('Playback complete');
                return;
            }

            setPlayback(prev => ({ ...prev, currentTime: newTime }));
        }, FRAME_INTERVAL_MS);

        return () => clearInterval(interval);
    }, [playback.isPlaying, playback.duration, playback.playbackSpeed, playback.sessionData.length]);

    // Update parent with interpolated data
    useEffect(() => {
        if (onDataUpdate) {
            const data = getCurrentData();
            if (data) {
                onDataUpdate(data);
            }
        }
    }, [getCurrentData, onDataUpdate]);

    // Control handlers
    const handlePlayPause = () => {
        setPlayback(prev => ({ ...prev, isPlaying: !prev.isPlaying }));
    };

    const handleReset = () => {
        setPlayback(prev => ({ ...prev, isPlaying: false, currentTime: 0 }));
    };

    const handleSpeedChange = (speed: string) => {
        setPlayback(prev => ({ ...prev, playbackSpeed: parseFloat(speed) }));
    };

    const handleSeek = (value: number[]) => {
        setPlayback(prev => ({ ...prev, currentTime: value[0] }));
    };

    const progress = playback.duration > 0 
        ? (playback.currentTime / playback.duration) * 100 
        : 0;

    return (
        <Card className="border-purple-500/30 bg-gradient-to-br from-purple-500/5 to-transparent">
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2">
                    <Play className="h-5 w-5 text-purple-500" />
                    Session Replay
                </CardTitle>
                <CardDescription>
                    Playback recorded dyno session data
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {loading ? (
                    <div className="text-center py-8 text-muted-foreground">
                        Loading session...
                    </div>
                ) : playback.sessionData.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                        No session data loaded
                    </div>
                ) : (
                    <>
                        {/* Progress bar */}
                        <div className="space-y-2">
                            <Slider
                                value={[playback.currentTime]}
                                max={playback.duration}
                                step={0.1}
                                onValueChange={handleSeek}
                                className="w-full"
                            />
                            <div className="flex justify-between text-xs text-muted-foreground">
                                <span>{formatTime(playback.currentTime)}</span>
                                <span>{progress.toFixed(1)}%</span>
                                <span>{formatTime(playback.duration)}</span>
                            </div>
                        </div>

                        {/* Controls */}
                        <div className="flex items-center gap-2">
                            <Button
                                onClick={handlePlayPause}
                                variant="default"
                                size="sm"
                            >
                                {playback.isPlaying ? (
                                    <>
                                        <Pause className="h-4 w-4 mr-1" />
                                        Pause
                                    </>
                                ) : (
                                    <>
                                        <Play className="h-4 w-4 mr-1" />
                                        Play
                                    </>
                                )}
                            </Button>

                            <Button
                                onClick={handleReset}
                                variant="outline"
                                size="sm"
                            >
                                <RotateCcw className="h-4 w-4 mr-1" />
                                Reset
                            </Button>

                            <div className="flex-1" />

                            <Select
                                value={playback.playbackSpeed.toString()}
                                onValueChange={handleSpeedChange}
                            >
                                <SelectTrigger className="w-24">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="0.5">0.5x</SelectItem>
                                    <SelectItem value="1">1x</SelectItem>
                                    <SelectItem value="2">2x</SelectItem>
                                    <SelectItem value="4">4x</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        {/* Stats */}
                        <div className="text-xs text-muted-foreground grid grid-cols-2 gap-2">
                            <div>Data Points: {playback.sessionData.length}</div>
                            <div>Speed: {playback.playbackSpeed}x</div>
                        </div>
                    </>
                )}
            </CardContent>
        </Card>
    );
}

export default SessionReplayPanel;
