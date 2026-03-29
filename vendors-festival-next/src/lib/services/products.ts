import type { ProductRecord } from "@/lib/types/marketplace";
import { createSupabaseAdminClient } from "@/lib/supabase/admin";
import { getCurrentSellerShop } from "@/lib/services/shops";
import { generateAIContext } from "@/lib/utils/ai-context";
import { normalizeProductRecord } from "@/lib/utils/marketplace-normalizers";

export async function addProductForShop(input: {
  userId: string;
  shopId: string;
  name: string;
  description: string;
  price: number;
  imageUrl?: string;
  stock: number;
}) {
  const sellerShop = await getCurrentSellerShop(input.userId);
  if (!sellerShop || sellerShop.id !== input.shopId) {
    throw new Error("You do not have permission to add products to this shop.");
  }

  const admin = createSupabaseAdminClient();
  const { data, error } = await admin
    .from("products")
    .insert({
      shop_id: input.shopId,
      name: input.name,
      description: input.description,
      price: input.price,
      image_url: input.imageUrl || null,
      stock: input.stock,
      ai_context: generateAIContext({
        name: input.name,
        description: input.description,
        price: input.price
      })
    })
    .select("*")
    .single();

  if (error || !data) {
    throw new Error(error?.message ?? "Unable to add product.");
  }

  return normalizeProductRecord(data);
}

export async function getSellerProducts(shopId: string, userId: string) {
  const sellerShop = await getCurrentSellerShop(userId);
  if (!sellerShop || sellerShop.id !== shopId) {
    throw new Error("You do not have access to these products.");
  }

  const admin = createSupabaseAdminClient();
  const { data, error } = await admin
    .from("products")
    .select("*")
    .eq("shop_id", shopId)
    .order("created_at", { ascending: false });

  if (error) {
    throw new Error(error.message);
  }

  return (data ?? []).map((row) => normalizeProductRecord(row));
}

export async function deleteProduct(productId: string, userId: string) {
  const sellerShop = await getCurrentSellerShop(userId);
  if (!sellerShop) {
    throw new Error("You do not have a shop.");
  }

  const admin = createSupabaseAdminClient();

  const { data: product, error: findError } = await admin
    .from("products")
    .select("id, shop_id")
    .eq("id", productId)
    .eq("shop_id", sellerShop.id)
    .maybeSingle();

  if (findError) {
    throw new Error(findError.message);
  }

  if (!product) {
    throw new Error("Product not found or you do not have permission to delete it.");
  }

  const { error } = await admin.from("products").delete().eq("id", productId);

  if (error) {
    throw new Error(error.message);
  }
}
