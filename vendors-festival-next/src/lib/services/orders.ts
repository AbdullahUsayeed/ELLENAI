import type { OrderRecord, OrderStatus } from "@/lib/types/marketplace";
import { createSupabaseAdminClient } from "@/lib/supabase/admin";
import { getCurrentSellerShop } from "@/lib/services/shops";
import { normalizeOrderRecord } from "@/lib/utils/marketplace-normalizers";

export async function createOrder(input: {
  productId: string;
  shopId: string;
  buyerName: string;
  buyerPhone: string;
  address: string;
  transactionId: string;
  paymentScreenshotUrl?: string;
}) {
  const admin = createSupabaseAdminClient();

  const { data: product, error: productError } = await admin
    .from("products")
    .select("id, stock, shop_id")
    .eq("id", input.productId)
    .eq("shop_id", input.shopId)
    .maybeSingle();

  if (productError) {
    throw new Error(productError.message);
  }

  if (!product) {
    throw new Error("Product not found for this shop.");
  }

  if (product.stock < 1) {
    throw new Error("This product is out of stock.");
  }

  const { data, error } = await admin
    .from("orders")
    .insert({
      product_id: input.productId,
      shop_id: input.shopId,
      buyer_name: input.buyerName,
      buyer_phone: input.buyerPhone,
      address: input.address,
      transaction_id: input.transactionId,
      status: "pending",
      payment_screenshot_url: input.paymentScreenshotUrl || null
    })
    .select("*")
    .single();

  if (error || !data) {
    throw new Error(error?.message ?? "Unable to create order.");
  }

  return normalizeOrderRecord(data);
}

export async function getSellerOrders(shopId: string, userId: string) {
  const sellerShop = await getCurrentSellerShop(userId);
  if (!sellerShop || sellerShop.id !== shopId) {
    throw new Error("You do not have access to these orders.");
  }

  const admin = createSupabaseAdminClient();
  const { data, error } = await admin
    .from("orders")
    .select("*")
    .eq("shop_id", shopId)
    .order("created_at", { ascending: false });

  if (error) {
    throw new Error(error.message);
  }

  return (data ?? []).map((row) => normalizeOrderRecord(row));
}

export async function updateOrderStatus(params: {
  orderId: string;
  shopId: string;
  userId: string;
  status: OrderStatus;
}) {
  const sellerShop = await getCurrentSellerShop(params.userId);
  if (!sellerShop || sellerShop.id !== params.shopId) {
    throw new Error("You do not have access to this shop.");
  }

  const admin = createSupabaseAdminClient();
  const { data, error } = await admin
    .from("orders")
    .update({ status: params.status })
    .eq("id", params.orderId)
    .eq("shop_id", params.shopId)
    .select("*")
    .single();

  if (error || !data) {
    throw new Error(error?.message ?? "Unable to update order status.");
  }

  return normalizeOrderRecord(data);
}
