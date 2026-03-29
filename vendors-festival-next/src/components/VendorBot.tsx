"use client";

import { motion } from "framer-motion";

type VendorBotProps = {
  status: "active" | "offline";
  accent?: string;
  glow?: string;
  lookX?: number;
  lookY?: number;
};

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

export function VendorBot({ status, accent = "#FFB647", glow = "#ffd080", lookX = 0, lookY = 0 }: VendorBotProps) {
  const active = status === "active";
  const eyeX = clamp(lookX, -1, 1) * 1.35;
  const eyeY = clamp(lookY, -1, 1) * 1.1;

  return (
    <motion.div
      className="relative flex h-24 w-24 items-end justify-center"
      animate={{ y: [0, -4, 0], scale: [1, 1.015, 1] }}
      transition={{ repeat: Infinity, duration: 2.4, ease: "easeInOut" }}
    >
      {/* Warm aura behind mascot */}
      <motion.div
        className="pointer-events-none absolute bottom-1 h-14 w-16 rounded-full blur-md"
        style={{ background: `radial-gradient(ellipse, ${glow}88 0%, transparent 72%)` }}
        animate={{ opacity: [0.35, 0.75, 0.35] }}
        transition={{ duration: 2.3, repeat: Infinity, ease: "easeInOut" }}
      />

      <span
        className={`absolute -right-0.5 top-3 h-3.5 w-3.5 rounded-full ${
          active ? "bg-emerald-400 shadow-[0_0_16px_rgba(74,222,128,.95)]" : "bg-slate-500"
        }`}
      />

      {/* Tiny antenna with bead for extra personality */}
      <div className="absolute left-1/2 top-1 h-3 w-[1.5px] -translate-x-1/2 rounded-full bg-white/35" />
      <div className="absolute left-1/2 top-0 h-2 w-2 -translate-x-1/2 rounded-full" style={{ background: accent, boxShadow: `0 0 10px ${glow}` }} />

      {/* Tiny floating hands */}
      <motion.div
        className="absolute left-2 top-[46px] h-3 w-3 rounded-full border border-white/35"
        style={{ background: `linear-gradient(180deg, ${accent}99 0%, #2a1a0f 100%)` }}
        animate={{ y: [0, -2.5, 0], rotate: [0, -10, 0] }}
        transition={{ duration: 1.9, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute right-2 top-[46px] h-3 w-3 rounded-full border border-white/35"
        style={{ background: `linear-gradient(180deg, ${accent}99 0%, #2a1a0f 100%)` }}
        animate={{ y: [0, -2.5, 0], rotate: [0, 10, 0] }}
        transition={{ duration: 1.9, repeat: Infinity, ease: "easeInOut", delay: 0.2 }}
      />

      {/* Body: plush pill shape */}
      <div className="relative z-10 h-8 w-12 rounded-t-[18px] rounded-b-[14px] border border-white/20 bg-gradient-to-b from-[#2a1a0f] via-[#1a1008] to-[#100804] opacity-95 shadow-[0_6px_10px_rgba(0,0,0,0.28)]" />

      {/* Face */}
      <motion.div
        className="absolute top-2 z-20 h-12 w-12 rounded-full border border-white/50"
        style={{
          background: `radial-gradient(circle at 35% 30%, #fff9d6 0%, #ffe4a6 28%, ${accent} 72%, #8a4b18 100%)`,
          boxShadow: `0 0 18px ${glow}, inset 0 -4px 8px rgba(0,0,0,0.25)`,
        }}
        animate={{ boxShadow: [`0 0 12px ${glow}`, `0 0 22px ${glow}`, `0 0 12px ${glow}`] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
      >
        {/* Tiny plush ears */}
        <span className="absolute -left-[2px] top-[9px] h-[8px] w-[6px] rounded-full bg-[#f8d995] opacity-85" />
        <span className="absolute -right-[2px] top-[9px] h-[8px] w-[6px] rounded-full bg-[#f8d995] opacity-85" />

        {/* Eyes with directional pupils (follows cursor softly) */}
        <span className="absolute left-[12.5px] top-[14px] h-[6px] w-[6px] rounded-full bg-[#f9edcf]/95" />
        <span className="absolute right-[12.5px] top-[14px] h-[6px] w-[6px] rounded-full bg-[#f9edcf]/95" />
        <motion.span
          className="absolute left-[14px] top-[15.5px] h-[3px] w-[3px] rounded-full bg-[#3d2213]"
          animate={{ x: eyeX, y: eyeY }}
          transition={{ duration: 0.14, ease: "easeOut" }}
        />
        <motion.span
          className="absolute right-[14px] top-[15.5px] h-[3px] w-[3px] rounded-full bg-[#3d2213]"
          animate={{ x: eyeX, y: eyeY }}
          transition={{ duration: 0.14, ease: "easeOut" }}
        />
        <motion.span
          className="absolute left-[14.9px] top-[15.6px] h-[1px] w-[1px] rounded-full bg-white/90"
          animate={{ x: eyeX * 0.6, y: eyeY * 0.6 }}
          transition={{ duration: 0.14, ease: "easeOut" }}
        />
        <motion.span
          className="absolute right-[14.9px] top-[15.6px] h-[1px] w-[1px] rounded-full bg-white/90"
          animate={{ x: eyeX * 0.6, y: eyeY * 0.6 }}
          transition={{ duration: 0.14, ease: "easeOut" }}
        />

        {/* Nose + smile */}
        <span className="absolute left-1/2 top-[22px] h-[1.8px] w-[1.8px] -translate-x-1/2 rounded-full bg-[#6a3a1f]" />
        <span className="absolute left-1/2 top-[24px] h-[2px] w-[12px] -translate-x-1/2 rounded-full bg-[#5a311a]" />

        {/* Soft blush cheeks */}
        <span className="absolute left-[8px] top-[22px] h-[5px] w-[6px] rounded-full bg-[#ff9aaa]/45 blur-[0.3px]" />
        <span className="absolute right-[8px] top-[22px] h-[5px] w-[6px] rounded-full bg-[#ff9aaa]/45 blur-[0.3px]" />
      </motion.div>
    </motion.div>
  );
}
