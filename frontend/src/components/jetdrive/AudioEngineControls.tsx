/**
 * AudioEngineControls - UI component for audio engine playback
 * 
 * Provides controls for:
 * - Enable/disable engine sound
 * - Volume control
 * - Mute toggle
 * - Visual feedback (waveform, RPM indicator)
 */

import { useEffect } from 'react';
import { Volume2, VolumeX, Power, Activity } from 'lucide-react';
import { Button } from '../ui/button';
import { Slider } from '../ui/slider';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { useAudioEngine } from '../../hooks/useAudioEngine';

interface AudioEngineControlsProps {
    /** Current RPM from dyno */
    rpm: number;
    /** Current load/throttle (0-1) */
    load?: number;
    /** Auto-start when RPM > threshold */
    autoStart?: boolean;
    /** RPM threshold for auto-start */
    autoStartRpm?: number;
    /** Compact mode for smaller displays */
    compact?: boolean;
    /** Number of cylinders */
    cylinders?: number;
    /** Fun mode - exaggerated sounds */
    funMode?: boolean;
}

export function AudioEngineControls({
    rpm,
    load = 0,
    autoStart = false,
    autoStartRpm = 1000,
    compact = false,
    cylinders = 2,
    funMode = true,
}: AudioEngineControlsProps) {
    const {
        state,
        startEngine,
        stopEngine,
        setRpm,
        setLoad,
        setVolume,
        toggleMute,
    } = useAudioEngine({ cylinders, funMode });

    // Update RPM and load when props change
    useEffect(() => {
        if (state.isPlaying) {
            setRpm(rpm);
            setLoad(load);
        }
    }, [rpm, load, state.isPlaying, setRpm, setLoad]);

    // Auto-start based on RPM (but don't auto-stop - let user control)
    useEffect(() => {
        if (!autoStart) return;

        // Only auto-start when RPM goes above threshold
        // Don't auto-stop - keep playing even at idle
        if (rpm > autoStartRpm && !state.isPlaying) {
            void startEngine();
        }
    }, [rpm, autoStart, autoStartRpm, state.isPlaying, startEngine]);

    const handleToggleEngine = () => {
        if (state.isPlaying) {
            stopEngine();
        } else {
            startEngine();
        }
    };

    if (compact) {
        return (
            <div className="flex items-center gap-2">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleToggleEngine}
                    className={state.isPlaying ? 'text-green-400' : 'text-zinc-500'}
                >
                    <Power className={`w-4 h-4 ${state.isPlaying ? 'animate-pulse' : ''}`} />
                </Button>

                <Button
                    variant="ghost"
                    size="icon"
                    onClick={toggleMute}
                    disabled={!state.isPlaying}
                    className={state.isMuted ? 'text-zinc-500' : 'text-cyan-400'}
                >
                    {state.isMuted ? (
                        <VolumeX className="w-4 h-4" />
                    ) : (
                        <Volume2 className="w-4 h-4" />
                    )}
                </Button>

                <div className="w-24">
                    <Slider
                        value={[state.volume * 100]}
                        onValueChange={([v]) => setVolume(v / 100)}
                        disabled={!state.isPlaying}
                        min={0}
                        max={100}
                        step={1}
                        className="cursor-pointer"
                    />
                </div>

                {state.isPlaying && (
                    <Badge
                        variant="outline"
                        className="bg-green-500/10 border-green-500/30 text-green-400 text-xs"
                    >
                        <Activity className="w-3 h-3 mr-1 animate-pulse" />
                        {rpm.toFixed(0)} RPM
                    </Badge>
                )}
            </div>
        );
    }

    return (
        <Card className="bg-zinc-900/50 border-zinc-800">
            <CardContent className="p-4">
                <div className="space-y-4">
                    {/* Header */}
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <div
                                className={`w-8 h-8 rounded-lg flex items-center justify-center ${state.isPlaying
                                    ? 'bg-green-500/10 border border-green-500/20'
                                    : 'bg-zinc-800/50 border border-zinc-700'
                                    }`}
                            >
                                <Volume2
                                    className={`w-4 h-4 ${state.isPlaying ? 'text-green-400' : 'text-zinc-500'
                                        }`}
                                />
                            </div>
                            <div>
                                <h3 className="text-sm font-medium text-zinc-200">Engine Audio</h3>
                                <p className="text-xs text-zinc-500">
                                    {state.isPlaying ? 'Playing' : 'Stopped'}
                                    {state.isPlaying && ` • ${rpm.toFixed(0)} RPM`}
                                </p>
                            </div>
                        </div>

                        <Button
                            onClick={handleToggleEngine}
                            size="sm"
                            variant={state.isPlaying ? 'destructive' : 'default'}
                            className={
                                !state.isPlaying
                                    ? 'bg-green-600 hover:bg-green-500'
                                    : ''
                            }
                        >
                            <Power className="w-3.5 h-3.5 mr-1.5" />
                            {state.isPlaying ? 'Stop' : 'Start'}
                        </Button>
                    </div>

                    {/* Volume Controls */}
                    {state.isPlaying && (
                        <div className="space-y-3">
                            {/* Volume Slider */}
                            <div>
                                <div className="flex items-center justify-between mb-2">
                                    <label className="text-xs text-zinc-400">Volume</label>
                                    <span className="text-xs font-mono text-zinc-500">
                                        {Math.round(state.volume * 100)}%
                                    </span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={toggleMute}
                                        className={`h-8 w-8 ${state.isMuted ? 'text-zinc-500' : 'text-cyan-400'
                                            }`}
                                    >
                                        {state.isMuted ? (
                                            <VolumeX className="w-4 h-4" />
                                        ) : (
                                            <Volume2 className="w-4 h-4" />
                                        )}
                                    </Button>
                                    <Slider
                                        value={[state.volume * 100]}
                                        onValueChange={([v]) => setVolume(v / 100)}
                                        min={0}
                                        max={100}
                                        step={1}
                                        className="flex-1"
                                    />
                                </div>
                            </div>

                            {/* Visual Feedback */}
                            <div className="rounded-lg bg-zinc-800/50 p-3 border border-zinc-700/50">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-xs text-zinc-400">Engine State</span>
                                    <Badge
                                        variant="outline"
                                        className="bg-green-500/10 border-green-500/30 text-green-400 text-xs"
                                    >
                                        <Activity className="w-3 h-3 mr-1" />
                                        Active
                                    </Badge>
                                </div>

                                {/* RPM Bar */}
                                <div className="space-y-1">
                                    <div className="flex items-center justify-between text-xs">
                                        <span className="text-zinc-500">RPM</span>
                                        <span className="font-mono text-cyan-400">
                                            {rpm.toFixed(0)}
                                        </span>
                                    </div>
                                    <div className="h-2 bg-zinc-900 rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-gradient-to-r from-cyan-500 to-cyan-400 transition-all duration-300"
                                            style={{
                                                width: `${Math.min(100, (rpm / 8000) * 100)}%`,
                                            }}
                                        />
                                    </div>
                                </div>

                                {/* Load Bar */}
                                <div className="space-y-1 mt-2">
                                    <div className="flex items-center justify-between text-xs">
                                        <span className="text-zinc-500">Load</span>
                                        <span className="font-mono text-orange-400">
                                            {Math.round(load * 100)}%
                                        </span>
                                    </div>
                                    <div className="h-2 bg-zinc-900 rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-gradient-to-r from-orange-500 to-red-500 transition-all duration-300"
                                            style={{ width: `${load * 100}%` }}
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Error Display */}
                    {state.error && (
                        <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-2">
                            {state.error}
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}

export default AudioEngineControls;

