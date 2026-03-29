"use client";

import { motion } from "framer-motion";

// Night bazaar — restrained palette: gold, amber, crimson, neon blue only
const NIGHT_LANTERNS = [
  { x: 95,   color: "#FFB647", glow: "#ffcc70", sz: 1.00 },
  { x: 235,  color: "#C0243C", glow: "#ff5070", sz: 0.88 },
  { x: 385,  color: "#FFB647", glow: "#ffd080", sz: 1.00 },
  { x: 540,  color: "#2C8EFF", glow: "#70c0ff", sz: 0.88 },
  { x: 700,  color: "#FFB647", glow: "#ffcc70", sz: 1.05 },
  { x: 855,  color: "#C0243C", glow: "#ff5070", sz: 0.88 },
  { x: 1005, color: "#FFB647", glow: "#ffd080", sz: 1.00 },
  { x: 1155, color: "#2C8EFF", glow: "#70c0ff", sz: 0.88 },
  { x: 1305, color: "#FFB647", glow: "#ffcc70", sz: 1.00 },
  { x: 1455, color: "#C0243C", glow: "#ff5070", sz: 0.88 },
];

// Twinkling star field
const STARS = Array.from({ length: 88 }, (_, i) => ({
  cx: (i * 173 + 47) % 1600,
  cy: (i * 107 + 23) % 340,
  r:  i % 11 === 0 ? 1.7 : i % 5 === 0 ? 1.1 : 0.7,
  delay: (i % 7) * 0.38,
  dur:   2.4 + (i % 5) * 0.55,
  baseOpacity: 0.12 + (i % 6) * 0.07,
}));

export function FestivalBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden">

      {/* ── Midnight sky ── */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(178deg, #04060F 0%, #080C1E 28%, #0E0B24 58%, #130921 82%, #0C0612 100%)",
        }}
      />

      {/* Purple-indigo nebula wisps */}
      <div
        className="absolute left-[18%] top-0 h-[320px] w-[680px] opacity-[0.22]"
        style={{
          background: "radial-gradient(ellipse at center, #2A1060 0%, transparent 65%)",
          filter: "blur(55px)",
        }}
      />
      <div
        className="absolute right-[14%] top-12 h-[240px] w-[480px] opacity-[0.13]"
        style={{
          background: "radial-gradient(ellipse at center, #1A0840 0%, transparent 70%)",
          filter: "blur(75px)",
        }}
      />

      {/* ── Star field ── */}
      <svg
        viewBox="0 0 1600 360"
        className="absolute left-0 top-0 w-full"
        style={{ height: "56%" }}
        aria-hidden="true"
        preserveAspectRatio="none"
      >
        {STARS.map((s, i) => (
          <motion.circle
            key={i}
            cx={s.cx}
            cy={s.cy}
            r={s.r}
            fill="white"
            initial={{ opacity: s.baseOpacity }}
            animate={{ opacity: [s.baseOpacity, s.baseOpacity * 0.3, s.baseOpacity] }}
            transition={{ duration: s.dur, repeat: Infinity, delay: s.delay, ease: "easeInOut" }}
          />
        ))}
      </svg>

      {/* ── Ground fog ── */}
      <div
        className="absolute bottom-0 h-44 w-full"
        style={{
          background:
            "linear-gradient(0deg, rgba(6,5,16,0.92) 0%, rgba(12,9,24,0.48) 58%, transparent 100%)",
        }}
      />
      <motion.div
        className="absolute bottom-14 left-0 h-28 w-full"
        style={{
          background: "radial-gradient(ellipse 85% 90% at 50% 100%, rgba(36,18,60,0.55) 0%, transparent 70%)",
          filter: "blur(18px)",
        }}
        animate={{ opacity: [0.30, 0.46, 0.30] }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* ── Warm ambient glow pools (simulating tent light on ground) ── */}
      <div
        className="absolute bottom-0 left-[10%] h-52 w-60 opacity-[0.22]"
        style={{
          background: "radial-gradient(ellipse, #E88C1A 0%, transparent 70%)",
          filter: "blur(32px)",
        }}
      />
      <div
        className="absolute bottom-0 left-[44%] h-60 w-72 opacity-[0.26]"
        style={{
          background: "radial-gradient(ellipse, #FFB647 0%, transparent 70%)",
          filter: "blur(24px)",
        }}
      />
      <div
        className="absolute bottom-0 right-[10%] h-52 w-60 opacity-[0.18]"
        style={{
          background: "radial-gradient(ellipse, #C0243C 0%, transparent 70%)",
          filter: "blur(38px)",
        }}
      />

      {/* ── Lantern rope ── */}
      <svg
        viewBox="0 0 1600 116"
        className="absolute left-0 top-0 w-full"
        style={{ height: "116px" }}
        aria-hidden="true"
        preserveAspectRatio="none"
      >
        <defs>
          {NIGHT_LANTERNS.map((l) => (
            <radialGradient key={`nlg-${l.x}`} id={`nlg-${l.x}`} cx="50%" cy="32%" r="62%">
              <stop offset="0%"   stopColor={l.glow}  stopOpacity="1" />
              <stop offset="100%" stopColor={l.color} stopOpacity="0.72" />
            </radialGradient>
          ))}
        </defs>

        {/* Rope catenary */}
        <path
          d="M-10 50 Q240 66 460 46 Q700 24 800 50 Q920 76 1120 48 Q1340 20 1610 50"
          fill="none"
          stroke="rgba(130,95,38,0.42)"
          strokeWidth="1.6"
        />

        {/* Lanterns */}
        {NIGHT_LANTERNS.map((l, i) => {
          const yRope = 50 + Math.sin((l.x / 1600) * Math.PI * 2.2) * 14;
          const sc = l.sz;
          return (
            <motion.g
              key={`nl-${l.x}`}
              animate={{ rotate: [0, i % 2 === 0 ? 3.8 : -3.8, 0] }}
              transition={{ duration: 3.8 + (i % 5) * 0.65, repeat: Infinity, ease: "easeInOut", delay: i * 0.15 }}
              style={{ transformOrigin: `${l.x}px ${yRope}px` }}
            >
              {/* Drop string */}
              <line x1={l.x} y1={yRope} x2={l.x} y2={yRope + 11 * sc} stroke="rgba(130,95,38,0.42)" strokeWidth="1" />
              {/* Outer corona */}
              <motion.ellipse
                cx={l.x} cy={yRope + 27 * sc} rx={20 * sc} ry={26 * sc}
                fill={l.glow}
                animate={{ opacity: [0.07, 0.20, 0.07] }}
                transition={{ duration: 1.9 + i * 0.22, repeat: Infinity, ease: "easeInOut" }}
              />
              {/* Top cap */}
              <rect x={l.x - 5.5 * sc} y={yRope + 10 * sc} width={11 * sc} height={4 * sc} rx={2 * sc} fill="rgba(55,34,8,0.88)" />
              {/* Body */}
              <rect x={l.x - 7 * sc} y={yRope + 13 * sc} width={14 * sc} height={22 * sc} rx={4.5 * sc} fill={`url(#nlg-${l.x})`} />
              {/* Inner flicker */}
              <motion.rect
                x={l.x - 3.8 * sc} y={yRope + 16 * sc} width={7.6 * sc} height={15 * sc} rx={2.5 * sc}
                fill="rgba(255,238,180,0.68)"
                animate={{ opacity: [0.45, 1, 0.45] }}
                transition={{ duration: 1.1 + (i % 4) * 0.28, repeat: Infinity, ease: "easeInOut" }}
              />
              {/* Bottom cap */}
              <rect x={l.x - 5.5 * sc} y={yRope + 34 * sc} width={11 * sc} height={3.5 * sc} rx={1.8 * sc} fill="rgba(55,34,8,0.88)" />
              {/* Tassel */}
              <line x1={l.x} y1={yRope + 37.5 * sc} x2={l.x} y2={yRope + 48 * sc} stroke={l.color} strokeWidth="1.6" opacity="0.85" />
              <circle cx={l.x} cy={yRope + 50 * sc} r={2.8 * sc} fill={l.color} opacity="0.92" />
            </motion.g>
          );
        })}
      </svg>

      {/* ── Floating embers / dust ── */}
      {[6, 17, 30, 47, 62, 76, 88].map((left, i) => (
        <motion.div
          key={`ember-${i}`}
          className="pointer-events-none absolute rounded-full"
          style={{
            left: `${left}%`,
            bottom: `${8 + (i % 4) * 12}%`,
            width:  i % 3 === 0 ? "3px" : "2px",
            height: i % 3 === 0 ? "3px" : "2px",
            background: i % 2 === 0 ? "#FFB647" : "#E88C1A",
            opacity: 0,
          }}
          animate={{ y: [0, -110, -260], opacity: [0, 0.55, 0], x: [0, i % 2 === 0 ? 20 : -18] }}
          transition={{ duration: 7.5 + i * 1.3, repeat: Infinity, delay: i * 2.2, ease: "easeOut" }}
        />
      ))}
    </div>
  );
}
