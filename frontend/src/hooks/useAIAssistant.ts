/**
 * useAIAssistant - AI voice assistant for DynoAI
 * 
 * Features:
 * - Text-to-speech voice feedback during dyno operations
 * - Professional, concise announcements
 * - Reacts to RPM, horsepower, knock detection, and pull events
 */

import { useCallback, useRef, useState, useEffect, useMemo } from 'react';

export interface AIAssistantState {
    isEnabled: boolean;
    isSpeaking: boolean;
    voiceName: string;
    volume: number;
    pitch: number;
    rate: number;
}

export interface UseAIAssistantOptions {
    enabled?: boolean;
    volume?: number;
    pitch?: number;
    rate?: number;
}

interface VoiceEvent {
    type: 'pull_start' | 'pull_end' | 'high_rpm' | 'peak_hp' | 'knock_detected' | 'afr_lean' | 'afr_rich' | 'good_pull' | 'record_hp' | 'idle' | 'revving' |
          // Wizard events
          'coverage_50' | 'coverage_75' | 'coverage_ready' | 'balance_warning' | 'apply_blocked' | 'apply_ready' |
          'step_collect' | 'step_analyze' | 'step_review' | 'step_complete' | 'wot_suggestion' | 'cruise_suggestion';
    value?: number;
}

// Professional, concise phrases for each event type
const PHRASES: Record<VoiceEvent['type'], string[]> = {
    pull_start: [
        "Pull started.",
        "Recording pull.",
        "Pull in progress.",
    ],
    pull_end: [
        "Pull complete.",
        "Data captured.",
        "Pull recorded.",
    ],
    high_rpm: [
        "High RPM.",
        "Approaching redline.",
    ],
    peak_hp: [
        "{{value}} horsepower.",
        "Peak: {{value}} HP.",
    ],
    knock_detected: [
        "Warning: knock detected.",
        "Knock event. Check timing.",
        "Detonation detected.",
    ],
    afr_lean: [
        "Running lean. Add fuel.",
        "AFR lean condition.",
    ],
    afr_rich: [
        "Running rich. Reduce fuel.",
        "AFR rich condition.",
    ],
    good_pull: [
        "Good pull. AFR on target.",
        "Clean pull.",
    ],
    record_hp: [
        "New record: {{value}} horsepower.",
        "Personal best: {{value}} HP.",
    ],
    idle: [
        "System ready.",
        "Standing by.",
    ],
    revving: [
        "Warming up.",
    ],

    // Wizard coverage events
    coverage_50: [
        "50 percent coverage.",
        "Halfway complete.",
    ],
    coverage_75: [
        "75 percent coverage.",
        "Almost ready.",
    ],
    coverage_ready: [
        "Coverage target reached. Ready for analysis.",
        "Sufficient data collected.",
    ],

    // Balance warnings
    balance_warning: [
        "Cylinder imbalance detected. Check sensors.",
        "Front and rear mismatch detected.",
    ],

    // Apply status
    apply_blocked: [
        "Apply blocked. Resolve issues first.",
        "Cannot apply. Check warnings.",
    ],
    apply_ready: [
        "Corrections ready to apply.",
        "Validation passed. Ready to apply.",
    ],

    // Step transitions
    step_collect: [
        "Data collection. Run pulls.",
        "Collecting. Begin pulls.",
    ],
    step_analyze: [
        "Analyzing data.",
        "Processing.",
    ],
    step_review: [
        "Review corrections.",
        "Verify before applying.",
    ],
    step_complete: [
        "Complete. Ready to flash.",
        "Tuning complete.",
    ],

    // Coverage suggestions
    wot_suggestion: [
        "Need WOT data. Full throttle pulls, 3000 to redline.",
        "Run wide open throttle pulls.",
    ],
    cruise_suggestion: [
        "Need cruise data. Steady 2000 to 4500 RPM.",
        "Run part-throttle sweeps.",
    ],
};

const DEFAULT_OPTIONS: Required<UseAIAssistantOptions> = {
    enabled: true,
    volume: 0.8,
    pitch: 1.0,   // Neutral pitch
    rate: 1.1,    // Slightly faster for efficiency
};

export function useAIAssistant(options: UseAIAssistantOptions = {}) {
    const opts = { ...DEFAULT_OPTIONS, ...options };

    const [state, setState] = useState<AIAssistantState>({
        isEnabled: opts.enabled,
        isSpeaking: false,
        voiceName: '',
        volume: opts.volume,
        pitch: opts.pitch,
        rate: opts.rate,
    });

    // Update enabled state when options change
    useEffect(() => {
        setState(prev => ({ ...prev, isEnabled: opts.enabled }));
        console.log('[AI Assistant] Enabled state changed:', opts.enabled);
    }, [opts.enabled]);

    const synthRef = useRef<SpeechSynthesis | null>(null);
    const voiceRef = useRef<SpeechSynthesisVoice | null>(null);
    const lastEventRef = useRef<string>('');
    const lastEventTimeRef = useRef<number>(0);
    const cooldownMs = 3000; // Minimum time between same event type

    // Track peak HP for record detection
    const peakHpRef = useRef<number>(0);

    // Initialize speech synthesis and find a suitable voice
    useEffect(() => {
        if (typeof window === 'undefined' || !window.speechSynthesis) {
            console.error('[AI Assistant] Speech synthesis not supported in this browser');
            return;
        }

        synthRef.current = window.speechSynthesis;
        console.log('[AI Assistant] Speech synthesis initialized');

        const loadVoices = () => {
            const voices = synthRef.current?.getVoices() ?? [];

            // Prefer clear, professional-sounding voices
            const preferredVoices = [
                // Windows Neural Voices - clear and professional
                'Microsoft David Online (Natural) - English (United States)',
                'Microsoft David',
                'Microsoft Mark Online (Natural) - English (United States)',
                'Microsoft Mark',
                'Microsoft Guy Online (Natural) - English (United States)',
                'Microsoft Guy',
                // Female neural voices (still professional)
                'Microsoft Aria Online (Natural) - English (United States)',
                'Microsoft Jenny Online (Natural) - English (United States)',

                // macOS voices
                'Alex',       // Clear male voice
                'Daniel',     // British male
                'Samantha',   // Clear female

                // Windows Desktop voices
                'Microsoft David Desktop',
                'Microsoft Zira Desktop',

                // Google voices (Chrome)
                'Google US English',
                'Google UK English Male',
                'Google UK English Female',
            ];

            // Find a preferred voice
            let selectedVoice: SpeechSynthesisVoice | null = null;

            for (const name of preferredVoices) {
                const voice = voices.find(v => v.name.includes(name));
                if (voice) {
                    selectedVoice = voice;
                    break;
                }
            }

            // Fallback to any English voice
            selectedVoice ??= voices.find(v => v.lang.startsWith('en')) ?? null;

            // Log all available voices for debugging
            console.log('[AI Assistant] Total voices available:', voices.length);
            console.log('[AI Assistant] All voices:', voices.map(v => `"${v.name}" (${v.lang})`).join('\n'));

            if (selectedVoice) {
                voiceRef.current = selectedVoice;
                setState(prev => ({ ...prev, voiceName: selectedVoice.name }));
                console.log('[AI Assistant] ✅ Selected voice:', selectedVoice.name, '(', selectedVoice.lang, ')');
            } else {
                console.warn('[AI Assistant] ❌ No suitable voice found!');
                console.warn('[AI Assistant] Available voices:', voices.map(v => v.name));
            }
        };

        // Load voices (they may load asynchronously)
        loadVoices();
        synthRef.current.addEventListener('voiceschanged', loadVoices);

        return () => {
            synthRef.current?.removeEventListener('voiceschanged', loadVoices);
        };
    }, []);

    // Speak a phrase
    const speak = useCallback((text: string) => {
        if (!synthRef.current) {
            console.error('[AI Assistant] Speech synthesis not available');
            return;
        }

        if (!state.isEnabled) {
            console.log('[AI Assistant] Not speaking - disabled');
            return;
        }

        console.log('[AI Assistant] Speaking:', text);
        console.log('[AI Assistant] State:', { volume: state.volume, pitch: state.pitch, rate: state.rate });

        // Cancel any ongoing speech
        synthRef.current.cancel();

        const utterance = new SpeechSynthesisUtterance(text);

        if (voiceRef.current) {
            utterance.voice = voiceRef.current;
            console.log('[AI Assistant] Using voice:', voiceRef.current.name);
        } else {
            console.log('[AI Assistant] No voice selected, using default');
        }

        utterance.volume = state.volume;
        utterance.pitch = state.pitch;
        utterance.rate = state.rate;

        utterance.onstart = () => {
            console.log('[AI Assistant] Speech started');
            setState(prev => ({ ...prev, isSpeaking: true }));
        };

        utterance.onend = () => {
            console.log('[AI Assistant] Speech ended');
            setState(prev => ({ ...prev, isSpeaking: false }));
        };

        utterance.onerror = (event) => {
            console.error('[AI Assistant] Speech error:', event.error);
            setState(prev => ({ ...prev, isSpeaking: false }));
        };

        utterance.onpause = () => {
            console.log('[AI Assistant] Speech paused');
        };

        utterance.onresume = () => {
            console.log('[AI Assistant] Speech resumed');
        };

        console.log('[AI Assistant] Calling speak()...');
        synthRef.current.speak(utterance);

        // Log the speaking state immediately
        setTimeout(() => {
            console.log('[AI Assistant] Speaking state:', synthRef.current?.speaking);
            console.log('[AI Assistant] Pending state:', synthRef.current?.pending);
        }, 100);
    }, [state.isEnabled, state.volume, state.pitch, state.rate]);

    // Trigger an event (selects random phrase and speaks it)
    const triggerEvent = useCallback((event: VoiceEvent) => {
        console.log('[AI Assistant] triggerEvent called:', event.type, 'enabled:', state.isEnabled);

        if (!state.isEnabled) {
            console.log('[AI Assistant] Event ignored - not enabled');
            return;
        }

        const now = Date.now();

        // Check cooldown for same event type
        if (event.type === lastEventRef.current && now - lastEventTimeRef.current < cooldownMs) {
            console.log('[AI Assistant] Event ignored - cooldown active');
            return;
        }

        const phrases = PHRASES[event.type];
        if (!phrases || phrases.length === 0) {
            console.log('[AI Assistant] No phrases for event type:', event.type);
            return;
        }

        // Select random phrase
        let phrase = phrases[Math.floor(Math.random() * phrases.length)];

        // Replace {{value}} placeholder
        if (event.value !== undefined) {
            phrase = phrase.replace('{{value}}', event.value.toFixed(0));
        }

        console.log('[AI Assistant] Selected phrase:', phrase);

        lastEventRef.current = event.type;
        lastEventTimeRef.current = now;

        speak(phrase);
    }, [state.isEnabled, speak]);

    // Convenience methods for specific events
    const onPullStart = useCallback(() => {
        console.log('[AI Assistant] onPullStart called');
        triggerEvent({ type: 'pull_start' });
    }, [triggerEvent]);

    const onPullEnd = useCallback((peakHp?: number) => {
        if (peakHp !== undefined) {
            // Check for new record
            if (peakHp > peakHpRef.current && peakHpRef.current > 0) {
                peakHpRef.current = peakHp;
                triggerEvent({ type: 'record_hp', value: peakHp });
                return;
            }
            peakHpRef.current = Math.max(peakHpRef.current, peakHp);
            triggerEvent({ type: 'peak_hp', value: peakHp });
        } else {
            triggerEvent({ type: 'pull_end' });
        }
    }, [triggerEvent]);

    const onHighRpm = useCallback(() => {
        triggerEvent({ type: 'high_rpm' });
    }, [triggerEvent]);

    const onKnockDetected = useCallback(() => {
        triggerEvent({ type: 'knock_detected' });
    }, [triggerEvent]);

    const onAfrLean = useCallback(() => {
        triggerEvent({ type: 'afr_lean' });
    }, [triggerEvent]);

    const onAfrRich = useCallback(() => {
        triggerEvent({ type: 'afr_rich' });
    }, [triggerEvent]);

    const onGoodPull = useCallback(() => {
        triggerEvent({ type: 'good_pull' });
    }, [triggerEvent]);

    // Wizard events
    const onCoverage50 = useCallback(() => {
        triggerEvent({ type: 'coverage_50' });
    }, [triggerEvent]);

    const onCoverage75 = useCallback(() => {
        triggerEvent({ type: 'coverage_75' });
    }, [triggerEvent]);

    const onCoverageReady = useCallback(() => {
        triggerEvent({ type: 'coverage_ready' });
    }, [triggerEvent]);

    const onBalanceWarning = useCallback(() => {
        triggerEvent({ type: 'balance_warning' });
    }, [triggerEvent]);

    const onApplyBlocked = useCallback(() => {
        triggerEvent({ type: 'apply_blocked' });
    }, [triggerEvent]);

    const onApplyReady = useCallback(() => {
        triggerEvent({ type: 'apply_ready' });
    }, [triggerEvent]);

    const onStepChange = useCallback((step: 'collect' | 'analyze' | 'review' | 'complete') => {
        triggerEvent({ type: `step_${step}` as VoiceEvent['type'] });
    }, [triggerEvent]);

    const onWotSuggestion = useCallback(() => {
        triggerEvent({ type: 'wot_suggestion' });
    }, [triggerEvent]);

    const onCruiseSuggestion = useCallback(() => {
        triggerEvent({ type: 'cruise_suggestion' });
    }, [triggerEvent]);

    // Toggle enabled state
    const setEnabled = useCallback((enabled: boolean) => {
        setState(prev => ({ ...prev, isEnabled: enabled }));
        if (!enabled && synthRef.current) {
            synthRef.current.cancel();
        }
    }, []);

    // Set volume
    const setVolume = useCallback((volume: number) => {
        setState(prev => ({ ...prev, volume: Math.max(0, Math.min(1, volume)) }));
    }, []);

    // Test voice
    const testVoice = useCallback(() => {
        console.log('[AI Assistant] testVoice called, state:', state);
        console.log('[AI Assistant] Available voices:', synthRef.current?.getVoices().length);

        // Force enable for testing
        if (!state.isEnabled) {
            console.log('[AI Assistant] Force enabling for test');
            setState(prev => ({ ...prev, isEnabled: true }));
        }

        const greetings = [
            "DynoAI assistant online. Ready for tuning.",
            "Voice assistant active. System ready.",
            "Assistant enabled. Standing by.",
        ];
        speak(greetings[Math.floor(Math.random() * greetings.length)]);
    }, [speak, state]);

    // Stop speaking
    const stop = useCallback(() => {
        if (synthRef.current) {
            synthRef.current.cancel();
            setState(prev => ({ ...prev, isSpeaking: false }));
        }
    }, []);

    // Get all available voices
    const getAvailableVoices = useCallback(() => {
        return synthRef.current?.getVoices() ?? [];
    }, []);

    // Set a specific voice by name
    const setVoice = useCallback((voiceName: string) => {
        const voices = synthRef.current?.getVoices() ?? [];
        const voice = voices.find(v => v.name === voiceName);
        if (voice) {
            voiceRef.current = voice;
            setState(prev => ({ ...prev, voiceName: voice.name }));
            console.log('[AI Assistant] Voice changed to:', voice.name);
        }
    }, []);

    return useMemo(() => ({
        state,
        speak,
        triggerEvent,
        onPullStart,
        onPullEnd,
        onHighRpm,
        onKnockDetected,
        onAfrLean,
        onAfrRich,
        onGoodPull,
        // Wizard events
        onCoverage50,
        onCoverage75,
        onCoverageReady,
        onBalanceWarning,
        onApplyBlocked,
        onApplyReady,
        onStepChange,
        onWotSuggestion,
        onCruiseSuggestion,
        // Settings
        setEnabled,
        setVolume,
        testVoice,
        stop,
        getAvailableVoices,
        setVoice,
    }), [
        state,
        speak,
        triggerEvent,
        onPullStart,
        onPullEnd,
        onHighRpm,
        onKnockDetected,
        onAfrLean,
        onAfrRich,
        onGoodPull,
        onCoverage50,
        onCoverage75,
        onCoverageReady,
        onBalanceWarning,
        onApplyBlocked,
        onApplyReady,
        onStepChange,
        onWotSuggestion,
        onCruiseSuggestion,
        setEnabled,
        setVolume,
        testVoice,
        stop,
        getAvailableVoices,
        setVoice,
    ]);
}

