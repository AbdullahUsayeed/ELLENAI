"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { TENT_THEMES } from "@/lib/constants/tent-themes";
import type { TentTheme } from "@/lib/constants/tent-themes";
import type { MessageRecord, OrderRecord, ProductRecord, ShopRecord } from "@/lib/types/marketplace";

type SellerDashboardProps = {
  shop: ShopRecord;
  products: ProductRecord[];
  orders: OrderRecord[];
  initialMessages: MessageRecord[];
};

function formatMessageTime(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(new Date(value));
}

export function SellerDashboard({ shop, products, orders, initialMessages }: SellerDashboardProps) {
  const router = useRouter();
  const [shopName, setShopName] = useState(shop.shop_name);
  const [bkashNumber, setBkashNumber] = useState(shop.bkash_number ?? "");
  const [tentTheme, setTentTheme] = useState(shop.tent_theme);
  const [logoUrl, setLogoUrl] = useState(shop.logo_url ?? "");
  const [ordersState, setOrdersState] = useState<OrderRecord[]>(orders);
  const [messages, setMessages] = useState<MessageRecord[]>(initialMessages);
  const [replyMessage, setReplyMessage] = useState("");
  const [productForm, setProductForm] = useState({
    name: "",
    description: "",
    price: "",
    image_url: "",
    stock: "1"
  });
  const [error, setError] = useState<string | null>(null);
  const [messageError, setMessageError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"shop" | "product" | "logout" | "reply" | null>(null);
  const [updatingOrderId, setUpdatingOrderId] = useState<string | null>(null);

  useEffect(() => {
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
          setMessageError(null);
        }
      } catch (fetchError) {
        if (!cancelled) {
          setMessageError(fetchError instanceof Error ? fetchError.message : "Unable to load messages.");
        }
      }
    };

    const poller = window.setInterval(() => {
      void syncMessages();
    }, 5000);

    return () => {
      cancelled = true;
      window.clearInterval(poller);
    };
  }, [shop.id]);

  const saveShop = async () => {
    setBusy("shop");
    setError(null);
    try {
      const response = await fetch("/api/shop/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shop_name: shopName,
          bkash_number: bkashNumber,
          tent_theme: tentTheme,
          logo_url: logoUrl
        })
      });

      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || "Unable to update shop.");
      }
      router.refresh();
    } catch (shopError) {
      setError(shopError instanceof Error ? shopError.message : "Unable to update shop.");
    } finally {
      setBusy(null);
    }
  };

  const addProduct = async () => {
    setBusy("product");
    setError(null);
    try {
      const response = await fetch("/api/products/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shop_id: shop.id,
          name: productForm.name,
          description: productForm.description,
          price: Number(productForm.price),
          image_url: productForm.image_url,
          stock: Number(productForm.stock)
        })
      });
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || "Unable to add product.");
      }

      setProductForm({ name: "", description: "", price: "", image_url: "", stock: "1" });
      router.refresh();
    } catch (productError) {
      setError(productError instanceof Error ? productError.message : "Unable to add product.");
    } finally {
      setBusy(null);
    }
  };

  const logout = async () => {
    setBusy("logout");
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  };

  const sendReply = async () => {
    const trimmedReply = replyMessage.trim();
    if (!trimmedReply) {
      return;
    }

    setBusy("reply");
    setMessageError(null);
    try {
      const response = await fetch("/api/messages/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shop_id: shop.id,
          sender_name: shop.shop_name,
          message: trimmedReply,
          is_from_seller: true
        })
      });

      const payload = (await response.json()) as {
        success: boolean;
        data?: { message: MessageRecord };
        error?: string;
      };

      if (!response.ok || !payload.success || !payload.data) {
        throw new Error(payload.error || "Unable to send message.");
      }

      setMessages((current) => [...current, payload.data!.message]);
      setReplyMessage("");
    } catch (replyError) {
      setMessageError(replyError instanceof Error ? replyError.message : "Unable to send message.");
    } finally {
      setBusy(null);
    }
  };

  const confirmOrder = async (orderId: string) => {
    setUpdatingOrderId(orderId);
    setError(null);
    try {
      const response = await fetch(`/api/dashboard/orders/${shop.id}/${orderId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "confirmed" })
      });

      const payload = (await response.json()) as {
        success: boolean;
        data?: OrderRecord;
        error?: string;
      };

      if (!response.ok || !payload.success || !payload.data) {
        throw new Error(payload.error || "Unable to update order.");
      }

      setOrdersState((current) => current.map((order) => (order.id === orderId ? payload.data! : order)));
    } catch (orderError) {
      setError(orderError instanceof Error ? orderError.message : "Unable to update order.");
    } finally {
      setUpdatingOrderId(null);
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
      <div className="space-y-6">
        <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-6">
          <div className="mb-4 flex items-center justify-between gap-4">
            <div>
              <h2 className="festival-title text-2xl font-black text-[#F5E4BD]">Seller dashboard</h2>
              <p className="mt-1 text-sm text-[#C8B68E]/75">Manage your public tent, bKash details, and theme.</p>
            </div>
            <button onClick={logout} disabled={busy === "logout"} className="rounded-2xl border border-white/10 bg-white/[0.05] px-4 py-2 text-sm font-semibold text-[#E8D8A8]">
              {busy === "logout" ? "Leaving..." : "Logout"}
            </button>
          </div>

          <div className="space-y-4">
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-[#E8D8A8]">Shop name</span>
              <input value={shopName} onChange={(event) => setShopName(event.target.value)} className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-[#F5E4BD] outline-none" />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-[#E8D8A8]">bKash number</span>
              <input value={bkashNumber} onChange={(event) => setBkashNumber(event.target.value)} className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-[#F5E4BD] outline-none" />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-[#E8D8A8]">Logo URL</span>
              <input value={logoUrl} onChange={(event) => setLogoUrl(event.target.value)} className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-[#F5E4BD] outline-none" />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-[#E8D8A8]">Tent outlook</span>
              <select value={tentTheme} onChange={(event) => setTentTheme(event.target.value as TentTheme)} className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-[#F5E4BD] outline-none">
                {TENT_THEMES.map((theme) => (
                  <option key={theme.value} value={theme.value}>{theme.label}</option>
                ))}
              </select>
            </label>
            <button onClick={saveShop} disabled={busy === "shop"} className="w-full rounded-2xl bg-gradient-to-r from-[#FFB647] to-[#C8941A] px-4 py-3 text-sm font-bold text-[#1f1408] disabled:opacity-60">
              {busy === "shop" ? "Saving..." : "Save shop settings"}
            </button>
          </div>
        </section>

        <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-6">
          <h3 className="text-lg font-bold text-[#F5E4BD]">Add product</h3>
          <p className="mt-1 text-sm text-[#C8B68E]/75">Upload your 20 products today with the fields below.</p>
          <div className="mt-4 space-y-4">
            <input placeholder="Product name" value={productForm.name} onChange={(event) => setProductForm((prev) => ({ ...prev, name: event.target.value }))} className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-[#F5E4BD] outline-none" />
            <textarea placeholder="Description" value={productForm.description} onChange={(event) => setProductForm((prev) => ({ ...prev, description: event.target.value }))} className="min-h-28 w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-[#F5E4BD] outline-none" />
            <div className="grid gap-4 sm:grid-cols-2">
              <input placeholder="Price (BDT)" type="number" value={productForm.price} onChange={(event) => setProductForm((prev) => ({ ...prev, price: event.target.value }))} className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-[#F5E4BD] outline-none" />
              <input placeholder="Stock" type="number" value={productForm.stock} onChange={(event) => setProductForm((prev) => ({ ...prev, stock: event.target.value }))} className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-[#F5E4BD] outline-none" />
            </div>
            <input placeholder="Image URL" value={productForm.image_url} onChange={(event) => setProductForm((prev) => ({ ...prev, image_url: event.target.value }))} className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-[#F5E4BD] outline-none" />
            <button onClick={addProduct} disabled={busy === "product"} className="w-full rounded-2xl border border-[#FFB647]/20 bg-[#FFB647]/10 px-4 py-3 text-sm font-bold text-[#FFB647] disabled:opacity-60">
              {busy === "product" ? "Adding product..." : "Add product"}
            </button>
          </div>
        </section>

        {error && <p className="rounded-2xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</p>}
      </div>

      <div className="space-y-6">
        <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-6">
          <div className="mb-4 flex items-center justify-between gap-4">
            <div>
              <h3 className="text-lg font-bold text-[#F5E4BD]">Inbox</h3>
              <p className="mt-1 text-sm text-[#C8B68E]/75">Live buyer questions and mascot handoff replies. Refreshes every 5 seconds.</p>
            </div>
            <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs font-bold uppercase tracking-[0.14em] text-[#E8D8A8]">
              {messages.length} messages
            </span>
          </div>

          <div className="max-h-[380px] space-y-3 overflow-y-auto rounded-[24px] border border-white/10 bg-black/20 p-4">
            {messages.length === 0 && <p className="text-sm text-[#C8B68E]/65">No buyer messages yet.</p>}
            {messages.map((message) => {
              const isSeller = message.is_from_seller;
              return (
                <div key={message.id} className={`flex ${isSeller ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[88%] rounded-[20px] px-4 py-3 ${isSeller ? "bg-[#FFB647]/15 text-[#F5E4BD]" : "bg-white/[0.06] text-[#E8D8A8]"}`}>
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#D8BF86]/72">{message.sender_name}</p>
                      <p className="text-[11px] text-[#C8B68E]/60">{formatMessageTime(message.created_at)}</p>
                    </div>
                    <p className="mt-2 text-sm leading-6">{message.message}</p>
                  </div>
                </div>
              );
            })}
          </div>

          {messageError && <p className="mt-4 rounded-2xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{messageError}</p>}

          <div className="mt-4 flex gap-3">
            <textarea
              placeholder="Reply to buyers from your tent inbox"
              value={replyMessage}
              onChange={(event) => setReplyMessage(event.target.value)}
              className="min-h-28 flex-1 rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-[#F5E4BD] outline-none"
            />
            <button onClick={sendReply} disabled={busy === "reply" || !replyMessage.trim()} className="self-end rounded-2xl bg-gradient-to-r from-[#FFB647] to-[#C8941A] px-5 py-3 text-sm font-bold text-[#1f1408] disabled:opacity-60">
              {busy === "reply" ? "Sending..." : "Send reply"}
            </button>
          </div>
        </section>

        <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-6">
          <div className="mb-4 flex items-center justify-between gap-4">
            <div>
              <h3 className="text-lg font-bold text-[#F5E4BD]">Products</h3>
              <p className="mt-1 text-sm text-[#C8B68E]/75">Current live inventory in your tent.</p>
            </div>
            <a
              href={`/shop/${shop.slug}`}
              className="rounded-2xl border border-white/10 bg-white/[0.05] px-4 py-2 text-sm font-semibold text-[#E8D8A8]"
              onClick={(event) => {
                const rect = (event.currentTarget as HTMLAnchorElement).getBoundingClientRect();
                const payload = {
                  x: rect.left + rect.width / 2,
                  y: rect.top + rect.height / 2,
                  accent: "#FFB647",
                  playSound: true,
                  at: Date.now(),
                };
                try {
                  window.localStorage.setItem("tent-enter-transition", JSON.stringify(payload));
                } catch {
                  // Ignore if storage is unavailable.
                }
              }}
            >
              View shop
            </a>
          </div>
          <div className="space-y-3">
            {products.length === 0 && <p className="text-sm text-[#C8B68E]/65">No products yet.</p>}
            {products.map((product) => (
              <div key={product.id} className="rounded-2xl border border-white/10 bg-black/16 px-4 py-3">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="font-semibold text-[#F5E4BD]">{product.name}</p>
                    <p className="mt-1 text-sm text-[#C8B68E]/70">{product.price} BDT • Stock {product.stock}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-6">
          <h3 className="text-lg font-bold text-[#F5E4BD]">Orders</h3>
          <p className="mt-1 text-sm text-[#C8B68E]/75">Customers who transferred by bKash and placed an order.</p>
          <div className="mt-4 space-y-3">
            {ordersState.length === 0 && <p className="text-sm text-[#C8B68E]/65">No orders yet.</p>}
            {ordersState.map((order) => (
              <div key={order.id} className="rounded-2xl border border-white/10 bg-black/16 px-4 py-3">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-semibold text-[#F5E4BD]">{order.buyer_name}</p>
                    <p className="mt-1 text-sm text-[#C8B68E]/70">{order.buyer_phone}</p>
                    <p className="mt-1 text-xs text-[#C8B68E]/55">TXN: {order.transaction_id}</p>
                    <p className="mt-2 text-sm text-[#C8B68E]/70">{order.delivery_address}</p>
                    {order.payment_screenshot_url && (
                      <a href={order.payment_screenshot_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-sm font-semibold text-[#FFB647] underline decoration-[#FFB647]/30 underline-offset-4">
                        View payment screenshot
                      </a>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-3">
                    <span className="rounded-full border border-[#FFB647]/20 bg-[#FFB647]/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] text-[#FFB647]">
                      {order.status}
                    </span>
                    {order.status === "pending" && (
                      <button
                        type="button"
                        onClick={() => void confirmOrder(order.id)}
                        disabled={updatingOrderId === order.id}
                        className="rounded-2xl border border-[#FFB647]/20 bg-[#FFB647]/10 px-4 py-2 text-xs font-bold uppercase tracking-[0.12em] text-[#FFB647] disabled:opacity-60"
                      >
                        {updatingOrderId === order.id ? "Confirming..." : "Confirm order"}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
