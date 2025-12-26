export type UiSoundKind =
  | "click"
  | "pull"
  | "success"
  | "error"
  | "warning"
  | "info"
  | "connect"
  | "disconnect";

type UiSoundSettings = {
  enabled: boolean;
  volume: number; // 0..1
};

const SETTINGS_KEY = "dynoai.ui_sounds.v1";
const DEFAULT_SETTINGS: UiSoundSettings = { enabled: true, volume: 0.18 };

function clamp01(n: number) {
  if (Number.isNaN(n)) return 0;
  return Math.min(1, Math.max(0, n));
}

function safeParseSettings(raw: string | null): UiSoundSettings | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<UiSoundSettings>;
    if (typeof parsed !== "object" || parsed === null) return null;
    const enabled = typeof parsed.enabled === "boolean" ? parsed.enabled : DEFAULT_SETTINGS.enabled;
    const volume = typeof parsed.volume === "number" ? clamp01(parsed.volume) : DEFAULT_SETTINGS.volume;
    return { enabled, volume };
  } catch {
    return null;
  }
}

function readSettings(): UiSoundSettings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  const parsed = safeParseSettings(window.localStorage.getItem(SETTINGS_KEY));
  return parsed ?? DEFAULT_SETTINGS;
}

function writeSettings(next: UiSoundSettings) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(next));
  window.dispatchEvent(new CustomEvent("dynoai:ui-sounds", { detail: next }));
}

let audioCtx: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctx) return null;

  if (!audioCtx) {
    audioCtx = new Ctx();
  }
  return audioCtx;
}

function tryResumeAudioContext(ctx: AudioContext) {
  // Important: do NOT await this. Some browsers require resume() to be called
  // synchronously during a user gesture, and awaiting can break that chain.
  if (ctx.state === "suspended") {
    try {
      void ctx.resume();
    } catch {
      // ignore
    }
  }
}

type Tone = {
  freq: number;
  ms: number;
  type?: OscillatorType;
  gain?: number;
};

function playToneSequence(ctx: AudioContext, tones: Tone[], masterVolume: number) {
  const startAt = ctx.currentTime + 0.001;
  let t = startAt;

  for (const tone of tones) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = tone.type ?? "sine";
    osc.frequency.setValueAtTime(tone.freq, t);

    const v = clamp01((tone.gain ?? 1) * masterVolume);
    // gentle envelope to avoid clicks
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(Math.max(0.0002, v), t + 0.006);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + tone.ms / 1000);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(t);
    osc.stop(t + tone.ms / 1000 + 0.01);

    t += tone.ms / 1000;
  }
}

function pattern(kind: UiSoundKind): Tone[] {
  switch (kind) {
    case "click":
      return [{ freq: 880, ms: 22, type: "sine", gain: 0.7 }];
    case "pull":
      // short "launch" chirp (distinct from click)
      return [
        { freq: 330, ms: 45, type: "sine", gain: 0.7 },
        { freq: 494, ms: 55, type: "sine", gain: 0.85 },
        { freq: 740, ms: 70, type: "sine", gain: 0.95 },
      ];
    case "success":
      return [
        { freq: 660, ms: 70, type: "sine", gain: 0.9 },
        { freq: 990, ms: 80, type: "sine", gain: 1.0 },
      ];
    case "error":
      return [
        { freq: 220, ms: 120, type: "square", gain: 0.7 },
        { freq: 196, ms: 140, type: "square", gain: 0.6 },
      ];
    case "warning":
      return [
        { freq: 523.25, ms: 90, type: "triangle", gain: 0.8 },
        { freq: 392, ms: 110, type: "triangle", gain: 0.7 },
      ];
    case "info":
      return [{ freq: 587.33, ms: 85, type: "sine", gain: 0.75 }];
    case "connect":
      return [
        { freq: 440, ms: 60, type: "sine", gain: 0.8 },
        { freq: 659.25, ms: 80, type: "sine", gain: 0.9 },
      ];
    case "disconnect":
      return [
        { freq: 659.25, ms: 70, type: "sine", gain: 0.8 },
        { freq: 440, ms: 90, type: "sine", gain: 0.8 },
      ];
    default:
      return [];
  }
}

export function getUiSoundsEnabled() {
  return readSettings().enabled;
}

export function setUiSoundsEnabled(enabled: boolean) {
  const prev = readSettings();
  writeSettings({ ...prev, enabled });
}

export function toggleUiSoundsEnabled() {
  const prev = readSettings();
  const next = { ...prev, enabled: !prev.enabled };
  writeSettings(next);
  return next.enabled;
}

export function setUiSoundsVolume(volume: number) {
  const prev = readSettings();
  writeSettings({ ...prev, volume: clamp01(volume) });
}

export function getUiSoundsSettings(): UiSoundSettings {
  return readSettings();
}

export function playUiSound(kind: UiSoundKind) {
  const settings = readSettings();
  if (!settings.enabled) return;
  if (settings.volume <= 0) return;

  const ctx = getAudioContext();
  if (!ctx) return;

  tryResumeAudioContext(ctx);
  // Schedule immediately; if resume completes slightly after, the scheduled tones will still play.
  playToneSequence(ctx, pattern(kind), settings.volume);
}


