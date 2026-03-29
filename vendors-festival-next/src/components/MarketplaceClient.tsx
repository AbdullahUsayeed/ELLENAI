"use client";

import { motion } from "framer-motion";
import { useMemo, useState } from "react";
import { vendors, type Vendor } from "@/data/vendors";
import { FestivalBackground } from "@/components/FestivalBackground";
import { TentShopCard } from "@/components/TentShopCard";
import { ChatModal } from "./ChatModal";
import { useAmbientAudio } from "@/lib/hooks/useAmbientAudio";

// Helper: keep finial star math clean
const FINIAL_ANGLES = [0, 60, 120, 180, 240, 300];

export function MarketplaceClient() {
  const [activeVendor, setActiveVendor] = useState<Vendor | null>(null);
  const [query, setQuery] = useState("");
  const [hoveredVendorId, setHoveredVendorId] = useState<string | null>(null);
  const { enabled, muted, start, toggleMute, playTap } = useAmbientAudio();

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return vendors;
    return vendors.filter((vendor) => {
      const corpus = `${vendor.name} ${vendor.banner} ${vendor.tagline} ${vendor.products
        .map((p) => `${p.name} ${p.price}`)
        .join(" ")}`.toLowerCase();
      return corpus.includes(q);
    });
  }, [query]);

  const getMood = (vendor: Vendor, index: number): "fashion" | "electronics" | "food" | "wellness" | "jewelry" | "home" => {
    const name = `${vendor.name} ${vendor.banner} ${vendor.tagline}`.toLowerCase();
    if (name.includes("tech") || name.includes("gadget") || name.includes("kiosk")) return "electronics";
    if (name.includes("ritual") || name.includes("scent") || name.includes("wellness")) return "wellness";
    if (name.includes("jewel") || name.includes("trinket") || name.includes("ring")) return "jewelry";
    if (name.includes("craft") || name.includes("bar") || name.includes("food")) return "food";
    if (name.includes("home") || name.includes("studio") || name.includes("decor")) return "home";
    return index % 2 === 0 ? "fashion" : "food";
  };

  return (
    <main className="relative min-h-screen overflow-x-hidden bg-[#070B18] text-[#E0D4B8]">
      <FestivalBackground />

      {/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
           HERO â€” NIGHT BAZAAR PERSPECTIVE SCENE
         â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */}
      <section
        className={`relative flex min-h-screen flex-col items-center justify-center overflow-hidden ${!enabled ? "cursor-pointer" : ""}`}
        onClick={!enabled ? start : undefined}
      >

        {/* Cinematic zoom-in on load */}
        <motion.div
          className="absolute inset-0 z-0"
          initial={{ scale: 1.07, opacity: 0.65 }}
          animate={{ scale: 1,    opacity: 1 }}
          transition={{ duration: 3.6, ease: "easeOut" }}
        >
          <svg
            viewBox="0 0 1440 540"
            preserveAspectRatio="xMidYMid slice"
            className="h-full w-full"
            aria-hidden="true"
          >
            <defs>
              {/* Ground */}
              <linearGradient id="groundG" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="#050411" />
                <stop offset="55%"  stopColor="#0C0A1C" />
                <stop offset="100%" stopColor="#190D14" />
              </linearGradient>

              {/* Hero tent roof â€” warm gold/amber */}
              <linearGradient id="heroRoofG" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%"   stopColor="#6A3008" />
                <stop offset="46%"  stopColor="#B86015" />
                <stop offset="100%" stopColor="#6A3008" />
              </linearGradient>
              <linearGradient id="heroRoofSheen" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="rgba(255,220,130,0.28)" />
                <stop offset="100%" stopColor="rgba(0,0,0,0)" />
              </linearGradient>

              {/* Left tent â€” crimson */}
              <linearGradient id="leftRoofG" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%"   stopColor="#4A0812" />
                <stop offset="50%"  stopColor="#8C1520" />
                <stop offset="100%" stopColor="#4A0812" />
              </linearGradient>

              {/* Right tent â€” neon blue */}
              <linearGradient id="rightRoofG" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%"   stopColor="#071860" />
                <stop offset="50%"  stopColor="#1240B0" />
                <stop offset="100%" stopColor="#071860" />
              </linearGradient>

              {/* Interior glows */}
              <radialGradient id="heroInnerG" cx="50%" cy="80%" r="70%">
                <stop offset="0%"   stopColor="rgba(255,168,50,0.40)" />
                <stop offset="55%"  stopColor="rgba(200,108,20,0.12)" />
                <stop offset="100%" stopColor="transparent" />
              </radialGradient>
              <radialGradient id="leftInnerG" cx="50%" cy="80%" r="70%">
                <stop offset="0%"   stopColor="rgba(192,40,55,0.28)" />
                <stop offset="100%" stopColor="transparent" />
              </radialGradient>
              <radialGradient id="rightInnerG" cx="50%" cy="80%" r="70%">
                <stop offset="0%"   stopColor="rgba(30,108,240,0.22)" />
                <stop offset="100%" stopColor="transparent" />
              </radialGradient>

              {/* Ground glows */}
              <radialGradient id="heroGroundG" cx="50%" cy="0%" r="80%">
                <stop offset="0%"   stopColor="rgba(210,130,30,0.35)" />
                <stop offset="62%"  stopColor="rgba(180,90,10,0.10)" />
                <stop offset="100%" stopColor="transparent" />
              </radialGradient>
              <radialGradient id="leftGroundG" cx="50%" cy="0%" r="80%">
                <stop offset="0%"   stopColor="rgba(192,40,55,0.22)" />
                <stop offset="100%" stopColor="transparent" />
              </radialGradient>
              <radialGradient id="rightGroundG" cx="50%" cy="0%" r="80%">
                <stop offset="0%"   stopColor="rgba(30,108,240,0.18)" />
                <stop offset="100%" stopColor="transparent" />
              </radialGradient>

              {/* Mist / atmosphere */}
              <radialGradient id="vpMistG" cx="50%" cy="50%" r="50%">
                <stop offset="0%"   stopColor="rgba(18,12,40,0.82)" />
                <stop offset="100%" stopColor="transparent" />
              </radialGradient>
              <linearGradient id="groundMistG" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="transparent" />
                <stop offset="100%" stopColor="rgba(10,6,22,0.80)" />
              </linearGradient>
              <radialGradient id="spotlightG" cx="50%" cy="0%" r="100%">
                <stop offset="0%"   stopColor="rgba(255,198,80,0.09)" />
                <stop offset="68%"  stopColor="transparent" />
              </radialGradient>

              {/* Side vignettes */}
              <linearGradient id="leftVigG" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%"   stopColor="rgba(7,11,24,0.80)" />
                <stop offset="100%" stopColor="transparent" />
              </linearGradient>
              <linearGradient id="rightVigG" x1="1" y1="0" x2="0" y2="0">
                <stop offset="0%"   stopColor="rgba(7,11,24,0.80)" />
                <stop offset="100%" stopColor="transparent" />
              </linearGradient>

              {/* Filters */}
              <filter id="glowF" x="-25%" y="-25%" width="150%" height="150%">
                <feGaussianBlur stdDeviation="4" result="b" />
                <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
              <filter id="softBlurF" x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur stdDeviation="14" />
              </filter>
              <filter id="tinyBlurF" x="-5%" y="-5%" width="110%" height="110%">
                <feGaussianBlur stdDeviation="2.5" />
              </filter>
            </defs>

            {/* â”€â”€ Ground plane â”€â”€ */}
            <path d="M0 540 L0 162 L720 90 L1440 162 L1440 540 Z" fill="url(#groundG)" />

            {/* Perspective grid â€” converging radials */}
            {[-650,-450,-300,-180,-100,-38,38,100,180,300,450,650].map((offset, i) => (
              <line key={`gl-${i}`}
                x1={720} y1={90}
                x2={720 + offset * 1.15} y2={540}
                stroke="rgba(255,240,180,0.020)" strokeWidth="1"
              />
            ))}
            {/* Horizontal depth cross-lines */}
            {[124,162,208,264,332,414].map((y, i) => {
              const t  = Math.max(0, (y - 90) / 450);
              const hw = t * 730;
              return (
                <line key={`cl-${i}`}
                  x1={720 - hw} y1={y}
                  x2={720 + hw} y2={y}
                  stroke="rgba(255,240,180,0.022)" strokeWidth="1"
                />
              );
            })}

            {/* Warm center path reflection */}
            <path d="M720 90 L555 540 L885 540 Z" fill="rgba(255,180,60,0.038)" />

            {/* Spotlight cone from above */}
            <path d="M720 0 L375 540 L1065 540 Z" fill="url(#spotlightG)" />

            {/* â”€â”€ Background ghost tents (near VP) â”€â”€ */}
            <g opacity="0.22" filter="url(#tinyBlurF)">
              <polygon points="502,208 560,128 618,208" fill="#18102C" stroke="#5040A0" strokeWidth="1" />
              <rect x="508" y="208" width="106" height="56" rx="2" fill="#100C1E" />
            </g>
            <g opacity="0.22" filter="url(#tinyBlurF)">
              <polygon points="822,208 880,128 938,208" fill="#10121E" stroke="#2050C0" strokeWidth="1" />
              <rect x="828" y="208" width="106" height="56" rx="2" fill="#080E1A" />
            </g>

            {/* VP mist */}
            <ellipse cx="720" cy="152" rx="268" ry="56" fill="url(#vpMistG)" filter="url(#softBlurF)" />

            {/* â”€â”€ LEFT MEDIUM TENT â€” crimson â”€â”€ */}
            <ellipse cx="240" cy="524" rx="174" ry="28" fill="url(#leftGroundG)" />
            <polygon points="98,492 130,296 352,296 384,492"
              fill="#0E0816" stroke="rgba(160,28,38,0.38)" strokeWidth="1.5" />
            <polygon points="98,492 130,296 352,296 384,492" fill="url(#leftInnerG)" />
            <polygon points="116,299 241,208 366,299" fill="url(#leftRoofG)" />
            <polygon points="116,299 241,208 366,299" fill="rgba(255,255,255,0.05)" />
            <polygon points="138,299 241,228 344,299" fill="rgba(140,20,28,0.38)" />
            <polygon points="116,299 241,208 366,299" fill="none" stroke="rgba(180,44,58,0.68)" strokeWidth="1.8" />
            {/* Left valance */}
            <path d="M116 299 Q126 312 136 299 Q146 286 156 299 Q166 312 176 299 Q186 286 196 299 Q206 312 216 299 Q226 286 236 299 Q246 312 256 299 Q266 286 276 299 Q286 312 296 299 Q306 286 316 299 Q326 312 336 299 Q346 286 356 299 Q366 312 366 299"
              fill="none" stroke="#C0243C" strokeWidth="2" opacity="0.88" />
            {/* Left lanterns */}
            {[164, 241, 318].map((x, i) => (
              <g key={`ll-${x}`}>
                <line x1={x} y1={272} x2={x} y2={284} stroke="rgba(100,58,25,0.5)" strokeWidth="1" />
                <ellipse cx={x} cy={293} rx={i === 1 ? 10 : 7.5} ry={i === 1 ? 6.5 : 5} fill="#C0243C" opacity="0.86" />
                <ellipse cx={x} cy={293} rx={i === 1 ? 4.5 : 3.2} ry={i === 1 ? 3 : 2.4} fill="rgba(255,155,140,0.72)" />
              </g>
            ))}
            <rect x="118" y="297" width="5" height="197" rx="1" fill="#100808" />
            <rect x="358" y="297" width="5" height="197" rx="1" fill="#100808" />

            {/* â”€â”€ RIGHT MEDIUM TENT â€” neon blue â”€â”€ */}
            <ellipse cx="1200" cy="524" rx="174" ry="28" fill="url(#rightGroundG)" />
            <polygon points="1056,492 1088,296 1310,296 1342,492"
              fill="#080C1A" stroke="rgba(28,88,200,0.38)" strokeWidth="1.5" />
            <polygon points="1056,492 1088,296 1310,296 1342,492" fill="url(#rightInnerG)" />
            <polygon points="1074,299 1199,208 1324,299" fill="url(#rightRoofG)" />
            <polygon points="1074,299 1199,208 1324,299" fill="rgba(255,255,255,0.04)" />
            <polygon points="1096,299 1199,228 1302,299" fill="rgba(18,68,195,0.38)" />
            <polygon points="1074,299 1199,208 1324,299" fill="none" stroke="rgba(44,140,255,0.68)" strokeWidth="1.8" />
            {/* Right valance */}
            <path d="M1074 299 Q1084 312 1094 299 Q1104 286 1114 299 Q1124 312 1134 299 Q1144 286 1154 299 Q1164 312 1174 299 Q1184 286 1194 299 Q1204 312 1214 299 Q1224 286 1234 299 Q1244 312 1254 299 Q1264 286 1274 299 Q1284 312 1294 299 Q1304 286 1314 299 Q1324 312 1324 299"
              fill="none" stroke="#2C8EFF" strokeWidth="2" opacity="0.88" />
            {/* Right lanterns */}
            {[1122, 1199, 1276].map((x, i) => (
              <g key={`rl-${x}`}>
                <line x1={x} y1={272} x2={x} y2={284} stroke="rgba(60,80,130,0.5)" strokeWidth="1" />
                <ellipse cx={x} cy={293} rx={i === 1 ? 10 : 7.5} ry={i === 1 ? 6.5 : 5} fill="#2C8EFF" opacity="0.86" />
                <ellipse cx={x} cy={293} rx={i === 1 ? 4.5 : 3.2} ry={i === 1 ? 3 : 2.4} fill="rgba(120,198,255,0.72)" />
              </g>
            ))}
            <rect x="1076" y="297" width="5" height="197" rx="1" fill="#080A12" />
            <rect x="1317" y="297" width="5" height="197" rx="1" fill="#080A12" />

            {/* â”€â”€ HERO TENT â€” gold/amber (center, large) â”€â”€ */}
            {/* Extended ground warmth */}
            <ellipse cx="720" cy="530" rx="372" ry="44" fill="url(#heroGroundG)" />
            <ellipse cx="720" cy="530" rx="260" ry="26" fill="rgba(220,138,28,0.14)" />

            {/* Tent walls â€” dark navy */}
            <polygon points="435,504 490,266 950,266 1005,504"
              fill="#10091C" stroke="rgba(210,144,35,0.35)" strokeWidth="1.5" />
            {/* Interior warm glow */}
            <polygon points="435,504 490,266 950,266 1005,504" fill="url(#heroInnerG)" />

            {/* Roof */}
            <polygon points="470,269 720,118 970,269" fill="url(#heroRoofG)" />
            <polygon points="470,269 720,118 970,269" fill="url(#heroRoofSheen)" />
            <polygon points="508,269 720,148 932,269" fill="rgba(180,104,20,0.36)" />
            {/* Glowing roof edge */}
            <polygon points="470,269 720,118 970,269" fill="none" stroke="#E8A030" strokeWidth="2.8" filter="url(#glowF)" />
            {/* Ridge lines */}
            <line x1={720} y1={118} x2={470} y2={269} stroke="rgba(255,220,120,0.42)" strokeWidth="1.2" />
            <line x1={720} y1={118} x2={970} y2={269} stroke="rgba(255,220,120,0.42)" strokeWidth="1.2" />

            {/* Peak finial */}
            {FINIAL_ANGLES.map((angle) => {
              const rad = (angle * Math.PI) / 180;
              const r   = angle % 120 === 0 ? 16 : 8;
              return (
                <line key={`fin-${angle}`}
                  x1={720} y1={118}
                  x2={720 + Math.cos(rad) * r}
                  y2={118 + Math.sin(rad) * r}
                  stroke="#FFD166" strokeWidth="2.5" strokeLinecap="round"
                />
              );
            })}
            <circle cx={720} cy={118} r={5.5} fill="#FFD166" filter="url(#glowF)" />

            {/* Scalloped valance â€” gold */}
            <path
              d="M470 269 Q488 285 506 269 Q524 253 542 269 Q560 285 578 269 Q596 253 614 269 Q632 285 650 269 Q668 253 686 269 Q704 285 722 269 Q740 253 758 269 Q776 285 794 269 Q812 253 830 269 Q848 285 866 269 Q884 253 902 269 Q920 285 938 269 Q956 253 970 269"
              fill="none" stroke="#FFD166" strokeWidth="2.8" filter="url(#glowF)" opacity="0.92"
            />
            {/* Valance fill */}
            <path
              d="M470 269 Q488 285 506 269 Q524 253 542 269 Q560 285 578 269 Q596 253 614 269 Q632 285 650 269 Q668 253 686 269 Q704 285 722 269 Q740 253 758 269 Q776 285 794 269 Q812 253 830 269 Q848 285 866 269 Q884 253 902 269 Q920 285 938 269 Q956 253 970 269"
              fill="rgba(180,110,20,0.40)"
            />

            {/* Hero tassels */}
            {[506,560,614,668,722,776,830,884,938].map((x, i) => (
              <g key={`htas-${x}`}>
                <line x1={x} y1={282} x2={x} y2={296} stroke="#FFD166" strokeWidth="1.8" />
                <circle cx={x} cy={299} r={4}
                  fill={["#FFB647","#C0243C","#FFB647","#2C8EFF","#FFB647","#C0243C","#FFB647","#2C8EFF","#FFB647"][i]} />
              </g>
            ))}

            {/* Hero lanterns â€” 5 */}
            {[542, 622, 720, 818, 898].map((x, i) => {
              const y  = i % 2 === 0 ? 246 : 232;
              const lc = i % 2 === 0 ? "#FFB647" : "#C0243C";
              const lg = i % 2 === 0 ? "rgba(255,232,160,0.72)" : "rgba(255,155,140,0.72)";
              return (
                <g key={`hlan-${x}`}>
                  <line x1={x} y1={y} x2={x} y2={y + 14} stroke="rgba(100,68,18,0.55)" strokeWidth="1.2" />
                  <ellipse cx={x} cy={y + 22} rx={11} ry={7} fill={lc} opacity="0.88" />
                  <ellipse cx={x} cy={y + 22} rx={5} ry={3.2} fill={lg} />
                  <ellipse cx={x} cy={y + 22} rx={17} ry={11} fill={lc} opacity="0.08" />
                </g>
              );
            })}

            {/* Hero side poles */}
            <rect x="474" y="267" width="6" height="239" rx="2" fill="#18100A" />
            <rect x="960" y="267" width="6" height="239" rx="2" fill="#18100A" />

            {/* â”€â”€ Ground mist overlay â”€â”€ */}
            <rect x="0" y="395" width="1440" height="145" fill="url(#groundMistG)" />

            {/* Side vignettes */}
            <rect x="0"    y="0" width="340"  height="540" fill="url(#leftVigG)" />
            <rect x="1100" y="0" width="340"  height="540" fill="url(#rightVigG)" />
          </svg>
        </motion.div>

        {/* â”€â”€ Title overlay â”€â”€ */}
        <div className="relative z-10 flex flex-col items-center px-4 text-center pointer-events-none">
          <motion.p
            initial={{ opacity: 0, letterSpacing: "0.55em" }}
            animate={{ opacity: 1, letterSpacing: "0.3em" }}
            transition={{ delay: 0.7, duration: 1.2 }}
            className="mb-4 text-xs font-bold uppercase text-[#FFB647]/75"
          >
            Festival Marketplace
          </motion.p>
          <motion.h1
            initial={{ opacity: 0, y: 32 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.0, duration: 1.1, ease: "easeOut" }}
            className="festival-title night-glow mb-5 text-[clamp(3.6rem,10vw,7.5rem)] font-black leading-none tracking-tight text-[#FFE0A0]"
          >
            VENDORS
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.55, duration: 0.9 }}
            className="max-w-[520px] text-sm text-[#C0AA80]/70 sm:text-base"
          >
            Step into a magical night market. Each glowing tent is a curated shop with its own world.
          </motion.p>
        </div>

        {/* Scroll indicator */}
        <motion.div
          className="absolute bottom-8 left-1/2 z-10 flex -translate-x-1/2 flex-col items-center gap-2 pointer-events-none"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 2.3, duration: 0.9 }}
        >
          <span className="text-[10px] uppercase tracking-[0.24em] text-[#FFB647]/50">
              {enabled ? "Enter the bazaar" : "Click to enter"}
          </span>
          <motion.div
            className="h-9 w-px bg-gradient-to-b from-[#FFB647]/55 to-transparent"
            animate={{ scaleY: [0.25, 1, 0.25], opacity: [0.35, 0.90, 0.35] }}
            transition={{ duration: 2.1, repeat: Infinity, ease: "easeInOut" }}
          />
        </motion.div>
      </section>

      {/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
           VENDOR SHOPS
         â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */}
      <section className="relative z-10 px-4 pb-20 pt-6 sm:px-8 lg:px-14">

        {/* Search + count bar */}
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55 }}
          viewport={{ once: true }}
          className="mb-8 flex flex-col gap-3 rounded-2xl border border-white/[0.08] bg-white/[0.04] px-5 py-4 backdrop-blur-sm sm:flex-row sm:items-center sm:justify-between"
        >
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search shops, products, or vibesâ€¦"
            className="w-full max-w-xl rounded-xl border border-white/[0.10] bg-white/[0.07] px-4 py-3 text-sm text-[#E0D4B8] outline-none placeholder:text-[#8A7A60]/55 focus:border-[#FFB647]/40 focus:bg-white/[0.10] transition"
          />
          <div className="shrink-0 rounded-xl border border-[#FFB647]/25 bg-[#FFB647]/[0.10] px-4 py-3 text-sm font-bold text-[#FFB647]">
            {filtered.length} tents open tonight
          </div>
        </motion.div>

        {/* Vendor scroll lane â€” upper row */}
        <div className="relative mb-12">
          <div className={`pointer-events-none absolute inset-0 z-10 rounded-2xl bg-black/60 transition-opacity duration-300 ${hoveredVendorId ? "opacity-100" : "opacity-0"}`} />
          <div className="custom-scroll-dark relative z-20 flex gap-12 overflow-x-auto pb-6 pt-2">
            {filtered.filter((_, i) => i % 2 === 0).map((vendor, laneIdx) => {
              const globalIndex = vendors.findIndex((v) => v.id === vendor.id);
              const hovered = hoveredVendorId === vendor.id;
              const dimmed  = hoveredVendorId !== null && !hovered;
              return (
                <motion.div
                  key={vendor.id}
                  initial={{ opacity: 0, y: 24 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ delay: laneIdx * 0.08, duration: 0.5 }}
                  viewport={{ once: true }}
                  animate={{ opacity: dimmed ? 0.32 : 1, scale: hovered ? 1.04 : 1 }}
                  onMouseEnter={() => { setHoveredVendorId(vendor.id); playTap(); }}
                  onMouseLeave={() => setHoveredVendorId(null)}
                  className="relative z-20 min-w-[370px] sm:min-w-[400px]"
                  style={{ marginTop: laneIdx % 2 === 0 ? 0 : 20 }}
                >
                  {hovered && (
                    <div className="pointer-events-none absolute -inset-4 z-10 rounded-[34px] border border-[#FFB647]/28 shadow-[0_0_52px_rgba(255,182,71,0.38)]" />
                  )}
                  <div className="relative z-20">
                    <TentShopCard vendor={vendor} onOpenChat={setActiveVendor} mood={getMood(vendor, globalIndex)} variant={globalIndex} />
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>

        {/* Lower row */}
        <div className="relative">
          <div className={`pointer-events-none absolute inset-0 z-10 rounded-2xl bg-black/60 transition-opacity duration-300 ${hoveredVendorId ? "opacity-100" : "opacity-0"}`} />
          <div className="custom-scroll-dark relative z-20 flex gap-12 overflow-x-auto pb-4 pt-2">
            {filtered.filter((_, i) => i % 2 === 1).map((vendor, laneIdx) => {
              const globalIndex = vendors.findIndex((v) => v.id === vendor.id);
              const hovered = hoveredVendorId === vendor.id;
              const dimmed  = hoveredVendorId !== null && !hovered;
              return (
                <motion.div
                  key={vendor.id}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ delay: laneIdx * 0.08, duration: 0.5 }}
                  viewport={{ once: true }}
                  animate={{ opacity: dimmed ? 0.32 : 1, scale: hovered ? 1.04 : 1 }}
                  onMouseEnter={() => { setHoveredVendorId(vendor.id); playTap(); }}
                  onMouseLeave={() => setHoveredVendorId(null)}
                  className="relative z-20 min-w-[370px] sm:min-w-[400px]"
                  style={{ marginTop: laneIdx % 2 === 0 ? 18 : 0 }}
                >
                  {hovered && (
                    <div className="pointer-events-none absolute -inset-4 z-10 rounded-[34px] border border-[#FFB647]/28 shadow-[0_0_52px_rgba(255,182,71,0.38)]" />
                  )}
                  <div className="relative z-20">
                    <TentShopCard vendor={vendor} onOpenChat={setActiveVendor} mood={getMood(vendor, globalIndex)} variant={globalIndex + 1} />
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      <ChatModal
        open={Boolean(activeVendor)}
        vendor={activeVendor}
        onClose={() => setActiveVendor(null)}
      />

      {/* Floating lantern mute toggle — appears after audio is started */}
      {enabled && (
        <button
          onClick={toggleMute}
          title={muted ? "Unmute ambience" : "Mute ambience"}
          className="fixed bottom-6 right-6 z-50 flex h-12 w-12 items-center justify-center rounded-full border border-white/10 bg-black/50 backdrop-blur-sm transition-all duration-300 hover:scale-110"
        >
          {/* Lantern SVG */}
          <svg viewBox="0 0 28 36" width="22" height="28" fill="none" aria-hidden>
            {/* Hanger */}
            <line x1="14" y1="0" x2="14" y2="4" stroke={muted ? "#555" : "#C89030"} strokeWidth="1.5" strokeLinecap="round" />
            <path d="M10 4 Q14 2 18 4" stroke={muted ? "#555" : "#C89030"} strokeWidth="1.5" fill="none" strokeLinecap="round" />
            {/* Body */}
            <rect x="8" y="5" width="12" height="22" rx="3"
              fill={muted ? "#1a1a1a" : "#1C0E00"}
              stroke={muted ? "#444" : "#C89030"}
              strokeWidth="1.2"
            />
            {/* Flame glow — hidden when muted */}
            {!muted && (
              <>
                <ellipse cx="14" cy="16" rx="5" ry="7" fill="rgba(255,168,50,0.18)" />
                <ellipse cx="14" cy="16" rx="2.5" ry="4" fill="rgba(255,200,80,0.55)" />
                <ellipse cx="14" cy="18" rx="1.4" ry="2.2" fill="rgba(255,240,180,0.80)" />
              </>
            )}
            {/* Bottom cap */}
            <rect x="9" y="26" width="10" height="3" rx="1"
              fill={muted ? "#333" : "#A07020"}
            />
          </svg>
          {/* Outer glow ring when active */}
          {!muted && (
            <span className="pointer-events-none absolute inset-0 rounded-full shadow-[0_0_16px_rgba(255,182,71,0.45)]" />
          )}
        </button>
      )}
    </main>
  );
}
