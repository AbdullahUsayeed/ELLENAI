"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// D major pentatonic — bright, hopeful, Ghibli-esque
const FREQS = [
  146.83, // D3
  164.81, // E3
  184.99, // F#3
  220.00, // A3
  246.94, // B3
  293.66, // D4
  329.63, // E4
  369.99, // F#4
  440.00, // A4
  493.88, // B4
  587.33, // D5
  659.25, // E5
];

// 32-step phrase: intro motif → ascent → peak → descent → bass rise → wander → resolve
const MELODY = [
  5, 6, 5, 7,
  6, 8, 9, 8,
  10, 11, 10, 9,
  8, 7, 6, 5,
  3, 4, 5, 6,
  7, 6, 8, 7,
  5, 9, 8, 6,
  5, 0, 5, 5,
];

// Irregular onset spacings (seconds) — breathing rhythm
const SPACINGS = [
  0.50, 0.35, 0.70, 0.50,
  0.40, 0.35, 0.65, 0.90,
  0.50, 0.35, 0.70, 0.65,
  0.50, 0.35, 0.50, 0.85,
  0.70, 0.40, 0.35, 0.50,
  0.45, 0.65, 0.40, 0.70,
  0.50, 0.35, 0.65, 0.50,
  0.90, 1.40, 0.50, 0.50,
];

// Steps in MELODY that also trigger a quiet bass doubling
const BASS_STEPS = new Set([3, 7, 11, 15, 23, 28]);

// Alternate panning per note (gentle stereo movement)
const PAN = [-0.22, 0.22, -0.12, 0.18, -0.25, 0.10, -0.18, 0.22];

export function useAmbientAudio() {
  const [enabled, setEnabled] = useState(false);
  const [muted, setMuted] = useState(false);

  const ctxRef = useRef<AudioContext | null>(null);
  const masterRef = useRef<GainNode | null>(null);
  const schedulerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const nextNoteTimeRef = useRef(0);
  const noteIdxRef = useRef(0);
  const noiseSourceRef = useRef<AudioBufferSourceNode | null>(null);

  /** Build and wire the AudioContext + master gain once. */
  const initCtx = useCallback((): AudioContext => {
    if (ctxRef.current) return ctxRef.current;
    const ctx = new AudioContext();
    const master = ctx.createGain();
    master.gain.value = 1;
    master.connect(ctx.destination);
    ctxRef.current = ctx;
    masterRef.current = master;
    return ctx;
  }, []);

  /** Layer 2 — brown noise (wind/crowd murmur) + cricket-like modulation. */
  const startAmbient = useCallback((ctx: AudioContext, master: GainNode) => {
    const rate = ctx.sampleRate;
    const len = rate * 6;
    const buf = ctx.createBuffer(1, len, rate);
    const data = buf.getChannelData(0);

    let last = 0;
    for (let i = 0; i < len; i++) {
      const w = Math.random() * 2 - 1;
      data[i] = (last + 0.02 * w) / 1.02;
      last = data[i];
    }

    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.loop = true;

    const wind = ctx.createBiquadFilter();
    wind.type = "lowpass";
    wind.frequency.value = 220;

    const cricket = ctx.createBiquadFilter();
    cricket.type = "bandpass";
    cricket.frequency.value = 3400;
    cricket.Q.value = 1.8;

    const cricketGain = ctx.createGain();
    cricketGain.gain.value = 0.13;

    const lfo = ctx.createOscillator();
    const lfoGain = ctx.createGain();
    lfo.frequency.value = 5.5;
    lfoGain.gain.value = 0.06;
    lfo.connect(lfoGain);
    lfoGain.connect(cricketGain.gain);
    lfo.start();

    const windGain = ctx.createGain();
    windGain.gain.value = 0.22;

    src.connect(wind);
    wind.connect(windGain);
    windGain.connect(master);

    src.connect(cricket);
    cricket.connect(cricketGain);
    cricketGain.connect(master);

    src.start();
    noiseSourceRef.current = src;
  }, []);

  /** Play a single piano voice: layered harmonics + optional bass double + panning. */
  const playVoice = useCallback((
    ctx: AudioContext,
    master: GainNode,
    freq: number,
    t: number,
    gainPeak: number,
    decayTime: number,
    pan: number,
  ) => {
    const panner = ctx.createStereoPanner();
    panner.pan.value = pan;
    panner.connect(master);

    // Primary tone — warm sine
    const osc1 = ctx.createOscillator();
    const env1 = ctx.createGain();
    osc1.type = "sine";
    osc1.frequency.value = freq;
    osc1.connect(env1); env1.connect(panner);
    env1.gain.setValueAtTime(0, t);
    env1.gain.linearRampToValueAtTime(gainPeak, t + 0.018);
    env1.gain.exponentialRampToValueAtTime(0.0001, t + decayTime);
    osc1.start(t); osc1.stop(t + decayTime);

    // 2nd harmonic — adds brightness (piano string resonance)
    const osc2 = ctx.createOscillator();
    const env2 = ctx.createGain();
    osc2.type = "sine";
    osc2.frequency.value = freq * 2;
    osc2.connect(env2); env2.connect(panner);
    env2.gain.setValueAtTime(0, t);
    env2.gain.linearRampToValueAtTime(gainPeak * 0.28, t + 0.014);
    env2.gain.exponentialRampToValueAtTime(0.0001, t + decayTime * 0.55);
    osc2.start(t); osc2.stop(t + decayTime * 0.55);

    // 3rd harmonic — subtle shimmer (inharmonic, gives life)
    const osc3 = ctx.createOscillator();
    const env3 = ctx.createGain();
    osc3.type = "sine";
    osc3.frequency.value = freq * 3.02; // slightly sharp = lively
    osc3.connect(env3); env3.connect(panner);
    env3.gain.setValueAtTime(0, t);
    env3.gain.linearRampToValueAtTime(gainPeak * 0.10, t + 0.010);
    env3.gain.exponentialRampToValueAtTime(0.0001, t + decayTime * 0.30);
    osc3.start(t); osc3.stop(t + decayTime * 0.30);
  }, []);

  /** Layer 1 — melodic piano scheduler. */
  const scheduleNote = useCallback((ctx: AudioContext, master: GainNode) => {
    const step = noteIdxRef.current % MELODY.length;
    const freq = FREQS[MELODY[step]];
    const spacing = SPACINGS[step];
    const pan = PAN[noteIdxRef.current % PAN.length];
    noteIdxRef.current++;

    const t = nextNoteTimeRef.current;
    playVoice(ctx, master, freq, t, 0.072, 2.8, pan);

    // Occasional quiet bass double — adds warmth and depth
    if (BASS_STEPS.has(step)) {
      playVoice(ctx, master, freq * 0.5, t + 0.01, 0.038, 3.5, -pan * 0.5);
    }

    nextNoteTimeRef.current += spacing;
  }, [playVoice]);

  const startPiano = useCallback((ctx: AudioContext, master: GainNode) => {
    nextNoteTimeRef.current = ctx.currentTime + 0.15;
    const tick = () => {
      while (nextNoteTimeRef.current < ctx.currentTime + 0.5) {
        scheduleNote(ctx, master);
      }
    };
    tick();
    schedulerRef.current = setInterval(tick, 100);
  }, [scheduleNote]);

  /** Tear down everything except the context itself. */
  const stopAll = useCallback(() => {
    if (schedulerRef.current) {
      clearInterval(schedulerRef.current);
      schedulerRef.current = null;
    }
    try { noiseSourceRef.current?.stop(); } catch {}
    noiseSourceRef.current = null;
  }, []);

  useEffect(() => {
    if (!enabled) return;
    const ctx = initCtx();
    const master = masterRef.current!;
    if (ctx.state === "suspended") ctx.resume();
    startAmbient(ctx, master);
    startPiano(ctx, master);
    return stopAll;
  }, [enabled, initCtx, startAmbient, startPiano, stopAll]);

  useEffect(() => {
    const ctx = ctxRef.current;
    const master = masterRef.current;
    if (!ctx || !master) return;
    master.gain.setTargetAtTime(muted ? 0 : 1, ctx.currentTime, 0.25);
  }, [muted]);

  const start = useCallback(() => setEnabled(true), []);
  const toggleMute = useCallback(() => setMuted((p) => !p), []);

  /** Layer 3b — soft marimba tap on tent hover. */
  const playTap = useCallback(() => {
    if (!enabled || muted) return;
    const ctx = ctxRef.current;
    const master = masterRef.current;
    if (!ctx || !master) return;
    if (ctx.state === "suspended") ctx.resume();

    const noteFreqs = [261.63, 293.66, 329.63, 392, 440];
    const freq = noteFreqs[Math.floor(Math.random() * noteFreqs.length)];
    const t = ctx.currentTime;

    const osc = ctx.createOscillator();
    const env = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    osc.connect(env); env.connect(master);
    env.gain.setValueAtTime(0, t);
    env.gain.linearRampToValueAtTime(0.07, t + 0.008);
    env.gain.exponentialRampToValueAtTime(0.0001, t + 0.45);
    osc.start(t); osc.stop(t + 0.45);

    const osc2 = ctx.createOscillator();
    const env2 = ctx.createGain();
    osc2.type = "sine";
    osc2.frequency.value = freq * 2.76;
    osc2.connect(env2); env2.connect(master);
    env2.gain.setValueAtTime(0, t);
    env2.gain.linearRampToValueAtTime(0.022, t + 0.006);
    env2.gain.exponentialRampToValueAtTime(0.0001, t + 0.18);
    osc2.start(t); osc2.stop(t + 0.18);
  }, [enabled, muted]);

  return { enabled, muted, start, toggleMute, playShimmer: playTap, playTap };
}
