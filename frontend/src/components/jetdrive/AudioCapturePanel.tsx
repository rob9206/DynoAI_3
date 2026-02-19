/**
 * AudioCapturePanel - Full-featured audio capture for dyno pulls
 * 
 * Features:
 * - Auto-records when dyno pull starts (RPM threshold detection)
 * - Real-time waveform and spectrum visualization
 * - Multi-band knock detection with confirmation logic
 * - Audible alarm when knock is detected
 * - Recording history with playback and download
 */

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Mic, MicOff, Play, Square, Download, Trash2, Volume2, VolumeX,
    AlertTriangle, Bell, BellOff
} from 'lucide-react';
import { toast } from '@/lib/toast';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Slider } from '../ui/slider';
import { Switch } from '../ui/switch';
import { Label } from '../ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';

import { AudioWaveform } from './AudioWaveform';
import { useAudioCapture, type RecordedAudio, type KnockEvent } from '../../hooks/useAudioCapture';

interface AudioCapturePanelProps {
    /** Whether dyno capture is active (for sync) */
    isDynoCapturing?: boolean;
    /** Current RPM for auto-record trigger */
    currentRpm?: number;
    /** RPM threshold to start auto-recording */
    rpmThreshold?: number;
    /** Callback when recording starts */
    onRecordingStart?: () => void;
    /** Callback when recording stops */
    onRecordingStop?: (recording: RecordedAudio | null) => void;
    /** Callback when knock is detected */
    onKnockDetected?: (event: KnockEvent) => void;
}

export function AudioCapturePanel({
    isDynoCapturing = false,
    currentRpm = 0,
    rpmThreshold = 2000,
    onRecordingStart,
    onRecordingStop,
    onKnockDetected,
}: AudioCapturePanelProps) {
    // Settings state
    const [knockSensitivity, setKnockSensitivity] = useState(0.7);
    const [showSpectrum, setShowSpectrum] = useState(true);
    const [autoRecord, setAutoRecord] = useState(true);
    const [alarmEnabled, setAlarmEnabledLocal] = useState(true);
    const [alarmVolume, setAlarmVolumeLocal] = useState(0.5);
    const [freqMin, setFreqMin] = useState(5000);
    const [freqMax, setFreqMax] = useState(15000);

    // Playback state
    const [playingUrl, setPlayingUrl] = useState<string | null>(null);
    const [audioElement, setAudioElement] = useState<HTMLAudioElement | null>(null);

    // Track if recording was auto-started (vs manually started)
    const [wasAutoStarted, setWasAutoStarted] = useState(false);

    // Safety timeout ref
    const safetyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const {
        state,
        analysis,
        recordings,
        requestPermission,
        startRecording,
        stopRecording,
        clearRecordings,
        downloadRecording,
        setAlarmEnabled,
        setAlarmVolume,
        testAlarm,
    } = useAudioCapture({
        enableAnalysis: true,
        enableKnockDetection: true,
        knockSensitivity,
        enableKnockAlarm: alarmEnabled,
        alarmVolume,
        knockFrequencyRange: [freqMin, freqMax],
    });

    // Sync alarm settings with hook
    useEffect(() => {
        setAlarmEnabled(alarmEnabled);
    }, [alarmEnabled, setAlarmEnabled]);

    useEffect(() => {
        setAlarmVolume(alarmVolume);
    }, [alarmVolume, setAlarmVolume]);

    const formatDuration = (ms: number) => {
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    };

    // Auto-record based on RPM threshold or dyno capture state
    useEffect(() => {
        if (!autoRecord || state.hasPermission !== true) return;

        const shouldRecord = isDynoCapturing || currentRpm > rpmThreshold;

        if (shouldRecord && !state.isRecording) {
            // Auto-start recording
            setWasAutoStarted(true);
            void startRecording();
            onRecordingStart?.();
            toast.success('Auto-recording started', {
                description: isDynoCapturing ? 'Dyno capture detected' : `RPM > ${rpmThreshold}`
            });

            // Set safety timeout to auto-stop after 5 minutes (only for auto-started recordings)
            safetyTimeoutRef.current = setTimeout(() => {
                void stopRecording().then(recording => {
                    onRecordingStop?.(recording);
                    setWasAutoStarted(false);
                    toast.warning('Recording auto-stopped', {
                        description: 'Maximum recording duration (5 min) reached',
                    });
                });
            }, 5 * 60 * 1000); // 5 minutes
        }

        // Cleanup timeout on unmount
        return () => {
            if (safetyTimeoutRef.current) {
                clearTimeout(safetyTimeoutRef.current);
            }
        };
    }, [isDynoCapturing, currentRpm, rpmThreshold, autoRecord, state.hasPermission, state.isRecording, startRecording, stopRecording, onRecordingStart, onRecordingStop]);

    // Auto-stop when pull ends (only for auto-started recordings)
    useEffect(() => {
        if (!wasAutoStarted || !state.isRecording) return;

        const shouldRecord = isDynoCapturing || currentRpm > rpmThreshold;
        const rpmBelowThreshold = currentRpm < rpmThreshold * 0.7; // 70% hysteresis

        if (!shouldRecord && !isDynoCapturing && rpmBelowThreshold) {
            // Clear safety timeout
            if (safetyTimeoutRef.current) {
                clearTimeout(safetyTimeoutRef.current);
                safetyTimeoutRef.current = null;
            }

            void stopRecording().then(recording => {
                onRecordingStop?.(recording);
                setWasAutoStarted(false);
                if (recording) {
                    toast.success('Auto-recording stopped', {
                        description: `${formatDuration(recording.duration)} • ${recording.knockEvents.length} knock events`,
                    });
                }
            });
        }
    }, [isDynoCapturing, currentRpm, rpmThreshold, wasAutoStarted, state.isRecording, stopRecording, onRecordingStop]);

    // Notify on knock detection
    useEffect(() => {
        if (analysis.knockDetected && analysis.knockEvents.length > 0) {
            const latestEvent = analysis.knockEvents[analysis.knockEvents.length - 1];
            onKnockDetected?.(latestEvent);
        }
    }, [analysis.knockDetected, analysis.knockEvents, onKnockDetected]);

    const handleToggleRecording = async () => {
        if (state.isRecording) {
            // Clear safety timeout when manually stopping
            if (safetyTimeoutRef.current) {
                clearTimeout(safetyTimeoutRef.current);
                safetyTimeoutRef.current = null;
            }
            setWasAutoStarted(false);

            const recording = await stopRecording();
            onRecordingStop?.(recording);
            if (recording) {
                toast.success('Recording saved', {
                    description: `${formatDuration(recording.duration)} • ${recording.knockEvents.length} knock events`,
                });
            }
        } else {
            // Mark as manually started (NOT auto-started)
            setWasAutoStarted(false);
            await startRecording();
            onRecordingStart?.();
            toast.success('Recording started (manual)');
        }
    };

    const handleRequestPermission = async () => {
        const granted = await requestPermission();
        if (granted) {
            toast.success('Microphone enabled', {
                description: 'Audio capture ready for knock detection',
            });
        } else {
            toast.error('Microphone access denied', {
                description: 'Please allow microphone access in browser settings',
            });
        }
    };

    const handlePlayRecording = (recording: RecordedAudio) => {
        // Stop current playback
        if (audioElement) {
            audioElement.pause();
            audioElement.currentTime = 0;
        }

        if (playingUrl === recording.url) {
            setPlayingUrl(null);
            setAudioElement(null);
            return;
        }

        const audio = new Audio(recording.url);
        audio.onended = () => {
            setPlayingUrl(null);
            setAudioElement(null);
        };
        void audio.play();
        setPlayingUrl(recording.url);
        setAudioElement(audio);
    };

    const handleTestAlarm = () => {
        testAlarm();
        toast.info('Alarm test', { description: 'Playing knock alarm sound' });
    };

    // Recent knock events
    const recentKnocks = analysis.knockEvents.slice(-10).reverse();

    return (
        <Card className="border-cyan-500/20 bg-gradient-to-br from-zinc-900/95 to-zinc-950/95">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className={`p-2.5 rounded-xl ${state.isRecording ? 'bg-red-500/20 border border-red-500/30' : 'bg-cyan-500/10 border border-cyan-500/20'}`}>
                            {state.isRecording ? (
                                <Mic className="h-5 w-5 text-red-400 animate-pulse" />
                            ) : (
                                <Mic className="h-5 w-5 text-cyan-400" />
                            )}
                        </div>
                        <div>
                            <CardTitle className="flex items-center gap-2 text-lg">
                                Audio Capture
                                {state.isRecording && (
                                    <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
                                        <span className="w-2 h-2 bg-red-500 rounded-full mr-1.5 animate-pulse" />
                                        REC {formatDuration(state.duration)}
                                        {wasAutoStarted && <span className="ml-1 text-[10px] opacity-70">(auto)</span>}
                                    </Badge>
                                )}
                            </CardTitle>
                            <CardDescription>
                                Engine audio recording with knock detection
                            </CardDescription>
                        </div>
                    </div>

                    {/* Controls */}
                    <div className="flex items-center gap-2">
                        {/* Emergency stop button when recording */}
                        {state.isRecording && (
                            <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => void handleToggleRecording()}
                                className="gap-1.5"
                            >
                                <Square className="h-3.5 w-3.5" />
                                Stop
                            </Button>
                        )}

                        {/* Alarm toggle */}
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setAlarmEnabledLocal(!alarmEnabled)}
                            className={alarmEnabled ? 'text-orange-400' : 'text-zinc-500'}
                            title={alarmEnabled ? 'Alarm enabled' : 'Alarm disabled'}
                        >
                            {alarmEnabled ? <Bell className="h-4 w-4" /> : <BellOff className="h-4 w-4" />}
                        </Button>
                    </div>
                </div>
            </CardHeader>

            <CardContent className="space-y-4">
                {/* Permission Request */}
                {state.hasPermission === null && (
                    <div className="text-center py-8 px-4 rounded-xl bg-zinc-800/30 border border-zinc-700/50">
                        <Mic className="h-12 w-12 mx-auto mb-4 text-cyan-400/50" />
                        <h3 className="text-lg font-medium mb-2">Enable Microphone</h3>
                        <p className="text-sm text-zinc-400 mb-4 max-w-sm mx-auto">
                            Allow microphone access to record engine audio and detect knock during dyno pulls.
                        </p>
                        <Button onClick={() => void handleRequestPermission()} className="bg-cyan-600 hover:bg-cyan-500">
                            <Mic className="h-4 w-4 mr-2" />
                            Enable Microphone
                        </Button>
                    </div>
                )}

                {state.hasPermission === false && (
                    <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30">
                        <div className="flex items-center gap-2 mb-2">
                            <MicOff className="h-5 w-5 text-red-400" />
                            <span className="font-medium text-red-400">Microphone Blocked</span>
                        </div>
                        <p className="text-sm text-red-300/80">
                            {state.error ?? 'Please enable microphone access in your browser settings and refresh.'}
                        </p>
                    </div>
                )}

                {state.hasPermission === true && (
                    <Tabs defaultValue="live" className="space-y-4">
                        <TabsList className="grid grid-cols-3 w-full">
                            <TabsTrigger value="live">Live</TabsTrigger>
                            <TabsTrigger value="recordings">
                                Recordings {recordings.length > 0 && `(${recordings.length})`}
                            </TabsTrigger>
                            <TabsTrigger value="settings">Settings</TabsTrigger>
                        </TabsList>

                        {/* Live Tab */}
                        <TabsContent value="live" className="space-y-4">
                            {/* Waveform Visualization */}
                            <AudioWaveform
                                waveform={analysis.waveform}
                                frequencies={analysis.frequencies}
                                volume={analysis.volume}
                                knockDetected={analysis.knockDetected}
                                height={100}
                                showSpectrum={showSpectrum}
                            />

                            {/* Controls */}
                            <div className="flex items-center gap-3">
                                <Button
                                    variant={state.isRecording ? 'destructive' : 'default'}
                                    onClick={() => void handleToggleRecording()}
                                    className={!state.isRecording ? 'bg-cyan-600 hover:bg-cyan-500' : ''}
                                >
                                    {state.isRecording ? (
                                        <><Square className="h-4 w-4 mr-2" /> Stop Recording</>
                                    ) : (
                                        <><Mic className="h-4 w-4 mr-2" /> Start Recording</>
                                    )}
                                </Button>

                                {state.isRecording && (
                                    <div className="flex items-center gap-2 text-sm">
                                        <span className="font-mono text-lg text-zinc-300">{formatDuration(state.duration)}</span>
                                        <div className="w-20 h-2 rounded-full bg-zinc-800 overflow-hidden">
                                            <motion.div
                                                className="h-full rounded-full"
                                                style={{
                                                    backgroundColor: analysis.volume > 0.8 ? '#ef4444' : analysis.volume > 0.5 ? '#f59e0b' : '#22c55e',
                                                }}
                                                animate={{ width: `${Math.min(analysis.volume * 300, 100)}%` }}
                                                transition={{ duration: 0.05 }}
                                            />
                                        </div>
                                    </div>
                                )}

                                <div className="flex-1" />

                                {autoRecord && (
                                    <Badge variant="outline" className="text-xs border-cyan-500/30 text-cyan-400">
                                        Auto-record @ {rpmThreshold} RPM
                                    </Badge>
                                )}
                            </div>

                            {/* Knock Alert */}
                            <AnimatePresence>
                                {analysis.knockDetected && (
                                    <motion.div
                                        initial={{ opacity: 0, scale: 0.95 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        exit={{ opacity: 0, scale: 0.95 }}
                                        className="p-4 rounded-xl bg-gradient-to-r from-orange-500/20 to-red-500/20 border border-orange-500/40"
                                    >
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-3">
                                                <motion.div
                                                    animate={{ scale: [1, 1.2, 1] }}
                                                    transition={{ repeat: Infinity, duration: 0.5 }}
                                                >
                                                    <AlertTriangle className="h-6 w-6 text-orange-400" />
                                                </motion.div>
                                                <div>
                                                    <div className="font-bold text-orange-300">KNOCK DETECTED!</div>
                                                    <div className="text-sm text-orange-400/80">
                                                        {analysis.peakFrequency.toFixed(0)} Hz • Check timing/fuel
                                                    </div>
                                                </div>
                                            </div>
                                            <Badge className="bg-orange-500/30 text-orange-200 border-orange-500/50 text-lg px-3">
                                                {analysis.knockEvents.length}
                                            </Badge>
                                        </div>
                                    </motion.div>
                                )}
                            </AnimatePresence>

                            {/* Knock Event History */}
                            {recentKnocks.length > 0 && !analysis.knockDetected && (
                                <div className="p-3 rounded-lg bg-zinc-800/50 border border-zinc-700/50">
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="text-sm font-medium text-zinc-400">
                                            Recent Knock Events ({analysis.knockEvents.length})
                                        </span>
                                    </div>
                                    <div className="space-y-1">
                                        {recentKnocks.slice(0, 5).map((event, idx) => (
                                            <div
                                                key={`${event.timestamp}-${idx}`}
                                                className="flex items-center justify-between text-xs font-mono"
                                            >
                                                <span className="text-zinc-500">{formatDuration(event.timestamp)}</span>
                                                <span className="text-orange-400">{event.frequency.toFixed(0)} Hz</span>
                                                <div className="w-16 h-1.5 rounded-full bg-zinc-700 overflow-hidden">
                                                    <div
                                                        className="h-full rounded-full bg-orange-500"
                                                        style={{ width: `${Math.min(event.intensity * 20, 100)}%` }}
                                                    />
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </TabsContent>

                        {/* Recordings Tab */}
                        <TabsContent value="recordings" className="space-y-4">
                            {recordings.length === 0 ? (
                                <div className="text-center py-8 text-zinc-500">
                                    <Mic className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                    <p className="text-sm">No recordings yet</p>
                                    <p className="text-xs mt-1">Start a recording or enable auto-record</p>
                                </div>
                            ) : (
                                <>
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-400">{recordings.length} recording(s)</span>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={clearRecordings}
                                            className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                                        >
                                            <Trash2 className="h-4 w-4 mr-1" />
                                            Clear All
                                        </Button>
                                    </div>

                                    <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                                        {recordings.slice().reverse().map((recording) => (
                                            <motion.div
                                                key={recording.startTime}
                                                initial={{ opacity: 0, y: -10 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                className="flex items-center justify-between p-3 rounded-lg bg-zinc-800/50 border border-zinc-700/50 hover:border-zinc-600/50 transition-colors"
                                            >
                                                <div className="flex items-center gap-3">
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-8 w-8"
                                                        onClick={() => handlePlayRecording(recording)}
                                                    >
                                                        {playingUrl === recording.url ? (
                                                            <Square className="h-4 w-4 text-cyan-400" />
                                                        ) : (
                                                            <Play className="h-4 w-4" />
                                                        )}
                                                    </Button>

                                                    <div>
                                                        <div className="font-mono text-sm">
                                                            {new Date(recording.startTime).toLocaleTimeString()}
                                                        </div>
                                                        <div className="text-xs text-zinc-500 flex items-center gap-2">
                                                            <span>{formatDuration(recording.duration)}</span>
                                                            {recording.knockEvents.length > 0 && (
                                                                <Badge variant="secondary" className="text-[10px] px-1.5 py-0 bg-orange-500/20 text-orange-400 border-orange-500/30">
                                                                    <AlertTriangle className="h-2.5 w-2.5 mr-0.5" />
                                                                    {recording.knockEvents.length} knocks
                                                                </Badge>
                                                            )}
                                                        </div>
                                                    </div>
                                                </div>

                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-8 w-8"
                                                    onClick={() => downloadRecording(recording)}
                                                    title="Download recording"
                                                >
                                                    <Download className="h-4 w-4" />
                                                </Button>
                                            </motion.div>
                                        ))}
                                    </div>
                                </>
                            )}
                        </TabsContent>

                        {/* Settings Tab */}
                        <TabsContent value="settings" className="space-y-4">
                            {/* Auto-Record */}
                            <div className="flex items-center justify-between p-3 rounded-lg bg-zinc-800/30">
                                <div>
                                    <Label className="text-sm">Auto-Record on Pull</Label>
                                    <p className="text-xs text-zinc-500">Start recording when RPM exceeds threshold</p>
                                </div>
                                <Switch checked={autoRecord} onCheckedChange={setAutoRecord} />
                            </div>

                            {/* Knock Sensitivity */}
                            <div className="p-3 rounded-lg bg-zinc-800/30 space-y-3">
                                <div className="flex items-center justify-between">
                                    <Label className="text-sm">Knock Sensitivity</Label>
                                    <span className="text-sm font-mono text-cyan-400">{(knockSensitivity * 100).toFixed(0)}%</span>
                                </div>
                                <Slider
                                    value={[knockSensitivity]}
                                    onValueChange={([v]) => setKnockSensitivity(v)}
                                    min={0.3}
                                    max={1}
                                    step={0.05}
                                />
                                <p className="text-xs text-zinc-500">Higher = more sensitive (may increase false positives)</p>
                            </div>

                            {/* Frequency Range */}
                            <div className="p-3 rounded-lg bg-zinc-800/30 space-y-3">
                                <Label className="text-sm">Knock Frequency Range</Label>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <Label className="text-xs text-zinc-500">Min (Hz)</Label>
                                        <div className="flex items-center gap-2 mt-1">
                                            <Slider
                                                value={[freqMin]}
                                                onValueChange={([v]) => setFreqMin(v)}
                                                min={3000}
                                                max={10000}
                                                step={500}
                                                className="flex-1"
                                            />
                                            <span className="text-xs font-mono w-12 text-right">{freqMin}</span>
                                        </div>
                                    </div>
                                    <div>
                                        <Label className="text-xs text-zinc-500">Max (Hz)</Label>
                                        <div className="flex items-center gap-2 mt-1">
                                            <Slider
                                                value={[freqMax]}
                                                onValueChange={([v]) => setFreqMax(v)}
                                                min={8000}
                                                max={20000}
                                                step={500}
                                                className="flex-1"
                                            />
                                            <span className="text-xs font-mono w-12 text-right">{freqMax}</span>
                                        </div>
                                    </div>
                                </div>
                                <p className="text-xs text-zinc-500">Engine knock typically occurs between 5-15 kHz</p>
                            </div>

                            {/* Alarm Settings */}
                            <div className="p-3 rounded-lg bg-zinc-800/30 space-y-3">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <Label className="text-sm">Knock Alarm</Label>
                                        <p className="text-xs text-zinc-500">Play audible alert when knock detected</p>
                                    </div>
                                    <Switch checked={alarmEnabled} onCheckedChange={setAlarmEnabledLocal} />
                                </div>

                                {alarmEnabled && (
                                    <>
                                        <div className="flex items-center gap-3">
                                            <VolumeX className="h-4 w-4 text-zinc-500" />
                                            <Slider
                                                value={[alarmVolume]}
                                                onValueChange={([v]) => setAlarmVolumeLocal(v)}
                                                min={0.1}
                                                max={1}
                                                step={0.1}
                                                className="flex-1"
                                            />
                                            <Volume2 className="h-4 w-4 text-zinc-500" />
                                            <span className="text-xs font-mono w-8">{(alarmVolume * 100).toFixed(0)}%</span>
                                        </div>
                                        <Button variant="outline" size="sm" onClick={handleTestAlarm} className="w-full">
                                            <Bell className="h-4 w-4 mr-2" />
                                            Test Alarm
                                        </Button>
                                    </>
                                )}
                            </div>

                            {/* Spectrum Display */}
                            <div className="flex items-center justify-between p-3 rounded-lg bg-zinc-800/30">
                                <div>
                                    <Label className="text-sm">Show Frequency Spectrum</Label>
                                    <p className="text-xs text-zinc-500">Display FFT analysis with knock range</p>
                                </div>
                                <Switch checked={showSpectrum} onCheckedChange={setShowSpectrum} />
                            </div>
                        </TabsContent>
                    </Tabs>
                )}
            </CardContent>
        </Card>
    );
}

export default AudioCapturePanel;
