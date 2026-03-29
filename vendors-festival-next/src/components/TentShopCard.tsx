"use client";

import { motion } from "framer-motion";
import type { Vendor } from "@/data/vendors";
import { VendorBot } from "@/components/VendorBot";

type TentShopCardProps = {
  vendor: Vendor;
  onOpenChat: (vendor: Vendor) => void;
  mood: "fashion" | "electronics" | "food" | "wellness" | "jewelry" | "home";
  variant: number;
};

type MoodTheme = {
  sign: string;
  accent: string;
  glow: string;
  roofDark: string;
  roofMid: string;
  innerGlow: string;
  floor: string;
  shelf: string;
  productIcon: string;
};

const MOOD_THEMES: Record<TentShopCardProps["mood"], MoodTheme> = {
  fashion:     { sign: "Fashion Edit",  accent: "#C0243C", glow: "#ff5070", roofDark: "#4A0812", roofMid: "#8C1520", innerGlow: "rgba(192,36,60,0.26)",   floor: "radial-gradient(ellipse at 50% 0%, rgba(192,36,60,0.22) 0%, rgba(0,0,0,0) 72%)",   shelf: "#1A0C10", productIcon: "hanger" },
  electronics: { sign: "Tech Hub",      accent: "#2C8EFF", glow: "#72c4ff", roofDark: "#071860", roofMid: "#1240B0", innerGlow: "rgba(44,142,255,0.20)",  floor: "radial-gradient(ellipse at 50% 0%, rgba(44,142,255,0.18) 0%, rgba(0,0,0,0) 72%)",  shelf: "#080E20", productIcon: "chip"   },
  food:        { sign: "Snack Bar",     accent: "#E88C1A", glow: "#ffc060", roofDark: "#6A3008", roofMid: "#B46015", innerGlow: "rgba(232,140,26,0.30)",  floor: "radial-gradient(ellipse at 50% 0%, rgba(232,140,26,0.24) 0%, rgba(0,0,0,0) 72%)",  shelf: "#1A1008", productIcon: "cup"    },
  wellness:    { sign: "Ritual Corner", accent: "#0FA29A", glow: "#40e8e0", roofDark: "#063830", roofMid: "#0A8870", innerGlow: "rgba(15,162,154,0.22)",  floor: "radial-gradient(ellipse at 50% 0%, rgba(15,162,154,0.18) 0%, rgba(0,0,0,0) 72%)",  shelf: "#061814", productIcon: "drop"   },
  jewelry:     { sign: "Gem Counter",   accent: "#C8941A", glow: "#ffe080", roofDark: "#4A3408", roofMid: "#A07818", innerGlow: "rgba(200,148,26,0.26)",  floor: "radial-gradient(ellipse at 50% 0%, rgba(200,148,26,0.22) 0%, rgba(0,0,0,0) 72%)",  shelf: "#1A1408", productIcon: "gem"    },
  home:        { sign: "Home Finds",    accent: "#C06830", glow: "#ffa860", roofDark: "#441808", roofMid: "#904020", innerGlow: "rgba(192,104,48,0.24)",  floor: "radial-gradient(ellipse at 50% 0%, rgba(192,104,48,0.20) 0%, rgba(0,0,0,0) 72%)",  shelf: "#180E08", productIcon: "vase"   },
};

const ROOF_PATHS = [
  "M30 132 L170 22 L310 132 Z",
  "M30 132 Q170 14 310 132 Z",
  "M30 132 L102 74 L170 28 L238 74 L310 132 Z"
];

const INNER_ROOF_PATHS = [
  "M56 145 L170 58 L284 145 Z",
  "M56 145 Q170 52 284 145 Z",
  "M56 145 L118 94 L170 62 L222 94 L284 145 Z"
];

const LANTERN_LAYOUTS = [
  [76, 122, 174, 226, 272],
  [92, 146, 202, 256],
  [62, 108, 154, 200, 246, 292]
];

function iconForProduct(kind: MoodTheme["productIcon"], color: string) {
  switch (kind) {
    case "hanger":
      return (
        <svg viewBox="0 0 40 30" className="h-5 w-7" aria-hidden="true">
          <path d="M17 7a3 3 0 1 1 6 0c0 1-1 2-2 3l7 6H12l7-6" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" />
          <path d="M7 18h26l-5 7H12z" fill="none" stroke={color} strokeWidth="2" />
        </svg>
      );
    case "chip":
      return (
        <svg viewBox="0 0 40 30" className="h-5 w-7" aria-hidden="true">
          <rect x="10" y="7" width="20" height="16" rx="3" fill="none" stroke={color} strokeWidth="2" />
          <rect x="16" y="12" width="8" height="6" rx="1" fill="none" stroke={color} strokeWidth="2" />
        </svg>
      );
    case "cup":
      return (
        <svg viewBox="0 0 40 30" className="h-5 w-7" aria-hidden="true">
          <path d="M12 8h16l-2 13H14z" fill="none" stroke={color} strokeWidth="2" />
          <path d="M27 11h4a3 3 0 0 1 0 6h-3" fill="none" stroke={color} strokeWidth="2" />
        </svg>
      );
    case "drop":
      return (
        <svg viewBox="0 0 40 30" className="h-5 w-7" aria-hidden="true">
          <path d="M20 6c4 6 6 8 6 11a6 6 0 1 1-12 0c0-3 2-5 6-11z" fill="none" stroke={color} strokeWidth="2" />
        </svg>
      );
    case "gem":
      return (
        <svg viewBox="0 0 40 30" className="h-5 w-7" aria-hidden="true">
          <path d="M10 12l4-5h12l4 5-10 11z" fill="none" stroke={color} strokeWidth="2" />
          <path d="M20 7v16" fill="none" stroke={color} strokeWidth="1.6" />
        </svg>
      );
    default:
      return (
        <svg viewBox="0 0 40 30" className="h-5 w-7" aria-hidden="true">
          <path d="M20 7c4 0 7 3 7 7v9H13v-9c0-4 3-7 7-7z" fill="none" stroke={color} strokeWidth="2" />
          <path d="M17 23v-4m6 4v-4" fill="none" stroke={color} strokeWidth="2" />
        </svg>
      );
  }
}

export function TentShopCard({ vendor, onOpenChat, mood, variant }: TentShopCardProps) {
  const [c0, c1] = vendor.canopy;
  const id = vendor.id;
  const theme = MOOD_THEMES[mood];
  const shape = variant % 3;
  const roofPath = ROOF_PATHS[shape];
  const innerRoofPath = INNER_ROOF_PATHS[shape];
  const lanterns = LANTERN_LAYOUTS[shape];
  const tasselColors = [c0, theme.accent, c1, theme.accent, c0, theme.accent];
  const productPreview = vendor.products.slice(0, 3);

  return (
    <motion.article
      onClick={() => onOpenChat(vendor)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpenChat(vendor);
        }
      }}
      role="button"
      tabIndex={0}
      aria-label={`Enter ${vendor.name}`}
      whileHover={{ y: -8, scale: 1.02 }}
      transition={{ type: "spring", stiffness: 160, damping: 20 }}
      className="group relative isolate overflow-visible cursor-pointer"
      style={{ filter: `drop-shadow(0 10px 24px ${theme.accent}44)` }}
    >
      {/* Ground glow pool */}
      <div className="pointer-events-none absolute -bottom-12 left-1/2 z-0 h-10 w-[90%] -translate-x-1/2 rounded-[50%] bg-black/45 blur-[12px]" />
      <div className="pointer-events-none absolute -bottom-8 left-1/2 z-0 h-20 w-[86%] -translate-x-1/2 rounded-[50%] blur-[20px]" style={{ background: theme.floor }} />
      <div className="pointer-events-none absolute -bottom-3 left-1/2 z-0 h-6 w-[72%] -translate-x-1/2 rounded-[50%] opacity-30" style={{ background: `radial-gradient(ellipse, ${theme.accent} 0%, transparent 70%)` }} />
      <div className="pointer-events-none absolute -bottom-4 left-1/2 z-0 h-8 w-[74%] -translate-x-1/2 rounded-[50%]" style={{ background: `radial-gradient(ellipse, ${theme.glow}55 0%, transparent 72%)` }} />
      {/* Floor light dots */}
      <div className="pointer-events-none absolute -bottom-0.5 left-[11%] z-0 h-2 w-2 rounded-full" style={{ background: theme.accent, boxShadow: `0 0 14px ${theme.glow}, 0 0 28px ${theme.glow}` }} />
      <div className="pointer-events-none absolute -bottom-0.5 right-[11%] z-0 h-2 w-2 rounded-full" style={{ background: theme.accent, boxShadow: `0 0 14px ${theme.glow}, 0 0 28px ${theme.glow}` }} />

      {/* Stronger visible side poles for depth */}
      <div className="pointer-events-none absolute left-3 top-16 z-20 h-36 w-[2px] rounded-full" style={{ background: "linear-gradient(180deg, #3a220f 0%, #180e06 100%)", boxShadow: "0 0 6px rgba(0,0,0,0.45)" }} />
      <div className="pointer-events-none absolute right-3 top-16 z-20 h-36 w-[2px] rounded-full" style={{ background: "linear-gradient(180deg, #3a220f 0%, #180e06 100%)", boxShadow: "0 0 6px rgba(0,0,0,0.45)" }} />
      <svg viewBox="0 0 360 80" className="pointer-events-none absolute left-0 top-10 z-10 h-20 w-full" aria-hidden="true">
        <path d="M10 42 C 70 22, 140 58, 204 34 C 250 16, 308 54, 350 36" fill="none" stroke="rgba(43,29,21,0.42)" strokeWidth="1.8" />
      </svg>

      <div className="relative z-20 h-[405px] w-[370px] sm:w-[400px]">
        <svg
          viewBox="0 0 340 300"
          className="absolute left-1/2 top-0 h-[320px] w-[120%] -translate-x-1/2"
          aria-hidden="true"
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
              {/* Night palette: dark navy walls, mood-colored roof */}
              <linearGradient id={`tg-${id}`} x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%"   stopColor={theme.roofDark} />
                <stop offset="46%"  stopColor={theme.roofMid} />
                <stop offset="100%" stopColor={theme.roofDark} />
            </linearGradient>
              <linearGradient id={`wall-${id}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="#1A1332" stopOpacity="0.96" />
                <stop offset="100%" stopColor="#0C0A1E" stopOpacity="0.98" />
              </linearGradient>
              <linearGradient id={`cloth-${id}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="rgba(255,255,255,0.14)" />
                <stop offset="100%" stopColor="rgba(255,255,255,0.01)" />
              </linearGradient>
              {/* Warm inner glow — makes tent feel lit from within */}
              <radialGradient id={`iglow-${id}`} cx="50%" cy="75%" r="65%">
                <stop offset="0%"   stopColor={theme.innerGlow} stopOpacity="1" />
                <stop offset="100%" stopColor="transparent" stopOpacity="0" />
              </radialGradient>
              <pattern id={`kilim-${id}`} x="0" y="0" width="26" height="26" patternUnits="userSpaceOnUse">
                <rect width="26" height="26" fill="transparent" />
                <polygon points="13,2 24,13 13,24 2,13" fill="none" stroke="rgba(255,255,255,0.18)" strokeWidth="0.9" />
                <circle cx="13" cy="13" r="1.7" fill="rgba(255,255,255,0.22)" />
            </pattern>
          </defs>

          <path d="M54 273 L58 148 L282 148 L286 273 Z" fill={`url(#wall-${id})`} stroke="rgba(255,255,255,0.40)" strokeWidth="1.3" />
          <path d={roofPath} fill={`url(#tg-${id})`} />
          <path d={roofPath} fill={`url(#kilim-${id})`} opacity="0.82" />
          <path d={innerRoofPath} fill={`url(#tg-${id})`} opacity="0.9" />
          <path d={innerRoofPath} fill={`url(#cloth-${id})`} />
          {/* Night: dark overlay dims bright vendor canopy colours */}
          <path d={roofPath} fill="rgba(4,3,12,0.55)" />
          {/* Night: warm inner glow — tent glows from within */}
          <path d="M54 273 L58 148 L282 148 L286 273 Z" fill={`url(#iglow-${id})`} />

          <path d="M50 146 Q64 165 78 146 Q92 127 106 146 Q120 165 134 146 Q148 127 162 146 Q176 165 190 146 Q204 127 218 146 Q232 165 246 146 Q260 127 274 146 Q288 165 302 146" fill="none" stroke="#FFD166" strokeWidth="2.2" />

          {lanterns.map((x, index) => {
            const yTop = index % 2 === 0 ? 123 : 109;
            const fill = index % 3 === 0 ? c0 : index % 3 === 1 ? theme.accent : c1;
            return (
              <motion.g
                key={`${id}-lantern-${x}`}
                animate={{ opacity: [0.78, 1, 0.78] }}
                transition={{ duration: 1.5 + index * 0.35, repeat: Infinity, ease: "easeInOut" }}
              >
                <line x1={x} y1={yTop} x2={x} y2={yTop + 11} stroke="rgba(43,29,21,0.48)" strokeWidth="1" />
                <ellipse cx={x} cy={yTop + 20} rx="11.5" ry="14" fill={fill} opacity="0.12" />
                <ellipse cx={x} cy={yTop + 20} rx="7" ry="9" fill={fill} opacity="0.90" />
                <motion.ellipse
                  cx={x}
                  cy={yTop + 20}
                  rx="3.3"
                  ry="4.4"
                  fill="rgba(255,255,220,0.42)"
                  animate={{ opacity: [0.35, 0.95, 0.35] }}
                  transition={{ duration: 1.2 + index * 0.28, repeat: Infinity, ease: "easeInOut" }}
                />
              </motion.g>
            );
          })}

          <line x1="56" y1="146" x2="56" y2="276" stroke="rgba(43,29,21,0.42)" strokeWidth="2" />
          <line x1="284" y1="146" x2="284" y2="276" stroke="rgba(43,29,21,0.42)" strokeWidth="2" />

          <path d="M54 274 C 102 256, 238 256, 286 274" fill="none" stroke="rgba(43,29,21,0.22)" strokeWidth="5" />

          {tasselColors.map((color, i) => {
            const x = 76 + i * 42;
            return (
              <g key={`${id}-tassel-${x}`}>
                <line x1={x} y1="163" x2={x} y2="173" stroke="rgba(255,215,50,0.9)" strokeWidth="1.4" />
                <circle cx={x} cy="175" r="2.8" fill={color} />
              </g>
            );
          })}
        </svg>

        <motion.div
          className="absolute left-[58px] top-[150px] z-30 h-[112px] w-[48px] rounded-b-2xl rounded-t-lg border border-white/30"
          style={{
            background: `linear-gradient(180deg, ${c0}26, ${c1}10), repeating-linear-gradient(100deg, rgba(255,255,255,0.08) 0 2px, transparent 2px 7px)`,
          }}
          animate={{ x: [0, -1.6, 0] }}
          transition={{ duration: 4.2, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute right-[58px] top-[150px] z-30 h-[112px] w-[48px] rounded-b-2xl rounded-t-lg border border-white/30"
          style={{
            background: `linear-gradient(180deg, ${c1}26, ${c0}10), repeating-linear-gradient(80deg, rgba(255,255,255,0.08) 0 2px, transparent 2px 7px)`,
          }}
          animate={{ x: [0, 1.6, 0] }}
          transition={{ duration: 4.6, repeat: Infinity, ease: "easeInOut" }}
        />

        <div
          className="absolute left-1/2 top-[82px] z-40 -translate-x-1/2 rounded-full border px-3 py-1 text-[10px] font-extrabold uppercase tracking-[0.15em] text-white"
          style={{ background: theme.accent, borderColor: "rgba(255,255,255,0.62)", boxShadow: `0 0 16px ${theme.glow}` }}
        >
          {theme.sign}
        </div>

        <div className="absolute left-1/2 top-[178px] z-40 flex w-[61%] -translate-x-1/2 items-end justify-center gap-2">
          {productPreview.map((product) => (
            <div
              key={product.id}
              className="flex h-[56px] w-[70px] flex-col items-center justify-center rounded-lg border border-white/80 px-1 text-center"
              style={{
                background: theme.shelf,
                border: `1px solid ${theme.accent}35`,
                boxShadow: `0 0 12px ${theme.accent}28, inset 0 1px 0 rgba(255,255,255,0.06)`,
              }}
              title={product.name}
            >
              {iconForProduct(theme.productIcon, theme.accent)}
              <p className="line-clamp-1 text-[8px] font-bold text-[#D0C090]/80">{product.name}</p>
            </div>
          ))}
        </div>

        <motion.div
          className="pointer-events-none absolute left-[46%] top-[152px] z-30 h-1 w-10 rounded-full"
          style={{ background: theme.accent, boxShadow: `0 0 22px ${theme.glow}` }}
          animate={{ opacity: [0.3, 0.75, 0.3] }}
          transition={{ duration: 2.6, repeat: Infinity, ease: "easeInOut" }}
        />

        <div className="pointer-events-none absolute inset-0 z-20">
          {[14, 28, 42, 56].map((x, i) => (
            <motion.span
              key={`${id}-dust-${x}`}
              className="absolute h-1.5 w-1.5 rounded-full"
              style={{ background: i % 2 === 0 ? `${theme.accent}aa` : "#FFB64766", left: `${x}%`, top: `${32 + i * 10}%` }}
              animate={{ y: [0, -8, 0], opacity: [0.2, 0.8, 0.2] }}
              transition={{ duration: 3 + i * 0.5, repeat: Infinity, ease: "easeInOut" }}
            />
          ))}
        </div>

        <div className={`absolute right-3 top-3 rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
          vendor.status === "active"
            ? "bg-emerald-400/90 text-white shadow-[0_0_10px_rgba(74,222,128,0.7)]"
            : "bg-slate-300/80 text-slate-600"
        }`}>
          {vendor.status === "active" ? "Open" : "Closed"}
        </div>
        </div>

        <div className="absolute left-1/2 top-[124px] z-40 w-[62%] -translate-x-1/2 text-center">
          <div className="pointer-events-none absolute left-1/2 top-[10px] h-8 w-[92%] -translate-x-1/2 rounded-full bg-black/28 blur-[3px]" />
          <p className="festival-title text-[1.02rem] font-black text-[#F0E4C4] drop-shadow-[0_1px_8px_rgba(0,0,0,0.8)]">{vendor.name}</p>
          <p className="line-clamp-1 text-[9px] font-semibold uppercase tracking-[0.09em] text-[#C0A870]/78">{vendor.banner}</p>
        </div>

        {/* CTA halo to signal interactivity */}
        <motion.div
          className="pointer-events-none absolute left-1/2 top-[266px] z-[52] h-10 w-[76%] -translate-x-1/2 rounded-xl"
          style={{ background: `radial-gradient(ellipse at center, ${theme.accent}66 0%, transparent 72%)` }}
          animate={{ opacity: [0.25, 0.55, 0.25] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
        />

        <motion.button
          onClick={(event) => {
            event.stopPropagation();
            onOpenChat(vendor);
          }}
          whileHover={{ y: -1, scale: 1.015 }}
          whileTap={{ scale: 0.985 }}
          className="absolute left-1/2 top-[270px] z-[55] w-[72%] -translate-x-1/2 cursor-pointer rounded-xl border px-2 py-1.5 text-sm font-bold transition hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0"
          style={{
            borderColor: `${theme.accent}55`,
            background: `linear-gradient(180deg, rgba(88,60,36,0.98) 0%, rgba(44,28,16,0.97) 54%, rgba(22,14,8,0.99) 100%)`,
            boxShadow: `0 14px 30px rgba(0,0,0,0.68), inset 0 1px 0 rgba(255,255,255,0.22), inset 0 -1px 0 rgba(0,0,0,0.45), 0 0 30px ${theme.accent}52`,
            outlineColor: theme.accent,
          }}
        >
          {/* Bench shine strip */}
          <span className="pointer-events-none absolute left-[8%] right-[8%] top-[5px] h-[1px] rounded-full bg-white/35" />
          {/* Soft accent underglow */}
          <span className="pointer-events-none absolute -bottom-[2px] left-1/2 h-[2px] w-[82%] -translate-x-1/2 rounded-full" style={{ background: `linear-gradient(90deg, transparent 0%, ${theme.accent} 50%, transparent 100%)`, opacity: 0.5 }} />
          <span className="relative inline-flex items-center gap-2 text-[13px] uppercase tracking-[0.1em]">
            <span style={{ color: theme.accent }}>*</span>
            <span style={{ color: "#E8D8A8" }}>Ask the vendor</span>
          </span>
        </motion.button>

        {/* Mascot sits behind the bench like a welcoming shopkeeper */}
        <div className="pointer-events-none absolute left-1/2 top-[216px] z-[54] h-[90px] w-[100px] -translate-x-1/2 overflow-hidden">
          <div className="absolute left-1/2 top-0 -translate-x-1/2 scale-[0.9]">
            <VendorBot status={vendor.status} accent={theme.accent} glow={theme.glow} />
          </div>
        </div>

        <p className="pointer-events-none absolute left-1/2 top-[308px] z-40 w-[80%] -translate-x-1/2 text-center text-[11px] font-medium text-[#A89060]/65">
          {vendor.tagline}
        </p>
    </motion.article>
  );
}
