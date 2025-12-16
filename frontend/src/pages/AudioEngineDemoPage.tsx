/**
 * Audio Engine Demo Page
 * 
 * Interactive demo for testing and showcasing the audio engine system.
 * Allows manual control of RPM and load to hear how the engine sounds.
 */

import { useState } from 'react';
import { Volume2, Play, Square, Zap, AlertTriangle, CheckCircle2, Bell } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Slider } from '../components/ui/slider';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { useAudioEngine } from '../hooks/useAudioEngine';

export default function AudioEngineDemoPage() {
    const [manualRpm, setManualRpm] = useState(1000);
    const [manualLoad, setManualLoad] = useState(0.5);
    const [cylinders, setCylinders] = useState(2);
    const [funMode, setFunMode] = useState(true);

    const {
        state,
        startEngine,
        stopEngine,
        setRpm,
        setLoad,
        setVolume,
        toggleMute,
        playStartup,
        playShutdown,
        playWarning,
        playSuccess,
        playBeep,
    } = useAudioEngine({ cylinders, enableCrackle: true, funMode });

    // Update audio engine when sliders change
    const handleRpmChange = (value: number[]) => {
        const rpm = value[0];
        setManualRpm(rpm);
        if (state.isPlaying) {
            setRpm(rpm);
        }
    };

    const handleLoadChange = (value: number[]) => {
        const load = value[0] / 100;
        setManualLoad(load);
        if (state.isPlaying) {
            setLoad(load);
        }
    };

    const handleVolumeChange = (value: number[]) => {
        setVolume(value[0] / 100);
    };

    const handleToggleEngine = async () => {
        if (state.isPlaying) {
            stopEngine();
        } else {
            await startEngine();
            setRpm(manualRpm);
            setLoad(manualLoad);
        }
    };

    // Preset scenarios
    const runIdleScenario = () => {
        setManualRpm(1000);
        setManualLoad(0.1);
        setRpm(1000);
        setLoad(0.1);
    };

    const runCruiseScenario = () => {
        setManualRpm(3000);
        setManualLoad(0.3);
        setRpm(3000);
        setLoad(0.3);
    };

    const runWotScenario = () => {
        setManualRpm(6000);
        setManualLoad(1.0);
        setRpm(6000);
        setLoad(1.0);
    };

    const runDecelScenario = () => {
        setManualRpm(5000);
        setManualLoad(0.05);
        setRpm(5000);
        setLoad(0.05);
    };

    return (
        <div className="min-h-screen bg-gradient-to-b from-zinc-950 via-zinc-900/95 to-zinc-950 p-6">
            <div className="max-w-4xl mx-auto space-y-6">

                {/* Header */}
                <div className="text-center space-y-2">
                    <h1 className="text-3xl font-bold text-white flex items-center justify-center gap-3">
                        <Volume2 className="w-8 h-8 text-cyan-400" />
                        Audio Engine Demo
                    </h1>
                    <p className="text-zinc-400">
                        Interactive testing for the DynoAI audio synthesis system
                    </p>
                </div>

                {/* Main Controls */}
                <Card className="bg-zinc-900/50 border-zinc-800">
                    <CardHeader>
                        <CardTitle className="flex items-center justify-between">
                            <span>Engine Controls</span>
                            <Badge
                                variant="outline"
                                className={
                                    state.isPlaying
                                        ? 'bg-green-500/10 border-green-500/30 text-green-400'
                                        : 'bg-zinc-800 border-zinc-700 text-zinc-500'
                                }
                            >
                                {state.isPlaying ? 'Playing' : 'Stopped'}
                            </Badge>
                        </CardTitle>
                        <CardDescription>
                            Adjust RPM and load to hear how the engine sounds
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">

                        {/* Start/Stop Button */}
                        <div className="flex justify-center">
                            <Button
                                onClick={() => void handleToggleEngine()}
                                size="lg"
                                className={
                                    state.isPlaying
                                        ? 'bg-red-600 hover:bg-red-500'
                                        : 'bg-green-600 hover:bg-green-500'
                                }
                            >
                                {state.isPlaying ? (
                                    <>
                                        <Square className="w-5 h-5 mr-2" />
                                        Stop Engine
                                    </>
                                ) : (
                                    <>
                                        <Play className="w-5 h-5 mr-2" />
                                        Start Engine
                                    </>
                                )}
                            </Button>
                        </div>

                        {/* RPM Slider */}
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <Label>RPM</Label>
                                <span className="text-2xl font-bold font-mono text-cyan-400">
                                    {manualRpm}
                                </span>
                            </div>
                            <Slider
                                value={[manualRpm]}
                                onValueChange={handleRpmChange}
                                min={500}
                                max={8000}
                                step={100}
                                disabled={!state.isPlaying}
                            />
                            <div className="flex justify-between text-xs text-zinc-500 mt-1">
                                <span>500</span>
                                <span>8000</span>
                            </div>
                        </div>

                        {/* Load Slider */}
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <Label>Load / Throttle</Label>
                                <span className="text-2xl font-bold font-mono text-orange-400">
                                    {Math.round(manualLoad * 100)}%
                                </span>
                            </div>
                            <Slider
                                value={[manualLoad * 100]}
                                onValueChange={handleLoadChange}
                                min={0}
                                max={100}
                                step={1}
                                disabled={!state.isPlaying}
                            />
                            <div className="flex justify-between text-xs text-zinc-500 mt-1">
                                <span>Idle</span>
                                <span>WOT</span>
                            </div>
                        </div>

                        {/* Volume Slider */}
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <Label>Volume</Label>
                                <div className="flex items-center gap-2">
                                    <span className="text-lg font-mono text-zinc-400">
                                        {Math.round(state.volume * 100)}%
                                    </span>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={toggleMute}
                                        className={state.isMuted ? 'text-zinc-500' : 'text-cyan-400'}
                                    >
                                        {state.isMuted ? 'Unmute' : 'Mute'}
                                    </Button>
                                </div>
                            </div>
                            <Slider
                                value={[state.volume * 100]}
                                onValueChange={handleVolumeChange}
                                min={0}
                                max={100}
                                step={1}
                            />
                        </div>

                        {/* Cylinder Configuration */}
                        <div>
                            <Label className="mb-2 block">Engine Configuration</Label>
                            <div className="flex gap-2">
                                {[1, 2, 4, 6, 8].map((cyl) => (
                                    <Button
                                        key={cyl}
                                        variant={cylinders === cyl ? 'default' : 'outline'}
                                        size="sm"
                                        onClick={() => setCylinders(cyl)}
                                        disabled={state.isPlaying}
                                    >
                                        {cyl} cyl
                                    </Button>
                                ))}
                            </div>
                            <p className="text-xs text-zinc-500 mt-1">
                                Stop engine to change cylinder count
                            </p>
                        </div>

                        {/* Fun Mode Toggle */}
                        <div className="p-4 rounded-lg bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/30">
                            <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2">
                                    <span className="text-2xl">🎉</span>
                                    <Label className="text-purple-300 font-bold">FUN MODE</Label>
                                </div>
                                <Button
                                    variant={funMode ? 'default' : 'outline'}
                                    size="sm"
                                    onClick={() => setFunMode(!funMode)}
                                    disabled={state.isPlaying}
                                    className={funMode ? 'bg-gradient-to-r from-purple-600 to-pink-600' : ''}
                                >
                                    {funMode ? '🔥 ON' : 'OFF'}
                                </Button>
                            </div>
                            <p className="text-xs text-purple-300/80">
                                {funMode
                                    ? '🚀 EXAGGERATED SOUNDS! Louder, crazier, more harmonics!'
                                    : 'Realistic engine sounds'}
                            </p>
                        </div>

                    </CardContent>
                </Card>

                {/* Preset Scenarios */}
                <Card className="bg-zinc-900/50 border-zinc-800">
                    <CardHeader>
                        <CardTitle>Preset Scenarios</CardTitle>
                        <CardDescription>
                            Quick presets to test different engine states
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            <Button
                                variant="outline"
                                onClick={runIdleScenario}
                                disabled={!state.isPlaying}
                                className="flex-col h-auto py-4"
                            >
                                <div className="text-2xl mb-1">🔵</div>
                                <div className="font-semibold">Idle</div>
                                <div className="text-xs text-zinc-500">1000 RPM • 10%</div>
                            </Button>

                            <Button
                                variant="outline"
                                onClick={runCruiseScenario}
                                disabled={!state.isPlaying}
                                className="flex-col h-auto py-4"
                            >
                                <div className="text-2xl mb-1">🟢</div>
                                <div className="font-semibold">Cruise</div>
                                <div className="text-xs text-zinc-500">3000 RPM • 30%</div>
                            </Button>

                            <Button
                                variant="outline"
                                onClick={runWotScenario}
                                disabled={!state.isPlaying}
                                className="flex-col h-auto py-4"
                            >
                                <div className="text-2xl mb-1">🔴</div>
                                <div className="font-semibold">WOT</div>
                                <div className="text-xs text-zinc-500">6000 RPM • 100%</div>
                            </Button>

                            <Button
                                variant="outline"
                                onClick={runDecelScenario}
                                disabled={!state.isPlaying}
                                className="flex-col h-auto py-4"
                            >
                                <div className="text-2xl mb-1">💥</div>
                                <div className="font-semibold">Decel</div>
                                <div className="text-xs text-zinc-500">5000 RPM • 5%</div>
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* Sound Effects */}
                <Card className="bg-zinc-900/50 border-zinc-800">
                    <CardHeader>
                        <CardTitle>Sound Effects</CardTitle>
                        <CardDescription>
                            Test individual sound effects and tones
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                            <Button
                                variant="outline"
                                onClick={playStartup}
                                className="flex-col h-auto py-3"
                            >
                                <Zap className="w-5 h-5 mb-1 text-green-400" />
                                <span className="text-xs">Startup</span>
                            </Button>

                            <Button
                                variant="outline"
                                onClick={playShutdown}
                                className="flex-col h-auto py-3"
                            >
                                <Square className="w-5 h-5 mb-1 text-zinc-400" />
                                <span className="text-xs">Shutdown</span>
                            </Button>

                            <Button
                                variant="outline"
                                onClick={playWarning}
                                className="flex-col h-auto py-3"
                            >
                                <AlertTriangle className="w-5 h-5 mb-1 text-orange-400" />
                                <span className="text-xs">Warning</span>
                            </Button>

                            <Button
                                variant="outline"
                                onClick={playSuccess}
                                className="flex-col h-auto py-3"
                            >
                                <CheckCircle2 className="w-5 h-5 mb-1 text-green-400" />
                                <span className="text-xs">Success</span>
                            </Button>

                            <Button
                                variant="outline"
                                onClick={() => playBeep(440, 0.2)}
                                className="flex-col h-auto py-3"
                            >
                                <Bell className="w-5 h-5 mb-1 text-cyan-400" />
                                <span className="text-xs">Beep</span>
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* Info */}
                <Card className="bg-zinc-900/30 border-zinc-800/50">
                    <CardContent className="pt-6">
                        <div className="space-y-3 text-sm text-zinc-400">
                            <p>
                                <strong className="text-zinc-300">How it works:</strong> The audio engine
                                synthesizes realistic engine sounds in real-time using the Web Audio API.
                                It generates a fundamental frequency based on RPM and cylinder count, plus
                                harmonics for character.
                            </p>
                            <p>
                                <strong className="text-zinc-300">Features:</strong> Load-based volume
                                modulation, exhaust noise layer, deceleration crackle (high RPM + low load),
                                and smooth frequency transitions.
                            </p>
                            <p>
                                <strong className="text-zinc-300">Try this:</strong> Start the engine at
                                idle, then slowly increase RPM while adjusting load to hear how the sound
                                changes. Try the "Decel" preset to hear exhaust pops!
                            </p>
                        </div>
                    </CardContent>
                </Card>

                {/* Error Display */}
                {state.error && (
                    <Card className="bg-red-500/10 border-red-500/30">
                        <CardContent className="pt-6">
                            <div className="flex items-start gap-3">
                                <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                                <div>
                                    <div className="font-semibold text-red-400 mb-1">Audio Error</div>
                                    <div className="text-sm text-red-300">{state.error}</div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                )}

            </div>
        </div>
    );
}

