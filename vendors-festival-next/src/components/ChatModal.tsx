"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import type { Product, Vendor } from "@/data/vendors";
import { VendorBot } from "@/components/VendorBot";

type ChatModalProps = {
  vendor: Vendor | null;
  open: boolean;
  onClose: () => void;
};

type Message = {
  id: string;
  from: "user" | "bot";
  text: string;
};

const quickQuestions = [
  "Is this available now?",
  "Do you have another size?",
  "Can this ship tomorrow?"
];

const cannedReplies = [
  "Yes, this is available now. I can also suggest the best matching piece in the tent.",
  "I have a few nearby alternatives. Tell me your preferred size or fit and I will guide you.",
  "Yes, if you order tonight I can prepare it for next-day dispatch."
];

function fallbackTheme(vendor: Vendor) {
  return {
    accent: vendor.canopy[1],
    glow: vendor.canopy[0],
    roofA: "#4A0812",
    roofB: "#8C1520"
  };
}

function playCurtainRustle() {
  try {
    const ctx = new AudioContext();
    const len = Math.floor(ctx.sampleRate * 0.35);
    const buf = ctx.createBuffer(1, len, ctx.sampleRate);
    const data = buf.getChannelData(0);

    let last = 0;
    for (let i = 0; i < len; i++) {
      const w = Math.random() * 2 - 1;
      data[i] = (last + 0.035 * w) / 1.035;
      last = data[i];
    }

    const src = ctx.createBufferSource();
    src.buffer = buf;

    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = 1400;
    bp.Q.value = 0.9;

    const gain = ctx.createGain();
    const t = ctx.currentTime;
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(0.07, t + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.34);

    src.connect(bp);
    bp.connect(gain);
    gain.connect(ctx.destination);
    src.start(t);
    src.stop(t + 0.35);
  } catch {
    // no-op
  }
}

function playInspectClick() {
  try {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "triangle";
    osc.frequency.value = 980;
    osc.connect(gain);
    gain.connect(ctx.destination);
    const t = ctx.currentTime;
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(0.045, t + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.13);
    osc.start(t);
    osc.stop(t + 0.13);
  } catch {
    // no-op
  }
}


export function ChatModal({ vendor, open, onClose }: ChatModalProps) {
  type ProductLayer = "upper" | "middle" | "lower";

  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(vendor?.products[0] ?? null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [chatOpen, setChatOpen] = useState(false);
  const [showIntro, setShowIntro] = useState(true);
  const [scrollTop, setScrollTop] = useState(0);
  const [scrollMax, setScrollMax] = useState(1);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [gaze, setGaze] = useState({ x: 0, y: 0 });
  const [bubbleIndex, setBubbleIndex] = useState(0);
  const [activeLayer, setActiveLayer] = useState<ProductLayer>("upper");
  const [showProductsSection, setShowProductsSection] = useState(true);

  useEffect(() => {
    if (!vendor) return;
    setSelectedProduct(vendor.products[0] ?? null);
    setInput("");
    setTyping(false);
    setChatOpen(false);
    setShowIntro(true);
    setBubbleIndex(0);
    setActiveLayer("middle");
    setShowProductsSection(true);
    setMessages([
      {
        id: `seed-${vendor.id}`,
        from: "bot",
        text: `Hi. Welcome to ${vendor.name}. ${vendor.products[0]?.name ?? "The latest drop"} is getting the most attention tonight.`
      }
    ]);

    playCurtainRustle();
    const t = window.setTimeout(() => setShowIntro(false), 980);
    return () => window.clearTimeout(t);
  }, [vendor, open]);

  const theme = useMemo(() => (vendor ? fallbackTheme(vendor) : fallbackTheme({
    id: "tmp",
    name: "Vendor",
    banner: "",
    tagline: "",
    status: "active",
    canopy: ["#FFB647", "#C0243C"],
    products: []
  })), [vendor]);

  const ratio = scrollTop / scrollMax;
  const isCitrus = vendor?.name.toLowerCase().includes("citrus") ?? false;

  const floorItems = useMemo(() => {
    if (!vendor) return [] as Product[];
    return vendor.products;
  }, [vendor]);

  const wallProducts = useMemo(() => {
    const PER = 10;
    const items = floorItems.slice(0, PER * 3);
    const layerOf = (i: number): ProductLayer => i < PER ? "upper" : i < PER * 2 ? "middle" : "lower";
    const layerCounts: Record<ProductLayer, number> = { upper: 0, middle: 0, lower: 0 };
    items.forEach((_, i) => { layerCounts[layerOf(i)]++; });
    const posTracker: Record<ProductLayer, number> = { upper: 0, middle: 0, lower: 0 };
    return items.map((product, idx) => {
      const layer = layerOf(idx);
      const posIdx = posTracker[layer]++;
      const count = layerCounts[layer];
      const t = count > 1 ? (posIdx / (count - 1)) - 0.5 : 0;
      const yCard = posIdx % 2 === 0 ? 76 : 138;
      const stringLen = yCard - 56;
      return { product, idx, layer, posIdx, t, yCard, stringLen };
    });
  }, [floorItems]);

  useEffect(() => {
    if (!open) return;
    const timer = window.setInterval(() => {
      setBubbleIndex((v) => (v + 1) % 3);
    }, 4200);
    return () => window.clearInterval(timer);
  }, [open]);

  const stars = useMemo(
    () =>
      Array.from({ length: 28 }, (_, i) => ({
        key: `star-${i}`,
        left: 4 + ((i * 31) % 90),
        top: 6 + ((i * 17) % 52),
        size: i % 3 === 0 ? 2.4 : 1.6,
        drift: i % 2 === 0 ? 1 : -1,
      })),
    []
  );

  const send = (prefilled?: string) => {
    const text = (prefilled ?? input).trim();
    if (!text || !vendor) return;

    const replyIndex = messages.length % cannedReplies.length;
    const userMsg: Message = { id: `u-${Date.now()}`, from: "user", text };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setTyping(true);

    window.setTimeout(() => {
      const botMsg: Message = {
        id: `b-${Date.now()}`,
        from: "bot",
        text: cannedReplies[replyIndex]
      };
      setMessages((prev) => [...prev, botMsg]);
      setTyping(false);
    }, 850);
  };

  return (
    <AnimatePresence>
      {open && vendor && (
        <motion.div
          className="fixed inset-0 z-[90] bg-[#04050d]/88 backdrop-blur-md"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="absolute inset-0 overflow-y-auto"
            initial={{ scale: 0.92, opacity: 0, y: 28 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.98, opacity: 0, y: 16 }}
            transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
          >
            <div
              className="min-h-full px-3 py-4 sm:px-6 sm:py-6 lg:px-10"
              onClick={(event) => event.stopPropagation()}
              onMouseMove={(event) => {
                const rect = event.currentTarget.getBoundingClientRect();
                const cx = rect.left + rect.width / 2;
                const cy = rect.top + rect.height / 2;
                const nx = (event.clientX - cx) / (rect.width / 2);
                const ny = (event.clientY - cy) / (rect.height / 2);
                setGaze({
                  x: Math.max(-1, Math.min(1, nx)),
                  y: Math.max(-1, Math.min(1, ny)),
                });
              }}
              onMouseLeave={() => setGaze({ x: 0, y: 0 })}
            >
              <div
                className="relative mx-auto max-w-7xl overflow-hidden rounded-[32px] border"
                style={{
                  borderColor: `${theme.accent}66`,
                  background: `radial-gradient(ellipse at 50% 44%, ${theme.accent}20 0%, rgba(10,8,22,0.86) 50%, rgba(2,2,10,0.96) 100%)`,
                  boxShadow: `0 0 0 1px ${theme.accent}22, 0 32px 90px rgba(0,0,0,0.65), 0 0 80px ${theme.accent}30`
                }}
              >
                <div className="pointer-events-none absolute inset-0 z-0" style={{ boxShadow: "inset 0 0 130px rgba(0,0,0,0.82)" }} />
                <div
                  className="pointer-events-none absolute inset-0 z-0 opacity-[0.12]"
                  style={{
                    backgroundImage:
                      "linear-gradient(0deg, rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px), radial-gradient(circle at 10% 20%, rgba(255,255,255,0.05) 0 1px, transparent 1px)",
                    backgroundSize: "3px 3px, 3px 3px, 24px 24px"
                  }}
                />
                <div className="pointer-events-none absolute inset-0 z-0">
                  {stars.map((star) => (
                    <span
                      key={star.key}
                      className="absolute rounded-full"
                      style={{
                        left: `${star.left}%`,
                        top: `${star.top}%`,
                        width: `${star.size}px`,
                        height: `${star.size}px`,
                        background: "rgba(255,236,185,0.82)",
                        boxShadow: `0 0 8px ${theme.glow}`,
                        transform: `translate(${star.drift * ratio * 10}px, ${-scrollTop * 0.12}px)`,
                        opacity: 0.25 + Math.abs(Math.sin(ratio * 2.6 + star.left * 0.03)) * 0.65
                      }}
                    />
                  ))}
                </div>

                <header className="sticky top-0 z-20 border-b bg-[#0A0D1BCC]/95 backdrop-blur-md" style={{ borderColor: `${theme.accent}3f` }}>
                  <div className="relative h-[220px] overflow-hidden px-5 pt-5 sm:h-[248px] sm:px-8">
                    <svg viewBox="0 0 1000 280" className="absolute inset-0 h-full w-full" preserveAspectRatio="none" aria-hidden="true">
                      <defs>
                        <linearGradient id="chat-roof" x1="0" y1="0" x2="1" y2="0">
                          <stop offset="0%" stopColor={theme.roofA} />
                          <stop offset="50%" stopColor={theme.roofB} />
                          <stop offset="100%" stopColor={theme.roofA} />
                        </linearGradient>
                      </defs>
                      <path d="M0 175 Q500 -8 1000 175 L1000 280 L0 280 Z" fill="url(#chat-roof)" opacity="0.95" />
                      <path d="M0 193 Q16 213 32 193 Q48 173 64 193 Q80 213 96 193 Q112 173 128 193 Q144 213 160 193 Q176 173 192 193 Q208 213 224 193 Q240 173 256 193 Q272 213 288 193 Q304 173 320 193 Q336 213 352 193 Q368 173 384 193 Q400 213 416 193 Q432 173 448 193 Q464 213 480 193 Q496 173 512 193 Q528 213 544 193 Q560 173 576 193 Q592 213 608 193 Q624 173 640 193 Q656 213 672 193 Q688 173 704 193 Q720 213 736 193 Q752 173 768 193 Q784 213 800 193 Q816 173 832 193 Q848 213 864 193 Q880 173 896 193 Q912 213 928 193 Q944 173 960 193 Q976 213 992 193" fill="none" stroke="rgba(255,216,150,0.78)" strokeWidth="3" />
                    </svg>

                    {/* Fabric weave + drape folds for tactile roof texture */}
                    <div
                      className="pointer-events-none absolute inset-0 opacity-[0.24]"
                      style={{
                        backgroundImage:
                          "linear-gradient(135deg, rgba(255,255,255,0.03) 25%, transparent 25%), linear-gradient(225deg, rgba(255,255,255,0.03) 25%, transparent 25%), linear-gradient(45deg, rgba(255,255,255,0.03) 25%, transparent 25%), linear-gradient(315deg, rgba(255,255,255,0.03) 25%, transparent 25%)",
                        backgroundSize: "4px 4px",
                        backgroundPosition: "0 0, 2px 0, 2px -2px, 0 2px"
                      }}
                    />
                    <div
                      className="pointer-events-none absolute inset-0 opacity-[0.20]"
                      style={{
                        background:
                          "linear-gradient(90deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0) 18%, rgba(255,255,255,0.08) 34%, rgba(255,255,255,0) 52%, rgba(255,255,255,0.07) 70%, rgba(255,255,255,0) 100%)"
                      }}
                    />

                    <div className="relative z-10 text-center">
                      <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-[#D8BF86]">Entering the tent</p>
                      <h2 className="festival-title mt-2 text-3xl font-black text-[#F5E4BD] sm:text-5xl">{vendor.name}</h2>
                      <p className="mt-2 text-sm font-semibold text-[#D8BF86]/95 sm:text-base">{vendor.banner}</p>
                    </div>

                    <div className="pointer-events-none absolute inset-x-8 top-14 z-10 flex justify-between">
                      {[0, 1, 2, 3, 4].map((n) => {
                        const phase = ratio * 8 + n * 0.9;
                        const swayX = Math.sin(phase) * 3;
                        const swayR = Math.sin(phase) * 4;
                        return (
                          <div key={`lantern-${n}`} className="relative" style={{ transform: `translateX(${swayX}px) rotate(${swayR}deg)` }}>
                            <span className="mx-auto block h-3 w-px bg-[#333]/80" />
                            <span className="mx-auto block h-7 w-px bg-white/24" />
                            <span
                              className="block h-6 w-4 rounded-full"
                              style={{
                                background: n % 2 === 0 ? theme.accent : "#FFB647",
                                boxShadow: `0 0 16px ${theme.glow}, 0 0 28px ${theme.glow}66`
                              }}
                            />
                          </div>
                        );
                      })}
                    </div>

                    {/* Lantern light wash onto the tent interior */}
                    <div className="pointer-events-none absolute inset-x-8 top-[78px] z-[9] flex justify-between">
                      {[0, 1, 2, 3, 4].map((n) => (
                        <span
                          key={`lantern-wash-${n}`}
                          className="h-28 w-36 rounded-[50%] blur-[18px]"
                          style={{
                            background:
                              n % 2 === 0
                                ? "radial-gradient(ellipse at 50% 10%, rgba(255,120,120,0.22) 0%, rgba(255,90,90,0.08) 40%, transparent 78%)"
                                : "radial-gradient(ellipse at 50% 10%, rgba(255,185,100,0.24) 0%, rgba(255,150,60,0.10) 40%, transparent 78%)"
                          }}
                        />
                      ))}
                    </div>

                    <button
                      onClick={onClose}
                      className="absolute right-5 top-5 z-30 rounded-full border border-white/12 bg-white/6 px-4 py-2 text-sm font-semibold text-[#E8D8A8] transition hover:bg-white/10"
                    >
                      Leave tent
                    </button>
                  </div>
                </header>

                <section className="relative z-10 px-4 pb-10 pt-6 sm:px-8">
                  <h3 className="festival-title mb-4 text-center text-2xl font-black text-[#F2DFB5]">Product Wall</h3>

                  <div className="mx-auto mb-4 flex max-w-4xl flex-col gap-3 rounded-2xl border border-[#E8D8A8]/18 bg-black/24 px-4 py-3 text-sm text-[#E8D8A8]/88 md:flex-row md:items-center md:justify-between">
                    <div>
                      <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-[#F5E4BD]">How to explore this tent</p>
                      <p className="mt-1">1. Choose a layer: Upper, Middle, or Lower.</p>
                      <p>2. Products on that wall layer become highlighted and easier to inspect.</p>
                      <p>3. Tap any hanging product card to inspect, or tap Ask below the mascot to chat.</p>
                    </div>
                    <button
                      onClick={() => setShowProductsSection((v) => !v)}
                      className="rounded-full border px-4 py-2 text-xs font-bold uppercase tracking-[0.12em]"
                      style={{
                        borderColor: `${theme.accent}95`,
                        color: showProductsSection ? "#120b07" : "#E8D8A8",
                        background: showProductsSection
                          ? `linear-gradient(180deg, ${theme.glow} 0%, ${theme.accent} 100%)`
                          : "rgba(0,0,0,0.24)",
                        boxShadow: showProductsSection ? `0 0 16px ${theme.accent}60` : "none"
                      }}
                    >
                      {showProductsSection ? "Hide products" : "Show products"}
                    </button>
                  </div>

                  <div className="relative mx-auto h-[520px] w-full max-w-5xl [perspective:1000px]">
                    <div className="pointer-events-none absolute inset-x-10 top-[56px] z-[11] h-[2px] bg-gradient-to-r from-transparent via-[#E8D8A8]/45 to-transparent" />
                    {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
                      <span
                        key={`hanger-${n}`}
                        className="pointer-events-none absolute z-[11] w-px bg-[#E8D8A8]/12"
                        style={{
                          left: `${5 + n * 9.5}%`,
                          top: "58px",
                          height: `${n % 2 === 0 ? 20 : 82}px`
                        }}
                      />
                    ))}

                    {/* Deep-stage parallax layers */}
                    <div
                      className="pointer-events-none absolute inset-0"
                      style={{ transform: `translate(${gaze.x * 6}px, ${gaze.y * 4}px)` }}
                    >
                      {/* Midground: blurry crate/shelf silhouettes */}
                      <div className="absolute left-[8%] top-[34%] h-20 w-28 rounded-lg border border-white/5 bg-black/28 blur-[1.2px]" />
                      <div className="absolute right-[10%] top-[40%] h-16 w-24 rounded-lg border border-white/5 bg-black/24 blur-[1.4px]" />
                      <div className="absolute left-[20%] top-[56%] h-[5px] w-36 rounded-full bg-[#3d2718]/70 blur-[1px]" />
                      <div className="absolute right-[22%] top-[60%] h-[5px] w-32 rounded-full bg-[#3d2718]/70 blur-[1px]" />
                    </div>

                    <div
                      className="pointer-events-none absolute inset-0"
                      style={{ transform: `translate(${gaze.x * 3}px, ${gaze.y * 2}px)` }}
                    >
                      {/* Background: slow bokeh motes */}
                      {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
                        <motion.span
                          key={`bokeh-${i}`}
                          className="absolute rounded-full bg-white/20"
                          style={{
                            left: `${10 + i * 11}%`,
                            top: `${18 + (i % 3) * 18}%`,
                            width: `${(i % 3) + 4}px`,
                            height: `${(i % 3) + 4}px`,
                            filter: "blur(1px)"
                          }}
                          animate={{ y: [0, -12, 0], opacity: [0.08, 0.24, 0.08] }}
                          transition={{ duration: 5 + i * 0.7, repeat: Infinity, ease: "easeInOut" }}
                        />
                      ))}
                    </div>

                    {/* Floor glow + path dots */}
                    <div className="pointer-events-none absolute inset-x-12 bottom-16 h-24 rounded-[50%] bg-black/35 blur-[10px]" />
                    <div
                      className="pointer-events-none absolute inset-x-16 bottom-14 h-14 rounded-[50%]"
                      style={{
                        background:
                          activeLayer === "upper"
                            ? "radial-gradient(ellipse, rgba(255,110,90,0.34) 0%, transparent 72%)"
                            : activeLayer === "middle"
                              ? `radial-gradient(ellipse, ${theme.accent}38 0%, transparent 72%)`
                              : "radial-gradient(ellipse, rgba(110,180,255,0.30) 0%, transparent 72%)"
                      }}
                    />

                    {/* Shopkeeper in the center of the stall */}
                    <motion.div
                      className="pointer-events-none absolute left-1/2 top-[58%] z-[16] -translate-x-1/2"
                      style={{
                        transform: `translate(-50%, 0) translateZ(96px)`,
                        filter: `drop-shadow(0 8px 16px rgba(0,0,0,0.55)) drop-shadow(0 0 18px ${theme.accent}55)`
                      }}
                      animate={{ y: [0, -4, 0] }}
                      transition={{ repeat: Infinity, duration: 2.6, ease: "easeInOut" }}
                    >
                      <div className="pointer-events-none absolute -bottom-1 left-1/2 h-3 w-20 -translate-x-1/2 rounded-full bg-black/45 blur-[2px]" />
                      <div className="pointer-events-none absolute bottom-0 left-1/2 h-7 w-24 -translate-x-1/2 bg-gradient-to-t from-black/75 via-black/26 to-transparent" />
                      <VendorBot status={vendor.status} accent={theme.accent} glow={theme.glow} lookX={gaze.x} lookY={gaze.y} />
                    </motion.div>

                    <div
                      className="pointer-events-none absolute left-1/2 top-[66%] z-[15] h-7 w-[220px] -translate-x-1/2 rounded-full"
                      style={{
                        background: "linear-gradient(180deg, rgba(12,8,6,0.96) 0%, rgba(5,4,3,0.98) 100%)",
                        boxShadow: "0 8px 16px rgba(0,0,0,0.48), inset 0 1px 0 rgba(255,255,255,0.06)"
                      }}
                    />

                    <motion.button
                      onClick={() => setChatOpen((v) => !v)}
                      className="absolute left-1/2 top-[73%] z-[20] -translate-x-1/2 rounded-full border px-5 py-2 text-xs font-bold uppercase tracking-[0.12em]"
                      style={{
                        borderColor: `${theme.accent}90`,
                        color: "#F5E4BD",
                        background: `radial-gradient(circle at 30% 30%, ${theme.glow}88 0%, ${theme.accent}88 55%, rgba(14,8,4,0.95) 100%)`,
                        boxShadow: `0 0 22px ${theme.accent}66`
                      }}
                      animate={{ scale: [1, 1.06, 1] }}
                      transition={{ repeat: Infinity, duration: 2.2, ease: "easeInOut" }}
                    >
                      {chatOpen ? "Close chat" : "Ask shopkeeper"}
                    </motion.button>

                    <motion.div
                      className="pointer-events-none absolute left-[56%] top-[56%] z-[20] max-w-[160px] rounded-2xl border border-white/20 bg-white/90 px-3 py-2 text-[10px] font-semibold text-[#5a3a1f]"
                      animate={{ opacity: [0, 1, 1, 0], y: [4, 0, 0, -2] }}
                      transition={{ duration: 3.8, repeat: Infinity, ease: "easeInOut" }}
                    >
                      {bubbleIndex === 0 ? "Pick any layer, I will guide you." : bubbleIndex === 1 ? "Try upper layer for featured pieces." : "Ask me about delivery and sizing."}
                      <span className="absolute -left-2 top-5 h-3 w-3 rotate-45 border-l border-b border-white/20 bg-white/90" />
                    </motion.div>

                    {/* Hanging wall products */}
                    {showProductsSection && (
                      <div className="absolute inset-0 z-[14] [transform-style:preserve-3d]">
                        {wallProducts.map(({ product, layer, posIdx, t, yCard, stringLen }) => {
                          const isActiveRow = layer === activeLayer;
                          const hovered = hoveredId === product.id;
                          const x = t * 840;
                          const z = isActiveRow ? 36 : 4;
                          const rotY = t * 6;

                          const hoverScale = hovered && isActiveRow ? 1.18 : 1;
                          const hoverZ = hovered && isActiveRow ? z + 32 : z;
                          const hoverRotY = hovered && isActiveRow ? 0 : rotY;

                          return (
                            <article
                              key={product.id}
                              className="group absolute left-1/2 top-0 w-[86px] cursor-pointer rounded-xl border p-1.5"
                              onMouseEnter={() => {
                                setHoveredId(product.id);
                                playInspectClick();
                              }}
                              onMouseLeave={() => setHoveredId(null)}
                              onClick={() => setSelectedProduct(product)}
                              style={{
                                zIndex: 45 + (isActiveRow ? 20 : 0) + (hovered ? 10 : 0),
                                transformOrigin: "top center",
                                transform: `translate(-50%, 0) translateX(${x}px) translateY(${yCard}px) translateZ(${hoverZ}px) rotateY(${hoverRotY}deg) scale(${hoverScale})`,
                                opacity: isActiveRow ? 1 : 0.35,
                                filter: `blur(${isActiveRow ? 0 : 0.8}px)`,
                                background: "linear-gradient(180deg, rgba(56,34,22,0.94) 0%, rgba(26,14,8,0.94) 100%)",
                                borderColor: `${theme.accent}${isActiveRow ? "9C" : "44"}`,
                                boxShadow: hovered
                                  ? `0 10px 22px rgba(0,0,0,0.52), 0 0 14px ${theme.accent}66`
                                  : "0 6px 14px rgba(0,0,0,0.36)",
                                transition: "transform 0.22s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.18s ease, opacity 0.18s ease"
                              }}
                            >
                              <span
                                className="pointer-events-none absolute left-1/2 -translate-x-1/2 w-px bg-[#E8D8A8]/40"
                                style={{ top: `-${stringLen}px`, height: `${stringLen}px` }}
                              />

                              {hovered && (
                                <div
                                  className="pointer-events-none absolute left-1/2 -translate-x-1/2"
                                  style={{
                                    top: `-${stringLen + 40}px`,
                                    height: "68px",
                                    width: "48px",
                                    clipPath: "polygon(46% 0%, 54% 0%, 100% 100%, 0% 100%)",
                                    background: `radial-gradient(ellipse at 50% 8%, ${theme.glow}88 0%, ${theme.accent}33 38%, transparent 78%)`,
                                    filter: "blur(1px)"
                                  }}
                                />
                              )}

                              <img
                                src={product.image}
                                alt={product.name}
                                className="h-14 w-full rounded-lg object-cover brightness-[0.86] transition duration-300 group-hover:brightness-100"
                                loading="lazy"
                              />
                              <h4 className="mt-1 line-clamp-1 text-[9px] font-black text-[#F5E4BD]">{product.name}</h4>
                              <p className="text-[9px] font-extrabold" style={{ color: theme.glow }}>{product.price}</p>

                              {isCitrus && (
                                <div
                                  className="pointer-events-none absolute inset-0 rounded-xl"
                                  style={{
                                    background: "linear-gradient(120deg, rgba(255,255,255,0.12), rgba(255,255,255,0.03))",
                                    backdropFilter: "blur(8px)",
                                    WebkitBackdropFilter: "blur(8px)"
                                  }}
                                />
                              )}
                            </article>
                          );
                        })}
                      </div>
                    )}

                    {!showProductsSection && (
                      <div className="absolute inset-x-0 top-[42%] z-[19] flex justify-center">
                        <div className="rounded-2xl border border-white/20 bg-black/35 px-5 py-3 text-sm text-[#E8D8A8]/90">
                          Products are hidden for this store view. Use Show products to browse layers.
                        </div>
                      </div>
                    )}

                    {/* Layer navigation controls */}
                    <div className="absolute inset-x-0 bottom-2 z-30 flex flex-col items-center gap-2">
                      <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#D8BF86]/80">Choose product layer</p>
                      <div className="flex items-center justify-center gap-3">
                        {(["upper", "middle", "lower"] as const).map((layer) => {
                          const active = layer === activeLayer;
                        return (
                          <button
                              key={`layer-${layer}`}
                              onClick={() => setActiveLayer(layer)}
                              className="rounded-full border px-4 py-1.5 text-[11px] font-bold uppercase tracking-[0.12em]"
                              disabled={!showProductsSection}
                              style={{
                                borderColor: active ? `${theme.accent}C0` : "rgba(255,255,255,0.24)",
                                color: !showProductsSection ? "#9d916f" : active ? "#120b07" : "#E8D8A8",
                                background: active
                                  ? `linear-gradient(180deg, ${theme.glow} 0%, ${theme.accent} 100%)`
                                  : "rgba(0,0,0,0.26)",
                                boxShadow: active ? `0 0 16px ${theme.accent}77` : "none"
                              }}
                              aria-label={`Show ${layer} product layer`}
                            >
                              {layer}
                            </button>
                        );
                      })}
                      </div>
                    </div>
                  </div>
                </section>

                <AnimatePresence>
                  {chatOpen && (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.92, y: 18 }}
                      animate={{ opacity: 1, scale: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.92, y: 14 }}
                      transition={{ duration: 0.25, ease: "easeOut" }}
                      className="absolute left-1/2 top-[40%] z-40 w-[min(460px,92vw)] -translate-x-1/2 rounded-[24px] border p-4"
                      style={{
                        borderColor: `${theme.accent}80`,
                        background: "linear-gradient(180deg, rgba(245,222,179,0.88) 0%, rgba(225,196,147,0.84) 100%)",
                        boxShadow: `0 24px 46px rgba(0,0,0,0.5), 0 0 24px ${theme.accent}66`
                      }}
                    >
                      <p className="festival-title text-xl font-black text-[#4c2e13]">Ask {vendor.name.split(" ")[0]}</p>
                      <p className="mt-1 text-sm text-[#6b4524]">Need sizing, styling, or delivery info? I can guide you through the collection.</p>

                      <div className="custom-scroll-dark mt-3 max-h-40 space-y-2 overflow-y-auto rounded-xl border border-[#8a6235]/28 bg-[#fff7e7]/65 p-2">
                        {messages.map((message) => (
                          <div key={message.id} className={`flex ${message.from === "user" ? "justify-end" : "justify-start"}`}>
                            <div
                              className={`max-w-[88%] rounded-2xl px-3 py-2 text-xs ${
                                message.from === "user"
                                  ? "text-[#130d06]"
                                  : "border border-[#8a6235]/22 bg-[#fffaf0]/85 text-[#50361f]"
                              }`}
                              style={message.from === "user" ? { background: `linear-gradient(180deg, ${theme.glow} 0%, ${theme.accent} 100%)` } : undefined}
                            >
                              {message.text}
                            </div>
                          </div>
                        ))}
                        {typing && <p className="text-xs text-[#6d4525]/75">Thinking...</p>}
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2">
                        {quickQuestions.map((question) => (
                          <button
                            key={question}
                            onClick={() => send(question)}
                            className="rounded-full border border-[#7d532b]/35 bg-[#fff5df]/75 px-3 py-1 text-xs font-semibold text-[#6d4525]"
                          >
                            {question}
                          </button>
                        ))}
                      </div>

                      <div className="mt-3 flex gap-2">
                        <input
                          value={input}
                          onChange={(event) => setInput(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter") send();
                          }}
                          placeholder={`Ask ${vendor.name.split(" ")[0]}...`}
                          className="w-full rounded-xl border border-[#7d532b]/28 bg-[#fffaf0]/75 px-3 py-2 text-xs text-[#5a3c22] outline-none"
                        />
                        <button
                          onClick={() => send()}
                          className="rounded-xl px-3 py-2 text-xs font-semibold text-[#130d06]"
                          style={{ background: `linear-gradient(180deg, ${theme.glow} 0%, ${theme.accent} 100%)` }}
                        >
                          Send
                        </button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                <AnimatePresence>
                  {selectedProduct && !chatOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 8 }}
                      className="pointer-events-none absolute bottom-5 right-6 z-30 hidden max-w-sm rounded-2xl border bg-black/35 p-3 md:block"
                      style={{ borderColor: `${theme.accent}44`, boxShadow: `0 0 20px ${theme.accent}33` }}
                    >
                      <p className="text-[10px] uppercase tracking-[0.2em] text-[#D8BF86]/70">Spotlight</p>
                      <p className="mt-1 text-sm font-bold text-[#F5E4BD]">{selectedProduct.name}</p>
                      <p className="text-xs" style={{ color: theme.glow }}>{selectedProduct.price}</p>
                    </motion.div>
                  )}
                </AnimatePresence>

                <AnimatePresence>
                  {showIntro && (
                    <motion.div
                      initial={{ opacity: 1 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.65, ease: "easeInOut" }}
                      className="absolute inset-0 z-50 flex items-center justify-center bg-[#020207]"
                    >
                      <motion.div
                        className="absolute inset-y-0 left-0 w-1/2 bg-[#0b0605]"
                        initial={{ x: 0 }}
                        animate={{ x: "-110%" }}
                        transition={{ duration: 0.95, ease: [0.2, 0.8, 0.2, 1] }}
                      />
                      <motion.div
                        className="absolute inset-y-0 right-0 w-1/2 bg-[#0b0605]"
                        initial={{ x: 0 }}
                        animate={{ x: "110%" }}
                        transition={{ duration: 0.95, ease: [0.2, 0.8, 0.2, 1] }}
                      />

                      <motion.div
                        initial={{ scale: 1.12, opacity: 0.2 }}
                        animate={{ scale: [1.12, 1, 0.96], opacity: [0.2, 1, 0] }}
                        transition={{ duration: 0.9, ease: "easeOut" }}
                        className="text-center"
                      >
                        <p className="text-xs font-bold uppercase tracking-[0.3em] text-[#D8BF86]/72">Entering Tent</p>
                        <h3 className="festival-title mt-4 text-4xl font-black text-[#F5E4BD] sm:text-6xl">{vendor.name}</h3>
                      </motion.div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
