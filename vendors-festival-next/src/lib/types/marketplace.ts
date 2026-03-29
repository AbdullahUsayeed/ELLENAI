import type { TentTheme } from "@/lib/constants/tent-themes";

export type PaymentMethod = {
  type: string;
  number: string;
};

export type TentThemeConfig = {
  key: TentTheme;
  accent?: string | null;
  glow?: string | null;
};

export type PublicUserRecord = {
  id: string;
  full_name: string;
  email: string;
  avatar_url: string | null;
  created_at: string;
};

export type ShopRecord = {
  id: string;
  user_id: string;
  name: string;
  shop_name: string;
  slug: string;
  tent_theme: TentTheme;
  tent_theme_config: TentThemeConfig;
  payment_methods: PaymentMethod[];
  bkash_number: string | null;
  rating: number;
  logo_url: string | null;
  is_verified: boolean;
  created_at: string;
};

export type ProductRecord = {
  id: string;
  shop_id: string;
  name: string;
  description: string;
  price: number;
  image_url: string | null;
  stock: number;
  ai_context: string;
  created_at: string;
};

export type OrderStatus = "pending" | "confirmed";

export type OrderRecord = {
  id: string;
  product_id: string;
  shop_id: string;
  buyer_name: string;
  buyer_phone: string;
  address: string;
  delivery_address: string;
  transaction_id: string;
  status: OrderStatus;
  payment_screenshot_url: string | null;
  created_at: string;
};

export type MessageRecord = {
  id: string;
  shop_id: string;
  sender_name: string;
  message: string;
  is_from_seller: boolean;
  is_read: boolean;
  created_at: string;
};

export type ShopWithProducts = {
  shop: ShopRecord;
  products: ProductRecord[];
};
