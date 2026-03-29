import { z } from "zod";
import { TENT_THEMES } from "@/lib/constants/tent-themes";

const tentThemeValues = TENT_THEMES.map((theme) => theme.value) as [string, ...string[]];
const paymentMethodSchema = z.object({
  type: z.string().trim().min(1).max(40),
  number: z.string().trim().min(3).max(40)
});

function normalizePaymentMethods(input: {
  payment_methods?: { type: string; number: string } | { type: string; number: string }[];
  bkash_number?: string;
}) {
  if (Array.isArray(input.payment_methods)) {
    return input.payment_methods;
  }

  if (input.payment_methods) {
    return [input.payment_methods];
  }

  if (input.bkash_number) {
    return [{ type: "bKash", number: input.bkash_number }];
  }

  return [];
}

export const signupSchema = z.object({
  full_name: z.string().trim().min(2).max(120),
  email: z.string().trim().email(),
  password: z.string().min(8).max(128)
});

export const loginSchema = z.object({
  email: z.string().trim().email(),
  password: z.string().min(8).max(128)
});

export const createShopSchema = z.object({
  name: z.string().trim().min(2).max(120).optional(),
  shop_name: z.string().trim().min(2).max(120).optional(),
  tent_theme: z
    .union([z.enum(tentThemeValues), z.object({ key: z.enum(tentThemeValues) })])
    .transform((value) => (typeof value === "string" ? value : value.key)),
  payment_methods: z.union([paymentMethodSchema, z.array(paymentMethodSchema)]).optional(),
  bkash_number: z.string().trim().min(11).max(20).optional(),
  logo_url: z.string().trim().url().optional().or(z.literal("")).transform((value) => value || undefined)
}).transform((value) => ({
  name: value.name ?? value.shop_name ?? "",
  tent_theme: value.tent_theme,
  payment_methods: normalizePaymentMethods(value),
  logo_url: value.logo_url
}));

export const addProductSchema = z.object({
  shop_id: z.string().uuid(),
  name: z.string().trim().min(2).max(140),
  description: z.string().trim().min(8).max(2000),
  price: z.coerce.number().int().positive(),
  image_url: z.string().trim().url().optional().or(z.literal("")).transform((value) => value || undefined),
  stock: z.coerce.number().int().min(0).default(1)
});

export const createOrderSchema = z.object({
  product_id: z.string().uuid(),
  shop_id: z.string().uuid(),
  buyer_name: z.string().trim().min(2).max(120),
  buyer_phone: z.string().trim().min(8).max(30),
  address: z.string().trim().min(10).max(500).optional(),
  delivery_address: z.string().trim().min(10).max(500).optional(),
  transaction_id: z.string().trim().min(6).max(120),
  payment_screenshot_url: z.string().trim().url().optional().or(z.literal("")).transform((value) => value || undefined)
}).transform((value) => ({
  ...value,
  address: value.address ?? value.delivery_address ?? ""
}));

export const updateShopSchema = z.object({
  name: z.string().trim().min(2).max(120).optional(),
  shop_name: z.string().trim().min(2).max(120).optional(),
  tent_theme: z
    .union([z.enum(tentThemeValues), z.object({ key: z.enum(tentThemeValues) })])
    .transform((value) => (typeof value === "string" ? value : value.key))
    .optional(),
  payment_methods: z.union([paymentMethodSchema, z.array(paymentMethodSchema)]).optional(),
  bkash_number: z.string().trim().min(11).max(20).optional(),
  logo_url: z.string().trim().url().optional().or(z.literal("")).transform((value) => value || undefined)
}).transform((value) => ({
  name: value.name ?? value.shop_name,
  tent_theme: value.tent_theme,
  payment_methods: normalizePaymentMethods(value),
  logo_url: value.logo_url
}));

export const updateOrderStatusSchema = z.object({
  status: z.enum(["pending", "confirmed"])
});

export const sendMessageSchema = z.object({
  shop_id: z.string().uuid(),
  sender_name: z.string().trim().min(2).max(120),
  message: z.string().trim().min(1).max(4000),
  is_from_seller: z.boolean().default(false),
  is_read: z.boolean().optional()
});
