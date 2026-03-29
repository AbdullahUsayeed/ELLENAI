"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { VendorBot } from "@/components/VendorBot";
import type { MessageRecord, ProductRecord, ShopRecord } from "@/lib/types/marketplace";

type ShopInteriorImmersiveProps = {
  shop: ShopRecord;
  products: ProductRecord[];
};

type InteriorTheme = {
  roofA: string;
  roofB: string;
  accent: string;
  glow: string;
  shelfA: string;
  shelfB: string;
};

type TentEnterTransition = {
  x: number;
  y: number;
  accent?: string;
  playSound?: boolean;
  at?: number;
};

const QUICK_PROMPTS = ["Is this available now?", "Any other color?", "Can I get express delivery?"];

function formatMessageTime(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit"
  }).format(new Date(value));
}

const THEMES: Record<ShopRecord["tent_theme"], InteriorTheme> = {
  "fashion-edit": {
    roofA: "#4A0812",
    roofB: "#8C1520",
    accent: "#ff4d4d",
    glow: "#ff7f7f",
    shelfA: "#3b2415",
    shelfB: "#24140b"
  },
  "tech-hub": {
    roofA: "#071860",
    roofB: "#1240B0",
    accent: "#2C8EFF",
    glow: "#78caff",
    shelfA: "#2e3844",
    shelfB: "#181e26"
  },
  "snack-bar": {
    roofA: "#6A3008",
    roofB: "#B46015",
    accent: "#E88C1A",
    glow: "#ffc060",
    shelfA: "#4a2d18",
    shelfB: "#25170d"
  },
  "ritual-corner": {
    roofA: "#063830",
    roofB: "#0A8870",
    accent: "#0FA29A",
    glow: "#66efe7",
    shelfA: "#2e3e38",
    shelfB: "#17241f"
  },
  "gem-counter": {
    roofA: "#4A3408",
    roofB: "#A07818",
    accent: "#C8941A",
    glow: "#ffe389",
    shelfA: "#4a3a1f",
    shelfB: "#271f11"
  },
  "home-finds": {
    roofA: "#441808",
    roofB: "#904020",
    accent: "#C06830",
    glow: "#ffba87",
    shelfA: "#4c2d20",
    shelfB: "#2a1810"
  }
};

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

export function ShopInteriorImmersive({ shop, products }: ShopInteriorImmersiveProps) {
  const theme = THEMES[shop.tent_theme];
  const [scrollTop, setScrollTop] = useState(0);
  const [scrollMax, setScrollMax] = useState(1);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [entered, setEntered] = useState(false);
  const [titleReady, setTitleReady] = useState(false);
  const [enterTransition, setEnterTransition] = useState<TentEnterTransition | null>(null);
  const [buyerName, setBuyerName] = useState("Festival Guest");
  const [draftMessage, setDraftMessage] = useState("");
  const [messages, setMessages] = useState<MessageRecord[]>([]);
  const [chatBusy, setChatBusy] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  const ratio = scrollTop / scrollMax;
  const buyerStorageKey = `vendor-chat-name:${shop.id}`;

  const visibleMessages = useMemo(
    () => messages.filter((message) => message.is_from_seller || message.sender_name === buyerName),
    [buyerName, messages]
  );

  useEffect(() => {
    const timer = window.setTimeout(() => setTitleReady(true), 220);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    try {
      const savedName = window.localStorage.getItem(buyerStorageKey);
      if (savedName) {
        setBuyerName(savedName);
      }
    } catch {
      // Ignore storage failures.
    }
  }, [buyerStorageKey]);

  useEffect(() => {
    try {
      window.localStorage.setItem(buyerStorageKey, buyerName.trim() || "Festival Guest");
    } catch {
      // Ignore storage failures.
    }
  }, [buyerName, buyerStorageKey]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem("tent-enter-transition");
      if (!raw) return;

      const parsed = JSON.parse(raw) as TentEnterTransition;
      window.localStorage.removeItem("tent-enter-transition");

      // Ignore very old transition payloads.
      if (parsed.at && Date.now() - parsed.at > 6000) {
        return;
      }

      setEnterTransition(parsed);
      if (parsed.playSound) {
        playCurtainRustle();
      }
    } catch {
      // Ignore malformed storage payloads.
    }

    const revealTimer = window.setTimeout(() => setEntered(true), 950);
    return () => window.clearTimeout(revealTimer);
  }, []);

  const stars = useMemo(
    () =>
      Array.from({ length: 34 }, (_, i) => {
        const seed = (shop.slug.length + 7) * (i + 17);
        return {
          key: `${shop.id}-star-${i}`,
          left: 2 + ((seed * 23) % 96),
          top: 6 + ((seed * 11) % 56),
          size: i % 4 === 0 ? 2.8 : i % 3 === 0 ? 2.1 : 1.5,
          twinkle: 1.7 + (i % 6) * 0.3,
          drift: i % 2 === 0 ? 1 : -1
        };
      }),
    [shop.id, shop.slug.length]
  );

  const leftRack = useMemo(() => products.slice(0, 3), [products]);
  const rightRack = useMemo(() => {
    if (products.length <= 3) {
      return products.slice(0, Math.min(3, products.length));
    }
    return products.slice(3, 6);
  }, [products]);

  useEffect(() => {
    if (!chatOpen) {
      return;
    }

    let cancelled = false;

    const syncMessages = async () => {
      try {
        const response = await fetch(`/api/messages/${shop.id}`, { cache: "no-store" });
        const payload = (await response.json()) as { success: boolean; data?: MessageRecord[]; error?: string };

        if (!response.ok || !payload.success || !payload.data) {
          throw new Error(payload.error || "Unable to load messages.");
        }

        if (!cancelled) {
          setMessages(payload.data);
          setChatError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setChatError(error instanceof Error ? error.message : "Unable to load messages.");
        }
      }
    };

    void syncMessages();
    const poller = window.setInterval(() => {
      void syncMessages();
    }, 5000);

    return () => {
      cancelled = true;
      window.clearInterval(poller);
    };
  }, [chatOpen, shop.id]);

  const sendMessage = async (messageText: string) => {
    const trimmedMessage = messageText.trim();
    const trimmedName = buyerName.trim() || "Festival Guest";

    if (!trimmedMessage) {
      return;
    }

    setChatBusy(true);
    setChatError(null);
    try {
      const response = await fetch("/api/messages/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shop_id: shop.id,
          sender_name: trimmedName,
          message: trimmedMessage,
          is_from_seller: false
        })
      });

      const payload = (await response.json()) as {
        success: boolean;
        data?: { message: MessageRecord; autoReply?: MessageRecord | null };
        error?: string;
      };

      if (!response.ok || !payload.success || !payload.data) {
        throw new Error(payload.error || "Unable to send message.");
      }

      setMessages((current) => {
        const next = [...current, payload.data!.message];
        if (payload.data?.autoReply) {
          next.push(payload.data.autoReply);
        }
        return next;
      });
      setDraftMessage("");
    } catch (error) {
      setChatError(error instanceof Error ? error.message : "Unable to send message.");
    } finally {
      setChatBusy(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#070B18] text-[#E8D8A8]">
      <div className="mx-auto max-w-6xl px-4 py-5 sm:px-6 lg:px-8">
        <div
          className="relative overflow-hidden rounded-[32px] border shadow-[0_28px_90px_rgba(0,0,0,0.48)]"
          style={{
            borderColor: `${theme.accent}66`,
            background: `radial-gradient(ellipse at 50% 45%, ${theme.accent}22 0%, rgba(10,12,26,0.78) 48%, rgba(2,2,8,0.95) 100%)`
          }}
        >
          <div className="pointer-events-none absolute inset-0 z-0">
            <div className="absolute inset-0" style={{ boxShadow: "inset 0 0 130px rgba(0,0,0,0.85)" }} />
            {stars.map((star) => (
              <span
                key={star.key}
                className="absolute rounded-full"
                style={{
                  left: `${star.left}%`,
                  top: `${star.top}%`,
                  width: `${star.size}px`,
                  height: `${star.size}px`,
                  background: "rgba(255,236,185,0.85)",
                  boxShadow: `0 0 8px ${theme.glow}`,
                  transform: `translate(${star.drift * ratio * 14}px, ${-scrollTop * 0.13}px)`,
                  opacity: 0.35 + Math.abs(Math.sin(ratio * star.twinkle)) * 0.6
                }}
              />
            ))}
          </div>

          <header className="sticky top-0 z-20 border-b bg-[#0A0D1BCC]/95 backdrop-blur-md" style={{ borderColor: `${theme.accent}3f` }}>
            <div className="relative h-[230px] overflow-hidden px-5 pt-4 sm:h-[258px] sm:px-8">
              <svg viewBox="0 0 1000 300" className="absolute inset-0 h-full w-full" preserveAspectRatio="none" aria-hidden="true">
                <defs>
                  <linearGradient id="interior-roof" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor={theme.roofA} />
                    <stop offset="50%" stopColor={theme.roofB} />
                    <stop offset="100%" stopColor={theme.roofA} />
                  </linearGradient>
                </defs>
                <path d="M0 188 Q500 -8 1000 188 L1000 300 L0 300 Z" fill="url(#interior-roof)" opacity="0.95" />
                <path d="M0 205 Q16 225 32 205 Q48 185 64 205 Q80 225 96 205 Q112 185 128 205 Q144 225 160 205 Q176 185 192 205 Q208 225 224 205 Q240 185 256 205 Q272 225 288 205 Q304 185 320 205 Q336 225 352 205 Q368 185 384 205 Q400 225 416 205 Q432 185 448 205 Q464 225 480 205 Q496 185 512 205 Q528 225 544 205 Q560 185 576 205 Q592 225 608 205 Q624 185 640 205 Q656 225 672 205 Q688 185 704 205 Q720 225 736 205 Q752 185 768 205 Q784 225 800 205 Q816 185 832 205 Q848 225 864 205 Q880 185 896 205 Q912 225 928 205 Q944 185 960 205 Q976 225 992 205" fill="none" stroke="rgba(255,216,150,0.78)" strokeWidth="3" />
              </svg>

              <motion.div
                className="relative z-10 text-center"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: titleReady ? 1 : 0, y: titleReady ? 0 : 12 }}
                transition={{ duration: 0.5, ease: "easeOut" }}
              >
                <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#D8BF86]/75">Moonthread Atelier</p>
                <h1 className="festival-title mt-2 text-3xl font-black text-[#F5E4BD] sm:text-5xl">{shop.shop_name}</h1>
                <p className="mt-2 text-sm text-[#C8B68E]/80">{shop.slug} • {products.length} curated pieces</p>
              </motion.div>

              <div className="pointer-events-none absolute inset-x-8 top-16 z-10 flex justify-between">
                {[0, 1, 2, 3, 4].map((n) => {
                  const phase = ratio * 8 + n * 0.9;
                  const swayX = Math.sin(phase) * 3;
                  const swayR = Math.sin(phase) * 4;
                  return (
                    <div key={`lantern-${n}`} className="relative" style={{ transform: `translateX(${swayX}px) rotate(${swayR}deg)` }}>
                      <span className="mx-auto block h-6 w-[1px] bg-white/30" />
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

              <motion.div
                className="absolute left-6 top-6 z-30"
                animate={{ y: [0, -6, 0] }}
                transition={{ repeat: Infinity, duration: 2.6, ease: "easeInOut" }}
              >
                <VendorBot status="active" accent={theme.accent} glow={theme.glow} />
              </motion.div>

              <motion.button
                onClick={() => setChatOpen((v) => !v)}
                className="absolute left-20 top-20 z-30 h-14 w-14 rounded-full border text-xs font-bold uppercase tracking-[0.08em]"
                style={{
                  borderColor: `${theme.accent}80`,
                  color: "#F5E4BD",
                  background: `radial-gradient(circle at 30% 30%, ${theme.glow}88 0%, ${theme.accent}88 55%, rgba(14,8,4,0.95) 100%)`,
                  boxShadow: `0 0 22px ${theme.accent}66`
                }}
                animate={{ scale: [1, 1.06, 1] }}
                transition={{ repeat: Infinity, duration: 2.2, ease: "easeInOut" }}
              >
                Ask
              </motion.button>
            </div>
          </header>

          <section
            className="custom-scroll-dark relative z-10 h-[calc(100vh-140px)] overflow-y-auto px-4 pb-10 pt-8 sm:px-8"
            onScroll={(event) => {
              const el = event.currentTarget;
              setScrollTop(el.scrollTop);
              setScrollMax(Math.max(1, el.scrollHeight - el.clientHeight));
            }}
          >
            <h2 className="festival-title mb-6 text-center text-2xl font-black text-[#F2DFB5]">Product Wall</h2>
            <div className="relative mx-auto max-w-6xl pb-16 [perspective:1200px]">
              <div className="pointer-events-none absolute inset-x-10 top-8 h-14 rounded-[50%] bg-black/40 blur-[8px]" />

              <div className="grid items-start gap-6 lg:grid-cols-[1fr_360px_1fr] lg:gap-8 [transform-style:preserve-3d]">
                <div className="space-y-5 [transform-style:preserve-3d]" style={{ transform: "rotateY(25deg) translateZ(0px)", transformOrigin: "right center" }}>
                  {leftRack.map((product, idx) => {
                    const hovered = hoveredId === product.id;
                    const yOffset = idx * 20;
                    return (
                      <motion.article
                        key={product.id}
                        className="group relative rounded-2xl border p-3 sm:p-4"
                        onMouseEnter={() => setHoveredId(product.id)}
                        onMouseLeave={() => setHoveredId(null)}
                        whileHover={{ rotateY: 0, scale: 1.1, z: 42 }}
                        transition={{ type: "spring", stiffness: 170, damping: 18 }}
                        style={{
                          transform: `translateY(${yOffset}px)`,
                          background: `linear-gradient(180deg, ${theme.shelfA}F1 0%, ${theme.shelfB}F2 100%)`,
                          borderColor: `${theme.accent}82`,
                          boxShadow: hovered
                            ? `-18px 16px 26px rgba(0,0,0,0.42), -28px 24px 36px rgba(0,0,0,0.36), 0 0 36px ${theme.accent}70`
                            : `-14px 12px 22px rgba(0,0,0,0.4), -22px 18px 30px rgba(0,0,0,0.28)`
                        }}
                      >
                        <span className="pointer-events-none absolute -top-[42px] left-4 h-[42px] w-px bg-[#e8d8a8]/55" />
                        <span className="pointer-events-none absolute -top-[42px] right-4 h-[42px] w-px bg-[#e8d8a8]/55" />
                        <div className="grid gap-3 sm:grid-cols-[120px_1fr] sm:gap-4">
                          <img
                            src={product.image_url || "https://picsum.photos/600/420?grayscale"}
                            alt={product.name}
                            className="h-24 w-full rounded-xl object-cover sm:h-32"
                            loading="lazy"
                          />
                          <div>
                            <h3 className="text-base font-black text-[#F5E4BD] sm:text-lg">{product.name}</h3>
                            <p className="mt-1 line-clamp-2 text-xs leading-5 text-[#D5C7A2]/82 sm:text-sm">{product.description}</p>
                            <div className="mt-3 flex items-center justify-between">
                              <span className="text-sm font-extrabold" style={{ color: theme.glow }}>BDT {product.price}</span>
                              <span className="text-[10px] uppercase tracking-[0.16em] text-[#C8B68E]/70">Stock {product.stock}</span>
                            </div>
                          </div>
                        </div>
                      </motion.article>
                    );
                  })}
                </div>

                <div className="relative min-h-[360px] [transform-style:preserve-3d]">
                  <div
                    className="pointer-events-none absolute left-1/2 top-[90px] h-44 w-44 -translate-x-1/2 rounded-full"
                    style={{
                      background: `radial-gradient(circle, ${theme.accent}75 0%, ${theme.accent}22 45%, transparent 72%)`,
                      boxShadow: `0 0 52px ${theme.accent}66`
                    }}
                  />

                  <motion.div
                    className="absolute left-1/2 top-[70px] -translate-x-1/2 [transform-style:preserve-3d]"
                    style={{ transform: "translateZ(100px)" }}
                    animate={{ y: [0, -4, 0] }}
                    transition={{ repeat: Infinity, duration: 2.4, ease: "easeInOut" }}
                  >
                    <VendorBot status="active" accent={theme.accent} glow={theme.glow} />
                  </motion.div>

                  <div
                    className="absolute left-1/2 top-[185px] h-7 w-[78%] -translate-x-1/2 rounded-full"
                    style={{
                      background: "linear-gradient(180deg, rgba(18,12,8,0.95) 0%, rgba(6,4,3,0.98) 100%)",
                      boxShadow: "0 8px 18px rgba(0,0,0,0.48), inset 0 1px 0 rgba(255,255,255,0.06)"
                    }}
                  />

                  <div
                    className="absolute left-1/2 top-[205px] h-12 w-[86%] -translate-x-1/2 rounded-[20px] border"
                    style={{
                      borderColor: `${theme.accent}50`,
                      background: "linear-gradient(180deg, rgba(54,34,21,0.9) 0%, rgba(23,14,9,0.95) 100%)"
                    }}
                  />
                </div>

                <div className="space-y-5 [transform-style:preserve-3d]" style={{ transform: "rotateY(-25deg) translateZ(0px)", transformOrigin: "left center" }}>
                  {rightRack.map((product, idx) => {
                    const hovered = hoveredId === product.id;
                    const yOffset = idx * 20;
                    return (
                      <motion.article
                        key={product.id}
                        className="group relative rounded-2xl border p-3 sm:p-4"
                        onMouseEnter={() => setHoveredId(product.id)}
                        onMouseLeave={() => setHoveredId(null)}
                        whileHover={{ rotateY: 0, scale: 1.1, z: 42 }}
                        transition={{ type: "spring", stiffness: 170, damping: 18 }}
                        style={{
                          transform: `translateY(${yOffset}px)`,
                          background: `linear-gradient(180deg, ${theme.shelfA}F1 0%, ${theme.shelfB}F2 100%)`,
                          borderColor: `${theme.accent}82`,
                          boxShadow: hovered
                            ? `18px 16px 26px rgba(0,0,0,0.42), 28px 24px 36px rgba(0,0,0,0.36), 0 0 36px ${theme.accent}70`
                            : `14px 12px 22px rgba(0,0,0,0.4), 22px 18px 30px rgba(0,0,0,0.28)`
                        }}
                      >
                        <span className="pointer-events-none absolute -top-[42px] left-4 h-[42px] w-px bg-[#e8d8a8]/55" />
                        <span className="pointer-events-none absolute -top-[42px] right-4 h-[42px] w-px bg-[#e8d8a8]/55" />
                        <div className="grid gap-3 sm:grid-cols-[120px_1fr] sm:gap-4">
                          <img
                            src={product.image_url || "https://picsum.photos/600/420?grayscale"}
                            alt={product.name}
                            className="h-24 w-full rounded-xl object-cover sm:h-32"
                            loading="lazy"
                          />
                          <div>
                            <h3 className="text-base font-black text-[#F5E4BD] sm:text-lg">{product.name}</h3>
                            <p className="mt-1 line-clamp-2 text-xs leading-5 text-[#D5C7A2]/82 sm:text-sm">{product.description}</p>
                            <div className="mt-3 flex items-center justify-between">
                              <span className="text-sm font-extrabold" style={{ color: theme.glow }}>BDT {product.price}</span>
                              <span className="text-[10px] uppercase tracking-[0.16em] text-[#C8B68E]/70">Stock {product.stock}</span>
                            </div>
                          </div>
                        </div>
                      </motion.article>
                    );
                  })}
                </div>
              </div>

              {products.length === 0 && (
                <p className="mt-8 text-center text-sm text-[#D5C7A2]/82">No products yet. Add items to bring this tent to life.</p>
              )}
            </div>
          </section>

          <AnimatePresence>
            {chatOpen && (
              <motion.div
                initial={{ opacity: 0, scale: 0.92, x: -24, y: -12 }}
                animate={{ opacity: 1, scale: 1, x: 0, y: 0 }}
                exit={{ opacity: 0, scale: 0.92, x: -20, y: -10 }}
                transition={{ duration: 0.25, ease: "easeOut" }}
                className="absolute left-6 top-[136px] z-40 w-[min(360px,86vw)] rounded-[24px] border p-4"
                style={{
                  borderColor: `${theme.accent}80`,
                  background: "linear-gradient(180deg, rgba(245,222,179,0.88) 0%, rgba(225,196,147,0.84) 100%)",
                  boxShadow: `0 24px 46px rgba(0,0,0,0.5), 0 0 24px ${theme.accent}66`
                }}
              >
                <p className="festival-title text-xl font-black text-[#4c2e13]">Ask {shop.shop_name.split(" ")[0]}</p>
                <p className="mt-1 text-sm text-[#6b4524]">Live shop assistant for sizing, styling, delivery, and stock checks. Replies refresh every 5 seconds.</p>
                <div className="mt-4 grid gap-3">
                  <label className="block">
                    <span className="mb-1 block text-[11px] font-bold uppercase tracking-[0.18em] text-[#7b522b]">Your name</span>
                    <input
                      value={buyerName}
                      onChange={(event) => setBuyerName(event.target.value)}
                      maxLength={40}
                      className="w-full rounded-2xl border border-[#7d532b]/30 bg-[#fff7e7]/85 px-3 py-2 text-sm text-[#5b381c] outline-none"
                      placeholder="Festival Guest"
                    />
                  </label>

                  <div className="max-h-72 space-y-3 overflow-y-auto rounded-[20px] border border-[#7d532b]/18 bg-[#fff9ee]/70 p-3">
                    {visibleMessages.length === 0 && !chatError && (
                      <p className="text-sm text-[#6b4524]">Start with a quick question and the mascot will answer right away.</p>
                    )}
                    {visibleMessages.map((message) => {
                      const isSeller = message.is_from_seller;
                      return (
                        <div key={message.id} className={`flex ${isSeller ? "justify-start" : "justify-end"}`}>
                          <div className={`max-w-[85%] rounded-[18px] px-3 py-2 ${isSeller ? "bg-[#6a3b1d] text-[#fff6e3]" : "bg-[#f3d39d] text-[#4a2d13]"}`}>
                            <p className="text-[11px] font-bold uppercase tracking-[0.14em] opacity-75">{message.sender_name}</p>
                            <p className="mt-1 text-sm leading-5">{message.message}</p>
                            <p className="mt-1 text-[11px] opacity-70">{formatMessageTime(message.created_at)}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {chatError && <p className="rounded-2xl border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-700">{chatError}</p>}

                  <div className="flex flex-wrap gap-2">
                    {QUICK_PROMPTS.map((prompt) => (
                      <button
                        key={prompt}
                        type="button"
                        onClick={() => void sendMessage(prompt)}
                        disabled={chatBusy}
                        className="rounded-full border border-[#7d532b]/35 bg-[#fff5df]/75 px-3 py-1 text-xs font-semibold text-[#6d4525] disabled:opacity-60"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>

                  <div className="flex gap-2">
                    <input
                      value={draftMessage}
                      onChange={(event) => setDraftMessage(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          void sendMessage(draftMessage);
                        }
                      }}
                      className="flex-1 rounded-2xl border border-[#7d532b]/30 bg-[#fff7e7]/85 px-3 py-2 text-sm text-[#5b381c] outline-none"
                      placeholder="Ask about stock, color, or delivery"
                    />
                    <button
                      type="button"
                      onClick={() => void sendMessage(draftMessage)}
                      disabled={chatBusy || !draftMessage.trim()}
                      className="rounded-2xl bg-[#6a3b1d] px-4 py-2 text-sm font-bold text-[#fff5df] disabled:opacity-60"
                    >
                      {chatBusy ? "Sending..." : "Send"}
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {!entered && (
              <motion.div
                initial={{ opacity: 1 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.65, ease: "easeInOut" }}
                className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-[#020207]"
              >
                {enterTransition && (
                  <motion.div
                    className="pointer-events-none absolute h-24 w-24 rounded-full"
                    style={{
                      left: enterTransition.x - 48,
                      top: enterTransition.y - 48,
                      background: `radial-gradient(circle, ${(enterTransition.accent ?? theme.accent)} 0%, transparent 70%)`,
                      boxShadow: `0 0 40px ${(enterTransition.accent ?? theme.accent)}88`
                    }}
                    initial={{ scale: 0.2, opacity: 0.9 }}
                    animate={{ scale: 22, opacity: 0 }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                  />
                )}

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
                  <h2 className="festival-title mt-4 text-4xl font-black text-[#F5E4BD] sm:text-6xl">{shop.shop_name}</h2>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </main>
  );
}
