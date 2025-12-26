import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { playUiSound } from '../lib/ui-sounds';

export type AudioEngineState = {
  isPlaying: boolean;
  rpm: number;
  load: number; // 0..1
  error?: string;
};

export type UseAudioEngineOptions = {
  cylinders?: number;
  funMode?: boolean;
  volume?: number; // 0..1
};

export type AudioEngineApi = {
  playStartup: () => void;
  playShutdown: () => void;
  playSuccess: () => void;
  playWarning: () => void;
  playBeep: (freq?: number, seconds?: number) => void;
  setRpm: (rpm: number) => void;
  setLoad: (load: number) => void;
  startEngine: () => Promise<void>;
  stopEngine: () => void;
  state: AudioEngineState;
  cylinders: number;
  funMode: boolean;
};

function clamp01(n: number) {
  if (Number.isNaN(n)) return 0;
  return Math.min(1, Math.max(0, n));
}

function clamp(n: number, lo: number, hi: number) {
  if (Number.isNaN(n)) return lo;
  return Math.min(hi, Math.max(lo, n));
}

function getAudioContext(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  const Ctx =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctx) return null;
  return new Ctx();
}

// A lightweight "engine drone" synthesizer meant for diagnostics/fun; not a high-fidelity model.
export function useAudioEngine(options: UseAudioEngineOptions = {}): AudioEngineApi {
  const cylinders = options.cylinders ?? 2;
  const funMode = !!options.funMode;
  const volume = clamp01(options.volume ?? 0.12);

  const ctxRef = useRef<AudioContext | null>(null);
  const masterGainRef = useRef<GainNode | null>(null);
  const osc1Ref = useRef<OscillatorNode | null>(null);
  const osc2Ref = useRef<OscillatorNode | null>(null);

  const rpmRef = useRef(0);
  const loadRef = useRef(0);

  const [state, setState] = useState<AudioEngineState>({
    isPlaying: false,
    rpm: 0,
    load: 0,
  });

  const updateSynth = useCallback(() => {
    const ctx = ctxRef.current;
    const master = masterGainRef.current;
    const osc1 = osc1Ref.current;
    if (!ctx || !master || !osc1) return;

    const rpm = rpmRef.current;
    const load = loadRef.current;

    // 4-stroke: firing events per rev = cylinders/2
    const fireHz = (Math.max(0, rpm) / 60) * (cylinders / 2);
    // Map to audible "engine" pitch. Keep within a sane range.
    const base = clamp(fireHz * 2 + load * 40, 30, 520);

    const now = ctx.currentTime;
    osc1.frequency.setTargetAtTime(base, now, 0.03);
    if (osc2Ref.current) {
      osc2Ref.current.frequency.setTargetAtTime(base * 1.98, now, 0.03);
    }

    // Load acts like "throttle"/loudness. Add a small floor to avoid total silence.
    const v = clamp01(volume * (0.25 + 0.9 * load));
    master.gain.setTargetAtTime(Math.max(0.0001, v), now, 0.04);
  }, [cylinders, volume]);

  const startEngine = useCallback(async () => {
    if (typeof window === 'undefined') return;
    if (ctxRef.current && state.isPlaying) return;

    try {
      const ctx = getAudioContext();
      if (!ctx) {
        setState((s) => ({ ...s, error: 'WebAudio not supported in this browser.' }));
        return;
      }

      // Try resuming (some browsers require user gesture).
      if (ctx.state === 'suspended') {
        try {
          await ctx.resume();
        } catch {
          // ignore; we’ll still create nodes so audio can start once resumed.
        }
      }

      const master = ctx.createGain();
      master.gain.value = 0.0001;
      master.connect(ctx.destination);

      const osc1 = ctx.createOscillator();
      osc1.type = funMode ? 'sawtooth' : 'triangle';
      osc1.connect(master);

      let osc2: OscillatorNode | null = null;
      if (funMode) {
        osc2 = ctx.createOscillator();
        osc2.type = 'square';
        osc2.connect(master);
      }

      ctxRef.current = ctx;
      masterGainRef.current = master;
      osc1Ref.current = osc1;
      osc2Ref.current = osc2;

      // Start oscillators slightly in the future to avoid clicks.
      const t = ctx.currentTime + 0.01;
      osc1.start(t);
      osc2?.start(t);

      setState((s) => ({
        ...s,
        isPlaying: true,
        error: undefined,
      }));

      updateSynth();
    } catch (err) {
      setState((s) => ({ ...s, error: String(err) }));
    }
  }, [funMode, state.isPlaying, updateSynth]);

  const stopEngine = useCallback(() => {
    const ctx = ctxRef.current;
    const osc1 = osc1Ref.current;
    const osc2 = osc2Ref.current;
    const master = masterGainRef.current;

    try {
      const now = ctx?.currentTime ?? 0;
      if (master && ctx) {
        master.gain.setTargetAtTime(0.0001, now, 0.03);
      }
      osc1?.stop(now + 0.05);
      osc2?.stop(now + 0.05);
    } catch {
      // ignore
    }

    try {
      osc1?.disconnect();
      osc2?.disconnect();
      master?.disconnect();
    } catch {
      // ignore
    }

    osc1Ref.current = null;
    osc2Ref.current = null;
    masterGainRef.current = null;

    if (ctx) {
      // Close to release the audio thread; we’ll recreate on next start.
      void ctx.close().catch(() => {});
    }
    ctxRef.current = null;

    setState((s) => ({ ...s, isPlaying: false }));
  }, []);

  const setRpm = useCallback(
    (rpm: number) => {
      rpmRef.current = Number.isFinite(rpm) ? rpm : 0;
      setState((s) => ({ ...s, rpm: rpmRef.current }));
      if (state.isPlaying) updateSynth();
    },
    [state.isPlaying, updateSynth],
  );

  const setLoad = useCallback(
    (load: number) => {
      loadRef.current = clamp01(load);
      setState((s) => ({ ...s, load: loadRef.current }));
      if (state.isPlaying) updateSynth();
    },
    [state.isPlaying, updateSynth],
  );

  const playBeep = useCallback((freq: number = 600, seconds: number = 0.08) => {
    if (typeof window === 'undefined') return;
    const ctx = getAudioContext();
    if (!ctx) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    const f = clamp(freq, 80, 2000);
    const dur = clamp(seconds, 0.02, 1.0);
    osc.type = 'sine';
    osc.frequency.value = f;

    gain.gain.value = 0.0001;
    osc.connect(gain);
    gain.connect(ctx.destination);

    const t0 = ctx.currentTime + 0.001;
    gain.gain.setValueAtTime(0.0001, t0);
    gain.gain.exponentialRampToValueAtTime(0.12, t0 + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);

    osc.start(t0);
    osc.stop(t0 + dur + 0.02);

    // Clean up.
    setTimeout(() => {
      try {
        osc.disconnect();
        gain.disconnect();
      } catch {
        // ignore
      }
      void ctx.close().catch(() => {});
    }, Math.ceil((dur + 0.05) * 1000));
  }, []);

  // Keep synth parameters updated while playing.
  useEffect(() => {
    if (!state.isPlaying) return;
    updateSynth();
  }, [state.isPlaying, state.rpm, state.load, updateSynth]);

  // Stop on unmount.
  useEffect(() => {
    return () => stopEngine();
  }, [stopEngine]);

  return useMemo<AudioEngineApi>(
    () => ({
      playStartup: () => playUiSound('connect'),
      playShutdown: () => playUiSound('disconnect'),
      playSuccess: () => playUiSound('success'),
      playWarning: () => playUiSound('warning'),
      playBeep,
      setRpm,
      setLoad,
      startEngine,
      stopEngine,
      state,
      cylinders,
      funMode,
    }),
    [cylinders, funMode, playBeep, setLoad, setRpm, startEngine, stopEngine, state],
  );
}


