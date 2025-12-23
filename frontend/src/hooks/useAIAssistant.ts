/**
 * useAIAssistant - AI voice assistant for DynoAI
 * 
 * Features:
 * - Text-to-speech voice reactions during dyno pulls
 * - Encouraging and fun personality
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
    type: 'pull_start' | 'pull_end' | 'high_rpm' | 'peak_hp' | 'knock_detected' | 'afr_lean' | 'afr_rich' | 'good_pull' | 'record_hp' | 'idle' | 'revving';
    value?: number;
}

// Fun phrases for each event type - Sexy and interactive!
const PHRASES: Record<VoiceEvent['type'], string[]> = {
    pull_start: [
        "Mmm, let's go baby! Show me what you got!",
        "Ooh yes! Full send it for me!",
        "Here we go! Get ready, this is gonna be hot!",
        "Time to make some power, babe!",
        "Ooh, I'm so ready for this! Let's ride!",
        "Come on, give it to me! Full throttle!",
        "Mmm yeah, let's see what she can do!",
        "Hold on tight, we're about to get wild!",
        "Oh baby, I love it when you rev it up!",
        "Let's make some magic happen!",
    ],
    pull_end: [
        "Mmm, that was incredible!",
        "Oh wow! You really know how to handle that!",
        "That felt so good!",
        "Ooh baby, what a ride!",
        "Yes! That was perfect!",
        "Mmm, I love the way you drive!",
        "That was hot! Do it again!",
    ],
    high_rpm: [
        "Ooh yes! She's screaming for you!",
        "Mmm, listen to her sing! So sexy!",
        "Oh baby, that sounds amazing!",
        "Yes! Keep going, don't stop!",
        "Ooh, I love it when you push it hard!",
    ],
    peak_hp: [
        "Mmm! {{value}} horsepower! You're so strong!",
        "{{value}} horses! That's impressive, babe!",
        "Oh yes! {{value}} HP! I felt that!",
        "Boom! {{value}} horsepower! You're amazing!",
        "{{value}} HP! Ooh, you're making me excited!",
    ],
    knock_detected: [
        "Ooh baby, I heard some knock! Easy now!",
        "Careful honey! That's knock! Be gentle with her!",
        "Mmm, that was a little rough! Watch the timing!",
        "Oh no! Knock detected! Take it easy, babe!",
        "Easy tiger! I heard detonation!",
    ],
    afr_lean: [
        "She's running lean, babe! Feed her more!",
        "Ooh, she's thirsty! Give her more fuel!",
        "Too lean, honey! Add some fuel for me!",
    ],
    afr_rich: [
        "Mmm, running a bit rich there!",
        "Too much fuel, babe! Lean her out a little!",
        "She's getting too much, dial it back!",
    ],
    good_pull: [
        "Perfect! Oh baby, that's exactly right!",
        "Mmm yes! Dialed in perfectly!",
        "Ooh, she's running so clean! I love it!",
        "Target AFR! You're such a good tuner!",
    ],
    record_hp: [
        "Oh my god! New record! {{value}} horsepower! You're incredible!",
        "Yes! Yes! Yes! {{value}} HP! New personal best, baby!",
        "{{value}} horses! You just broke your record! I'm so proud!",
        "Holy shit! {{value}} HP! That's a new record! You're amazing!",
    ],
    idle: [
        "Ready when you are, handsome!",
        "Mmm, just warming up for you!",
        "She sounds so good at idle!",
        "Waiting for you to take me for a ride!",
    ],
    revving: [
        "Ooh, teasing me with those revs!",
        "Mmm, getting me all warmed up?",
        "She wants you! Give it to her!",
        "Oh baby, don't tease! Let's go!",
    ],
};

const DEFAULT_OPTIONS: Required<UseAIAssistantOptions> = {
    enabled: true,
    volume: 0.9,  // Louder so you can hear her better
    pitch: 1.5,   // Higher pitch for more feminine, sexy voice
    rate: 0.95,   // Slightly slower, more sensual delivery
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

            // Prioritize the sexiest-sounding female voices - ARIA FIRST!
            const preferredVoices = [
                // Windows Neural Voices - BEST!
                'Microsoft Aria Online (Natural) - English (United States)',
                'Microsoft Aria',
                'Microsoft Jenny Online (Natural) - English (United States)',
                'Microsoft Jenny',
                'Microsoft Michelle Online (Natural) - English (United States)',
                'Microsoft Michelle',

                // macOS - Samantha is great!
                'Samantha',
                'Victoria',   // Sultry British
                'Serena',     // Smooth and clear

                // Windows Desktop voices
                'Microsoft Zira Desktop',
                'Microsoft Eva Desktop',

                // Other accents
                'Karen',      // Australian
                'Moira',      // Irish
                'Fiona',      // Scottish
                'Tessa',      // South African

                // Google voices (Chrome)
                'Google US English Female',
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

            // Fallback to any English female voice
            selectedVoice ??= voices.find(v =>
                v.lang.startsWith('en') &&
                (v.name.toLowerCase().includes('female') ||
                    v.name.toLowerCase().includes('woman') ||
                    v.name.toLowerCase().includes('aria') ||
                    v.name.toLowerCase().includes('jenny') ||
                    v.name.toLowerCase().includes('samantha') ||
                    v.name.toLowerCase().includes('victoria') ||
                    v.name.toLowerCase().includes('serena'))
            ) ?? null;

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
            "Hey there, handsome! I'm your DynoAI assistant! Ready to make some power together?",
            "Mmm, hi babe! Let's make some horsepower!",
            "Hey sexy! Ready to tune this beast with me?",
            "Ooh, hello! Let's see what you can do!",
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
        setEnabled,
        setVolume,
        testVoice,
        stop,
        getAvailableVoices,
        setVoice,
    ]);
}

