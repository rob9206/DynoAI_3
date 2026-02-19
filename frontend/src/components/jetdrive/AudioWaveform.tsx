/**
 * AudioWaveform - Real-time audio visualization component
 * 
 * Displays:
 * - Waveform oscilloscope view
 * - Frequency spectrum (FFT) with knock frequency range highlighted
 * - Volume meter
 */

import { useRef, useEffect, useCallback, useState } from 'react';
import { motion } from 'framer-motion';

interface AudioWaveformProps {
  /** Waveform data (time domain) */
  waveform: Float32Array | null;
  /** Frequency data (FFT) */
  frequencies: Float32Array | null;
  /** Current volume level (0-1) */
  volume: number;
  /** Is knock currently detected */
  knockDetected: boolean;
  /** Component height in pixels */
  height?: number;
  /** Show frequency spectrum view */
  showSpectrum?: boolean;
  /** Waveform color */
  waveformColor?: string;
  /** Spectrum color */
  spectrumColor?: string;
  /** Knock highlight color */
  knockColor?: string;
}

// Constants for knock frequency visualization
const SAMPLE_RATE = 44100;
const KNOCK_FREQ_MIN = 5000;
const KNOCK_FREQ_MAX = 15000;

export function AudioWaveform({
  waveform,
  frequencies,
  volume,
  knockDetected,
  height = 120,
  showSpectrum = true,
  waveformColor = '#22d3ee',
  spectrumColor = '#4ade80',
  knockColor = '#f97316',
}: AudioWaveformProps) {
  const waveformCanvasRef = useRef<HTMLCanvasElement>(null);
  const spectrumCanvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number | null>(null);
  
  // Store latest data in refs for animation frame
  const waveformRef = useRef(waveform);
  const frequenciesRef = useRef(frequencies);
  
  useEffect(() => {
    waveformRef.current = waveform;
    frequenciesRef.current = frequencies;
  }, [waveform, frequencies]);
  
  // Draw waveform
  const drawWaveform = useCallback(() => {
    const canvas = waveformCanvasRef.current;
    const data = waveformRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    const { width, height: canvasHeight } = canvas;
    const centerY = canvasHeight / 2;
    
    // Clear canvas
    ctx.fillStyle = 'rgba(0, 0, 0, 0.1)';
    ctx.fillRect(0, 0, width, canvasHeight);
    
    // Draw center line
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, centerY);
    ctx.lineTo(width, centerY);
    ctx.stroke();
    
    if (!data || data.length === 0) {
      // Draw flat line when no data
      ctx.strokeStyle = waveformColor;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, centerY);
      ctx.lineTo(width, centerY);
      ctx.stroke();
      return;
    }
    
    // Draw waveform
    ctx.strokeStyle = knockDetected ? knockColor : waveformColor;
    ctx.lineWidth = 2;
    ctx.beginPath();
    
    const sliceWidth = width / data.length;
    let x = 0;
    
    for (let i = 0; i < data.length; i++) {
      const y = centerY + data[i] * centerY * 0.9;
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
      x += sliceWidth;
    }
    
    ctx.stroke();
    
    // Add glow effect when knock detected
    if (knockDetected) {
      ctx.shadowColor = knockColor;
      ctx.shadowBlur = 10;
      ctx.stroke();
      ctx.shadowBlur = 0;
    }
  }, [waveformColor, knockColor, knockDetected]);
  
  // Draw frequency spectrum
  const drawSpectrum = useCallback(() => {
    const canvas = spectrumCanvasRef.current;
    const data = frequenciesRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    const { width, height: canvasHeight } = canvas;
    
    // Clear canvas
    ctx.fillStyle = 'rgba(0, 0, 0, 0.15)';
    ctx.fillRect(0, 0, width, canvasHeight);
    
    if (!data || data.length === 0) return;
    
    // Calculate frequency bins
    const binCount = data.length;
    const binWidth = (SAMPLE_RATE / 2) / binCount;
    const knockMinBin = Math.floor(KNOCK_FREQ_MIN / binWidth);
    const knockMaxBin = Math.ceil(KNOCK_FREQ_MAX / binWidth);
    
    // We'll show frequencies up to ~20kHz (most of audible range)
    const maxFreq = 20000;
    const binsToShow = Math.min(binCount, Math.ceil(maxFreq / binWidth));
    const barWidth = width / binsToShow;
    
    // Draw bars
    for (let i = 0; i < binsToShow; i++) {
      // Convert dB to linear scale (data is in dB, typically -100 to 0)
      const db = data[i];
      const normalizedDb = (db + 100) / 100; // Normalize -100..0 to 0..1
      const barHeight = Math.max(0, normalizedDb * canvasHeight);
      
      // Highlight knock frequency range
      const isKnockRange = i >= knockMinBin && i <= knockMaxBin;
      
      if (isKnockRange) {
        ctx.fillStyle = knockDetected 
          ? knockColor 
          : `rgba(249, 115, 22, ${0.3 + normalizedDb * 0.7})`;
      } else {
        ctx.fillStyle = `rgba(74, 222, 128, ${0.2 + normalizedDb * 0.8})`;
      }
      
      ctx.fillRect(
        i * barWidth,
        canvasHeight - barHeight,
        barWidth - 1,
        barHeight
      );
    }
    
    // Draw knock range overlay
    const knockStartX = (knockMinBin / binsToShow) * width;
    const knockEndX = (knockMaxBin / binsToShow) * width;
    
    ctx.strokeStyle = 'rgba(249, 115, 22, 0.5)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.strokeRect(knockStartX, 0, knockEndX - knockStartX, canvasHeight);
    ctx.setLineDash([]);
    
    // Label knock range
    ctx.fillStyle = 'rgba(249, 115, 22, 0.8)';
    ctx.font = '10px monospace';
    ctx.fillText('Knock Range', knockStartX + 4, 12);
  }, [spectrumColor, knockColor, knockDetected]);
  
  // Animation loop
  useEffect(() => {
    const animate = () => {
      drawWaveform();
      if (showSpectrum) {
        drawSpectrum();
      }
      animationFrameRef.current = requestAnimationFrame(animate);
    };
    
    animate();
    
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [drawWaveform, drawSpectrum, showSpectrum]);
  
  // Handle canvas resize
  useEffect(() => {
    const resizeCanvas = (canvas: HTMLCanvasElement | null) => {
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * window.devicePixelRatio;
      canvas.height = rect.height * window.devicePixelRatio;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
      }
    };
    
    resizeCanvas(waveformCanvasRef.current);
    resizeCanvas(spectrumCanvasRef.current);
    
    const handleResize = () => {
      resizeCanvas(waveformCanvasRef.current);
      resizeCanvas(spectrumCanvasRef.current);
    };
    
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);
  
  return (
    <div className="space-y-3">
      {/* Waveform display */}
      <div className="relative">
        <div className="absolute top-2 left-2 flex items-center gap-2 z-10">
          <span className="text-xs font-mono text-muted-foreground">WAVEFORM</span>
          {knockDetected && (
            <motion.span
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="px-2 py-0.5 bg-orange-500/20 border border-orange-500/50 rounded text-xs font-bold text-orange-400"
            >
              KNOCK!
            </motion.span>
          )}
        </div>
        <canvas
          ref={waveformCanvasRef}
          style={{ width: '100%', height: height }}
          className="rounded-lg bg-black/40 border border-white/10"
        />
        
        {/* Volume meter */}
        <div className="absolute right-2 top-2 bottom-2 w-2 rounded-full bg-black/40 overflow-hidden">
          <motion.div
            className="absolute bottom-0 left-0 right-0 rounded-full"
            style={{
              backgroundColor: volume > 0.8 ? '#ef4444' : volume > 0.5 ? '#f59e0b' : '#22c55e',
            }}
            animate={{ height: `${Math.min(volume * 100 * 3, 100)}%` }}
            transition={{ duration: 0.05 }}
          />
        </div>
      </div>
      
      {/* Frequency spectrum */}
      {showSpectrum && (
        <div className="relative">
          <div className="absolute top-2 left-2 z-10">
            <span className="text-xs font-mono text-muted-foreground">FREQUENCY SPECTRUM</span>
          </div>
          <canvas
            ref={spectrumCanvasRef}
            style={{ width: '100%', height: height * 0.8 }}
            className="rounded-lg bg-black/40 border border-white/10"
          />
          
          {/* Frequency scale */}
          <div className="flex justify-between text-[10px] font-mono text-muted-foreground mt-1 px-1">
            <span>0Hz</span>
            <span>5kHz</span>
            <span>10kHz</span>
            <span>15kHz</span>
            <span>20kHz</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default AudioWaveform;

