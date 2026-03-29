import { DEFAULT_TENT_THEME, TENT_THEMES, isTentTheme } from "@/lib/constants/tent-themes";
import type {
  MessageRecord,
  OrderRecord,
  OrderStatus,
  PaymentMethod,
  ProductRecord,
  ShopRecord,
  TentThemeConfig
} from "@/lib/types/marketplace";
import { generateAIContext } from "@/lib/utils/ai-context";

const THEME_ACCENTS = Object.fromEntries(
  TENT_THEMES.map((theme) => [theme.value, theme.accent])
) as Record<string, string>;

function asObject(value: unknown) {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

export function normalizeTentThemeConfig(value: unknown): TentThemeConfig {
  if (typeof value === "string" && isTentTheme(value)) {
    return { key: value, accent: THEME_ACCENTS[value] ?? null, glow: null };
  }

  const obj = asObject(value);
  const keyCandidate = typeof obj?.key === "string" && isTentTheme(obj.key) ? obj.key : DEFAULT_TENT_THEME;

  return {
    key: keyCandidate,
    accent: typeof obj?.accent === "string" ? obj.accent : THEME_ACCENTS[keyCandidate] ?? null,
    glow: typeof obj?.glow === "string" ? obj.glow : null
  };
}

export function normalizePaymentMethods(value: unknown): PaymentMethod[] {
  const normalizeOne = (candidate: unknown): PaymentMethod | null => {
    const obj = asObject(candidate);
    const type = typeof obj?.type === "string" ? obj.type.trim() : "";
    const number = typeof obj?.number === "string" ? obj.number.trim() : "";

    if (!type || !number) {
      return null;
    }

    return { type, number };
  };

  if (Array.isArray(value)) {
    return value.map(normalizeOne).filter((item): item is PaymentMethod => Boolean(item));
  }

  const single = normalizeOne(value);
  return single ? [single] : [];
}

function primaryPaymentNumber(methods: PaymentMethod[]) {
  return methods.find((method) => method.type.toLowerCase() === "bkash")?.number ?? methods[0]?.number ?? null;
}

export function normalizeShopRecord(row: Record<string, unknown>): ShopRecord {
  const name = String(row.name ?? row.shop_name ?? "").trim();
  const paymentMethods = normalizePaymentMethods(
    row.payment_methods ?? (row.bkash_number ? [{ type: "bKash", number: row.bkash_number }] : [])
  );
  const themeConfig = normalizeTentThemeConfig(row.tent_theme);

  return {
    id: String(row.id ?? ""),
    user_id: String(row.user_id ?? ""),
    name,
    shop_name: name,
    slug: String(row.slug ?? ""),
    tent_theme: themeConfig.key,
    tent_theme_config: themeConfig,
    payment_methods: paymentMethods,
    bkash_number: primaryPaymentNumber(paymentMethods),
    rating: typeof row.rating === "number" ? row.rating : Number(row.rating ?? 4.5),
    logo_url: typeof row.logo_url === "string" ? row.logo_url : null,
    is_verified: Boolean(row.is_verified),
    created_at: String(row.created_at ?? "")
  };
}

export function normalizeProductRecord(row: Record<string, unknown>): ProductRecord {
  const name = String(row.name ?? "");
  const description = String(row.description ?? "");
  const price = typeof row.price === "number" ? row.price : Number(row.price ?? 0);

  return {
    id: String(row.id ?? ""),
    shop_id: String(row.shop_id ?? ""),
    name,
    description,
    price,
    image_url: typeof row.image_url === "string" ? row.image_url : null,
    stock: typeof row.stock === "number" ? row.stock : Number(row.stock ?? 0),
    ai_context:
      typeof row.ai_context === "string" && row.ai_context.trim()
        ? row.ai_context
        : generateAIContext({ name, description, price }),
    created_at: String(row.created_at ?? "")
  };
}

export function normalizeOrderRecord(row: Record<string, unknown>): OrderRecord {
  const address = String(row.address ?? row.delivery_address ?? "");
  const status = row.status === "confirmed" ? "confirmed" : "pending";

  return {
    id: String(row.id ?? ""),
    product_id: String(row.product_id ?? ""),
    shop_id: String(row.shop_id ?? ""),
    buyer_name: String(row.buyer_name ?? ""),
    buyer_phone: String(row.buyer_phone ?? ""),
    address,
    delivery_address: address,
    transaction_id: String(row.transaction_id ?? ""),
    status: status satisfies OrderStatus,
    payment_screenshot_url: typeof row.payment_screenshot_url === "string" ? row.payment_screenshot_url : null,
    created_at: String(row.created_at ?? "")
  };
}

export function normalizeMessageRecord(row: Record<string, unknown>): MessageRecord {
  return {
    id: String(row.id ?? ""),
    shop_id: String(row.shop_id ?? ""),
    sender_name: String(row.sender_name ?? ""),
    message: String(row.message ?? ""),
    is_from_seller: Boolean(row.is_from_seller),
    is_read: Boolean(row.is_read),
    created_at: String(row.created_at ?? "")
  };
}