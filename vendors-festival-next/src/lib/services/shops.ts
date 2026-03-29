import type { User } from "@supabase/supabase-js";
import type { TentTheme } from "@/lib/constants/tent-themes";
import type { PaymentMethod, ShopRecord, ShopWithProducts } from "@/lib/types/marketplace";
import { createSupabaseAdminClient } from "@/lib/supabase/admin";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { generateUniqueShopSlug } from "@/lib/utils/slug";
import { normalizeProductRecord, normalizeShopRecord } from "@/lib/utils/marketplace-normalizers";

async function shopSlugExists(slug: string) {
  const admin = createSupabaseAdminClient();
  const { data, error } = await admin.from("shops").select("id").eq("slug", slug).maybeSingle();
  if (error) {
    throw new Error(error.message);
  }
  return Boolean(data);
}

export async function createOrUpdateShopForUser(input: {
  userId: string;
  shopName: string;
  tentTheme: TentTheme;
  paymentMethods?: PaymentMethod[];
  bkashNumber?: string;
  logoUrl?: string;
}) {
  const admin = createSupabaseAdminClient();
  const { data: existingShop, error: existingShopError } = await admin
    .from("shops")
    .select("id, slug, name")
    .eq("user_id", input.userId)
    .maybeSingle();

  if (existingShopError) {
    throw new Error(existingShopError.message);
  }

  let slug = existingShop?.slug;
  if (!slug || (existingShop && existingShop.name !== input.shopName)) {
    slug = await generateUniqueShopSlug(input.shopName, async (candidate) => {
      if (existingShop?.slug === candidate) {
        return false;
      }
      return shopSlugExists(candidate);
    });
  }

  const paymentMethods = input.paymentMethods ?? (input.bkashNumber ? [{ type: "bKash", number: input.bkashNumber }] : []);

  const payload = {
    user_id: input.userId,
    name: input.shopName,
    slug,
    tent_theme: { key: input.tentTheme },
    payment_methods: paymentMethods,
    logo_url: input.logoUrl || null
  };

  const query = existingShop
    ? admin.from("shops").update(payload).eq("id", existingShop.id).select("*").single()
    : admin.from("shops").insert(payload).select("*").single();

  const { data, error } = await query;
  if (error || !data) {
    throw new Error(error?.message ?? "Unable to save shop.");
  }

  return normalizeShopRecord(data);
}

export async function getShopBySlug(slug: string): Promise<ShopWithProducts | null> {
  const admin = createSupabaseAdminClient();
  const { data: shop, error: shopError } = await admin.from("shops").select("*").eq("slug", slug).maybeSingle();

  if (shopError) {
    throw new Error(shopError.message);
  }

  if (!shop) {
    return null;
  }

  const { data: products, error: productsError } = await admin
    .from("products")
    .select("*")
    .eq("shop_id", shop.id)
    .order("created_at", { ascending: false });

  if (productsError) {
    throw new Error(productsError.message);
  }

  return {
    shop: normalizeShopRecord(shop),
    products: (products ?? []).map((product) => normalizeProductRecord(product))
  };
}

export async function getShopWithProductsById(shopId: string): Promise<ShopWithProducts | null> {
  const admin = createSupabaseAdminClient();
  const { data: shop, error: shopError } = await admin.from("shops").select("*").eq("id", shopId).maybeSingle();

  if (shopError) {
    throw new Error(shopError.message);
  }

  if (!shop) {
    return null;
  }

  const { data: products, error: productsError } = await admin
    .from("products")
    .select("*")
    .eq("shop_id", shopId)
    .order("created_at", { ascending: false });

  if (productsError) {
    throw new Error(productsError.message);
  }

  return {
    shop: normalizeShopRecord(shop),
    products: (products ?? []).map((product) => normalizeProductRecord(product))
  };
}

export async function getCurrentAuthenticatedUser() {
  const supabase = await createSupabaseServerClient();
  const {
    data: { user },
    error
  } = await supabase.auth.getUser();

  if (error) {
    throw new Error(error.message);
  }

  return user;
}

export async function requireAuthenticatedUser() {
  const user = await getCurrentAuthenticatedUser();
  if (!user) {
    throw new Error("Authentication required.");
  }
  return user;
}

export async function getCurrentSellerShop(userOrId?: string | User) {
  const userId = typeof userOrId === "string" ? userOrId : userOrId?.id ?? (await requireAuthenticatedUser()).id;
  const admin = createSupabaseAdminClient();
  const { data, error } = await admin.from("shops").select("*").eq("user_id", userId).maybeSingle();

  if (error) {
    throw new Error(error.message);
  }

  return data ? normalizeShopRecord(data) : null;
}

export async function updateShopProfile(
  shopId: string,
  userId: string,
  updates: {
    name?: string;
    shop_name?: string;
    tent_theme?: TentTheme;
    payment_methods?: PaymentMethod[];
    bkash_number?: string;
    logo_url?: string;
  }
) {
  const currentShop = await getCurrentSellerShop(userId);
  if (!currentShop || currentShop.id !== shopId) {
    throw new Error("You do not have access to this shop.");
  }

  return createOrUpdateShopForUser({
    userId,
    shopName: updates.name ?? updates.shop_name ?? currentShop.name,
    tentTheme: updates.tent_theme ?? currentShop.tent_theme,
    paymentMethods:
      updates.payment_methods && updates.payment_methods.length > 0
        ? updates.payment_methods
        : updates.bkash_number
          ? [{ type: "bKash", number: updates.bkash_number }]
          : currentShop.payment_methods,
    bkashNumber: updates.bkash_number ?? currentShop.bkash_number ?? "",
    logoUrl: updates.logo_url ?? currentShop.logo_url ?? undefined
  });
}
