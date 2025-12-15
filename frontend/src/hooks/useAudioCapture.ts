/**
 * useAudioCapture - React hook for microphone audio capture and analysis
 * 
 * Provides:
 * - Microphone permission handling
 * - Real-time audio recording during dyno pulls
 * - Waveform data for visualization
 * - FFT frequency analysis for knock detection
 * - Audio recording with WAV export
 */

import { useState, useCallback, useRef, useEffect } from 'react';

// Audio analysis configuration
const FFT_SIZE = 2048;
const SAMPLE_RATE = 44100;

// Knock detection frequency bands (engine knock typically 5-15kHz but varies by engine)
const KNOCK_BANDS = [
    { min: 5000, max: 7000, weight: 1.0 },   // Primary knock range
    { min: 7000, max: 10000, weight: 0.8 },  // Secondary range
    { min: 10000, max: 15000, weight: 0.6 }, // High frequency harmonics
];

// Knock detection thresholds
const KNOCK_CONFIRM_COUNT = 2;  // Number of consecutive detections to confirm knock
const KNOCK_COOLDOWN_MS = 200;  // Minimum time between knock events

export interface AudioCaptureState {
    hasPermission: boolean | null;
    isRecording: boolean;
    isPaused: boolean;
    duration: number;
    error: string | null;
}

export interface AudioAnalysis {
    waveform: Float32Array | null;
    frequencies: Float32Array | null;
    volume: number;
    peakFrequency: number;
    knockDetected: boolean;
    knockEvents: KnockEvent[];
}

export interface KnockEvent {
    timestamp: number;
    frequency: number;
    intensity: number;
}

export interface RecordedAudio {
    blob: Blob;
    url: string;
    duration: number;
    startTime: number;
    endTime: number;
    knockEvents: KnockEvent[];
}

export interface UseAudioCaptureOptions {
    /** Enable real-time analysis (waveform, FFT) - default: true */
    enableAnalysis?: boolean;
    /** Enable knock detection - default: true */
    enableKnockDetection?: boolean;
    /** Analysis update interval in ms - default: 50 */
    analysisInterval?: number;
    /** Knock detection sensitivity (0-1) - default: 0.7 */
    knockSensitivity?: number;
    /** Enable audible alarm on knock detection - default: false */
    enableKnockAlarm?: boolean;
    /** Knock alarm volume (0-1) - default: 0.5 */
    alarmVolume?: number;
    /** Custom knock frequency range [min, max] in Hz */
    knockFrequencyRange?: [number, number];
}

export interface UseAudioCaptureReturn {
    // State
    state: AudioCaptureState;
    analysis: AudioAnalysis;
    recordings: RecordedAudio[];

    // Actions
    requestPermission: () => Promise<boolean>;
    startRecording: () => Promise<void>;
    stopRecording: () => Promise<RecordedAudio | null>;
    pauseRecording: () => void;
    resumeRecording: () => void;
    clearRecordings: () => void;
    downloadRecording: (recording: RecordedAudio, filename?: string) => void;

    // Alarm controls
    setAlarmEnabled: (enabled: boolean) => void;
    setAlarmVolume: (volume: number) => void;
    testAlarm: () => void;

    // Refs for external visualization
    analyserNode: React.RefObject<AnalyserNode | null>;
}

const DEFAULT_OPTIONS: Required<UseAudioCaptureOptions> = {
    enableAnalysis: true,
    enableKnockDetection: true,
    analysisInterval: 50,
    knockSensitivity: 0.7,
    enableKnockAlarm: false,
    alarmVolume: 0.5,
    knockFrequencyRange: [5000, 15000],
};

export function useAudioCapture(options: UseAudioCaptureOptions = {}): UseAudioCaptureReturn {
    const opts = { ...DEFAULT_OPTIONS, ...options };

    // State
    const [state, setState] = useState<AudioCaptureState>(() => {
        // Check if we have permission stored
        const storedPermission = localStorage.getItem('dynoai_audio_permission');
        return {
            hasPermission: storedPermission === 'granted' ? true : null,
            isRecording: false,
            isPaused: false,
            duration: 0,
            error: null,
        };
    });

    const [analysis, setAnalysis] = useState<AudioAnalysis>({
        waveform: null,
        frequencies: null,
        volume: 0,
        peakFrequency: 0,
        knockDetected: false,
        knockEvents: [],
    });

    const [recordings, setRecordings] = useState<RecordedAudio[]>([]);

    // Refs for audio handling
    const audioContextRef = useRef<AudioContext | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const mediaStreamRef = useRef<MediaStream | null>(null);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const chunksRef = useRef<Blob[]>([]);
    const startTimeRef = useRef<number>(0);
    const knockEventsRef = useRef<KnockEvent[]>([]);
    const analysisIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const durationIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // Knock detection state
    const knockConfirmCountRef = useRef<number>(0);
    const lastKnockTimeRef = useRef<number>(0);

    // Alarm state
    const [alarmEnabled, setAlarmEnabled] = useState(opts.enableKnockAlarm);
    const [alarmVolume, setAlarmVolume] = useState(opts.alarmVolume);

    // Play knock alarm sound
    const playAlarm = useCallback(() => {
        if (!alarmEnabled || !audioContextRef.current) return;

        const ctx = audioContextRef.current;

        // Create alarm sound: two-tone beep
        const osc1 = ctx.createOscillator();
        const osc2 = ctx.createOscillator();
        const gain = ctx.createGain();

        osc1.type = 'square';
        osc1.frequency.value = 880; // A5
        osc2.type = 'square';
        osc2.frequency.value = 1760; // A6

        gain.gain.value = alarmVolume * 0.3;

        osc1.connect(gain);
        osc2.connect(gain);
        gain.connect(ctx.destination);

        const now = ctx.currentTime;

        // Rapid beeping pattern
        gain.gain.setValueAtTime(alarmVolume * 0.3, now);
        gain.gain.setValueAtTime(0, now + 0.1);
        gain.gain.setValueAtTime(alarmVolume * 0.3, now + 0.15);
        gain.gain.setValueAtTime(0, now + 0.25);
        gain.gain.setValueAtTime(alarmVolume * 0.3, now + 0.3);
        gain.gain.setValueAtTime(0, now + 0.4);

        osc1.start(now);
        osc2.start(now);
        osc1.stop(now + 0.5);
        osc2.stop(now + 0.5);
    }, [alarmEnabled, alarmVolume]);

    // Test alarm sound
    const testAlarm = useCallback(() => {
        if (!audioContextRef.current) {
            // Create temporary context for test
            const ctx = new AudioContext();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'square';
            osc.frequency.value = 880;
            gain.gain.value = alarmVolume * 0.3;
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.3);
            return;
        }
        playAlarm();
    }, [playAlarm, alarmVolume]);

    // Request microphone permission
    const requestPermission = useCallback(async (): Promise<boolean> => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false,
                    sampleRate: SAMPLE_RATE,
                }
            });

            // Store the stream for later use
            mediaStreamRef.current = stream;

            // Initialize audio context and analyser
            audioContextRef.current = new AudioContext({ sampleRate: SAMPLE_RATE });
            analyserRef.current = audioContextRef.current.createAnalyser();
            analyserRef.current.fftSize = FFT_SIZE;
            analyserRef.current.smoothingTimeConstant = 0.3;

            // Connect stream to analyser
            const source = audioContextRef.current.createMediaStreamSource(stream);
            source.connect(analyserRef.current);

            // Store permission in localStorage
            localStorage.setItem('dynoai_audio_permission', 'granted');

            setState(prev => ({ ...prev, hasPermission: true, error: null }));
            return true;
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Microphone access denied';

            // Store denied state
            localStorage.setItem('dynoai_audio_permission', 'denied');

            setState(prev => ({
                ...prev,
                hasPermission: false,
                error: message
            }));
            return false;
        }
    }, []);

    // Analyze audio for waveform, FFT, and knock detection
    const analyzeAudio = useCallback(() => {
        if (!analyserRef.current) return;

        const analyser = analyserRef.current;
        const bufferLength = analyser.frequencyBinCount;

        // Get waveform data
        const waveform = new Float32Array(bufferLength);
        analyser.getFloatTimeDomainData(waveform);

        // Get frequency data
        const frequencies = new Float32Array(bufferLength);
        analyser.getFloatFrequencyData(frequencies);

        // Calculate volume (RMS)
        let sum = 0;
        for (const sample of waveform) {
            sum += sample * sample;
        }
        const volume = Math.sqrt(sum / waveform.length);

        // Find peak frequency
        let maxDb = -Infinity;
        let peakIndex = 0;
        for (let i = 0; i < frequencies.length; i++) {
            if (frequencies[i] > maxDb) {
                maxDb = frequencies[i];
                peakIndex = i;
            }
        }
        const binFrequency = (SAMPLE_RATE / 2) / bufferLength;
        const peakFrequency = peakIndex * binFrequency;

        // Advanced knock detection with multi-band analysis
        let knockDetected = false;
        if (opts.enableKnockDetection) {
            const [freqMin, freqMax] = opts.knockFrequencyRange;
            const minBin = Math.floor(freqMin / binFrequency);
            const maxBin = Math.ceil(freqMax / binFrequency);

            // Calculate weighted energy across knock frequency bands
            let totalKnockEnergy = 0;
            let totalWeight = 0;

            for (const band of KNOCK_BANDS) {
                const bandMinBin = Math.floor(band.min / binFrequency);
                const bandMaxBin = Math.ceil(band.max / binFrequency);
                let bandEnergy = 0;
                let bandCount = 0;

                for (let i = bandMinBin; i < bandMaxBin && i < frequencies.length; i++) {
                    bandEnergy += Math.pow(10, frequencies[i] / 20);
                    bandCount++;
                }

                if (bandCount > 0) {
                    totalKnockEnergy += (bandEnergy / bandCount) * band.weight;
                    totalWeight += band.weight;
                }
            }

            const avgKnockEnergy = totalWeight > 0 ? totalKnockEnergy / totalWeight : 0;

            // Calculate baseline energy (low frequencies < 2kHz)
            let baselineEnergy = 0;
            let baselineCount = 0;
            const baselineBin = Math.ceil(2000 / binFrequency);

            for (let i = 0; i < baselineBin && i < frequencies.length; i++) {
                baselineEnergy += Math.pow(10, frequencies[i] / 20);
                baselineCount++;
            }
            baselineEnergy = baselineCount > 0 ? baselineEnergy / baselineCount : 0.001;

            // Knock ratio with sensitivity adjustment
            const knockRatio = avgKnockEnergy / (baselineEnergy || 0.001);
            const threshold = 1.5 + (1 - opts.knockSensitivity) * 3; // 1.5 to 4.5 based on sensitivity

            const instantKnock = knockRatio > threshold && volume > 0.01;

            // Confirmation logic - require consecutive detections to reduce false positives
            const now = Date.now();
            if (instantKnock) {
                if (now - lastKnockTimeRef.current < 100) { // Within 100ms window
                    knockConfirmCountRef.current++;
                } else {
                    knockConfirmCountRef.current = 1;
                }
                lastKnockTimeRef.current = now;

                // Confirm knock after KNOCK_CONFIRM_COUNT consecutive detections
                knockDetected = knockConfirmCountRef.current >= KNOCK_CONFIRM_COUNT;
            } else {
                // Decay confirmation count
                if (now - lastKnockTimeRef.current > 200) {
                    knockConfirmCountRef.current = Math.max(0, knockConfirmCountRef.current - 1);
                }
            }

            // Record knock event and trigger alarm
            if (knockDetected) {
                const timeSinceLastEvent = knockEventsRef.current.length > 0
                    ? now - (startTimeRef.current + knockEventsRef.current[knockEventsRef.current.length - 1].timestamp)
                    : KNOCK_COOLDOWN_MS + 1;

                if (timeSinceLastEvent > KNOCK_COOLDOWN_MS) {
                    // Find dominant frequency in knock range
                    let dominantFreq = peakFrequency;
                    let maxEnergy = -Infinity;
                    for (let i = minBin; i < maxBin && i < frequencies.length; i++) {
                        if (frequencies[i] > maxEnergy) {
                            maxEnergy = frequencies[i];
                            dominantFreq = i * binFrequency;
                        }
                    }

                    const event: KnockEvent = {
                        timestamp: state.isRecording ? now - startTimeRef.current : now,
                        frequency: dominantFreq,
                        intensity: knockRatio,
                    };
                    knockEventsRef.current.push(event);

                    // Trigger alarm
                    playAlarm();
                }
            }
        }

        setAnalysis({
            waveform,
            frequencies,
            volume,
            peakFrequency,
            knockDetected,
            knockEvents: [...knockEventsRef.current],
        });
    }, [opts.enableKnockDetection, opts.knockSensitivity, opts.knockFrequencyRange, state.isRecording, playAlarm]);

    // Start recording
    const startRecording = useCallback(async () => {
        // Request permission if not already granted
        if (!mediaStreamRef.current) {
            const granted = await requestPermission();
            if (!granted) return;
        }

        // Resume audio context if suspended
        if (audioContextRef.current?.state === 'suspended') {
            await audioContextRef.current.resume();
        }

        const stream = mediaStreamRef.current;
        if (!stream) {
            setState(prev => ({ ...prev, error: 'No audio stream available' }));
            return;
        }

        try {
            // Create MediaRecorder
            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : 'audio/webm';

            mediaRecorderRef.current = new MediaRecorder(stream, { mimeType });
            chunksRef.current = [];
            knockEventsRef.current = [];
            startTimeRef.current = Date.now();

            mediaRecorderRef.current.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    chunksRef.current.push(e.data);
                }
            };

            mediaRecorderRef.current.start(100); // Collect data every 100ms

            setState(prev => ({
                ...prev,
                isRecording: true,
                isPaused: false,
                duration: 0,
                error: null,
            }));

            // Start duration timer
            durationIntervalRef.current = setInterval(() => {
                setState(prev => ({
                    ...prev,
                    duration: Date.now() - startTimeRef.current,
                }));
            }, 100);

            // Start analysis
            if (opts.enableAnalysis) {
                analysisIntervalRef.current = setInterval(analyzeAudio, opts.analysisInterval);
            }

        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to start recording';
            setState(prev => ({ ...prev, error: message }));
        }
    }, [requestPermission, opts.enableAnalysis, opts.analysisInterval, analyzeAudio]);

    // Stop recording
    const stopRecording = useCallback(async (): Promise<RecordedAudio | null> => {
        return new Promise((resolve) => {
            const recorder = mediaRecorderRef.current;

            // Clear intervals
            if (analysisIntervalRef.current) {
                clearInterval(analysisIntervalRef.current);
                analysisIntervalRef.current = null;
            }
            if (durationIntervalRef.current) {
                clearInterval(durationIntervalRef.current);
                durationIntervalRef.current = null;
            }

            if (!recorder || recorder.state === 'inactive') {
                setState(prev => ({ ...prev, isRecording: false, isPaused: false }));
                resolve(null);
                return;
            }

            recorder.onstop = () => {
                const endTime = Date.now();
                const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
                const url = URL.createObjectURL(blob);

                const recording: RecordedAudio = {
                    blob,
                    url,
                    duration: endTime - startTimeRef.current,
                    startTime: startTimeRef.current,
                    endTime,
                    knockEvents: [...knockEventsRef.current],
                };

                setRecordings(prev => [...prev, recording]);

                setState(prev => ({
                    ...prev,
                    isRecording: false,
                    isPaused: false,
                }));

                resolve(recording);
            };

            recorder.stop();
        });
    }, []);

    // Pause recording
    const pauseRecording = useCallback(() => {
        if (mediaRecorderRef.current?.state === 'recording') {
            mediaRecorderRef.current.pause();
            setState(prev => ({ ...prev, isPaused: true }));
        }
    }, []);

    // Resume recording
    const resumeRecording = useCallback(() => {
        if (mediaRecorderRef.current?.state === 'paused') {
            mediaRecorderRef.current.resume();
            setState(prev => ({ ...prev, isPaused: false }));
        }
    }, []);

    // Clear all recordings
    const clearRecordings = useCallback(() => {
        // Revoke object URLs to free memory
        recordings.forEach(r => URL.revokeObjectURL(r.url));
        setRecordings([]);
    }, [recordings]);

    // Download a recording
    const downloadRecording = useCallback((recording: RecordedAudio, filename?: string) => {
        const link = document.createElement('a');
        link.href = recording.url;
        link.download = filename ?? `dyno_audio_${new Date(recording.startTime).toISOString().replace(/[:.]/g, '-')}.webm`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }, []);

    // Auto-initialize if permission was previously granted
    useEffect(() => {
        const storedPermission = localStorage.getItem('dynoai_audio_permission');
        if (storedPermission === 'granted' && !mediaStreamRef.current) {
            // Silently request permission to restore the stream
            void requestPermission();
        }
    }, [requestPermission]);

    // Cleanup on unmount
    useEffect(() => {
        // Capture current recordings ref to avoid stale closure
        const currentRecordings = recordings;
        return () => {
            if (analysisIntervalRef.current) {
                clearInterval(analysisIntervalRef.current);
            }
            if (durationIntervalRef.current) {
                clearInterval(durationIntervalRef.current);
            }
            if (mediaStreamRef.current) {
                mediaStreamRef.current.getTracks().forEach(track => track.stop());
            }
            if (audioContextRef.current) {
                void audioContextRef.current.close();
            }
            currentRecordings.forEach(r => URL.revokeObjectURL(r.url));
        };
    }, [recordings]);

    return {
        state,
        analysis,
        recordings,
        requestPermission,
        startRecording,
        stopRecording,
        pauseRecording,
        resumeRecording,
        clearRecordings,
        downloadRecording,
        setAlarmEnabled,
        setAlarmVolume,
        testAlarm,
        analyserNode: analyserRef,
    };
}

export default useAudioCapture;

