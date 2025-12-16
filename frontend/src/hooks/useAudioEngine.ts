/**
 * useAudioEngine - React hook for synthesizing and playing engine sounds
 * 
 * Features:
 * - Real-time engine sound synthesis based on RPM
 * - Exhaust note simulation with harmonics
 * - Load-based sound modulation (WOT vs idle)
 * - Sound effects for events (startup, shutdown, warnings)
 * - Volume and mix controls
 */

import { useState, useCallback, useRef, useEffect } from 'react';

// Audio configuration
const SAMPLE_RATE = 44100;
const BASE_FREQUENCY = 30; // Hz - minimum frequency floor
const MIN_RPM_FREQUENCY = 40; // Hz - frequency at idle (~800 RPM)

export interface AudioEngineState {
    isPlaying: boolean;
    isMuted: boolean;
    volume: number;
    rpm: number;
    load: number; // 0-1, affects exhaust note intensity
    error: string | null;
}

export interface AudioEngineOptions {
    /** Master volume (0-1) - default: 0.5 */
    volume?: number;
    /** Number of cylinders - default: 2 (V-twin) */
    cylinders?: number;
    /** Enable exhaust crackle on decel - default: true */
    enableCrackle?: boolean;
    /** Enable turbo/supercharger whine - default: false */
    enableBoost?: boolean;
    /** Fun mode - exaggerated, ridiculous sounds - default: false */
    funMode?: boolean;
}

export interface UseAudioEngineReturn {
    // State
    state: AudioEngineState;

    // Actions
    startEngine: () => Promise<void>;
    stopEngine: () => void;
    setRpm: (rpm: number) => void;
    setLoad: (load: number) => void; // 0-1
    setVolume: (volume: number) => void;
    toggleMute: () => void;

    // Sound effects
    playStartup: () => void;
    playShutdown: () => void;
    playWarning: () => void;
    playSuccess: () => void;
    playBeep: (frequency?: number, duration?: number) => void;
}

const DEFAULT_OPTIONS: Required<AudioEngineOptions> = {
    volume: 0.5,
    cylinders: 2,
    enableCrackle: true,
    enableBoost: false,
    funMode: true, // Default to FUN MODE!
};

export function useAudioEngine(options: AudioEngineOptions = {}): UseAudioEngineReturn {
    const opts = { ...DEFAULT_OPTIONS, ...options };

    // State
    const [state, setState] = useState<AudioEngineState>({
        isPlaying: false,
        isMuted: false,
        volume: opts.volume,
        rpm: 0,
        load: 0,
        error: null,
    });

    // Audio context and nodes
    const audioContextRef = useRef<AudioContext | null>(null);
    const masterGainRef = useRef<GainNode | null>(null);
    const engineOscillatorsRef = useRef<OscillatorNode[]>([]);
    const engineGainsRef = useRef<GainNode[]>([]);
    const exhaustNoiseRef = useRef<AudioBufferSourceNode | null>(null);
    const exhaustGainRef = useRef<GainNode | null>(null);
    const crackleSourceRef = useRef<AudioBufferSourceNode | null>(null);
    const crackleGainRef = useRef<GainNode | null>(null);

    // Animation frame for smooth RPM transitions
    const animationFrameRef = useRef<number | null>(null);
    const targetRpmRef = useRef(0);
    const currentRpmRef = useRef(0);
    const targetLoadRef = useRef(0);
    const currentLoadRef = useRef(0);
    const isPlayingRef = useRef(false); // Use ref to avoid stale closure in animation loop

    // Initialize audio context
    const initAudioContext = useCallback(() => {
        if (audioContextRef.current) return;

        try {
            audioContextRef.current = new AudioContext({ sampleRate: SAMPLE_RATE });
            masterGainRef.current = audioContextRef.current.createGain();
            masterGainRef.current.connect(audioContextRef.current.destination);
            masterGainRef.current.gain.value = state.isMuted ? 0 : state.volume;
        } catch (err) {
            setState(prev => ({
                ...prev,
                error: err instanceof Error ? err.message : 'Failed to initialize audio'
            }));
        }
    }, [state.isMuted, state.volume]);

    // Generate pink noise for exhaust character
    const createNoiseBuffer = useCallback((duration = 2): AudioBuffer => {
        const ctx = audioContextRef.current!;
        const bufferSize = ctx.sampleRate * duration;
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);

        // Pink noise generation (1/f noise for realistic exhaust)
        let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
        for (let i = 0; i < bufferSize; i++) {
            const white = Math.random() * 2 - 1;
            b0 = 0.99886 * b0 + white * 0.0555179;
            b1 = 0.99332 * b1 + white * 0.0750759;
            b2 = 0.96900 * b2 + white * 0.1538520;
            b3 = 0.86650 * b3 + white * 0.3104856;
            b4 = 0.55000 * b4 + white * 0.5329522;
            b5 = -0.7616 * b5 - white * 0.0168980;
            data[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.11;
            b6 = white * 0.115926;
        }

        return buffer;
    }, []);

    // Create engine sound with harmonics
    const createEngineSound = useCallback(() => {
        if (!audioContextRef.current || !masterGainRef.current) return;

        const ctx = audioContextRef.current;
        const master = masterGainRef.current;

        // Clear existing oscillators
        engineOscillatorsRef.current.forEach(osc => {
            try { osc.stop(); } catch { }
            osc.disconnect();
        });
        engineGainsRef.current.forEach(gain => gain.disconnect());
        engineOscillatorsRef.current = [];
        engineGainsRef.current = [];

        // Create fundamental and harmonics for engine character
        // Fundamental = (RPM / 60) * (cylinders / 2) for 4-stroke
        const harmonics = opts.funMode ? [
            // FUN MODE - EXAGGERATED HARMONICS!
            { mult: 1.0, gain: 1.2 },   // Fundamental - LOUDER!
            { mult: 2.0, gain: 0.8 },   // 2nd harmonic - MORE!
            { mult: 3.0, gain: 0.6 },   // 3rd harmonic - AGGRESSIVE!
            { mult: 4.0, gain: 0.5 },   // 4th harmonic - CRAZY!
            { mult: 5.0, gain: 0.4 },   // 5th harmonic - WILD!
            { mult: 7.0, gain: 0.3 },   // 7th harmonic - EXTRA!
            { mult: 0.5, gain: 0.8 },   // Sub-harmonic - RUMBLE!
            { mult: 0.25, gain: 0.6 },  // Deep sub - EARTHQUAKE!
        ] : [
            { mult: 1.0, gain: 0.8 },   // Fundamental
            { mult: 2.0, gain: 0.4 },   // 2nd harmonic
            { mult: 3.0, gain: 0.2 },   // 3rd harmonic
            { mult: 4.0, gain: 0.15 },  // 4th harmonic
            { mult: 5.0, gain: 0.1 },   // 5th harmonic
            { mult: 0.5, gain: 0.3 },   // Sub-harmonic for V-twin character
        ];

        harmonics.forEach(({ mult, gain }) => {
            const osc = ctx.createOscillator();
            const gainNode = ctx.createGain();

            // Use sawtooth for rich harmonic content (or square for fun mode!)
            osc.type = opts.funMode ? 'square' : 'sawtooth';
            osc.frequency.value = BASE_FREQUENCY * mult;

            gainNode.gain.value = gain * (opts.funMode ? 0.5 : 0.3); // Start louder in fun mode!

            osc.connect(gainNode);
            gainNode.connect(master);
            osc.start();

            engineOscillatorsRef.current.push(osc);
            engineGainsRef.current.push(gainNode);
        });

        // Create exhaust noise layer
        const noiseBuffer = createNoiseBuffer(2);
        const createExhaustNoise = () => {
            if (!audioContextRef.current || !masterGainRef.current) return;

            const source = ctx.createBufferSource();
            source.buffer = noiseBuffer;
            source.loop = true;

            const gain = ctx.createGain();
            gain.gain.value = opts.funMode ? 0.3 : 0.1; // Louder in fun mode!

            const filter = ctx.createBiquadFilter();
            filter.type = 'bandpass';
            filter.frequency.value = opts.funMode ? 150 : 200; // Lower for more rumble
            filter.Q.value = opts.funMode ? 2.0 : 1.0; // More resonance!

            source.connect(filter);
            filter.connect(gain);
            gain.connect(master);
            source.start();

            exhaustNoiseRef.current = source;
            exhaustGainRef.current = gain;
        };

        createExhaustNoise();

        // Create crackle/pop layer for deceleration
        if (opts.enableCrackle) {
            const crackleBuffer = createNoiseBuffer(0.5);
            const crackleSource = ctx.createBufferSource();
            crackleSource.buffer = crackleBuffer;
            crackleSource.loop = true;

            const crackleGain = ctx.createGain();
            crackleGain.gain.value = 0; // Off by default

            const crackleFilter = ctx.createBiquadFilter();
            crackleFilter.type = 'highpass';
            crackleFilter.frequency.value = 800;

            crackleSource.connect(crackleFilter);
            crackleFilter.connect(crackleGain);
            crackleGain.connect(master);
            crackleSource.start();

            crackleSourceRef.current = crackleSource;
            crackleGainRef.current = crackleGain;
        }
    }, [createNoiseBuffer, opts.enableCrackle, opts.funMode]);

    // Update engine sound based on RPM and load
    const updateEngineSound = useCallback(() => {
        if (!audioContextRef.current || engineOscillatorsRef.current.length === 0) return;

        const ctx = audioContextRef.current;
        const rpm = currentRpmRef.current;
        const load = currentLoadRef.current;

        // Calculate fundamental frequency - MORE DRAMATIC in fun mode!
        // Base formula: freq = (RPM / 60) * (cylinders / 2)
        // But we multiply to make it more audible and fun
        const baseFreq = (rpm / 60) * (opts.cylinders / 2);
        const fundamentalFreq = opts.funMode
            ? Math.max(MIN_RPM_FREQUENCY, baseFreq * 2.5) // Fun mode: 2.5x frequency for dramatic effect!
            : Math.max(MIN_RPM_FREQUENCY, baseFreq);

        // Harmonic multipliers - MUST match createEngineSound!
        const harmonicMultipliers = opts.funMode
            ? [1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 0.5, 0.25] // 8 harmonics for fun mode
            : [1.0, 2.0, 3.0, 4.0, 5.0, 0.5];           // 6 harmonics normal

        // Update oscillator frequencies
        engineOscillatorsRef.current.forEach((osc, i) => {
            const harmonic = harmonicMultipliers[i] || 1.0;
            const targetFreq = Math.max(BASE_FREQUENCY, fundamentalFreq * harmonic);

            // Smooth frequency transition - FASTER in fun mode for more responsive feel
            osc.frequency.setTargetAtTime(
                targetFreq,
                ctx.currentTime,
                opts.funMode ? 0.02 : 0.05 // Faster response in fun mode!
            );
        });

        // Update gains based on load (throttle position)
        // Higher load = louder, more aggressive
        const baseVolume = Math.min(1.0, rpm / 8000); // Volume increases with RPM
        const loadFactor = opts.funMode
            ? 0.5 + (load * 1.5)  // FUN MODE: LOUDER AND MORE DRAMATIC!
            : 0.3 + (load * 0.7); // 30% base, up to 100% at full load

        engineGainsRef.current.forEach((gain, i) => {
            const harmonicGain = opts.funMode
                ? [1.2, 0.8, 0.6, 0.5, 0.4, 0.3, 0.8, 0.6][i] || 0.2  // FUN MODE GAINS!
                : [0.8, 0.4, 0.2, 0.15, 0.1, 0.3][i] || 0.1;
            const targetGain = harmonicGain * baseVolume * loadFactor * (opts.funMode ? 1.5 : 1.0);

            gain.gain.setTargetAtTime(
                targetGain,
                ctx.currentTime,
                0.05
            );
        });

        // Update exhaust noise
        if (exhaustGainRef.current) {
            const exhaustVolume = baseVolume * load * (opts.funMode ? 0.6 : 0.3); // LOUDER EXHAUST!
            exhaustGainRef.current.gain.setTargetAtTime(
                exhaustVolume,
                ctx.currentTime,
                0.05
            );
        }

        // Update crackle (active on decel: high RPM, low load)
        if (crackleGainRef.current && opts.enableCrackle) {
            const isDecel = rpm > 3000 && load < 0.2;
            const crackleVolume = isDecel
                ? (opts.funMode ? 0.4 : 0.15) * (rpm / 8000)  // CRAZY CRACKLE IN FUN MODE!
                : 0;
            crackleGainRef.current.gain.setTargetAtTime(
                crackleVolume,
                ctx.currentTime,
                0.02
            );
        }
    }, [opts.cylinders, opts.enableCrackle, opts.funMode]);

    // Animation loop for smooth RPM/load transitions
    const animationLoop = useCallback(() => {
        // Check ref instead of state to avoid stale closure!
        if (!isPlayingRef.current) return;

        // Smooth interpolation
        const rpmDiff = targetRpmRef.current - currentRpmRef.current;
        const loadDiff = targetLoadRef.current - currentLoadRef.current;

        // Exponential smoothing - FASTER for more responsive feel
        currentRpmRef.current += rpmDiff * 0.15; // Increased from 0.1
        currentLoadRef.current += loadDiff * 0.2;  // Increased from 0.15

        // Update audio
        updateEngineSound();

        // Continue loop using ref
        animationFrameRef.current = requestAnimationFrame(animationLoop);
    }, [updateEngineSound]);

    // Start engine
    const startEngine = useCallback(async () => {
        initAudioContext();

        if (!audioContextRef.current) {
            setState(prev => ({ ...prev, error: 'Audio context not available' }));
            return;
        }

        // Resume if suspended (browser autoplay policy)
        if (audioContextRef.current.state === 'suspended') {
            await audioContextRef.current.resume();
        }

        createEngineSound();

        // Set playing state - BOTH state and ref!
        isPlayingRef.current = true;
        setState(prev => ({ ...prev, isPlaying: true, error: null }));

        // Start animation loop
        animationFrameRef.current = requestAnimationFrame(animationLoop);
    }, [initAudioContext, createEngineSound, animationLoop]);

    // Stop engine
    const stopEngine = useCallback(() => {
        // Stop animation loop - set ref FIRST to stop the loop
        isPlayingRef.current = false;
        if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current);
            animationFrameRef.current = null;
        }

        // Stop all oscillators
        engineOscillatorsRef.current.forEach(osc => {
            try { osc.stop(); } catch { }
            osc.disconnect();
        });
        engineGainsRef.current.forEach(gain => gain.disconnect());
        engineOscillatorsRef.current = [];
        engineGainsRef.current = [];

        // Stop noise sources
        if (exhaustNoiseRef.current) {
            try { exhaustNoiseRef.current.stop(); } catch { }
            exhaustNoiseRef.current.disconnect();
            exhaustNoiseRef.current = null;
        }
        if (crackleSourceRef.current) {
            try { crackleSourceRef.current.stop(); } catch { }
            crackleSourceRef.current.disconnect();
            crackleSourceRef.current = null;
        }

        setState(prev => ({ ...prev, isPlaying: false, rpm: 0, load: 0 }));
        targetRpmRef.current = 0;
        currentRpmRef.current = 0;
        targetLoadRef.current = 0;
        currentLoadRef.current = 0;
    }, []);

    // Set RPM
    const setRpm = useCallback((rpm: number) => {
        targetRpmRef.current = Math.max(0, Math.min(10000, rpm));
        setState(prev => ({ ...prev, rpm: targetRpmRef.current }));
    }, []);

    // Set load (0-1)
    const setLoad = useCallback((load: number) => {
        targetLoadRef.current = Math.max(0, Math.min(1, load));
        setState(prev => ({ ...prev, load: targetLoadRef.current }));
    }, []);

    // Set volume
    const setVolume = useCallback((volume: number) => {
        const vol = Math.max(0, Math.min(1, volume));
        setState(prev => ({ ...prev, volume: vol }));

        if (masterGainRef.current && !state.isMuted) {
            masterGainRef.current.gain.setValueAtTime(
                vol,
                audioContextRef.current?.currentTime ?? 0
            );
        }
    }, [state.isMuted]);

    // Toggle mute
    const toggleMute = useCallback(() => {
        setState(prev => {
            const newMuted = !prev.isMuted;

            if (masterGainRef.current && audioContextRef.current) {
                masterGainRef.current.gain.setValueAtTime(
                    newMuted ? 0 : prev.volume,
                    audioContextRef.current.currentTime
                );
            }

            return { ...prev, isMuted: newMuted };
        });
    }, []);

    // Sound effects
    const playBeep = useCallback((frequency = 440, duration = 0.1) => {
        if (!audioContextRef.current || !masterGainRef.current) {
            initAudioContext();
            if (!audioContextRef.current || !masterGainRef.current) return;
        }

        const ctx = audioContextRef.current;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.frequency.value = frequency;
        osc.type = 'sine';

        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + duration);

        osc.connect(gain);
        gain.connect(masterGainRef.current);

        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + duration);
    }, [initAudioContext]);

    const playStartup = useCallback(() => {
        // Startup chime: rising tone
        playBeep(200, 0.05);
        setTimeout(() => playBeep(400, 0.05), 50);
        setTimeout(() => playBeep(600, 0.1), 100);
    }, [playBeep]);

    const playShutdown = useCallback(() => {
        // Shutdown: falling tone
        playBeep(600, 0.05);
        setTimeout(() => playBeep(400, 0.05), 50);
        setTimeout(() => playBeep(200, 0.1), 100);
    }, [playBeep]);

    const playWarning = useCallback(() => {
        // Warning: alternating tones
        playBeep(800, 0.1);
        setTimeout(() => playBeep(600, 0.1), 120);
        setTimeout(() => playBeep(800, 0.1), 240);
    }, [playBeep]);

    const playSuccess = useCallback(() => {
        // Success: ascending arpeggio
        playBeep(523, 0.08); // C
        setTimeout(() => playBeep(659, 0.08), 80); // E
        setTimeout(() => playBeep(784, 0.15), 160); // G
    }, [playBeep]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            stopEngine();
            if (audioContextRef.current) {
                void audioContextRef.current.close();
            }
        };
    }, [stopEngine]);

    return {
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
    };
}

export default useAudioEngine;

